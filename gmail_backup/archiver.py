"""
Turn one raw email into one folder on disk:

    2026-05-30_1432__Invoice March__a1b2c3/
        email.eml      full original (headers + body + attachments)
        body.html     readable rendering of the body
        invoice.pdf   each attachment under its original name
"""

from __future__ import annotations

import email
import re
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path

from .config import Config

_ILLEGAL = re.compile(r'[\\/:*?"<>|\r\n\t]')


@dataclass
class ArchiveResult:
    message_id: str
    date: str
    sender: str
    recipient: str
    subject: str
    folder: str
    num_attachments: int
    size_kb: int
    archived_at: str
    backup_type: str

    def as_row(self) -> tuple:
        return (
            self.message_id, self.date, self.sender, self.recipient, self.subject,
            self.folder, self.num_attachments, self.size_kb, self.archived_at,
            self.backup_type,
        )


def sanitize(name: str, fallback: str = "untitled") -> str:
    """Make a string safe for a Windows/macOS/Linux file or folder name."""
    if not name:
        return fallback
    cleaned = _ILLEGAL.sub(" ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or fallback


def _build_folder_name(dt: datetime | None, subject: str, message_id: str) -> str:
    stamp = dt.strftime("%Y-%m-%d_%H%M") if dt else "0000-00-00_0000"
    safe_subject = sanitize(subject)[:80].strip() or "(no subject)"
    return f"{stamp}__{safe_subject}__{message_id[-6:]}"


def _unique_dir(parent: Path, name: str) -> Path:
    """Return a non-existing directory path, suffixing -2, -3... on collision."""
    candidate = parent / name
    i = 2
    while candidate.exists():
        candidate = parent / f"{name}-{i}"
        i += 1
    return candidate


def _to_bytes(content) -> bytes:
    return content.encode("utf-8") if isinstance(content, str) else content


def archive_message(
    raw_bytes: bytes, message_id: str, cfg: Config, backup_type: str
) -> ArchiveResult:
    """Parse and write a single email. Returns the index row data."""
    msg: EmailMessage = email.message_from_bytes(raw_bytes, policy=policy.default)

    subject = msg["subject"] or "(no subject)"
    sender = str(msg["from"] or "")
    recipient = str(msg["to"] or "")
    try:
        dt = parsedate_to_datetime(msg["date"]) if msg["date"] else None
    except (TypeError, ValueError):
        dt = None

    folder = _unique_dir(cfg.backup_dir, _build_folder_name(dt, subject, message_id))
    folder.mkdir(parents=True, exist_ok=True)

    # 1) Full original email.
    if cfg.save_eml:
        (folder / "email.eml").write_bytes(raw_bytes)

    # 2) Readable body (prefer HTML, fall back to plain text).
    if cfg.save_html:
        body = msg.get_body(preferencelist=("html", "plain"))
        if body is not None:
            content = body.get_content()
            ext = "html" if body.get_content_subtype() == "html" else "txt"
            (folder / f"body.{ext}").write_text(
                content if isinstance(content, str) else str(content),
                encoding="utf-8",
            )

    # 3) Attachments under their original filenames.
    total_bytes = 0
    count = 0
    for part in msg.iter_attachments():
        if (
            not cfg.include_inline_images
            and part.get_content_disposition() == "inline"
        ):
            continue
        filename = sanitize(part.get_filename() or f"attachment-{count + 1}")
        data = _to_bytes(part.get_content())
        target = _unique_file(folder, filename)
        target.write_bytes(data)
        total_bytes += len(data)
        count += 1

    return ArchiveResult(
        message_id=message_id,
        date=dt.isoformat() if dt else "",
        sender=sender,
        recipient=recipient,
        subject=subject,
        folder=str(folder),
        num_attachments=count,
        size_kb=round(total_bytes / 1024),
        archived_at=datetime.now().isoformat(timespec="seconds"),
        backup_type=backup_type,
    )


def _unique_file(parent: Path, name: str) -> Path:
    """Avoid clobbering two attachments that share a filename."""
    candidate = parent / name
    if not candidate.exists():
        return candidate
    stem, dot, ext = name.partition(".")
    i = 2
    while candidate.exists():
        suffix = f"-{i}"
        candidate = parent / (f"{stem}{suffix}.{ext}" if dot else f"{name}{suffix}")
        i += 1
    return candidate
