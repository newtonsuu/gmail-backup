# Gmail → Drive/Local Backup (Python)

A standalone Python app that archives every email under a chosen Gmail
**label** into **one folder per email** — containing the full original
`.eml`, a readable `body.html`, and all attachments. A SQLite database tracks
what's been archived (so runs are idempotent and resumable), and a browsable
**Excel** index is exported after every run.

Gmail access is **read-only** — the app can never modify or delete your mail.

## How the backup logic works

Emails never change once received, so classic "full / differential /
incremental" file-backup logic doesn't apply. Instead:

- **First run = "Full":** archives everything under the label.
- **Every run after = "Incremental":** archives only emails not already in the
  database (matched by Gmail message ID).

Progress is committed after **every** email, so pressing Ctrl-C — or a crash,
or hitting an API quota — loses nothing. Just run it again and it resumes.

Unlike the Apps Script version, there's **no ~6-minute time limit**, so a large
first backup can complete in a single run.

## Where do backups go?

By default, to `EmailBackup/` in your home folder. **To get them into Google
Drive**, set `BACKUP_DIR` to a path inside your *Google Drive for Desktop*
folder (e.g. `G:\My Drive\EmailBackup`) — Drive then syncs everything up
automatically. This is far more robust than uploading via the API.

## One-time setup

### 1. Install Python deps
```powershell
cd C:\Users\jericho.james.guanga\GmailBackupPython
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Get `credentials.json` (Google OAuth client)
1. Go to <https://console.cloud.google.com/> → create (or pick) a project.
2. **APIs & Services → Library →** enable **Gmail API**.
3. **APIs & Services → OAuth consent screen:** choose **External**, fill in the
   app name/email, and under **Test users** add your own Gmail address.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID →**
   application type **Desktop app**. Download the JSON.
5. Save it as **`credentials.json`** next to `main.py`.

### 3. Configure
```powershell
copy .env.example .env
```
Edit `.env` and set `LABEL_NAME` to your exact Gmail label (and optionally
`BACKUP_DIR`).

### 4. Authorize + verify
```powershell
python main.py setup
```
A browser window opens once for you to grant read-only access. It then confirms
your label was found.

## Daily use

```powershell
python main.py run       # archive new emails (full the first time)
python main.py status    # show progress
python main.py export    # rebuild the Excel index from the database
```

Tip for a first test: set `MAX_MESSAGES=20` in `.env`, run once to confirm the
output looks right, then remove it and run again for the rest.

## Output layout

```
EmailBackup/
  backup_index.db                 (state / dedup — don't delete)
  Email Backup Index.xlsx         (browsable index)
  2026-05-30_1432__Invoice March__a1b2c3/
      email.eml                   (full original email)
      body.html                  (readable body)
      invoice.pdf                (attachment)
  2026-05-29_0901__Trip photos__d4e5f6/
      email.eml
      body.html
      IMG_2031.jpg
```

Excel columns: `Message ID | Date | From | To | Subject | Folder |
# Attachments | Size (KB) | Archived At | Backup Type`.

## Automating it (optional)

Use **Windows Task Scheduler** to run a daily backup. Action → Start a program:

- Program: `C:\Users\jericho.james.guanga\GmailBackupPython\.venv\Scripts\python.exe`
- Arguments: `main.py run`
- Start in: `C:\Users\jericho.james.guanga\GmailBackupPython`

## Project layout

| Path | Purpose |
|------|---------|
| `main.py` | CLI: `setup` / `run` / `status` / `export`. |
| `gmail_backup/config.py` | All settings (env-overridable). |
| `gmail_backup/auth.py` | OAuth + Gmail service (read-only scope). |
| `gmail_backup/gmail_client.py` | List by label, fetch raw messages. |
| `gmail_backup/archiver.py` | One email → one folder (.eml + html + attachments). |
| `gmail_backup/index.py` | SQLite state + Excel export. |
| `gmail_backup/backup.py` | Orchestration: full/incremental, resume, summary. |

## Security notes

`credentials.json`, `token.json`, and `.env` are secrets and are git-ignored.
Don't commit or share them. Revoke access anytime at
<https://myaccount.google.com/permissions>.
