import re
import os
import smtplib
import ssl
from email.message import EmailMessage
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from ..extensions import db
from ..models import (
    AnalyticsSnapshot, Assignment, CalendarEvent, ContactMessage, Exam, ExamTopic, FocusSession,
    Goal, Note, Notification, Progress, Quiz, QuizAttempt, QuizQuestion,
    RevisionPlan, Roadmap, RoadmapTask, StudySession, Subject, StudentProfile,
    UsageEvent, User,
)

api = Blueprint("api", __name__)


def owner_id():
    return int(session["user_id"])


def now_utc():
    return datetime.now(timezone.utc)


def user_timezone(user_id):
    user = db.session.get(User, user_id)
    name = user.profile.timezone_name if user and user.profile else "UTC"
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def local_date(value, user_id):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(user_timezone(user_id)).date()


def user_today(user_id):
    return now_utc().astimezone(user_timezone(user_id)).date()


def fail(message, status=400):
    return jsonify({"error": message}), status


def body():
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def text(data, key, label, limit, required=False):
    value = str(data.get(key, "") or "").strip()
    if required and not value:
        raise ValueError(f"{label} is required.")
    if len(value) > limit:
        raise ValueError(f"{label} must be {limit} characters or fewer.")
    return value


def int_value(value, label, low, high):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a whole number.")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if not low <= parsed <= high:
        raise ValueError(f"{label} must be between {low} and {high}.")
    return parsed


def parse_datetime(value, label, required=True):
    if value in (None, ""):
        if required:
            raise ValueError(f"{label} is required.")
        return None
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Enter a valid {label.lower()}.")
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def iso(value):
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def subject_for(user_id, raw_id):
    if raw_id in (None, ""):
        return None
    try:
        subject_id = int(raw_id)
    except (TypeError, ValueError):
        raise ValueError("Choose a valid subject.")
    subject = Subject.query.filter_by(id=subject_id, user_id=user_id).first()
    if not subject:
        raise ValueError("That subject isn't in your study space.")
    return subject


def event_json(item):
    result = {
        "id": item.id, "title": item.title, "event_type": item.event_type,
        "starts_at": iso(item.starts_at), "ends_at": iso(item.ends_at),
        "all_day": item.all_day, "details": item.details, "subject_id": item.subject_id,
        "subject": item.subject.name if item.subject else None,
        "source_type": item.source_type, "source_id": item.source_id,
    }
    # Assignment calendar entries are linked records. Expose their persisted
    # status so the calendar can complete/reopen the actual assignment rather
    # than changing a decorative calendar event.
    if item.source_type == "assignment" and item.source_id:
        assignment = Assignment.query.filter_by(
            id=item.source_id, user_id=item.user_id
        ).first()
        if assignment:
            result["assignment_id"] = assignment.id
            result["status"] = assignment.status
    return result


def assignment_json(item):
    return {
        "id": item.id, "title": item.title, "description": item.description,
        "subject_id": item.subject_id, "subject": item.subject.name if item.subject else "",
        "due_at": iso(item.due_at), "priority": item.priority, "status": item.status,
        "estimated_minutes": item.estimated_minutes, "completed_at": iso(item.completed_at),
        "created_at": iso(item.created_at),
    }


def exam_json(item):
    return {
        "id": item.id, "title": item.title, "subject_id": item.subject_id,
        "subject": item.subject.name if item.subject else "", "exam_at": iso(item.exam_at),
        "location": item.location, "notes": item.notes, "topics": [
            {"id": topic.id, "title": topic.title, "status": topic.status} for topic in item.topics
        ],
    }


def roadmap_json(item):
    total = len(item.tasks)
    completed = sum(task.status == "done" for task in item.tasks)
    return {
        "id": item.id, "title": item.title, "description": item.description,
        "subject_id": item.subject_id, "subject": item.subject.name if item.subject else "",
        "status": item.status, "created_at": iso(item.created_at),
        "total_tasks": total, "completed_tasks": completed,
        "completion_rate": round(completed / total * 100) if total else 0,
        "tasks": [{
            "id": task.id, "title": task.title, "description": task.description,
            "position": task.position, "estimated_minutes": task.estimated_minutes,
            "status": task.status, "completed_at": iso(task.completed_at),
        } for task in item.tasks],
    }


def note_json(item):
    return {
        "id": item.id, "title": item.title, "content": item.content,
        "subject_id": item.subject_id, "subject": item.subject.name if item.subject else "",
        "tags": item.tags or [], "created_at": iso(item.created_at), "updated_at": iso(item.updated_at),
    }


def sync_linked_event(user_id, kind, item_id, title, subject_id, starts_at, duration=60, all_day=False):
    event = CalendarEvent.query.filter_by(user_id=user_id, source_type=kind, source_id=item_id).first()
    if event is None:
        event = CalendarEvent(user_id=user_id, source_type=kind, source_id=item_id)
        db.session.add(event)
    event.title = title
    event.event_type = kind
    event.subject_id = subject_id
    event.starts_at = starts_at
    event.ends_at = starts_at + timedelta(minutes=duration) if not all_day else None
    event.all_day = all_day


@api.errorhandler(IntegrityError)
def integrity_error(_error):
    db.session.rollback()
    return fail("This record conflicts with one already saved.", 409)


@api.errorhandler(SQLAlchemyError)
def database_error(_error):
    db.session.rollback()
    current_app.logger.exception("StudyX API database operation failed")
    if isinstance(_error, OperationalError) and "database is locked" in str(_error.orig).lower():
        return fail("Database is busy. Save any changes in DB Browser, disconnect it, and try again.", 503)
    return fail("We couldn't save that just now. Please try again.", 500)


