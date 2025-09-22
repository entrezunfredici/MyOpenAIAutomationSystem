"""Exécution des projets et correction automatisée via OpenAI."""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config_manager import ConfigManager


class OpenAIResponder:
    """Encapsule l'appel à l'API OpenAI et la mise en forme des requêtes."""

    def __init__(self, api_key: Optional[str], model: str = "gpt-4.1-mini") -> None:
        self.api_key = api_key
        self.model = model
        self._client = None
        self._init_error: Optional[str] = None
        if api_key:
            try:
                from openai import OpenAI  # type: ignore

                self._client = OpenAI(api_key=api_key)
            except Exception as exc:  # pragma: no cover - dépend de l'environnement
                self._init_error = str(exc)

    def is_ready(self) -> bool:
        return self._client is not None and self._init_error is None

    def explain_unavailable(self) -> str:
        if not self.api_key:
            return "Aucune clef API OpenAI n'est configurée."
        if self._init_error:
            return f"Impossible d'initialiser le client OpenAI: {self._init_error}"
        return "Client OpenAI non initialisé pour une raison inconnue."

    def request_fix(
        self,
        project_path: Path,
        command: str,
        stdout: str,
        stderr: str,
    ) -> Optional[Dict[str, object]]:
        if not self.is_ready():
            return None

        trimmed_stdout = stdout[-4000:]
        trimmed_stderr = stderr[-4000:]
        prompt = textwrap.dedent(
            f"""
            You are an autonomous senior software engineer working inside the sandbox directory
            `{project_path}`. The following command failed: `{command}`.

            stdout (last 4000 chars):
            {trimmed_stdout}

            stderr (last 4000 chars):
            {trimmed_stderr}

            Analyse the failure and propose concrete fixes. Respond strictly in JSON with the schema:
            {{
              "notes": "Optional explanation",
              "files": [{{"path": "relative/path.py", "content": "full new file content"}}],
              "commands": ["optional shell command to run", ...]
            }}

            Only include files that must be overwritten with the new content. Do not include explanations
            outside the JSON payload.
            """
        ).strip()

        try:  # pragma: no cover - dépend d'un appel réseau
            response = self._client.responses.create(  # type: ignore[union-attr]
                model=self.model,
                input=[
                    {"role": "system", "content": "You write JSON patches to fix projects."},
                    {"role": "user", "content": prompt},
                ],
                max_output_tokens=1200,
            )
        except Exception as exc:  # pragma: no cover
            self._init_error = str(exc)
            return None

        text = getattr(response, "output_text", None)
        if not text:
            try:
                text = "".join(
                    block.text  # type: ignore[attr-defined]
                    for item in getattr(response, "output", [])
                    for block in getattr(item, "content", [])
                    if hasattr(block, "text")
                )
            except Exception:  # pragma: no cover - en cas de structure inattendue
                text = None
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None


class ProjectRunner:
    """Orchestre l'exécution d'un projet et les demandes de correction."""

    def __init__(self, config_manager: ConfigManager, project_manager, max_fix_loops: int = 3) -> None:
        self.config_manager = config_manager
        self.project_manager = project_manager
        self.max_fix_loops = max_fix_loops

    def _apply_file_patch(self, project_path: Path, file_info: Dict[str, str]) -> None:
        relative_path = Path(file_info["path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Chemin de fichier non sûr reçu: {relative_path}")
        target_path = project_path / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(file_info["content"], encoding="utf-8")

    def _run_shell_command(self, command: str, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
        )

    def _attempt_fix(
        self,
        responder: OpenAIResponder,
        project_path: Path,
        command: str,
        stdout: str,
        stderr: str,
    ) -> bool:
        fix_payload = responder.request_fix(project_path, command, stdout, stderr)
        if not fix_payload:
            return False

        files: Iterable[Dict[str, str]] = fix_payload.get("files", [])  # type: ignore[assignment]
        for file_info in files:
            try:
                self._apply_file_patch(project_path, file_info)
            except Exception as exc:
                print(f"Impossible d'appliquer la modification proposée: {exc}")
                return False

        for extra_command in fix_payload.get("commands", []):  # type: ignore[assignment]
            if not isinstance(extra_command, str):
                continue
            print(f"Exécution de la commande suggérée: {extra_command}")
            result = self._run_shell_command(extra_command, project_path)
            if result.returncode != 0:
                print("La commande suggérée a échoué:")
                print(result.stdout)
                print(result.stderr)
                return False

        notes = fix_payload.get("notes")
        if notes:
            print("Notes Codex:", notes)
        return True

    def run_project(self, project_name: str, password: str, max_attempts: Optional[int] = None) -> None:
        config = self.config_manager.load_config(password)
        sandbox_path = config.get("sandbox_path")
        if not sandbox_path:
            raise ValueError("Le chemin du sandbox n'est pas défini dans la configuration.")

        project_info = self.project_manager.get_project(project_name)
        raw_commands = project_info.get("commands", [])  # type: ignore[assignment]
        commands: List[str] = [str(cmd) for cmd in raw_commands]
        if not commands:
            raise ValueError("Aucune commande de démarrage n'est associée à ce projet.")

        project_path = Path(sandbox_path).expanduser().resolve() / project_name
        if not project_path.exists():
            raise FileNotFoundError(
                f"Le dossier du projet '{project_name}' est introuvable dans le sandbox."
            )
        responder = OpenAIResponder(config.get("openai_api_key"))
        attempts_limit = max_attempts or self.max_fix_loops

        for command in commands:
            attempt = 0
            while attempt < attempts_limit:
                attempt += 1
                print(f"[MOAIAP] Exécution de '{command}' (tentative {attempt}/{attempts_limit})")
                result = self._run_shell_command(command, project_path)
                if result.returncode == 0:
                    print(f"[MOAIAP] Commande '{command}' terminée avec succès.")
                    break

                print("[MOAIAP] La commande a échoué. Sortie :")
                print(result.stdout)
                print(result.stderr)

                if responder.is_ready():
                    print("[MOAIAP] Demande d'une correction automatique à OpenAI...")
                    success = self._attempt_fix(
                        responder,
                        project_path,
                        command,
                        result.stdout,
                        result.stderr,
                    )
                    if not success:
                        print("[MOAIAP] Impossible d'appliquer automatiquement la correction proposée.")
                        if attempt >= attempts_limit:
                            raise RuntimeError(
                                "La commande échoue malgré les tentatives automatiques."
                            )
                        continue
                else:
                    print("[MOAIAP]", responder.explain_unavailable())
                    raise RuntimeError("Impossible de corriger automatiquement l'erreur.")
            else:
                raise RuntimeError(
                    f"Nombre maximum de tentatives atteint pour la commande '{command}'."
                )
