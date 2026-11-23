# StudyX AI data model

## Storage

The application uses its standalone local database at `instance/studyx_blue.sqlite3`. SQLAlchemy owns the schema and database sessions. The app does not read a connection URL from the environment, so running it always uses SQLite.

Every private record carries a `user_id` and API queries filter on the authenticated account. Child records also use foreign keys to their owner object. Passwords use Werkzeug's scrypt password hash; plain-text passwords are never saved. User input is bounded and checked in the API before writing.

## Tables

| Table | What it stores | Important links |
|---|---|---|
| `users` | Account email, password hash and active state | One profile and many owned records |
| `student_profiles` | Display name, course, image URL, time zone and preferences | One-to-one with `users` |
| `subjects` | Student courses, category, difficulty and target hours | Assignments, exams, events and study records |
| `assignments` | Due date, priority, status and estimated time | User and optional subject |
| `exams` / `exam_topics` | Exam schedule and optional preparation topics | Exam topics cascade from their exam |
| `calendar_events` | Standalone events plus linked assignment, exam, revision and study events | User, optional subject and source record reference |
| `study_sessions` | Actual and planned study minutes, subject and start time | User and optional subject |
| `focus_sessions` | Timer duration, elapsed time and completion status | User and optional subject; creates a study session and event |
| `notes` | Titles, content, tags and timestamps | User and optional subject |
| `quizzes` / `quiz_questions` | Student-authored questions, options and correct answers | Questions cascade from a quiz |
| `quiz_attempts` | Score, submitted answers and attempt time | User and quiz |
| `goals` | Study-minute target and date range | User; actual minutes are calculated from saved sessions |
| `revision_plans` | Topic, due time and completion status | User and optional subject; creates a calendar event |
| `roadmaps` / `roadmap_tasks` | Learning paths and ordered, completable steps | Roadmap tasks cascade when a roadmap is removed |
| `progress` | Roadmap, assignment, quiz and study-session milestones | User and optional roadmap; milestone history is kept when a roadmap is removed |
| `analytics` | Actual rolling study-minute snapshots and their date window | Unique per user, metric and reporting window |
| `notifications` | Saved in-app reminders and read state | User |
| `tutor_messages` | Previous student questions and assistant responses | User |
| `usage_events` | Page views, button clicks, page time and selected feature actions | User; details deliberately exclude form values |
| `password_reset_tokens` | One-time, expiring, hashed reset tokens | User |
| `push_subscriptions` | Future browser push subscription storage | User; delivery is not enabled in this build |

## Calendar sync rules

Assignments, exams, timer sessions and manually added study sessions create calendar rows in the same database transaction as their source record. Deleting an assignment or exam removes its linked event. A standalone event can be edited or deleted in the calendar. The calendar is therefore a view of saved records, not a separate temporary schedule.

## Schema changes

`db.create_all()` creates missing tables at startup for a new local project and leaves existing tables and rows in place. It does not alter an existing table. Use Flask-Migrate for later changes: create a revision, inspect its operations, then run `flask --app run.py db upgrade`. The first app-created database should be stamped to the checked-in initial migration before generating future revisions.