@api.get("/dashboard")
def dashboard():
    user_id = owner_id()
    today = user_today(user_id)
    start_of_week = today - timedelta(days=today.weekday())
    assignments = Assignment.query.filter_by(user_id=user_id).all()
    exams = Exam.query.filter_by(user_id=user_id).order_by(Exam.exam_at).all()
    sessions = StudySession.query.filter_by(user_id=user_id).order_by(StudySession.started_at.desc()).all()
    upcoming = sorted(
        [item for item in assignments if item.status != "done"],
        key=lambda item: item.due_at or now_utc(),
    )[:5]
    future_exams = [
        item for item in exams
        if (item.exam_at.replace(tzinfo=timezone.utc) if item.exam_at.tzinfo is None else item.exam_at) >= now_utc()
    ]
    by_day = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        selected = [item for item in sessions if local_date(item.started_at, user_id) == day]
        by_day.append({
            "date": day.isoformat(), "label": day.strftime("%a"),
            "minutes": sum(item.actual_minutes for item in selected),
        })
    week_minutes = sum(
        item.actual_minutes for item in sessions if local_date(item.started_at, user_id) >= start_of_week
    )
    completed = sum(item.status == "done" for item in assignments)
    total = len(assignments)
    profile = db.session.get(User, user_id).profile
    unread = Notification.query.filter_by(user_id=user_id, read_at=None).count()
    goal = Goal.query.filter_by(user_id=user_id, completed=False).order_by(Goal.ends_on).first()
    return jsonify({
        "profile": {
            "full_name": profile.full_name if profile else "Student",
            "course_name": profile.course_name if profile else "",
        },
        "assignments": {
            "total": total, "completed": completed,
            "completion_rate": completed / total if total else None,
            "upcoming": [assignment_json(item) for item in upcoming],
        },
        "exams": {
            "count": len(exams),
            "next": exam_json(future_exams[0]) if future_exams else None,
        },
        "study": {
            "total_minutes": sum(item.actual_minutes for item in sessions),
            "week_minutes": week_minutes, "session_count": len(sessions),
            "streak_days": len({local_date(item.started_at, user_id) for item in sessions
                                 if local_date(item.started_at, user_id) <= today}),
            "by_day": by_day, "recent": [{
                "id": item.id, "subject": item.subject_name or "Study session",
                "actual_minutes": item.actual_minutes, "started_at": iso(item.started_at),
            } for item in sessions[:5]],
        },
        "goal": {
            "id": goal.id, "title": goal.title, "target_minutes": goal.target_minutes,
            "current_minutes": sum(item.actual_minutes for item in sessions
                                   if local_date(item.started_at, user_id) >= goal.starts_on) if goal else 0,
        } if goal else None,
        "unread_notifications": unread,
        "has_quiz_data": bool(QuizAttempt.query.filter_by(user_id=user_id).first()),
    })


@api.get("/assignments")
def assignments_list():
    items = Assignment.query.filter_by(user_id=owner_id()).order_by(Assignment.due_at).all()
    return jsonify([assignment_json(item) for item in items])


@api.post("/assignments")
def assignment_create():
    data = body()
    user_id = owner_id()
    try:
        title = text(data, "title", "Assignment title", 180, True)
        description = text(data, "description", "Description", 4000)
        subject = subject_for(user_id, data.get("subject_id"))
        due_at = parse_datetime(data.get("due_at"), "Due date")
        priority = data.get("priority", "medium")
        if priority not in {"low", "medium", "high"}:
            raise ValueError("Choose low, medium or high priority.")
        minutes = int_value(data.get("estimated_minutes", 45), "Estimated time", 5, 720)
    except ValueError as error:
        return fail(str(error))
    item = Assignment(user_id=user_id, subject=subject, title=title, description=description,
                      due_at=due_at, priority=priority, estimated_minutes=minutes)
    db.session.add(item)
    db.session.flush()
    sync_linked_event(user_id, "assignment", item.id, item.title, item.subject_id,
                      item.due_at, item.estimated_minutes)
    db.session.add(Notification(user_id=user_id, title="Assignment added",
                                message=f"{item.title} is saved to your calendar.",
                                category="assignment"))
    db.session.commit()
    return jsonify(assignment_json(item)), 201


@api.patch("/assignments/<int:item_id>")
def assignment_update(item_id):
    item = Assignment.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Assignment not found.", 404)
    data = body()
    previous_status = item.status
    try:
        if "title" in data:
            item.title = text(data, "title", "Assignment title", 180, True)
        if "description" in data:
            item.description = text(data, "description", "Description", 4000)
        if "subject_id" in data:
            item.subject = subject_for(owner_id(), data["subject_id"])
        if "due_at" in data:
            item.due_at = parse_datetime(data["due_at"], "Due date")
        if "estimated_minutes" in data:
            item.estimated_minutes = int_value(data["estimated_minutes"], "Estimated time", 5, 720)
        if "priority" in data:
            if data["priority"] not in {"low", "medium", "high"}:
                raise ValueError("Choose low, medium or high priority.")
            item.priority = data["priority"]
        if "status" in data:
            if data["status"] not in {"todo", "in_progress", "done"}:
                raise ValueError("Choose a valid assignment status.")
            item.status = data["status"]
            item.completed_at = now_utc() if item.status == "done" else None
    except ValueError as error:
        db.session.rollback()
        return fail(str(error))
    sync_linked_event(owner_id(), "assignment", item.id, item.title, item.subject_id,
                      item.due_at, item.estimated_minutes)
    if previous_status != "done" and item.status == "done":
        db.session.add(Progress(user_id=owner_id(), event_type="assignment_completed",
                                title=item.title, details={"assignment_id": item.id}))
    db.session.commit()
    return jsonify(assignment_json(item))


@api.delete("/assignments/<int:item_id>")
def assignment_delete(item_id):
    item = Assignment.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Assignment not found.", 404)
    CalendarEvent.query.filter_by(user_id=owner_id(), source_type="assignment", source_id=item.id).delete()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@api.get("/exams")
def exams_list():
    return jsonify([exam_json(item) for item in Exam.query.filter_by(user_id=owner_id()).order_by(Exam.exam_at).all()])


@api.post("/exams")
def exam_create():
    data = body()
    try:
        title = text(data, "title", "Exam title", 180, True)
        subject = subject_for(owner_id(), data.get("subject_id"))
        exam_at = parse_datetime(data.get("exam_at"), "Exam date")
        location = text(data, "location", "Location", 140)
        notes = text(data, "notes", "Revision notes", 3000)
        raw_topics = data.get("topics", [])
        if not isinstance(raw_topics, list) or len(raw_topics) > 50:
            raise ValueError("Add no more than 50 exam topics.")
    except ValueError as error:
        return fail(str(error))
    item = Exam(user_id=owner_id(), subject=subject, title=title, exam_at=exam_at,
                location=location, notes=notes)
    db.session.add(item)
    db.session.flush()
    sync_linked_event(owner_id(), "exam", item.id, item.title, item.subject_id, item.exam_at, 60)
    for topic in raw_topics:
        clean = str(topic or "").strip()
        if clean:
            item.topics.append(ExamTopic(title=clean[:180]))
    db.session.add(Notification(user_id=owner_id(), title="Exam added",
                                message=f"{item.title} is now on your calendar.", category="exam"))
    db.session.commit()
    return jsonify(exam_json(item)), 201


@api.delete("/exams/<int:item_id>")
def exam_delete(item_id):
    item = Exam.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Exam not found.", 404)
    CalendarEvent.query.filter_by(user_id=owner_id(), source_type="exam", source_id=item.id).delete()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@api.patch("/exams/<int:item_id>")
