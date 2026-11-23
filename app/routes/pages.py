import os
from flask import Blueprint, abort, current_app, render_template, send_from_directory, session
from ..extensions import db
from ..models import User


pages = Blueprint("pages", __name__)

PUBLIC = {
    "features": ("Features", "public_features"),
    "how-it-works": ("How it works", "public_how"),
    "about": ("About", "public_about"),
    "contact": ("Contact", "public_contact"),
}
WORKSPACE = {
    "dashboard": ("Overview", "dashboard"),
    "calendar": ("Calendar", "calendar"),
    "assignments": ("Assignments", "assignments"),
    "exams": ("Exams", "exams"),
    "subjects": ("Courses", "subjects"),
    "quizzes": ("Quizzes", "quizzes"),
    "timetable": ("Smart timetable", "timetable"),
    "focus": ("Focus timer", "focus"),
    "progress": ("Progress", "progress"),
}


@pages.get("/")
def public_landing():
    return render_template("landing.html")


@pages.get("/sw.js")
def service_worker():
    response = send_from_directory(current_app.static_folder, "sw.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@pages.get("/features")
def public_features():
    return render_template("public.html", title="Tools that make studying feel lighter",
                           label="THE STUDYX TOOLKIT", active="features", public_kind="features")


@pages.get("/how-it-works")
def public_how():
    return render_template("public.html", title="A clear path from plan to progress",
                           label="A SIMPLE RHYTHM", active="how-it-works", public_kind="how")


@pages.get("/about")
def public_about():
    return render_template("public.html", title="Built for the way students actually learn",
                           label="OUR APPROACH", active="about", public_kind="about")


@pages.get("/contact")
def public_contact():
    return render_template("public.html", title="Tell us what would help",
                           label="GET IN TOUCH", active="contact", public_kind="contact")


def render_workspace(page_key):
    if page_key not in WORKSPACE:
        abort(404)
    title, _slug = WORKSPACE[page_key]
    return render_template("app_shell.html", page=page_key, page_title=title,
                           workspace_pages=WORKSPACE)


for slug in WORKSPACE:
    def view(current_slug=slug):
        return render_workspace(current_slug)
    pages.add_url_rule(f"/{slug}", endpoint=f"workspace_{slug}", view_func=view)


@pages.get("/contact-inbox")
def contact_inbox():
    admin = os.environ.get("STUDYX_CONTACT_ADMIN_EMAIL", "").strip().lower()
    user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    if not admin or not user or user.email.lower() != admin:
        abort(403)
    return render_template("app_shell.html", page="contact_inbox", page_title="Contact inbox",
                           workspace_pages=WORKSPACE)
