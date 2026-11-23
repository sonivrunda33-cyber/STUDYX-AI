# StudyX AI — Student study workspace

StudyX AI is a standalone Flask application for organizing courses, assignments, exams, study time and progress. It uses its own SQLite database and does not read or modify the older StudyX project.

The interface uses a blue and white light theme or a blue and near-black dark theme, with a glass-like dashboard, a small CSS 3D study scene, motion effects and responsive layouts. The dashboard shows only information saved by the signed-in student. It does not show a quiz average. There is no Lab Research page or module.

## Included features

- Account registration, sign in, sign out, password reset links for local development, password hashing and CSRF protection.
- Eight workspace pages: Overview, Calendar, Assignments, Exams, Courses, Focus Timer, Progress and Smart Timetable.
- Calendar entries are saved in SQLite. Assignment and exam dates, finished focus sessions and manually entered study sessions appear on the calendar automatically.
- Timer presets plus a custom duration from 1 to 720 minutes. Start, pause, resume, finish and reset are supported; an in-progress timer survives a page refresh. Saved sessions update study history, progress and the calendar.
- Real progress calculations from saved records; no seeded/demo user data is included.
- SQLite storage at `instance/studyx_blue.sqlite3`, SQLAlchemy models, Flask-Migrate, a minimal installable PWA shell and privacy-conscious usage-event logging.

## Run on Windows

Open PowerShell in this folder and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000), create a student account, then add courses and your study data. The first run initializes `instance/studyx_blue.sqlite3` automatically. That database file stays local and is excluded from Git and the project ZIP.

If the Python launcher cannot find the installed interpreter, use its executable path for the virtual environment command, for example:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" -m venv .venv
```

If PowerShell blocks activation, use the virtual environment executable directly:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run.py
```

Set a private, random `STUDYX_SECRET_KEY` in `.env` before using the app beyond a local demo.

## Use on mobile and laptop

Run `python run.py --lan` and visit your laptop's Wi-Fi IPv4 address from a phone on the same network. For a public HTTPS link, use a persistent hosted database. See [MOBILE-LAPTOP-SETUP.md](MOBILE-LAPTOP-SETUP.md) for exact steps, networking and data-safety notes.

## Database and migrations

SQLite is initialized automatically when the app starts. Existing database records are not deleted or replaced. The active workspace uses user profiles, courses, assignments, exams, calendar events, study and focus sessions, and progress. Legacy tables from earlier StudyX features stay in the SQLite file so their records are not erased; those pages are not part of this workspace.

For an existing auto-initialized local database, mark the current initial schema as the migration baseline once:

```powershell
flask --app run.py db stamp head
```

After changing a model, create and inspect a migration, then apply it:

```powershell
flask --app run.py db migrate -m "describe the schema change"
flask --app run.py db upgrade
```

Never remove `instance/studyx_blue.sqlite3` to apply a migration. Back it up before schema changes. This project uses its local SQLite file.

## If PyCharm shows blank tables or "database is locked"

- Stop Flask (`Ctrl+C`). In PyCharm DB Browser, **Commit** any work you want to keep, or **Rollback** unwanted pending edits; then **Disconnect** the SQLite connection. Auto-Commit OFF can leave an edit transaction open and prevent Flask writes.
- Run `python tools/check_database.py` from the folder containing `run.py`. This prints the exact database path, journal mode, and number of users **without changing or creating a database**.
- Start Flask again with `python run.py`. The app now waits up to 30 seconds for short SQLite locks and enables WAL mode when the database permits it, so ordinary readers can coexist with a writer.
- If you reconnect PyCharm to view records, use the same `instance/studyx_blue.sqlite3` file and avoid holding open write transactions. Refresh the table and clear filters. Never delete the database or its `-wal`/`-shm` files while connections are active.
- WAL does **not** bypass an active uncommitted write from DB Browser: finish that transaction or disconnect the editor. The API will return HTTP 503 with a busy-database message if a lock persists.

Your existing `instance/studyx_blue.sqlite3` is **not in the project ZIP**. Keep that file when updating the code; it holds registered users, subjects, and study data.

## Tests

Run the automated database and application checks:

```powershell
python -m unittest discover -s tests -v
node tests/timer_ui.test.js
```

The tests cover automatic SQLite initialization, registration and login, password hashes, account isolation, calendar persistence, focus and manual session records, progress, and rendering only the eight selected workspace pages. See [docs/USER-VALIDATION.md](docs/USER-VALIDATION.md) for the separate real-user study plan. Automated tests do not replace the assignment's required participant survey or usability sessions.

## Project layout

```text
app/
  routes/                Flask pages, authentication and JSON API
  static/css/            Theme, page and responsive styles
  static/js/studyx.js    Calendar, timer, forms, charts and interactions
  templates/             Public pages, sign-in and workspace pages
  models.py              SQLAlchemy data model
instance/                 Local SQLite database (ignored)
migrations/               Alembic migration environment and initial revision
tests/                    Automated application and persistence tests
docs/                     Database and user-validation notes
```

## Deployment notes

Use HTTPS and a strong secret in deployment, and set `STUDYX_COOKIE_SECURE=1`. `gunicorn run:app` is intended for Linux-based hosting. Do not commit `.env` or the local SQLite file.