def exam_update(item_id):
    item = Exam.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Exam not found.", 404)
    data = body()
    try:
        if "title" in data:
            item.title = text(data, "title", "Exam title", 180, True)
        if "exam_at" in data:
            item.exam_at = parse_datetime(data["exam_at"], "Exam date")
        if "subject_id" in data:
            item.subject = subject_for(owner_id(), data["subject_id"])
        if "location" in data:
            item.location = text(data, "location", "Location", 140)
        if "notes" in data:
            item.notes = text(data, "notes", "Revision notes", 3000)
        if "topics" in data:
            raw_topics = data["topics"]
            if not isinstance(raw_topics, list) or len(raw_topics) > 50:
                raise ValueError("Add no more than 50 exam topics.")
            item.topics.clear()
            for value in raw_topics:
                clean = str(value or "").strip()
                if clean:
                    item.topics.append(ExamTopic(title=clean[:180]))
    except ValueError as error:
        db.session.rollback()
        return fail(str(error))
    sync_linked_event(owner_id(), "exam", item.id, item.title, item.subject_id, item.exam_at, 60)
    db.session.commit()
    return jsonify(exam_json(item))


@api.get("/subjects")
def subjects_list():
    items = Subject.query.filter_by(user_id=owner_id()).order_by(Subject.name).all()
    result = []
    for item in items:
        study_minutes = db.session.query(func.coalesce(func.sum(StudySession.actual_minutes), 0)).filter_by(
            user_id=owner_id(), subject_id=item.id
        ).scalar()
        result.append({
            "id": item.id, "name": item.name, "category": item.category, "color": item.color,
            "difficulty": item.difficulty, "target_hours": item.target_hours,
            "study_minutes": int(study_minutes or 0),
        })
    return jsonify(result)


@api.post("/subjects")
def subject_create():
    data = body()
    try:
        name = text(data, "name", "Subject name", 120, True)
        category = text(data, "category", "Category", 80) or "Core"
        difficulty = int_value(data.get("difficulty", 3), "Difficulty", 1, 5)
        target_hours = float(data.get("target_hours", 0) or 0)
        if not 0 <= target_hours <= 500:
            raise ValueError("Target hours must be between 0 and 500.")
        color = data.get("color", "blue")
        if color not in {"blue", "cyan", "violet", "mint", "amber"}:
            raise ValueError("Choose a valid subject color.")
    except (ValueError, TypeError) as error:
        return fail(str(error))
    item = Subject(user_id=owner_id(), name=name, category=category,
                   difficulty=difficulty, target_hours=target_hours, color=color)
    db.session.add(item)
    db.session.commit()
    return jsonify({"id": item.id, "name": item.name, "category": item.category,
                    "difficulty": item.difficulty, "target_hours": item.target_hours,
                    "color": item.color, "study_minutes": 0}), 201


@api.delete("/subjects/<int:item_id>")
def subject_delete(item_id):
    item = Subject.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Subject not found.", 404)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@api.patch("/subjects/<int:item_id>")
def subject_update(item_id):
    item = Subject.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Subject not found.", 404)
    data = body()
    try:
        if "name" in data:
            item.name = text(data, "name", "Subject name", 120, True)
        if "category" in data:
            item.category = text(data, "category", "Category", 80) or "Core"
        if "difficulty" in data:
            item.difficulty = int_value(data["difficulty"], "Difficulty", 1, 5)
        if "target_hours" in data:
            item.target_hours = float(data["target_hours"])
            if not 0 <= item.target_hours <= 500:
                raise ValueError("Target hours must be between 0 and 500.")
    except (ValueError, TypeError) as error:
        db.session.rollback()
        return fail(str(error))
    db.session.commit()
    return jsonify({"id": item.id, "name": item.name, "category": item.category,
                    "difficulty": item.difficulty, "target_hours": item.target_hours})


@api.get("/notes")
def notes_list():
    items = Note.query.filter_by(user_id=owner_id()).order_by(Note.updated_at.desc()).all()
    return jsonify([note_json(item) for item in items])


@api.post("/notes")
def note_create():
    data = body()
    try:
        title = text(data, "title", "Note title", 180, True)
        content = text(data, "content", "Note content", 50000)
        subject = subject_for(owner_id(), data.get("subject_id"))
        tags = data.get("tags", [])
        if not isinstance(tags, list) or len(tags) > 20:
            raise ValueError("Add no more than 20 tags.")
        tags = [str(tag).strip()[:32] for tag in tags if str(tag).strip()]
    except ValueError as error:
        return fail(str(error))
    item = Note(user_id=owner_id(), subject=subject, title=title, content=content, tags=tags)
    db.session.add(item)
    db.session.commit()
    return jsonify(note_json(item)), 201


@api.patch("/notes/<int:item_id>")
def note_update(item_id):
    item = Note.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Note not found.", 404)
    data = body()
    try:
        if "title" in data:
            item.title = text(data, "title", "Note title", 180, True)
        if "content" in data:
            item.content = text(data, "content", "Note content", 50000)
        if "subject_id" in data:
            item.subject = subject_for(owner_id(), data["subject_id"])
        if "tags" in data:
            if not isinstance(data["tags"], list) or len(data["tags"]) > 20:
                raise ValueError("Add no more than 20 tags.")
            item.tags = [str(tag).strip()[:32] for tag in data["tags"] if str(tag).strip()]
    except ValueError as error:
        db.session.rollback()
        return fail(str(error))
    db.session.commit()
    return jsonify(note_json(item))


@api.delete("/notes/<int:item_id>")
def note_delete(item_id):
    item = Note.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Note not found.", 404)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@api.get("/calendar-events")
def calendar_list():
    user_id = owner_id()
    start = parse_datetime(request.args.get("start"), "Start date")
    end = parse_datetime(request.args.get("end"), "End date")
    if end <= start:
        return fail("Calendar end date must be after its start date.")
    items = CalendarEvent.query.filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.starts_at >= start,
        CalendarEvent.starts_at < end,
    ).order_by(CalendarEvent.starts_at).all()
    return jsonify([event_json(item) for item in items])


@api.post("/calendar-events")
def calendar_create():
    data = body()
    try:
        title = text(data, "title", "Event title", 180, True)
        kind = data.get("event_type", "study")
        if kind not in {"study", "personal", "assignment", "exam", "reminder"}:
            raise ValueError("Choose a valid calendar event type.")
        start = parse_datetime(data.get("starts_at"), "Start date")
        end = parse_datetime(data.get("ends_at"), "End date", required=False)
        if end and end <= start:
            raise ValueError("Event end time must be after its start time.")
        all_day = data.get("all_day", False)
        if not isinstance(all_day, bool):
            raise ValueError("Choose whether this event lasts all day.")
        subject = subject_for(owner_id(), data.get("subject_id"))
        details = text(data, "details", "Event details", 2000)
    except ValueError as error:
        return fail(str(error))
    item = CalendarEvent(user_id=owner_id(), subject=subject, title=title,
                         event_type=kind, starts_at=start, ends_at=end,
                         all_day=all_day, details=details)
    db.session.add(item)
    db.session.commit()
    return jsonify(event_json(item)), 201


