"""
Configuration.

Everything has a sensible default. Override any value by creating a `.env`
file next to main.py (copy `.env.example`) — no code changes needed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Load a .env file if python-dotenv is installed (optional convenience).
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is optional
    pass


def _flag(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # The exact Gmail label to back up (case-sensitive). Nested = "Work/Invoices".
    label_name: str = os.environ.get("LABEL_NAME", "Receipts")

    # Where backups are written. Point this at your Google Drive for Desktop
    # folder to have everything auto-sync into Drive.
    backup_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("BACKUP_DIR", str(Path.home() / "EmailBackup"))
        )
    )

    # What to save inside each email's folder.
    save_eml: bool = _flag("SAVE_EML", True)       # full original .eml (perfect fidelity)
    save_html: bool = _flag("SAVE_HTML", True)     # readable body.html
    include_inline_images: bool = _flag("INCLUDE_INLINE_IMAGES", False)

    # Safety cap: stop after N new emails in one run (0 = no cap). Useful for a
    # first test run.
    max_messages: int = int(os.environ.get("MAX_MESSAGES", "0"))

    # OAuth files. credentials.json is downloaded from Google Cloud (see README).
    # token.json is created automatically after the first authorization.
    credentials_file: Path = field(
        default_factory=lambda: Path(os.environ.get("CREDENTIALS_FILE", "credentials.json"))
    )
    token_file: Path = field(
        default_factory=lambda: Path(os.environ.get("TOKEN_FILE", "token.json"))
    )

    @property
    def db_path(self) -> Path:
        """SQLite index — the source of truth for what's already archived."""
        return self.backup_dir / "backup_index.db"

    @property
    def xlsx_path(self) -> Path:
        """Human-browsable Excel export of the index."""
        return self.backup_dir / "Email Backup Index.xlsx"


def load_config() -> Config:
    return Config()
