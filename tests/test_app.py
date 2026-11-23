import os
import tempfile
import unittest
from datetime import datetime, time, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from sqlalchemy import inspect

from app import create_app
from app.extensions import db


class StudyXAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "studyx_test.sqlite3")
        self.database_url = f"sqlite:///{self.database_path.replace(os.sep, '/') }"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret-key-that-is-long-enough",
            "SQLALCHEMY_DATABASE_URI": self.database_url,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.register_and_sign_in(self.client)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def csrf(self, client):
        with client.session_transaction() as session:
            return session.get("_csrf_token")

    def register_and_sign_in(self, client, email="student@example.test", name="Study Student"):
        client.get("/register")
        token = self.csrf(client)
        response = client.post("/register", data={
            "csrf_token": token,
            "full_name": name,
            "email": email,
            "password": "a-secure-test-password",
            "confirm_password": "a-secure-test-password",
        })
        self.assertEqual(response.status_code, 302)
        client.get("/dashboard")  # issue a fresh CSRF token after the login session rotates
        return client

    def sign_in(self, client, email="student@example.test"):
        client.get("/login")
        response = client.post("/login", data={
            "csrf_token": self.csrf(client),
            "email": email,
            "password": "a-secure-test-password",
        })
        self.assertEqual(response.status_code, 302)
        client.get("/dashboard")
        return client

    def api(self, client, path, method="get", payload=None):
        return getattr(client, method)(
            f"/api{path}",
            json=payload if payload is not None else None,
            headers={"X-CSRF-Token": self.csrf(client)} if method.lower() != "get" else {},
        )

    def test_database_initializes_all_core_tables(self):
        with self.app.app_context():
            tables = set(inspect(db.engine).get_table_names())
        expected = {
            "users", "student_profiles", "subjects", "assignments", "exams",
            "calendar_events", "study_sessions", "focus_sessions", "notes",
            "quizzes", "quiz_questions", "quiz_attempts", "revision_plans",
            "goals", "notifications", "tutor_messages", "usage_events",
            "roadmaps", "roadmap_tasks", "progress", "analytics",
        }
        self.assertTrue(expected.issubset(tables))

    def test_sqlite_uses_wal_and_waits_for_short_locks(self):
        # A read transaction held by a database viewer should not stop writes.
        with self.app.app_context():
            with db.engine.connect() as connection:
                self.assertEqual(connection.exec_driver_sql("PRAGMA journal_mode").scalar(), "wal")
                timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar()
                self.assertGreaterEqual(timeout, 30000)

    def test_default_project_database_is_local_sqlite(self):
        with patch.dict(os.environ, {"STUDYX_DATABASE_URL": "postgresql://ignored/ignored"}):
            standalone_app = create_app()
        with standalone_app.app_context():
            self.assertEqual(db.engine.url.drivername, "sqlite")
            self.assertEqual(db.engine.url.database.split("/")[-1], "studyx_blue.sqlite3")
            db.session.remove()
            db.engine.dispose()

    def test_public_and_workspace_templates_render(self):
        for path in ["/", "/features", "/how-it-works", "/about", "/contact", "/sw.js"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()
        worker_response = self.client.get("/sw.js")
        worker = worker_response.get_data(as_text=True)
        worker_response.close()
        self.assertIn("/static/css/studyx-progress.css", worker)
        self.assertNotIn("studyx-roadmaps.css", worker)
        stylesheet = self.client.get("/static/css/studyx-progress.css")
        self.assertEqual(stylesheet.status_code, 200)
        stylesheet.close()
        for key in ("dashboard", "calendar", "assignments", "exams", "subjects",
                    "quizzes", "timetable", "focus", "progress"):
            with self.subTest(page=key):
                response = self.client.get(f"/{key}")
                self.assertEqual(response.status_code, 200)
                response.close()
        for removed in ("planner", "notes", "assistant", "revision", "roadmaps",
                        "goals", "notifications", "profile", "settings"):
            with self.subTest(removed_page=removed):
                self.assertEqual(self.client.get(f"/{removed}").status_code, 404)
        dashboard = self.client.get("/dashboard").get_data(as_text=True)
        for label in ("Overview", "Calendar", "Assignments", "Exams", "Courses",
                      "Focus timer", "Progress", "Smart timetable", "Quizzes", "Log out"):
            with self.subTest(nav_label=label):
                self.assertIn(label, dashboard)
        for label in ("Practice quizzes", "AI study assistant", "Revision planner", "Study goals"):
            with self.subTest(removed_label=label):
                self.assertNotIn(label, dashboard)

    def test_registration_login_and_hashed_password(self):
        with self.app.app_context():
            from app.models import User
            user = User.query.filter_by(email="student@example.test").one()
            self.assertNotEqual(user.password_hash, "a-secure-test-password")
            self.assertTrue(user.password_hash.startswith("scrypt:"))
        self.client.post("/logout", data={"csrf_token": self.csrf(self.client)})
        login_page = self.client.get("/login")
        self.assertEqual(login_page.status_code, 200)
        response = self.client.post("/login", data={
            "csrf_token": self.csrf(self.client),
            "email": "student@example.test",
            "password": "a-secure-test-password",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/api/dashboard").status_code, 200)

    def test_write_api_rejects_a_missing_csrf_token(self):
        response = self.client.post("/api/subjects", json={"name": "Should not save"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Your session security token expired. Refresh and try again.")

    def test_course_assignment_and_calendar_persist_after_new_app_instance(self):
        subject = self.api(self.client, "/subjects", "post", {"name": "Statistics", "target_hours": 6})
        self.assertEqual(subject.status_code, 201)
        subject_id = subject.get_json()["id"]
        due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        assignment = self.api(self.client, "/assignments", "post", {
            "title": "Practice set", "subject_id": subject_id, "due_at": due,
            "priority": "high", "estimated_minutes": 50,
        })
        self.assertEqual(assignment.status_code, 201)
        self.assertEqual(len(self.api(self.client, "/calendar-events?start=2020-01-01T00:00:00Z&end=2035-01-01T00:00:00Z").get_json()), 1)

        # Recreate the application against the same SQLite file to represent a restart.
        restarted_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret-key-that-is-long-enough",
            "SQLALCHEMY_DATABASE_URI": self.database_url,
        })
        restarted_client = restarted_app.test_client()
        self.sign_in(restarted_client)
        self.assertEqual(len(self.api(restarted_client, "/assignments").get_json()), 1)
        self.assertEqual(len(self.api(restarted_client, "/subjects").get_json()), 1)
        with restarted_app.app_context():
            db.session.remove()
            db.engine.dispose()

    def test_timer_and_manual_study_time_are_saved(self):
        subject = self.api(self.client, "/subjects", "post", {"name": "Python"}).get_json()
        started = datetime.now(timezone.utc) - timedelta(minutes=32)
        focus = self.api(self.client, "/focus-sessions", "post", {
            "planned_minutes": 45, "actual_minutes": 32, "status": "stopped",
            "started_at": started.isoformat(), "ended_at": datetime.now(timezone.utc).isoformat(),
            "subject_id": subject["id"],
        })
        self.assertEqual(focus.status_code, 201)
        manual = self.api(self.client, "/study-sessions", "post", {
            "minutes": 90, "started_at": started.isoformat(), "subject_id": subject["id"],
        })
        self.assertEqual(manual.status_code, 201)
        self.assertNotIn("quiz_average", self.api(self.client, "/dashboard").get_json())
        self.assertEqual(len(self.api(self.client, "/focus-sessions").get_json()), 1)

    def test_course_and_assignment_data_isolation(self):
        course = self.api(self.client, "/subjects", "post", {"name": "Private course"})
        self.assertEqual(course.status_code, 201)
        other = self.app.test_client()
        self.register_and_sign_in(other, email="other@example.test", name="Other Student")
        self.assertEqual(self.api(other, "/subjects").get_json(), [])
        due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        assignment = self.api(other, "/assignments", "post", {
            "title": "Other student's assignment", "due_at": due,
        })
        self.assertEqual(assignment.status_code, 201)
        updated = self.api(self.client, f"/assignments/{assignment.get_json()['id']}", "patch", {"status": "done"})
        self.assertEqual(updated.status_code, 404)
        updated = self.api(other, f"/assignments/{assignment.get_json()['id']}", "patch", {"status": "done"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["status"], "done")

    def test_assignment_completion_records_progress_and_analytics_snapshot(self):
        assignment = self.api(self.client, "/assignments", "post", {
            "title": "Finish probability worksheet",
            "due_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(assignment.status_code, 201)
        completed = self.api(self.client, f"/assignments/{assignment.get_json()['id']}", "patch", {"status": "done"})
        self.assertEqual(completed.status_code, 200)
        self.assertTrue(any(row["event_type"] == "assignment_completed" for row in self.api(self.client, "/progress").get_json()))
        self.assertEqual(self.api(self.client, "/analytics").status_code, 200)
        with self.app.app_context():
            from app.models import AnalyticsSnapshot
            snapshot = AnalyticsSnapshot.query.filter_by(metric_key="study_minutes_30d").one()
            self.assertEqual(snapshot.metric_value, 0)

    def test_progress_shows_new_courses_before_first_study_session(self):
        course = self.api(self.client, "/subjects", "post", {
            "name": "New JavaScript Course", "target_hours": 2,
        })
        self.assertEqual(course.status_code, 201)
        course_id = course.get_json()["id"]
        analytics = self.api(self.client, "/analytics").get_json()
        matching = [row for row in analytics["by_subject"] if row["id"] == course_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["minutes"], 0)
        self.assertEqual(matching[0]["progress_percent"], 0)
        self.assertEqual(matching[0]["target_minutes"], 120)
        self.assertEqual(matching[0]["assignments_total"], 0)

        assignment = self.api(self.client, "/assignments", "post", {
            "title": "JavaScript practice", "subject_id": course_id,
            "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        })
        self.assertEqual(assignment.status_code, 201)
        before = next(row for row in self.api(self.client, "/analytics").get_json()["by_subject"]
                      if row["id"] == course_id)
        self.assertEqual((before["assignments_completed"], before["assignments_total"]), (0, 1))
        task_id = assignment.get_json()["id"]
        done = self.api(self.client, f"/assignments/{task_id}", "patch", {"status": "done"})
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.get_json()["status"], "done")
        after = next(row for row in self.api(self.client, "/analytics").get_json()["by_subject"]
                     if row["id"] == course_id)
        self.assertEqual((after["assignments_completed"], after["assignments_total"]), (1, 1))
        self.assertEqual(after["progress_percent"], 50)  # study target 0%, assignment completion 100%
        self.assertEqual(after["progress_basis"], "combined")
        self.assertEqual(self.api(self.client, "/analytics").get_json()["assignments"]["completed"], 1)
        reopened = self.api(self.client, f"/assignments/{task_id}", "patch", {"status": "todo"})
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.get_json()["status"], "todo")
        self.assertEqual(next(row for row in self.api(self.client, "/analytics").get_json()["by_subject"]
                             if row["id"] == course_id)["assignments_completed"], 0)

    def test_course_progress_shows_assignment_percent_without_study_target(self):
        course = self.api(self.client, "/subjects", "post", {"name": "Self Study"}).get_json()
        due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        task = self.api(self.client, "/assignments", "post", {
            "title": "Practice", "subject_id": course["id"], "due_at": due,
        }).get_json()
        self.api(self.client, f"/assignments/{task['id']}", "patch", {"status": "done"})
        course_progress = next(row for row in self.api(self.client, "/analytics").get_json()["by_subject"]
                               if row["id"] == course["id"])
        self.assertEqual(course_progress["progress_percent"], 100)
        self.assertEqual(course_progress["progress_basis"], "assignments")

    def test_analytics_uses_the_profile_timezone_for_session_dates(self):
        with self.app.app_context():
            from app.models import User
            user = User.query.filter_by(email="student@example.test").one()
            profile_timezone = ZoneInfo(user.profile.timezone_name)
            local_day = datetime.now(timezone.utc).astimezone(profile_timezone).date()
            session_time = datetime.combine(local_day, time(hour=1), tzinfo=profile_timezone)
            started_at = session_time.astimezone(timezone.utc)

        stored = self.api(self.client, "/study-sessions", "post", {
            "minutes": 25, "started_at": started_at.isoformat(),
        })
        self.assertEqual(stored.status_code, 201)
        day = next(row for row in self.api(self.client, "/analytics").get_json()["daily"]
                   if row["date"] == local_day.isoformat())
        self.assertEqual(day["minutes"], 25)



    def test_public_contact_saves_to_existing_database_and_admin_only_inbox(self):
        guest = self.app.test_client()
        guest.get("/contact")
        response = guest.post("/api/contact", json={"name": "A Student", "email": "ask@example.test",
                                                    "message": "Please add chapter summaries"},
                              headers={"X-CSRF-Token": self.csrf(guest)})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.get_json()["saved"])
        self.assertFalse(response.get_json()["email_sent"])
        with self.app.app_context():
            from app.models import ContactMessage
            saved = ContactMessage.query.one()
            self.assertEqual(saved.email, "ask@example.test")
            self.assertFalse(saved.email_sent)
        self.assertEqual(self.api(self.client, "/contact-messages").status_code, 403)
        with patch.dict(os.environ, {"STUDYX_CONTACT_ADMIN_EMAIL": "student@example.test"}):
            listing = self.api(self.client, "/contact-messages")
            self.assertEqual(listing.status_code, 200)
            self.assertEqual(listing.get_json()[0]["message"], "Please add chapter summaries")
            inbox = self.client.get("/contact-inbox")
            self.assertEqual(inbox.status_code, 200)

    def test_linked_quiz_creation_answering_and_account_isolation(self):
        course = self.api(self.client, "/subjects", "post", {"name": "Web Technology"})
        self.assertEqual(course.status_code, 201)
        course_id = course.get_json()["id"]
        data = {"title": "HTML review", "subject_id": course_id, "questions": [
            {"prompt": "HTML lists are written with?", "options": ["ul", "img", "em"], "correct_answer": "ul"},
            {"prompt": "HTML is a?", "options": ["Markup language", "Database"], "correct_answer": "Markup language"}]}
        no_course = self.api(self.client, "/quizzes", "post", {**data, "subject_id": None})
        self.assertEqual(no_course.status_code, 400)
        created = self.api(self.client, "/quizzes", "post", data)
        self.assertEqual(created.status_code, 201)
        quiz_id = created.get_json()["id"]
        listing = self.api(self.client, "/quizzes").get_json()
        self.assertEqual(listing[0]["subject_id"], course_id)
        questions = self.api(self.client, f"/quizzes/{quiz_id}").get_json()["questions"]
        answers = {str(q["id"]): ("ul" if idx == 0 else "Markup language") for idx, q in enumerate(questions)}
        attempt = self.api(self.client, f"/quizzes/{quiz_id}/attempts", "post", {"answers": answers})
        self.assertEqual(attempt.status_code, 201)
        self.assertEqual(attempt.get_json()["score"], 2)
        self.assertEqual(self.api(self.client, "/quizzes").get_json()[0]["attempt_count"], 1)
        other = self.app.test_client()
        self.register_and_sign_in(other, "other@example.test", "Other Student")
        self.assertEqual(self.api(other, f"/quizzes/{quiz_id}").status_code, 404)

    def test_assignment_completion_api_and_logout_button(self):
        html = self.client.get("/assignments").get_data(as_text=True)
        self.assertIn("Log out", html)
        self.assertIn("assignmentList", html)
        task = self.api(self.client, "/assignments", "post", {
            "title": "Finish practice problems",
            "due_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})
        self.assertEqual(task.status_code, 201)
        task_id = task.get_json()["id"]
        checked = self.api(self.client, f"/assignments/{task_id}", "patch", {"status": "done"})
        self.assertEqual(checked.get_json()["status"], "done")
        self.assertIsNotNone(checked.get_json()["completed_at"])
        reopened = self.api(self.client, f"/assignments/{task_id}", "patch", {"status": "todo"})
        self.assertIsNone(reopened.get_json()["completed_at"])
        self.client.post("/logout", data={"csrf_token": self.csrf(self.client)})
        self.assertEqual(self.client.get("/dashboard").status_code, 302)

if __name__ == "__main__":
    unittest.main()