@api.patch("/calendar-events/<int:item_id>")
def calendar_update(item_id):
    item = CalendarEvent.query.filter_by(id=item_id, user_id=owner_id(), source_type="calendar").first()
    if not item:
        return fail("Calendar event not found.", 404)
    data = body()
    try:
        if "title" in data:
            item.title = text(data, "title", "Event title", 180, True)
        if "event_type" in data:
            if data["event_type"] not in {"study", "personal", "reminder"}:
                raise ValueError("Choose a valid calendar event type.")
            item.event_type = data["event_type"]
        if "starts_at" in data:
            item.starts_at = parse_datetime(data["starts_at"], "Start date")
        if "ends_at" in data:
            item.ends_at = parse_datetime(data["ends_at"], "End date", required=False)
        if item.ends_at and item.ends_at <= item.starts_at:
            raise ValueError("Event end time must be after its start time.")
        if "all_day" in data:
            if not isinstance(data["all_day"], bool):
                raise ValueError("Choose whether this event lasts all day.")
            item.all_day = data["all_day"]
        if "details" in data:
            item.details = text(data, "details", "Event details", 2000)
        if "subject_id" in data:
            item.subject = subject_for(owner_id(), data["subject_id"])
    except ValueError as error:
        db.session.rollback()
        return fail(str(error))
    db.session.commit()
    return jsonify(event_json(item))


@api.delete("/calendar-events/<int:item_id>")
def calendar_delete(item_id):
    item = CalendarEvent.query.filter_by(id=item_id, user_id=owner_id(), source_type="calendar").first()
    if not item:
        return fail("Calendar event not found.", 404)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@api.get("/focus-sessions")
def focus_list():
    rows = FocusSession.query.filter_by(user_id=owner_id()).order_by(FocusSession.started_at.desc()).limit(100).all()
    return jsonify([{
        "id": item.id, "subject_id": item.subject_id, "planned_minutes": item.planned_minutes,
        "actual_minutes": item.actual_minutes, "status": item.status,
        "started_at": iso(item.started_at), "ended_at": iso(item.ended_at),
    } for item in rows])


@api.post("/focus-sessions")
def focus_create():
    data = body()
    try:
        planned = int_value(data.get("planned_minutes"), "Timer length", 1, 720)
        actual = int_value(data.get("actual_minutes", planned), "Time focused", 1, 720)
        status = data.get("status", "completed" if actual >= planned else "stopped")
        if status not in {"completed", "stopped"}:
            raise ValueError("Choose completed or stopped.")
        started = parse_datetime(data.get("started_at"), "Start time")
        ended = parse_datetime(data.get("ended_at"), "End time", required=False) or started + timedelta(minutes=actual)
        if ended <= started:
            raise ValueError("Timer end time must be after its start time.")
        subject = subject_for(owner_id(), data.get("subject_id"))
    except ValueError as error:
        return fail(str(error))
    item = FocusSession(user_id=owner_id(), subject_id=subject.id if subject else None,
                        planned_minutes=planned, actual_minutes=actual, status=status,
                        started_at=started, ended_at=ended)
    session_item = StudySession(
        user_id=owner_id(), subject_id=subject.id if subject else None,
        subject_name=subject.name if subject else "Independent study",
        planned_minutes=planned, actual_minutes=actual, started_at=started,
        completed=status == "completed", source="focus",
    )
    db.session.add_all([item, session_item])
    db.session.flush()
    calendar_item = CalendarEvent(
        user_id=owner_id(), subject_id=subject.id if subject else None,
        title=f"Focus session · {subject.name}" if subject else "Focus session",
        event_type="study", starts_at=started, ends_at=ended,
        details=f"{actual} minutes saved from your focus timer.",
        source_type="focus_session", source_id=item.id,
    )
    db.session.add(calendar_item)
    db.session.add(Progress(user_id=owner_id(), event_type="focus_session_saved",
                            title="Focus session saved", details={"minutes": actual}))
    db.session.commit()
    return jsonify({
        "id": item.id, "planned_minutes": item.planned_minutes, "actual_minutes": item.actual_minutes,
        "status": item.status, "started_at": iso(item.started_at), "ended_at": iso(item.ended_at),
    }), 201


@api.post("/study-sessions")
def manual_session_create():
    data = body()
    try:
        minutes = int_value(data.get("minutes"), "Study time", 1, 720)
        subject = subject_for(owner_id(), data.get("subject_id"))
        started = parse_datetime(data.get("started_at") or now_utc().isoformat(), "Start time")
    except ValueError as error:
        return fail(str(error))
    item = StudySession(
        user_id=owner_id(), subject_id=subject.id if subject else None,
        subject_name=subject.name if subject else "Independent study",
        planned_minutes=minutes, actual_minutes=minutes, started_at=started,
        completed=True, source="manual",
    )
    db.session.add(item)
    db.session.flush()
    db.session.add(CalendarEvent(
        user_id=owner_id(), subject_id=subject.id if subject else None,
        title=f"Study session · {subject.name}" if subject else "Study session",
        event_type="study", starts_at=started, ends_at=started + timedelta(minutes=minutes),
        details=f"{minutes} minutes of study time entered manually.",
        source_type="study_session", source_id=item.id,
    ))
    db.session.add(Progress(user_id=owner_id(), event_type="study_session_saved",
                            title="Study session saved", details={"minutes": minutes}))
    db.session.commit()
    return jsonify({
        "id": item.id, "minutes": item.actual_minutes, "subject": item.subject_name,
        "started_at": iso(item.started_at),
    }), 201


@api.get("/goals")
def goals_list():
    user_id = owner_id()
    rows = Goal.query.filter_by(user_id=user_id).order_by(Goal.ends_on.desc()).all()
    sessions = StudySession.query.filter_by(user_id=user_id).all()
    output = []
    for item in rows:
        minutes = sum(
            study.actual_minutes for study in sessions
            if item.starts_on <= local_date(study.started_at, user_id) <= item.ends_on
        )
        output.append({
            "id": item.id, "title": item.title, "target_minutes": item.target_minutes,
            "period": item.period, "starts_on": item.starts_on.isoformat(),
            "ends_on": item.ends_on.isoformat(), "current_minutes": minutes,
            "completed": item.completed or minutes >= item.target_minutes,
        })
    return jsonify(output)


