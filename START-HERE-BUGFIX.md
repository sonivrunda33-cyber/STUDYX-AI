# STUDYX AI — Existing UI, focused bug fixes

This is **the same existing website**, not a redesigned/new study app. The original blue theme, pages, core models, and responsive CSS have been kept. Only the requested bugs/features were changed.

## 1. Important: preserve the SAME existing database

The ZIP does **not** contain a replacement `studyx_blue.sqlite3`. Existing student records are on your laptop, not in this download. Do not delete, replace, or rename the old database without a backup.

1. Stop the Flask server in PyCharm with **Ctrl+C** and disconnect PyCharm DB Browser (commit or roll back any pending edits first).
2. Extract this ZIP to a *separate* folder. Open the folder containing `run.py` in PyCharm.
3. Find your OLD working `instance\studyx_blue.sqlite3` file. Run this in the **new** folder **before the first launch**, using your actual old path:

```powershell
python .\tools\import_existing_db.py "C:\FULL\PATH\TO\OLD\instance\studyx_blue.sqlite3"
```

The importer uses SQLite's backup API (which includes committed WAL data), checks integrity and registered users, and refuses to overwrite a destination file. The original is not changed. If the target already exists, STOP and inspect it; do not overwrite.

4. Copy the original project's `.env` into this folder if it exists (this preserves sessions and app settings). **Never upload `.env` publicly.**
5. Install dependencies if needed: `python -m pip install -r requirements.txt`
6. Run `python run.py` (laptop), or `python run.py --lan` (mobile on the same trusted Wi-Fi).
7. The app's existing startup `db.create_all()` adds just the new `contact_messages` table if needed. All existing tables and records remain.

## 2. Fixed functionality

- **Contact**: Name, reply email, message; `POST /api/contact` stores the submission in the existing database table `contact_messages`. Form shows the actual save state. It does not fake successful email delivery.
- **Optional contact email**: In `.env` set `STUDYX_CONTACT_ADMIN_EMAIL` and all `STUDYX_SMTP_*` fields (host, port, user, password, from) for actual SMTP sending. If email is missing or fails, the database still stores the message and the UI explicitly says delivery is not configured/pending. Don't commit credentials to Git.
- **Contact inbox**: Register or use the account matching `STUDYX_CONTACT_ADMIN_EMAIL`; it sees **Contact inbox** in the workspace sidebar at `/contact-inbox`. Other users cannot view its messages. You can also review `contact_messages` in DB Browser.
- **Tasks**: Actual clickable checkboxes appear on both Assignments and Dashboard. Checked state is persisted to `assignments.status` and completion updates progress. Unchecking reopens the task.
- **Logo**: Sidebar logo, text, and dashboard decorative logo have fixed dimensions on every page/theme; no size jumps.
- **Quiz linked to course**: Sidebar **Quizzes** and **Courses → Create course quiz**; choose an existing course, build questions with selectable answers, take quiz, and save attempts and score to existing `quizzes`, `quiz_questions`, and `quiz_attempts`. No new quiz tables are needed.
- **Logout**: Visible in the sidebar (mobile menu included) and desktop header. Uses the existing protected POST `/logout` route, not a GET link.
- **Cache**: Service worker cache updated and CSS/JS URLs versioned to prevent old UI appearing on navigation.

## 3. Contact email example (optional)

Append the following to your private `.env` file (replace placeholders with valid credentials):

```dotenv
STUDYX_CONTACT_ADMIN_EMAIL=admin@example.com
STUDYX_SMTP_HOST=smtp.example.com
STUDYX_SMTP_PORT=587
STUDYX_SMTP_USER=your_smtp_username
STUDYX_SMTP_PASSWORD=your_private_app_password
STUDYX_SMTP_FROM=verified-sender@example.com
```

For SMTP port 465 the app uses SMTP over SSL; for other ports it connects with STARTTLS. Your email provider must allow SMTP and your FROM address. Without working credentials, you can still view every message from `/contact-inbox` by setting the admin email to the email of an existing StudyX account.

## 4. Quick testing

1. Log in, **Courses → Add course** (e.g. Programming).
2. Click **Create course quiz** on that course. Add questions/options, save, take the quiz, submit. Verify attempts/score persist after refreshing.
3. **Assignments → Add assignment**. An empty checkbox appears. Tap to complete (tick); refresh to confirm state. Try marking open again. Check the dashboard's **Coming up** checkboxes too.
4. **Contact → Send message**. Verify saved feedback and record in DB Browser (`contact_messages`). Email will only be sent if SMTP is configured; otherwise message is saved, **not emailed**.
5. Navigate Dashboard → Courses → Progress and confirm logo remains fixed. Then click **Log out** and confirm dashboard redirects to login.

## 5. Testing limitations

`python -m compileall`, `node --check`, and existing Node timer UI test were run successfully here. A full Flask integration/browser test could **not** be executed in this workspace because the Flask dependencies were not installed and the environment cannot download them. Use your PyCharm virtual environment for live verification.
