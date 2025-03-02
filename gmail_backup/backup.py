"""
Orchestration: tie auth + Gmail + archiver + index together.

Backup model (emails are immutable, so classic differential/incremental
file logic doesn't apply):
  * First run  -> "Full"        : archive everything under the label.
  * Later runs -> "Incremental" : archive only message IDs not already indexed.

Idempotent and resumable: progress is committed to SQLite after every email,
so Ctrl-C or a crash loses nothing — just run again to continue.
"""

from __future__ import annotations

from datetime import datetime

from .archiver import archive_message
from .auth import get_service
from .config import Config
from .gmail_client import fetch_raw, find_label_id, iter_message_ids, list_label_names
from .index import Index


def _resolve_label(service, cfg: Config) -> str:
    label_id = find_label_id(service, cfg.label_name)
    if label_id is None:
        names = ", ".join(list_label_names(service)) or "(none found)"
        raise SystemExit(
            f'Gmail label "{cfg.label_name}" not found.\n'
            f"Available labels: {names}\n"
            "Fix LABEL_NAME in your .env (or config.py) — it is case-sensitive."
        )
    return label_id


def run_backup(cfg: Config) -> None:
    service = get_service(cfg)
    label_id = _resolve_label(service, cfg)
    cfg.backup_dir.mkdir(parents=True, exist_ok=True)

    index = Index(cfg.db_path)
    done = index.archived_ids()
    is_full = index.get_meta("initial_backup_done") != "true"
    backup_type = "Full" if is_full else "Incremental"

    print(f'▶ {backup_type} backup of "{cfg.label_name}"')
    print(f"  Destination : {cfg.backup_dir}")
    print(f"  Already archived: {len(done)} email(s)\n")

    archived = skipped = errors = 0
    interrupted = False

    try:
        for message_id in iter_message_ids(service, label_id):
            if message_id in done:
                skipped += 1
                continue
            if cfg.max_messages and archived >= cfg.max_messages:
                print(f"  (hit MAX_MESSAGES={cfg.max_messages}; stopping — rerun for the rest)")
                interrupted = True
                break
            try:
                raw = fetch_raw(service, message_id)
                result = archive_message(raw, message_id, cfg, backup_type)
                index.add(result.as_row())
                done.add(message_id)
                archived += 1
                print(f"  ✓ {result.subject[:60]}  ({result.num_attachments} attachment(s))")
            except Exception as exc:  # one bad email must not kill the run
                errors += 1
                print(f"  ⚠ {message_id}: {exc}")
    except KeyboardInterrupt:
        interrupted = True
        print("\n  Interrupted — progress saved. Run again to resume.")

    # Mark the full backup complete only if we finished the whole label.
    if is_full and not interrupted:
        index.set_meta("initial_backup_done", "true")
    index.set_meta("last_run_at", datetime.now().isoformat(timespec="seconds"))

    index.export_xlsx(cfg.xlsx_path)
    index.close()

    print(
        f"\n■ Done. Archived {archived} | Skipped {skipped} | Errors {errors}"
        + ("  (more remain)" if interrupted else "")
    )
    print(f"  Index (Excel): {cfg.xlsx_path}")


def print_status(cfg: Config) -> None:
    if not cfg.db_path.exists():
        print("No backup has run yet. Run:  python main.py setup   then:  python main.py run")
        return
    index = Index(cfg.db_path)
    print(f"Label            : {cfg.label_name}")
    initial = index.get_meta("initial_backup_done") == "true"
    print(f"Initial backup   : {'complete (now incremental)' if initial else 'not finished yet'}")
    print(f"Total archived   : {index.count()}")
    print(f"Last run at      : {index.get_meta('last_run_at', 'never')}")
    print(f"Destination      : {cfg.backup_dir}")
    print(f"Index (Excel)    : {cfg.xlsx_path}")
    index.close()