@api.post("/goals")
def goal_create():
    data = body()
    try:
        title = text(data, "title", "Goal title", 180, True)
        target = int_value(data.get("target_minutes"), "Goal duration", 15, 20000)
        period = data.get("period", "week")
        if period not in {"day", "week", "month"}:
            raise ValueError("Choose day, week or month.")
        starts = date.fromisoformat(str(data.get("starts_on") or user_today(owner_id()).isoformat()))
        ends = date.fromisoformat(str(data.get("ends_on") or (starts + timedelta(days=6)).isoformat()))
        if ends < starts or (ends - starts).days > 366:
            raise ValueError("Choose a valid goal date range of up to one year.")
    except (ValueError, TypeError) as error:
        return fail(str(error))
    item = Goal(user_id=owner_id(), title=title, target_minutes=target, period=period,
                starts_on=starts, ends_on=ends)
    db.session.add(item)
    db.session.commit()
    return jsonify({"id": item.id, "title": title, "target_minutes": target,
                    "period": period, "starts_on": starts.isoformat(), "ends_on": ends.isoformat(),
                    "current_minutes": 0, "completed": False}), 201


@api.patch("/goals/<int:item_id>")
def goal_update(item_id):
    item = Goal.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Goal not found.", 404)
    data = body()
    try:
        if "title" in data:
            item.title = text(data, "title", "Goal title", 180, True)
        if "target_minutes" in data:
            item.target_minutes = int_value(data["target_minutes"], "Goal duration", 15, 20000)
        if "completed" in data:
            if not isinstance(data["completed"], bool):
                raise ValueError("Goal completion must be true or false.")
            item.completed = data["completed"]
    except ValueError as error:
        db.session.rollback()
        return fail(str(error))
    db.session.commit()
    return jsonify({"id": item.id, "title": item.title, "target_minutes": item.target_minutes,
                    "period": item.period, "starts_on": item.starts_on.isoformat(),
                    "ends_on": item.ends_on.isoformat(), "completed": item.completed})


@api.delete("/goals/<int:item_id>")
def goal_delete(item_id):
    item = Goal.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Goal not found.", 404)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@api.get("/roadmaps")
def roadmaps_list():
    rows = Roadmap.query.filter_by(user_id=owner_id()).order_by(Roadmap.created_at.desc()).all()
    return jsonify([roadmap_json(item) for item in rows])


@api.post("/roadmaps")
def roadmap_create():
    data = body()
    try:
        title = text(data, "title", "Roadmap title", 180, True)
        description = text(data, "description", "Description", 4000)
        subject = subject_for(owner_id(), data.get("subject_id"))
        tasks = data.get("tasks")
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= 100:
            raise ValueError("Add between 1 and 100 roadmap steps.")
        prepared = []
        for position, raw in enumerate(tasks):
            task = raw if isinstance(raw, dict) else {"title": raw}
            task_title = str(task.get("title", "") or "").strip()
            if not task_title or len(task_title) > 180:
                raise ValueError(f"Roadmap step {position + 1} needs a title under 180 characters.")
            minutes = int_value(task.get("estimated_minutes", 30), "Step estimate", 5, 720)
            prepared.append(RoadmapTask(
                user_id=owner_id(), title=task_title,
                description=str(task.get("description", "") or "").strip()[:2000],
                position=position, estimated_minutes=minutes,
            ))
    except ValueError as error:
        return fail(str(error))
    item = Roadmap(user_id=owner_id(), subject=subject, title=title,
                   description=description, tasks=prepared)
    db.session.add(item)
    db.session.flush()
    db.session.add(Progress(user_id=owner_id(), roadmap_id=item.id,
                            event_type="roadmap_created", title=item.title,
                            details={"step_count": len(prepared)}))
    db.session.commit()
    return jsonify(roadmap_json(item)), 201


@api.patch("/roadmaps/<int:roadmap_id>")
def roadmap_update(roadmap_id):
    item = Roadmap.query.filter_by(id=roadmap_id, user_id=owner_id()).first()
    if not item:
        return fail("Roadmap not found.", 404)
    data = body()
    try:
        if "title" in data:
            item.title = text(data, "title", "Roadmap title", 180, True)
        if "description" in data:
            item.description = text(data, "description", "Description", 4000)
        if "subject_id" in data:
            item.subject = subject_for(owner_id(), data["subject_id"])
    except ValueError as error:
        db.session.rollback()
        return fail(str(error))
    db.session.commit()
    return jsonify(roadmap_json(item))


@api.delete("/roadmaps/<int:roadmap_id>")
def roadmap_delete(roadmap_id):
    item = Roadmap.query.filter_by(id=roadmap_id, user_id=owner_id()).first()
    if not item:
        return fail("Roadmap not found.", 404)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@api.post("/roadmaps/<int:roadmap_id>/tasks")
def roadmap_task_create(roadmap_id):
    item = Roadmap.query.filter_by(id=roadmap_id, user_id=owner_id()).first()
    if not item:
        return fail("Roadmap not found.", 404)
    data = body()
    try:
        title = text(data, "title", "Step title", 180, True)
        description = text(data, "description", "Step description", 2000)
        minutes = int_value(data.get("estimated_minutes", 30), "Step estimate", 5, 720)
    except ValueError as error:
        return fail(str(error))
    task = RoadmapTask(user_id=owner_id(), roadmap=item, title=title,
                       description=description, estimated_minutes=minutes,
                       position=len(item.tasks))
    item.status = "active"
    db.session.add(task)
    db.session.commit()
    return jsonify(roadmap_json(item)), 201


@api.patch("/roadmap-tasks/<int:task_id>")
def roadmap_task_update(task_id):
    task = RoadmapTask.query.filter_by(id=task_id, user_id=owner_id()).first()
    if not task or task.roadmap.user_id != owner_id():
        return fail("Roadmap step not found.", 404)
    data = body()
    previous_status = task.status
    try:
        if "title" in data:
            task.title = text(data, "title", "Step title", 180, True)
        if "description" in data:
            task.description = text(data, "description", "Step description", 2000)
        if "estimated_minutes" in data:
            task.estimated_minutes = int_value(data["estimated_minutes"], "Step estimate", 5, 720)
        if "status" in data:
            if data["status"] not in {"todo", "done"}:
                raise ValueError("Choose pending or complete for this step.")
            task.status = data["status"]
            task.completed_at = now_utc() if task.status == "done" else None
    except ValueError as error:
        db.session.rollback()
        return fail(str(error))
    roadmap = task.roadmap
    all_done = bool(roadmap.tasks) and all(row.status == "done" for row in roadmap.tasks)
    roadmap.status = "completed" if all_done else "active"
    if previous_status != "done" and task.status == "done":
        db.session.add(Progress(user_id=owner_id(), roadmap_id=roadmap.id,
                                event_type="roadmap_step_completed", title=task.title,
                                details={"roadmap_id": roadmap.id, "task_id": task.id}))
        if all_done:
            db.session.add(Progress(user_id=owner_id(), roadmap_id=roadmap.id,
                                    event_type="roadmap_completed", title=roadmap.title,
                                    details={"task_count": len(roadmap.tasks)}))
    db.session.commit()
    return jsonify(roadmap_json(roadmap))


