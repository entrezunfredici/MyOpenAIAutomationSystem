# MyOpenAIAutomationPackage

MyOpenAIAutomationPackage (MOAIAP) est un outil en ligne de commande qui aide à orchestrer des projets dans un dossier sandbox et à exploiter l'API d'OpenAI pour résoudre automatiquement les erreurs de démarrage.

## Installation

```bash
pip install MyOpenAIAutomationPackage
```

## Commande principale

Le package expose la commande `MOAIAP` avec plusieurs sous-commandes :

- `MOAIAP config` – Configure les secrets (dossier sandbox, identifiants Git, clefs API, clefs SSH) et les stocke localement dans un fichier chiffré.
- `MOAIAP create-project` – Crée un projet dans le sandbox en clonant un dépôt Git et en mémorisant les commandes de démarrage associées.
- `MOAIAP run-project` – Exécute les commandes d'un projet donné et, en cas d'échec, sollicite OpenAI (Codex) pour proposer une correction automatique.

## Développement

Le projet suit une structure basée sur `pyproject.toml` et utilise `setuptools`. Les fichiers sources se trouvent dans `src/my_openai_automation_package/`.
