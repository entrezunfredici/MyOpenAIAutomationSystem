"""Gestion de la configuration sécurisée pour MOAIAP."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from getpass import getpass
from pathlib import Path
from typing import Dict, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet


@dataclass
class ConfigData:
    """Structure forte pour représenter les données de configuration."""

    sandbox_path: str
    git_username: Optional[str] = None
    git_email: Optional[str] = None
    git_token: Optional[str] = None
    openai_api_key: Optional[str] = None
    ssh_private_key: Optional[str] = None
    ssh_public_key: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Optional[str]]:
        data: Dict[str, Optional[str]] = {
            "sandbox_path": self.sandbox_path,
            "git_username": self.git_username,
            "git_email": self.git_email,
            "git_token": self.git_token,
            "openai_api_key": self.openai_api_key,
            "ssh_private_key": self.ssh_private_key,
            "ssh_public_key": self.ssh_public_key,
        }
        data.update(self.extra)
        return data


class ConfigManager:
    """Gère le stockage chiffré des données de configuration."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        self.config_dir = config_dir or Path.home() / ".moaiap"
        self.config_file = self.config_dir / "config.enc"
        self.projects_file = self.config_dir / "projects.json"

    # ------------------------------------------------------------------
    # Gestion des mots de passe
    # ------------------------------------------------------------------
    @staticmethod
    def prompt_password(confirm: bool = False) -> str:
        """Demande un mot de passe maître à l'utilisateur."""

        password = getpass("Entrez le mot de passe maître: ")
        if confirm:
            confirmation = getpass("Confirmez le mot de passe maître: ")
            if password != confirmation:
                raise ValueError("Le mot de passe et sa confirmation ne correspondent pas.")
        if not password:
            raise ValueError("Le mot de passe ne peut pas être vide.")
        return password

    # ------------------------------------------------------------------
    # Stockage sécurisé
    # ------------------------------------------------------------------
    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    @staticmethod
    def _encrypt(data: Dict[str, Optional[str]], password: str) -> Dict[str, str]:
        salt = os.urandom(16)
        key = ConfigManager._derive_key(password, salt)
        fernet = Fernet(key)
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        encrypted = fernet.encrypt(payload)
        return {
            "salt": base64.b64encode(salt).decode("utf-8"),
            "data": encrypted.decode("utf-8"),
        }

    @staticmethod
    def _decrypt(encrypted_payload: Dict[str, str], password: str) -> Dict[str, Optional[str]]:
        salt = base64.b64decode(encrypted_payload["salt"])
        key = ConfigManager._derive_key(password, salt)
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_payload["data"].encode("utf-8"))
        return json.loads(decrypted)

    def config_exists(self) -> bool:
        return self.config_file.exists()

    def save_config(self, config: ConfigData, password: str) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        payload = self._encrypt(config.to_dict(), password)
        self.config_file.write_text(json.dumps(payload, indent=2))

    def load_config(self, password: str) -> Dict[str, Optional[str]]:
        if not self.config_file.exists():
            raise FileNotFoundError(
                "Aucun fichier de configuration chiffré trouvé. Lancez `MOAIAP config` d'abord."
            )
        encrypted_payload = json.loads(self.config_file.read_text())
        return self._decrypt(encrypted_payload, password)

    # ------------------------------------------------------------------
    # Gestion des projets enregistrés
    # ------------------------------------------------------------------
    def load_projects(self) -> Dict[str, Dict[str, object]]:
        if not self.projects_file.exists():
            return {}
        return json.loads(self.projects_file.read_text())

    def save_projects(self, projects: Dict[str, Dict[str, object]]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.projects_file.write_text(json.dumps(projects, ensure_ascii=False, indent=2))