@api.delete("/roadmap-tasks/<int:task_id>")
def roadmap_task_delete(task_id):
    task = RoadmapTask.query.filter_by(id=task_id, user_id=owner_id()).first()
    if not task or task.roadmap.user_id != owner_id():
        return fail("Roadmap step not found.", 404)
    roadmap = task.roadmap
    roadmap.tasks.remove(task)
    db.session.delete(task)
    db.session.flush()
    for position, row in enumerate(roadmap.tasks):
        row.position = position
    roadmap.status = "completed" if roadmap.tasks and all(row.status == "done" for row in roadmap.tasks) else "active"
    db.session.commit()
    return jsonify(roadmap_json(roadmap))


@api.get("/progress")
def progress_list():
    rows = Progress.query.filter_by(user_id=owner_id()).order_by(Progress.created_at.desc()).limit(100).all()
    return jsonify([{
        "id": item.id, "roadmap_id": item.roadmap_id, "event_type": item.event_type,
        "title": item.title, "details": item.details or {}, "created_at": iso(item.created_at),
    } for item in rows])


@api.get("/notifications")
def notifications_list():
    items = Notification.query.filter_by(user_id=owner_id()).order_by(Notification.created_at.desc()).limit(100).all()
    return jsonify([{
        "id": item.id, "title": item.title, "message": item.message, "category": item.category,
        "read": item.read_at is not None, "created_at": iso(item.created_at),
    } for item in items])


@api.patch("/notifications/<int:item_id>")
def notification_read(item_id):
    item = Notification.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Notification not found.", 404)
    item.read_at = now_utc()
    db.session.commit()
    return jsonify({"ok": True})


@api.post("/notifications/read-all")
def notifications_read_all():
    Notification.query.filter_by(user_id=owner_id(), read_at=None).update({"read_at": now_utc()})
    db.session.commit()
    return jsonify({"ok": True})


@api.get("/preferences")
def preferences_get():
    profile = db.session.get(User, owner_id()).profile
    return jsonify((profile.preferences or {}) if profile else {})


@api.get("/profile")
def profile_get():
    user = db.session.get(User, owner_id())
    profile = user.profile
    return jsonify({
        "email": user.email,
        "created_at": iso(user.created_at),
        "full_name": profile.full_name if profile else "Student",
        "course_name": profile.course_name if profile else "",
        "profile_image_url": profile.profile_image_url if profile else "",
    })


@api.patch("/profile")
def profile_update():
    user = db.session.get(User, owner_id())
    data = body()
    try:
        name = text(data, "full_name", "Name", 100, True)
        if len(name) < 2:
            raise ValueError("Name must contain at least two characters.")
        course = text(data, "course_name", "Course name", 140)
        image = text(data, "profile_image_url", "Profile image URL", 500)
        if image and not image.startswith(("https://", "http://")):
            raise ValueError("Use a valid profile image URL.")
    except ValueError as error:
        return fail(str(error))
    if not user.profile:
        user.profile = StudentProfile(full_name=name)
    user.profile.full_name = name
    user.profile.course_name = course
    user.profile.profile_image_url = image
    session["display_name"] = name
    db.session.commit()
    return jsonify({"full_name": name, "course_name": course, "profile_image_url": image})


@api.patch("/preferences")
def preferences_update():
    data = body()
    if not isinstance(data.get("preferences"), dict):
        return fail("Preferences should be an object.")
    user = db.session.get(User, owner_id())
    if not user.profile:
        return fail("Student profile not found.", 404)
    current = user.profile.preferences or {}
    allowed = {"theme_mode", "reminders_enabled", "weekly_goal_minutes", "focus_sound"}
    updates = {key: value for key, value in data["preferences"].items() if key in allowed}
    if "theme_mode" in updates and updates["theme_mode"] not in {"light", "dark"}:
        return fail("Choose light or dark mode.")
    if "reminders_enabled" in updates and not isinstance(updates["reminders_enabled"], bool):
        return fail("Reminder preference must be true or false.")
    if "weekly_goal_minutes" in updates:
        try:
            updates["weekly_goal_minutes"] = int_value(updates["weekly_goal_minutes"], "Weekly goal", 60, 10000)
        except ValueError as error:
            return fail(str(error))
    user.profile.preferences = {**current, **updates}
    if "theme_mode" in updates:
        session["theme_mode"] = updates["theme_mode"]
    db.session.commit()
    return jsonify(user.profile.preferences)


