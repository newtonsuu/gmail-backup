"""
The index: a small SQLite database that records every archived email.

It serves two jobs at once:
  1. Dedup / resume state — we skip any message ID already present, which is
     what makes runs idempotent and safely re-runnable.
  2. The data source for the browsable Excel export.
"""

from __future__ import annotations

from pathlib import Path

import sqlite3

COLUMNS = [
    "Message ID", "Date", "From", "To", "Subject",
    "Folder", "# Attachments", "Size (KB)", "Archived At", "Backup Type",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS archived (
    message_id      TEXT PRIMARY KEY,
    date            TEXT,
    sender          TEXT,
    recipient       TEXT,
    subject         TEXT,
    folder          TEXT,
    num_attachments INTEGER,
    size_kb         INTEGER,
    archived_at     TEXT,
    backup_type     TEXT
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class Index:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # --- archived set -------------------------------------------------------
    def archived_ids(self) -> set[str]:
        cur = self.conn.execute("SELECT message_id FROM archived")
        return {row[0] for row in cur.fetchall()}

    def add(self, row: tuple) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO archived VALUES (?,?,?,?,?,?,?,?,?,?)", row
        )
        self.conn.commit()  # commit per-email so an interrupt loses nothing

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM archived").fetchone()[0]

    # --- meta key/value -----------------------------------------------------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        cur = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, str(value))
        )
        self.conn.commit()

    # --- export -------------------------------------------------------------
    def export_xlsx(self, path: Path) -> None:
        """Write a fresh .xlsx snapshot of the whole index."""
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = "Index"
        ws.append(COLUMNS)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"

        for row in self.conn.execute(
            "SELECT message_id, date, sender, recipient, subject, folder, "
            "num_attachments, size_kb, archived_at, backup_type "
            "FROM archived ORDER BY date"
        ):
            ws.append(list(row))

        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(path))
