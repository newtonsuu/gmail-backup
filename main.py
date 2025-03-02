"""
Gmail -> Drive/local backup — command-line entry point.

Usage:
    python main.py setup     One-time: authorize Google + verify your label.
    python main.py run       Back up new emails (full first time, then only new).
    python main.py status    Show progress.
    python main.py export    Rewrite the Excel index from the database.

Run `python main.py <command> -h` for command-specific help.
"""

from __future__ import annotations

import argparse
import sys

from gmail_backup.backup import print_status, run_backup
from gmail_backup.config import load_config


def cmd_setup(cfg) -> None:
    from gmail_backup.auth import get_service
    from gmail_backup.gmail_client import find_label_id, list_label_names

    print("Authorizing with Google (a browser window may open)...")
    service = get_service(cfg)
    print("✅ Authorized. Gmail access is read-only.\n")

    label_id = find_label_id(service, cfg.label_name)
    if label_id:
        print(f'✅ Found label: "{cfg.label_name}"')
    else:
        print(f'⚠ Label "{cfg.label_name}" not found. Available labels:')
        for name in list_label_names(service):
            print(f"     - {name}")
        print("\n   Set LABEL_NAME in your .env to one of the above.")

    cfg.backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nBackup folder ready: {cfg.backup_dir}")
    print("Next: python main.py run")


def cmd_export(cfg) -> None:
    from gmail_backup.index import Index

    if not cfg.db_path.exists():
        print("Nothing to export yet — run a backup first.")
        return
    index = Index(cfg.db_path)
    index.export_xlsx(cfg.xlsx_path)
    index.close()
    print(f"✅ Wrote {cfg.xlsx_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="main.py", description="Back up Gmail (by label) to a folder per email."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="Authorize Google and verify the label.")
    sub.add_parser("run", help="Archive new emails under the label.")
    sub.add_parser("status", help="Show backup progress.")
    sub.add_parser("export", help="Rewrite the Excel index from the database.")

    args = parser.parse_args(argv)
    cfg = load_config()

    if args.command == "setup":
        cmd_setup(cfg)
    elif args.command == "run":
        run_backup(cfg)
    elif args.command == "status":
        print_status(cfg)
    elif args.command == "export":
        cmd_export(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