@api.get("/analytics")
def analytics():
    user_id = owner_id()
    sessions = StudySession.query.filter_by(user_id=user_id).all()
    today = user_today(user_id)
    daily = []
    for offset in range(29, -1, -1):
        day = today - timedelta(days=offset)
        matching = [item for item in sessions if local_date(item.started_at, user_id) == day]
        daily.append({
            "date": day.isoformat(), "minutes": sum(item.actual_minutes for item in matching),
            "sessions": len(matching),
        })
    assignments = Assignment.query.filter_by(user_id=user_id).all()
    total_minutes = sum(item.actual_minutes for item in sessions)
    recent_minutes = sum(day["minutes"] for day in daily)
    subjects = Subject.query.filter_by(user_id=user_id).all()
    # Return EVERY saved course, including new courses with zero study sessions.
    # Before this fix the `if minutes` guard hid all newly created courses.
    by_subject = []
    for subject in subjects:
        minutes = sum(item.actual_minutes for item in sessions if item.subject_id == subject.id)
        course_assignments = [item for item in assignments if item.subject_id == subject.id]
        completed = sum(item.status == "done" for item in course_assignments)
        target_minutes = max(0, round((subject.target_hours or 0) * 60))
        study_percent = min(100, round(minutes * 100 / target_minutes)) if target_minutes else 0
        assignment_percent = round(completed * 100 / len(course_assignments)) if course_assignments else 0
        if target_minutes and course_assignments:
            # Both tracked activities contribute equally and transparently.
            progress_percent = round((study_percent + assignment_percent) / 2)
            progress_basis = "combined"
        elif target_minutes:
            progress_percent = study_percent
            progress_basis = "study_target"
        elif course_assignments:
            progress_percent = assignment_percent
            progress_basis = "assignments"
        else:
            progress_percent = 0
            progress_basis = "none"
        by_subject.append({
            "id": subject.id,
            "name": subject.name,
            "minutes": minutes,
            "color": subject.color,
            "target_minutes": target_minutes,
            "assignments_total": len(course_assignments),
            "assignments_completed": completed,
            "progress_percent": progress_percent,
            "progress_basis": progress_basis,
            "study_percent": study_percent,
            "assignment_percent": assignment_percent,
        })
    snapshot = AnalyticsSnapshot.query.filter_by(
        user_id=user_id, metric_key="study_minutes_30d",
        period_start=today - timedelta(days=29), period_end=today,
    ).first()
    if snapshot is None:
        snapshot = AnalyticsSnapshot(
            user_id=user_id, metric_key="study_minutes_30d",
            period_start=today - timedelta(days=29), period_end=today,
        )
        db.session.add(snapshot)
    snapshot.metric_value = recent_minutes
    snapshot.dimensions = {
        "session_count_30d": sum(item["sessions"] for item in daily),
        "completed_assignments": sum(item.status == "done" for item in assignments),
        "total_assignments": len(assignments),
    }
    db.session.flush()
    db.session.commit()
    return jsonify({
        "daily": daily, "total_study_minutes": total_minutes,
        "session_count": len(sessions), "study_minutes_30d": recent_minutes,
        "snapshot_at": iso(snapshot.captured_at),
        "assignments": {
            "total": len(assignments),
            "completed": sum(item.status == "done" for item in assignments),
        },
        "by_subject": by_subject,
    })


