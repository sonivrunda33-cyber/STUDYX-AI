# StudyX AI: Progress and assignment checkbox fix

This patch modifies the **existing** STUDYX-AI-Blue-BUGFIX project. No new UI theme, model tables or empty database are created.

## Fixed
- `/api/analytics` now returns **all saved courses**, including new ones with zero study minutes. The Progress page shows course name, study minutes/target, completed/total assignments and a progress indicator. When both a study target and assignments exist, each contributes 50% to the course progress indicator; otherwise progress follows the one available activity.
- Assignment rows and dashboard tasks use an accessible click/touch checkbox with a visible SVG tick, instead of relying on CSS pseudo-elements on a native checkbox.
- Once the checkbox `PATCH /api/assignments/<id>` succeeds, the page refreshes to show persisted data. If the request fails, the checkbox resets and shows an error.
- GET requests to the API bypass browser caches; static asset versions and the service worker cache are bumped so phones use the latest JavaScript/CSS.

## Install without losing your data
1. Stop Flask (`Ctrl+C`) and disconnect your database viewer in PyCharm to avoid SQLite locks.
2. **Back up** your current `instance/studyx_blue.sqlite3`, `.env` and any other original data. Do **not** overwrite them.
3. Apply only the changed source files from this ZIP over your previous STUDYX-AI-Blue-BUGFIX project, or extract the complete project to a temporary separate folder and copy your existing `instance/` and `.env` yourself. Do not start a fresh database by mistake.
4. Use the Python environment that runs your app: `python -m pip install -r requirements.txt` then `python run.py --lan` (optional `--lan` for same-Wi-Fi phones).
5. Refresh the website once on both devices; if the service worker still shows old files, close and reopen the tab or clear the website's cached files.

## Verify
1. Add a new course with no study sessions. Open Progress: it should be listed at `0%`, `0m`, and `0/0 assignments`.
2. Add an assignment linked to that course. Open Progress again: should show `0/1 assignments`.
3. In Assignments, tick its square. It should show a tick and reload after the API saves. Check Completed filter, and Progress should now show `1/1 assignments`.
4. Untick the assignment. The page reloads and the assignment reopens.
5. The overall study-minutes metric increases only when study sessions are saved. Creating a course by itself does **not** count as study time.

## Tests
`python -m unittest discover -s tests -p "test_app.py"` (requires installed dependencies)
`node --check app/static/js/studyx.js`

## Calendar completion fix (added)
- Calendar day details and Agenda view now show the same visible checkbox for assignment events.
- The calendar API includes the linked assignment ID and its saved status. Ticking the calendar checkbox calls the existing assignment update API, so the assignment, dashboard, and Progress metrics all use the same database record.
- Ordinary personal/study/reminder calendar events are not given completion checkboxes; only actual linked assignments can affect assignment progress.
