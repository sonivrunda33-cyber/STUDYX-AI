from datetime import datetime, timezone

from .extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    profile = db.relationship("StudentProfile", back_populates="user", uselist=False,
                              cascade="all, delete-orphan")
    subjects = db.relationship("Subject", back_populates="user", cascade="all, delete-orphan")
    assignments = db.relationship("Assignment", back_populates="user", cascade="all, delete-orphan")
    exams = db.relationship("Exam", back_populates="user", cascade="all, delete-orphan")
    calendar_events = db.relationship("CalendarEvent", back_populates="user", cascade="all, delete-orphan")
    study_sessions = db.relationship("StudySession", back_populates="user", cascade="all, delete-orphan")
    focus_sessions = db.relationship("FocusSession", back_populates="user", cascade="all, delete-orphan")
    notes = db.relationship("Note", back_populates="user", cascade="all, delete-orphan")
    goals = db.relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    reset_tokens = db.relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    roadmaps = db.relationship("Roadmap", back_populates="user", cascade="all, delete-orphan")
    progress_records = db.relationship("Progress", back_populates="user", cascade="all, delete-orphan")
    analytics_snapshots = db.relationship("AnalyticsSnapshot", back_populates="user", cascade="all, delete-orphan")


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    course_name = db.Column(db.String(140), nullable=False, default="")
    profile_image_url = db.Column(db.String(500), nullable=False, default="")
    timezone_name = db.Column(db.String(80), nullable=False, default="Asia/Kolkata")
    preferences = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="profile")


class Subject(db.Model):
    __tablename__ = "subjects"
    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uq_subject_user_name"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="Core")
    color = db.Column(db.String(24), nullable=False, default="blue")
    difficulty = db.Column(db.Integer, nullable=False, default=3)
    target_hours = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User", back_populates="subjects")
    assignments = db.relationship("Assignment", back_populates="subject")
    exams = db.relationship("Exam", back_populates="subject")
    events = db.relationship("CalendarEvent", back_populates="subject")
    notes = db.relationship("Note", back_populates="subject")
    revision_plans = db.relationship("RevisionPlan", back_populates="subject")


class Assignment(db.Model):
    __tablename__ = "assignments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    due_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    priority = db.Column(db.String(16), nullable=False, default="medium")
    status = db.Column(db.String(16), nullable=False, default="todo", index=True)
    estimated_minutes = db.Column(db.Integer, nullable=False, default=45)
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User", back_populates="assignments")
    subject = db.relationship("Subject", back_populates="assignments")


class Exam(db.Model):
    __tablename__ = "exams"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(180), nullable=False)
    exam_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    location = db.Column(db.String(140), nullable=False, default="")
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User", back_populates="exams")
    subject = db.relationship("Subject", back_populates="exams")
    topics = db.relationship("ExamTopic", back_populates="exam", cascade="all, delete-orphan")


class ExamTopic(db.Model):
    __tablename__ = "exam_topics"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="todo")
    exam = db.relationship("Exam", back_populates="topics")


class CalendarEvent(db.Model):
    __tablename__ = "calendar_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(180), nullable=False)
    event_type = db.Column(db.String(24), nullable=False, default="study")
    starts_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    ends_at = db.Column(db.DateTime(timezone=True))
    all_day = db.Column(db.Boolean, nullable=False, default=False)
    details = db.Column(db.Text, nullable=False, default="")
    source_type = db.Column(db.String(24), nullable=False, default="calendar")
    source_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="calendar_events")
    subject = db.relationship("Subject", back_populates="events")


class StudySession(db.Model):
    __tablename__ = "study_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    subject_name = db.Column(db.String(120), nullable=False, default="")
    planned_minutes = db.Column(db.Integer, nullable=False)
    actual_minutes = db.Column(db.Integer, nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    completed = db.Column(db.Boolean, nullable=False, default=True)
    source = db.Column(db.String(24), nullable=False, default="manual")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User", back_populates="study_sessions")


class FocusSession(db.Model):
    __tablename__ = "focus_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    planned_minutes = db.Column(db.Integer, nullable=False)
    actual_minutes = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="completed")
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ended_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User", back_populates="focus_sessions")


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(180), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    tags = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="notes")
    subject = db.relationship("Subject", back_populates="notes")


class Goal(db.Model):
    __tablename__ = "goals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    target_minutes = db.Column(db.Integer, nullable=False, default=600)
    period = db.Column(db.String(16), nullable=False, default="week")
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User", back_populates="goals")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False, default="")
    category = db.Column(db.String(24), nullable=False, default="reminder")
    read_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    user = db.relationship("User", back_populates="notifications")


class Quiz(db.Model):
    __tablename__ = "quizzes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(180), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    questions = db.relationship("QuizQuestion", cascade="all, delete-orphan", order_by="QuizQuestion.id")
    attempts = db.relationship("QuizAttempt", cascade="all, delete-orphan", order_by="QuizAttempt.id")


class QuizQuestion(db.Model):
    __tablename__ = "quiz_questions"

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=False)
    correct_answer = db.Column(db.String(300), nullable=False)


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    answers = db.Column(db.JSON, nullable=False)
    attempted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class RevisionPlan(db.Model):
    __tablename__ = "revision_plans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(180), nullable=False)
    due_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    status = db.Column(db.String(16), nullable=False, default="scheduled")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    subject = db.relationship("Subject", back_populates="revision_plans")


class TutorMessage(db.Model):
    __tablename__ = "tutor_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)
    provider = db.Column(db.String(32), nullable=False, default="gemini")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class UsageEvent(db.Model):
    __tablename__ = "usage_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_name = db.Column(db.String(80), nullable=False)
    page = db.Column(db.String(50), nullable=False, default="")
    duration_ms = db.Column(db.Integer)
    detail = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class PushSubscription(db.Model):
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    subscription_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User", back_populates="reset_tokens")


class Roadmap(db.Model):
    __tablename__ = "roadmaps"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="roadmaps")
    subject = db.relationship("Subject")
    tasks = db.relationship("RoadmapTask", back_populates="roadmap", cascade="all, delete-orphan",
                             order_by="RoadmapTask.position")
    progress_records = db.relationship("Progress", back_populates="roadmap")


class RoadmapTask(db.Model):
    __tablename__ = "roadmap_tasks"

    id = db.Column(db.Integer, primary_key=True)
    roadmap_id = db.Column(db.Integer, db.ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    position = db.Column(db.Integer, nullable=False, default=0)
    estimated_minutes = db.Column(db.Integer, nullable=False, default=30)
    status = db.Column(db.String(16), nullable=False, default="todo")
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    roadmap = db.relationship("Roadmap", back_populates="tasks")


class Progress(db.Model):
    __tablename__ = "progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    roadmap_id = db.Column(db.Integer, db.ForeignKey("roadmaps.id", ondelete="SET NULL"), index=True)
    event_type = db.Column(db.String(40), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    details = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    user = db.relationship("User", back_populates="progress_records")
    roadmap = db.relationship("Roadmap", back_populates="progress_records")


class AnalyticsSnapshot(db.Model):
    __tablename__ = "analytics"
    __table_args__ = (db.UniqueConstraint("user_id", "metric_key", "period_start", "period_end",
                                           name="uq_analytics_user_metric_window"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_key = db.Column(db.String(80), nullable=False)
    metric_value = db.Column(db.Float, nullable=False, default=0)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    dimensions = db.Column(db.JSON, nullable=False, default=dict)
    captured_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="analytics_snapshots")


class ContactMessage(db.Model):
    """Messages from the public contact form. Never tied to a student account."""
    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    message = db.Column(db.Text, nullable=False)
    email_sent = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)