@api.post("/timetable/generate")
def timetable_generate():
    user_id = owner_id()
    data = body()
    try:
        available_minutes = int_value(data.get("available_minutes", 180), "Available study time", 15, 720)
        day = date.fromisoformat(str(data.get("date") or user_today(user_id).isoformat()))
        start_hour = int_value(data.get("start_hour", 9), "Start hour", 0, 23)
        end_hour = int_value(data.get("end_hour", 21), "End hour", 1, 24)
        if end_hour <= start_hour:
            raise ValueError("End time must be after start time.")
        available_minutes = min(available_minutes, (end_hour - start_hour) * 60)
    except ValueError as error:
        return fail(str(error))
    pending = Assignment.query.filter(
        Assignment.user_id == user_id, Assignment.status != "done"
    ).order_by(Assignment.due_at, Assignment.priority.desc()).all()
    exams = Exam.query.filter(Exam.user_id == user_id, Exam.exam_at >= now_utc()).order_by(Exam.exam_at).all()
    candidates = []
    seen = set()
    for item in pending:
        if item.id not in seen:
            candidates.append({
                "title": item.title, "subject_id": item.subject_id,
                "minutes": min(item.estimated_minutes, 120), "kind": "assignment",
            })
            seen.add(item.id)
    for item in exams:
        key = -item.id
        if key not in seen and item.exam_at.date() <= day + timedelta(days=10):
            candidates.append({
                "title": f"Review for {item.title}", "subject_id": item.subject_id,
                "minutes": 40, "kind": "revision",
            })
            seen.add(key)
    slots = []
    cursor = datetime.combine(day, time(start_hour), tzinfo=timezone.utc)
    available_end = datetime.combine(day, time(end_hour % 24), tzinfo=timezone.utc)
    remaining = available_minutes
    for item in candidates:
        if remaining <= 0 or cursor >= available_end:
            break
        minutes = min(item["minutes"], remaining, int((available_end - cursor).total_seconds() // 60))
        if minutes < 10:
            break
        slots.append({
            "title": item["title"], "subject_id": item["subject_id"], "event_type": item["kind"],
            "starts_at": cursor.isoformat(), "ends_at": (cursor + timedelta(minutes=minutes)).isoformat(),
            "minutes": minutes,
        })
        cursor += timedelta(minutes=minutes + 10)
        remaining -= minutes + 10
    return jsonify({"date": day.isoformat(), "source_count": len(pending) + len(exams),
                    "slots": slots, "saved": False})


@api.get("/revision-plans")
def revisions_list():
    rows = RevisionPlan.query.filter_by(user_id=owner_id()).order_by(RevisionPlan.due_at).all()
    return jsonify([{
        "id": item.id, "title": item.title, "subject_id": item.subject_id,
        "subject": item.subject.name if item.subject else "", "due_at": iso(item.due_at),
        "status": item.status,
    } for item in rows])


@api.post("/revision-plans")
def revision_create():
    data = body()
    try:
        title = text(data, "title", "Revision title", 180, True)
        due = parse_datetime(data.get("due_at"), "Revision date")
        subject = subject_for(owner_id(), data.get("subject_id"))
    except ValueError as error:
        return fail(str(error))
    item = RevisionPlan(user_id=owner_id(), subject=subject, title=title, due_at=due)
    db.session.add(item)
    db.session.flush()
    sync_linked_event(owner_id(), "revision", item.id, item.title, item.subject_id, due, 45)
    db.session.commit()
    return jsonify({"id": item.id, "title": item.title, "subject_id": item.subject_id,
                    "due_at": iso(item.due_at), "status": item.status}), 201


@api.patch("/revision-plans/<int:item_id>")
def revision_update(item_id):
    item = RevisionPlan.query.filter_by(id=item_id, user_id=owner_id()).first()
    if not item:
        return fail("Revision item not found.", 404)
    data = body()
    if "status" in data:
        if data["status"] not in {"scheduled", "done"}:
            return fail("Choose scheduled or done.")
        item.status = data["status"]
    db.session.commit()
    return jsonify({"ok": True, "status": item.status})


@api.get("/quizzes")
def quizzes_list():
    quizzes = Quiz.query.filter_by(user_id=owner_id()).order_by(Quiz.created_at.desc()).all()
    return jsonify([{
        "id": item.id, "title": item.title, "subject_id": item.subject_id,
        "question_count": len(item.questions), "attempt_count": len(item.attempts),
        "latest_score": item.attempts[-1].score if item.attempts else None,
        "latest_total": item.attempts[-1].total_questions if item.attempts else None,
    } for item in quizzes])


@api.post("/quizzes")
def quiz_create():
    data = body()
    try:
        title = text(data, "title", "Quiz title", 180, True)
        subject = subject_for(owner_id(), data.get("subject_id"))
        if subject is None:
            raise ValueError("Choose a course to link this quiz.")
        questions = data.get("questions")
        if not isinstance(questions, list) or not 1 <= len(questions) <= 50:
            raise ValueError("Add between 1 and 50 questions.")
        prepared = []
        for index, question in enumerate(questions):
            if not isinstance(question, dict):
                raise ValueError(f"Question {index + 1} is invalid.")
            prompt = str(question.get("prompt", "")).strip()
            options = question.get("options")
            if not prompt or len(prompt) > 1500 or not isinstance(options, list) or not 2 <= len(options) <= 8:
                raise ValueError(f"Question {index + 1} needs a prompt and 2–8 options.")
            options = [str(option).strip()[:300] for option in options]
            if any(not option for option in options) or len(set(options)) != len(options):
                raise ValueError(f"Question {index + 1} needs distinct non-empty options.")
            answer = str(question.get("correct_answer", "")).strip()
            if answer not in options:
                raise ValueError(f"Question {index + 1} needs one correct option.")
            prepared.append(QuizQuestion(prompt=prompt, options=options, correct_answer=answer))
    except ValueError as error:
        return fail(str(error))
    item = Quiz(user_id=owner_id(), subject_id=subject.id if subject else None,
                title=title, questions=prepared)
    db.session.add(item)
    db.session.commit()
    return jsonify({"id": item.id, "title": item.title, "question_count": len(item.questions)}), 201


@api.get("/quizzes/<int:quiz_id>")
def quiz_get(quiz_id):
    item = Quiz.query.filter_by(id=quiz_id, user_id=owner_id()).first()
    if not item:
        return fail("Quiz not found.", 404)
    return jsonify({
        "id": item.id, "title": item.title,
        "questions": [{"id": question.id, "prompt": question.prompt, "options": question.options}
                      for question in item.questions],
    })


@api.delete("/quizzes/<int:quiz_id>")
def quiz_delete(quiz_id):
    item = Quiz.query.filter_by(id=quiz_id, user_id=owner_id()).first()
    if not item:
        return fail("Quiz not found.", 404)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@api.post("/quizzes/<int:quiz_id>/attempts")
def quiz_attempt(quiz_id):
    item = Quiz.query.filter_by(id=quiz_id, user_id=owner_id()).first()
    if not item:
        return fail("Quiz not found.", 404)
    answers = body().get("answers")
    if not isinstance(answers, dict) or len(answers) != len(item.questions):
        return fail("Answer each quiz question before submitting.")
    score = 0
    clean_answers = {}
    for question in item.questions:
        answer = str(answers.get(str(question.id), "")).strip()
        if answer not in question.options:
            return fail("An answer doesn't match that question's options.")
        clean_answers[str(question.id)] = answer
        score += answer == question.correct_answer
    attempt = QuizAttempt(user_id=owner_id(), quiz_id=item.id, score=score,
                          total_questions=len(item.questions), answers=clean_answers)
    db.session.add(attempt)
    db.session.add(Progress(user_id=owner_id(), event_type="quiz_attempt_saved",
                            title=item.title, details={"score": score, "total": len(item.questions)}))
    db.session.commit()
    return jsonify({"score": score, "total_questions": len(item.questions)}), 201


@api.post("/usage-events")
def usage_event():
    data = body()
    name = str(data.get("event_name", "")).strip()[:80]
    if not name:
        return fail("Event name is required.")
    duration = data.get("duration_ms")
    try:
        duration = int_value(duration, "Interaction duration", 0, 86400000) if duration is not None else None
    except ValueError as error:
        return fail(str(error))
    details = data.get("detail", {})
    if not isinstance(details, dict):
        return fail("Event details should be an object.")
    db.session.add(UsageEvent(user_id=owner_id(), event_name=name,
                              page=str(data.get("page", ""))[:50], duration_ms=duration,
                              detail=details))
    db.session.commit()
    return jsonify({"ok": True}), 201


# Contact submissions use the existing SQLite/PostgreSQL database. Email delivery is
# optional: never claim delivery unless a configured SMTP server accepted the mail.
@api.post("/contact")
def contact_create():
    data = body()
    try:
        name = text(data, "name", "Your name", 100, True)
        email = text(data, "email", "Your email", 254, True).lower()
        message = text(data, "message", "Message", 2000, True)
    except ValueError as error:
        return fail(str(error))
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return fail("Enter a valid email so we can reply.")
    if len(message) < 5:
        return fail("Please write a message of at least 5 characters.")
    # An invisible honeypot reduces accidental automated submissions.
    if data.get("website"):
        return jsonify({"saved": True, "email_sent": False}), 201
    item = ContactMessage(name=name, email=email, message=message)
    db.session.add(item)
    db.session.commit()

    recipient = os.environ.get("STUDYX_CONTACT_ADMIN_EMAIL", "").strip()
    host = os.environ.get("STUDYX_SMTP_HOST", "").strip()
    sender = os.environ.get("STUDYX_SMTP_FROM", "").strip()
    smtp_user = os.environ.get("STUDYX_SMTP_USER", "").strip()
    smtp_password = os.environ.get("STUDYX_SMTP_PASSWORD", "")
    if all((recipient, host, sender, smtp_user, smtp_password)):
        try:
            mail = EmailMessage()
            mail["From"] = sender
            mail["To"] = recipient
            mail["Reply-To"] = email
            mail["Subject"] = f"StudyX contact #{item.id}"
            mail.set_content(f"From: {name}\nEmail: {email}\n\n{message}")
            port = int(os.environ.get("STUDYX_SMTP_PORT", "587"))
            if port == 465:
                with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=12) as client:
                    client.login(smtp_user, smtp_password)
                    client.send_message(mail)
            else:
                with smtplib.SMTP(host, port, timeout=12) as client:
                    client.starttls(context=ssl.create_default_context())
                    client.login(smtp_user, smtp_password)
                    client.send_message(mail)
            item.email_sent = True
            db.session.commit()
        except (OSError, smtplib.SMTPException, ValueError) as error:
            current_app.logger.warning("Contact email delivery failed (message %s): %s", item.id, type(error).__name__)
            db.session.rollback()
    return jsonify({"saved": True, "email_sent": item.email_sent,
                    "message": ("Message delivered to the project email." if item.email_sent else
                                "Message saved to the project database. Email delivery is not configured or is pending.")}), 201


@api.get("/contact-messages")
def contact_messages_list():
    recipient = os.environ.get("STUDYX_CONTACT_ADMIN_EMAIL", "").strip().lower()
    user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    if not recipient or not user or user.email.lower() != recipient:
        return fail("Only the configured project admin can view contact messages.", 403)
    rows = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(100).all()
    return jsonify([{"id": row.id, "name": row.name, "email": row.email,
                     "message": row.message, "email_sent": row.email_sent,
                     "created_at": iso(row.created_at)} for row in rows])
