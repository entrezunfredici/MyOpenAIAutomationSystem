"""Interface en ligne de commande pour MyOpenAIAutomationPackage."""

from __future__ import annotations

import argparse
import sys
from getpass import getpass
from pathlib import Path
from typing import List, Optional

from .config_manager import ConfigData, ConfigManager
from .project_manager import ProjectManager
from .runner import ProjectRunner


def _resolve_optional_file(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = Path(value).expanduser()
    if candidate.exists():
        return candidate.read_text()
    return value


def _prompt_if_missing(prompt_text: str, secret: bool = False) -> Optional[str]:
    if secret:
        value = getpass(prompt_text)
    else:
        value = input(prompt_text)
    return value.strip() or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="MOAIAP",
        description="Automatise la configuration et l'exécution de projets OpenAI dans un sandbox.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Configure les secrets chiffrés localement")
    config_parser.add_argument("--sandbox", help="Chemin du dossier sandbox")
    config_parser.add_argument("--git-username", help="Nom d'utilisateur Git")
    config_parser.add_argument("--git-email", help="Adresse e-mail Git")
    config_parser.add_argument("--git-token", help="Token personnel Git")
    config_parser.add_argument("--openai-key", help="Clef API OpenAI")
    config_parser.add_argument("--ssh-private-key", help="Chemin ou contenu de la clef privée SSH")
    config_parser.add_argument("--ssh-public-key", help="Chemin ou contenu de la clef publique SSH")

    create_parser = subparsers.add_parser("create-project", help="Crée un projet dans le sandbox")
    create_parser.add_argument("--name", required=True, help="Nom du projet")
    create_parser.add_argument("--repo", required=True, help="URL du dépôt Git")
    create_parser.add_argument(
        "--start-cmd",
        dest="start_cmds",
        action="append",
        help="Commande de démarrage (peut être répétée)",
    )
    create_parser.add_argument("--branch", help="Branche Git à cloner")

    run_parser = subparsers.add_parser("run-project", help="Exécute un projet et corrige les erreurs via OpenAI")
    run_parser.add_argument("name", help="Nom du projet à exécuter")
    run_parser.add_argument(
        "--max-attempts",
        type=int,
        help="Nombre maximum de tentatives par commande",
    )

    return parser


def handle_config(args: argparse.Namespace, config_manager: ConfigManager) -> None:
    sandbox = args.sandbox or _prompt_if_missing("Chemin du dossier sandbox: ")
    if not sandbox:
        raise ValueError("Le chemin du sandbox est obligatoire.")

    git_username = args.git_username or _prompt_if_missing("Nom d'utilisateur Git (optionnel): ")
    git_email = args.git_email or _prompt_if_missing("Adresse e-mail Git (optionnel): ")
    git_token = args.git_token or _prompt_if_missing("Token Git (optionnel): ", secret=True)
    openai_key = args.openai_key or _prompt_if_missing("Clef API OpenAI (optionnel): ", secret=True)

    ssh_private = _resolve_optional_file(
        args.ssh_private_key or _prompt_if_missing("Chemin vers la clef privée SSH (optionnel): ")
    )
    ssh_public = _resolve_optional_file(
        args.ssh_public_key or _prompt_if_missing("Chemin vers la clef publique SSH (optionnel): ")
    )

    password = config_manager.prompt_password(confirm=True)
    config = ConfigData(
        sandbox_path=sandbox,
        git_username=git_username,
        git_email=git_email,
        git_token=git_token,
        openai_api_key=openai_key,
        ssh_private_key=ssh_private,
        ssh_public_key=ssh_public,
    )
    config_manager.save_config(config, password)
    print("Configuration sauvegardée avec succès.")


def _collect_start_commands(initial: Optional[List[str]]) -> List[str]:
    commands: List[str] = list(initial or [])
    while not commands:
        value = _prompt_if_missing(
            "Commande de démarrage (laisser vide pour terminer): "
        )
        if not value:
            if commands:
                break
            print("Au moins une commande est nécessaire.")
            continue
        commands.append(value)
    return commands


def handle_create_project(args: argparse.Namespace, config_manager: ConfigManager) -> None:
    password = config_manager.prompt_password()
    config = config_manager.load_config(password)
    sandbox_path = config.get("sandbox_path")
    if not sandbox_path:
        raise ValueError("Le chemin du sandbox n'est pas défini. Configurez-le via `MOAIAP config`.")

    project_manager = ProjectManager(config_manager)
    sandbox = project_manager.ensure_sandbox(str(sandbox_path))
    project_dir = sandbox / args.name

    commands = _collect_start_commands(args.start_cmds)

    print(f"Clonage du dépôt {args.repo} vers {project_dir}...")
    project_manager.clone_repository(args.repo, project_dir, branch=args.branch)
    project_manager.register_project(
        args.name,
        args.repo,
        commands,
        metadata={"branch": args.branch},
    )
    print(f"Projet '{args.name}' créé avec succès dans le sandbox.")


def handle_run_project(args: argparse.Namespace, config_manager: ConfigManager) -> None:
    password = config_manager.prompt_password()
    project_manager = ProjectManager(config_manager)
    runner = ProjectRunner(config_manager, project_manager)
    runner.run_project(args.name, password, max_attempts=args.max_attempts)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_manager = ConfigManager()

    try:
        if args.command == "config":
            handle_config(args, config_manager)
        elif args.command == "create-project":
            handle_create_project(args, config_manager)
        elif args.command == "run-project":
            handle_run_project(args, config_manager)
        else:  # pragma: no cover - sécurité
            parser.error("Commande non reconnue.")
            return 1
    except KeyboardInterrupt:
        print("\nOpération annulée par l'utilisateur.")
        return 1
    except Exception as exc:
        print(f"Erreur: {exc}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
