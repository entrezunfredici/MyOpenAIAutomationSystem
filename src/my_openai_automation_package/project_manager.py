"""Gestion des projets sandbox pour MOAIAP."""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config_manager import ConfigManager


class ProjectManager:
    """Gère la création et le suivi des projets sandbox."""

    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager

    # ------------------------------------------------------------------
    # Gestion du registre des projets
    # ------------------------------------------------------------------
    def _load_projects(self) -> Dict[str, Dict[str, object]]:
        return self.config_manager.load_projects()

    def _save_projects(self, projects: Dict[str, Dict[str, object]]) -> None:
        self.config_manager.save_projects(projects)

    def register_project(
        self,
        name: str,
        repo_url: str,
        commands: Iterable[str],
        metadata: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        projects = self._load_projects()
        if name in projects:
            raise ValueError(f"Le projet '{name}' existe déjà dans le registre.")

        project_info = {
            "name": name,
            "repo_url": repo_url,
            "commands": list(commands),
            "created_at": dt.datetime.utcnow().isoformat(),
        }
        if metadata:
            project_info.update(metadata)

        projects[name] = project_info
        self._save_projects(projects)
        return project_info

    def get_project(self, name: str) -> Dict[str, object]:
        projects = self._load_projects()
        if name not in projects:
            raise KeyError(f"Aucun projet nommé '{name}' n'est enregistré. Utilisez `MOAIAP create-project`. ")
        return projects[name]

    def list_projects(self) -> List[Dict[str, object]]:
        projects = self._load_projects()
        return list(projects.values())

    # ------------------------------------------------------------------
    # Interaction Git / filesystem
    # ------------------------------------------------------------------
    def clone_repository(
        self,
        repo_url: str,
        destination: Path,
        branch: Optional[str] = None,
    ) -> None:
        if destination.exists():
            raise FileExistsError(
                f"Le dossier destination '{destination}' existe déjà. Choisissez un autre nom de projet."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = ["git", "clone", repo_url, str(destination)]
        if branch:
            command.insert(2, "--branch")
            command.insert(3, branch)
        process = subprocess.run(command, check=False, capture_output=True, text=True)
        if process.returncode != 0:
            raise RuntimeError(
                "Échec du clonage du dépôt Git:\n" + process.stderr.strip()
            )

    def ensure_sandbox(self, sandbox_path: str) -> Path:
        sandbox = Path(sandbox_path).expanduser().resolve()
        sandbox.mkdir(parents=True, exist_ok=True)
        return sandbox
