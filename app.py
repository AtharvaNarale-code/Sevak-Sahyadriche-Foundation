#pythonpython -m pip install Flask-Login 
"""
Sevak Sahyadriche Foundation - Website Backend
Flask application powering the public site (home, about, treks/events,
gallery, contact) and a protected admin panel for managing upcoming
treks and events.
"""
import os
from dotenv import load_dotenv

load_dotenv()
import re
from glob import glob
from pathlib import Path
from datetime import datetime, date

from flask import (
    Flask, render_template, redirect, url_for, request,
    flash, abort, session
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
IS_VERCEL = os.environ.get("VERCEL") == "1" or os.environ.get("VERCEL") == "true"

# Vercel deployments have a read-only filesystem. Only /tmp is writable there.
# Locally, keep using the normal project folders/database.
UPLOAD_FOLDER = (
    os.path.join("/tmp", "sevak", "uploads")
    if IS_VERCEL
    else os.path.join(BASE_DIR, "static", "img", "treks")
)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not configured. Set it in your environment before starting the app.")
app.config["SECRET_KEY"] = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("SESSION_COOKIE_SECURE", "1" if IS_VERCEL else "0") == "1"
)

# Keep SQLite for now. On Vercel it must live in /tmp because the deployment
# filesystem is read-only. This is intentionally temporary; persistent DB
# storage can be added later without changing the public site routes.
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:////tmp/sevak.db"
    if IS_VERCEL
    else "sqlite:///" + os.path.join(BASE_DIR, "sevak.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB uploads

# Production secrets MUST be supplied through environment variables.
# Never commit real SECRET_KEY / ADMIN_PASSWORD_HASH values to GitHub.

if IS_VERCEL:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "admin_login"
login_manager.login_message = "Please log in to access the admin panel."
login_manager.login_message_category = "warning"


@login_manager.unauthorized_handler
def unauthorized():
    flash("Please log in to access the admin panel.", "warning")
    return redirect(url_for("admin_login", next=request.path))


# ---------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------

class AdminSessionUser(UserMixin):
    """Authenticated admin identity.

    The admin username and password hash are supplied through environment
    variables. No admin password is stored in this source code or database.
    """

    id = "admin"

    @property
    def username(self):
        return ADMIN_USERNAME


ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")

if not ADMIN_PASSWORD_HASH:
    raise RuntimeError(
        "ADMIN_PASSWORD_HASH is not configured. "
        "Set it as an environment variable before starting the app."
    )

ADMIN_USER = AdminSessionUser()


class Trek(db.Model):
    """Represents an upcoming/past trek OR cultural event run by the
    foundation. `category` distinguishes 'Trek' vs 'Event'."""
    __tablename__ = "treks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(30), nullable=False, default="Trek")  # Trek / Cultural Event / Fort Visit
    location = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(30), default="Moderate")  # Easy / Moderate / Difficult
    event_date = db.Column(db.Date, nullable=False)
    duration = db.Column(db.String(50), default="1 Day")
    price = db.Column(db.String(50), default="Free")
    total_slots = db.Column(db.Integer, default=30)
    slots_filled = db.Column(db.Integer, default=0)
    image_filename = db.Column(db.String(255), nullable=True)
    contact_person = db.Column(db.String(100), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def slots_left(self):
        return max((self.total_slots or 0) - (self.slots_filled or 0), 0)

    @property
    def is_upcoming(self):
        return self.event_date >= date.today()

    @property
    def image_url(self):
        if self.image_filename:
            return url_for("static", filename=f"img/treks/{self.image_filename}")
        return url_for("static", filename="img/placeholder.svg")


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)


# On Vercel, initialize the temporary SQLite database for the current
# serverless instance so public pages and the admin panel can load.
if IS_VERCEL:
    with app.app_context():
        db.create_all()


@login_manager.user_loader
def load_user(user_id):
    if user_id == ADMIN_USER.id:
        return ADMIN_USER
    return None


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.context_processor
def inject_globals():
    return {"current_year": datetime.utcnow().year, "org_name": "Sevak Sahyadriche"}


# ---------------------------------------------------------------------
# PUBLIC ROUTES
# ---------------------------------------------------------------------

@app.route("/")
def home():
    published_query = Trek.query.filter(Trek.is_published.is_(True))
    upcoming = (
        published_query.filter(Trek.event_date >= date.today())
        .order_by(Trek.event_date.asc())
        .limit(3)
        .all()
    )
    gallery_items = (
        published_query.filter(Trek.event_date < date.today())
        .order_by(Trek.event_date.desc())
        .limit(6)
        .all()
    )
    stats = {
        "published": published_query.count(),
        "upcoming": published_query.filter(Trek.event_date >= date.today()).count(),
        "completed": published_query.filter(Trek.event_date < date.today()).count(),
        "cultural": published_query.filter(Trek.category.ilike("%cultural%")).count(),
    }
    return render_template("index.html", upcoming=upcoming, gallery_items=gallery_items, stats=stats)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/treks")
def treks():
    filter_type = request.args.get("type", "upcoming")
    query = Trek.query.filter(Trek.is_published.is_(True))

    if filter_type == "upcoming":
        query = query.filter(Trek.event_date >= date.today()).order_by(Trek.event_date.asc())
    elif filter_type == "past":
        query = query.filter(Trek.event_date < date.today()).order_by(Trek.event_date.desc())
    else:
        query = query.order_by(Trek.event_date.asc())

    all_treks = query.all()
    return render_template("treks.html", treks=all_treks, filter_type=filter_type)


@app.route("/treks/<int:trek_id>")
def trek_detail(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if not trek.is_published and not current_user.is_authenticated:
        abort(404)
    return render_template("trek_detail.html", trek=trek)


@app.route("/gallery")
def gallery():
    past_treks = (
        Trek.query.filter(Trek.is_published.is_(True), Trek.event_date < date.today())
        .order_by(Trek.event_date.desc())
        .all()
    )
    return render_template("gallery.html", treks=past_treks)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not message:
            flash("Please fill in your name, email, and message.", "danger")
            return redirect(url_for("contact"))

        msg = ContactMessage(name=name, email=email, phone=phone, message=message)
        db.session.add(msg)
        db.session.commit()
        flash("Thank you! Your message has been sent to the Sevak Sahyadriche team.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")
# ============================================================
# MARATHI HOME PAGE SECTIONS
# ============================================================

@app.route("/mohim")
def mohim():
    # Mohim number is based on creation order:
    # newest = highest number (for example 31, 30, 29...)
    all_published = (
        Trek.query
        .filter(Trek.is_published.is_(True))
        .order_by(Trek.created_at.desc(), Trek.id.desc())
        .all()
    )

    total_mohim = len(all_published)

    mohim_items = []
    for index, trek in enumerate(all_published):
        number = total_mohim - index
        photos = _mohim_photos(number)
        mohim_items.append({
            "trek": trek,
            "number": number,
            "main_photo": photos[0] if photos else None,
        })

    latest_mohim = mohim_items[:3]
    all_mohim = mohim_items[3:]

    return render_template(
        "mohim.html",
        latest_mohim=latest_mohim,
        all_mohim=all_mohim,
        total_mohim=total_mohim,
    )


def _mohim_photo_sort_key(path):
    """Keep main.jpg first, then photo2.jpg, photo3.jpg, etc."""
    name = os.path.splitext(os.path.basename(path))[0].lower()
    if name == "main":
        return (0, 0)
    match = re.match(r"photo(\d+)$", name)
    if match:
        return (1, int(match.group(1)))
    return (2, name)


def _mohim_photos(mohim_number):
    """Return all photos stored in static/img/mohim/<number>/."""
    folder = os.path.join(BASE_DIR, "static", "img", "mohim", str(mohim_number))
    if not os.path.isdir(folder):
        return []

    extensions = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif")
    paths = []
    for extension in extensions:
        paths.extend(glob(os.path.join(folder, extension)))

    paths.sort(key=_mohim_photo_sort_key)

    return [
        url_for(
            "static",
            filename=os.path.relpath(path, os.path.join(BASE_DIR, "static")).replace(os.sep, "/")
        )
        for path in paths
    ]


def _mohim_text_file(mohim_number, filename):
    """Read an optional text file from a Mohim's photo folder."""
    path = os.path.join(
        BASE_DIR, "static", "img", "mohim", str(mohim_number), filename
    )
    if not os.path.isfile(path):
        return None

    try:
        return Path(path).read_text(encoding="utf-8").strip() or None
    except (OSError, UnicodeError):
        return None


@app.route("/mohim/<int:trek_id>")
def mohim_detail(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    if not trek.is_published and not current_user.is_authenticated:
        abort(404)

    # Find the same descending Mohim number used on the listing page.
    published = (
        Trek.query
        .filter(Trek.is_published.is_(True))
        .order_by(Trek.created_at.desc(), Trek.id.desc())
        .all()
    )

    number = None
    for index, item in enumerate(published):
        if item.id == trek.id:
            number = len(published) - index
            break

    # For an unpublished item opened by an authenticated admin, keep a
    # stable folder fallback based on its database id.
    if number is None:
        number = trek.id

    photos = _mohim_photos(number)
    activity = _mohim_text_file(number, "activity.txt")
    details = _mohim_text_file(number, "details.txt")

    return render_template(
        "mohim_detail.html",
        trek=trek,
        mohim_number=number,
        photos=photos,
        activity=activity,
        details=details,
    )


@app.route("/foreign-diaspora")
def foreign_diaspora():
    return render_template("foreign_diaspora.html")


@app.route("/yuva-manch")
def yuva_manch():
    return render_template("yuva_manch.html")


@app.route("/lekh")
def lekh():
    return render_template("lekh.html")


@app.route("/donate")
def donate():
    return render_template("donate.html")
# ---------------------------------------------------------------------
# ADMIN AUTH
# ---------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and check_password_hash(
            ADMIN_PASSWORD_HASH, password
        ):
            login_user(ADMIN_USER)
            flash("Welcome back!", "success")

            # Only allow local relative redirects.
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)

            return redirect(url_for("admin_dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("admin/login.html")


@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------------
# ADMIN PANEL - DASHBOARD
# ---------------------------------------------------------------------

@app.route("/admin")
@login_required
def admin_dashboard():
    total_treks = Trek.query.count()
    upcoming_count = Trek.query.filter(Trek.event_date >= date.today()).count()
    unread_messages = ContactMessage.query.filter_by(is_read=False).count()
    recent_treks = Trek.query.order_by(Trek.created_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        total_treks=total_treks,
        upcoming_count=upcoming_count,
        unread_messages=unread_messages,
        recent_treks=recent_treks,
    )


# ---------------------------------------------------------------------
# ADMIN PANEL - TREK / EVENT CRUD
# ---------------------------------------------------------------------

@app.route("/admin/treks")
@login_required
def admin_treks():
    all_treks = Trek.query.order_by(Trek.event_date.desc()).all()
    return render_template("admin/trek_list.html", treks=all_treks)


def _save_uploaded_image(file_storage):
    """Save an uploaded image and return its filename, or None."""
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        flash("Unsupported image format. Use png, jpg, jpeg, webp or gif.", "danger")
        return None

    filename = secure_filename(file_storage.filename)
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
    file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
    return unique_name


def _trek_from_form(trek):
    trek.title = request.form.get("title", "").strip()
    trek.category = request.form.get("category", "Trek")
    trek.location = request.form.get("location", "").strip()
    trek.description = request.form.get("description", "").strip()
    trek.difficulty = request.form.get("difficulty", "Moderate")
    trek.duration = request.form.get("duration", "1 Day").strip()
    trek.price = request.form.get("price", "Free").strip()
    trek.contact_person = request.form.get("contact_person", "").strip()
    trek.contact_phone = request.form.get("contact_phone", "").strip()
    trek.is_published = request.form.get("is_published") == "on"

    try:
        trek.total_slots = int(request.form.get("total_slots") or 0)
    except ValueError:
        trek.total_slots = 0
    try:
        trek.slots_filled = int(request.form.get("slots_filled") or 0)
    except ValueError:
        trek.slots_filled = 0

    date_str = request.form.get("event_date")
    if date_str:
        trek.event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    uploaded_name = _save_uploaded_image(request.files.get("image"))
    if uploaded_name:
        trek.image_filename = uploaded_name

    return trek


@app.route("/admin/treks/new", methods=["GET", "POST"])
@login_required
def admin_trek_new():
    if request.method == "POST":
        trek = Trek(event_date=date.today())
        trek = _trek_from_form(trek)

        if not trek.title or not trek.location or not trek.description:
            flash("Title, location, and description are required.", "danger")
            return render_template("admin/trek_form.html", trek=trek, mode="new")

        db.session.add(trek)
        db.session.commit()
        flash(f'"{trek.title}" has been added.', "success")
        return redirect(url_for("admin_treks"))

    return render_template("admin/trek_form.html", trek=None, mode="new")


@app.route("/admin/treks/<int:trek_id>/edit", methods=["GET", "POST"])
@login_required
def admin_trek_edit(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    if request.method == "POST":
        trek = _trek_from_form(trek)

        if not trek.title or not trek.location or not trek.description:
            flash("Title, location, and description are required.", "danger")
            return render_template("admin/trek_form.html", trek=trek, mode="edit")

        db.session.commit()
        flash(f'"{trek.title}" has been updated.', "success")
        return redirect(url_for("admin_treks"))

    return render_template("admin/trek_form.html", trek=trek, mode="edit")


@app.route("/admin/treks/<int:trek_id>/delete", methods=["POST"])
@login_required
def admin_trek_delete(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    db.session.delete(trek)
    db.session.commit()
    flash(f'"{trek.title}" has been deleted.', "info")
    return redirect(url_for("admin_treks"))


@app.route("/admin/treks/<int:trek_id>/toggle-publish", methods=["POST"])
@login_required
def admin_trek_toggle_publish(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    trek.is_published = not trek.is_published
    db.session.commit()
    return redirect(url_for("admin_treks"))


# ---------------------------------------------------------------------
# ADMIN PANEL - CONTACT MESSAGES
# ---------------------------------------------------------------------

@app.route("/admin/messages")
@login_required
def admin_messages():
    messages = ContactMessage.query.order_by(ContactMessage.submitted_at.desc()).all()
    return render_template("admin/messages.html", messages=messages)


@app.route("/admin/messages/<int:msg_id>/read", methods=["POST"])
@login_required
def admin_message_read(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)
    msg.is_read = True
    db.session.commit()
    return redirect(url_for("admin_messages"))


@app.route("/admin/messages/<int:msg_id>/delete", methods=["POST"])
@login_required
def admin_message_delete(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)
    db.session.delete(msg)
    db.session.commit()
    flash("Message deleted.", "info")
    return redirect(url_for("admin_messages"))


# ---------------------------------------------------------------------
# ADMIN PANEL - CHANGE PASSWORD
# ---------------------------------------------------------------------

@app.route("/admin/change-password")
@login_required
def admin_change_password():
    flash(
        "The admin password is managed through the server environment. "
        "Update ADMIN_PASSWORD_HASH and redeploy to change it.",
        "info",
    )
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------
# CLI / SETUP HELPERS
# ---------------------------------------------------------------------

@app.cli.command("init-db")
def init_db():
    """Create application tables.

    Admin credentials are environment-managed and are not inserted into DB.
    """
    db.create_all()
    print("Database initialized.")


@app.cli.command("seed-demo")
def seed_demo():
    """Add a few sample treks so the site isn't empty on first run."""
    from datetime import timedelta

    samples = [
        Trek(
            title="Rajgad Fort Night Trek",
            category="Trek",
            location="Rajgad Fort, Pune District",
            description=(
                "An overnight trek to Rajgad, Chhatrapati Shivaji Maharaj's "
                "first capital. Includes a heritage walk through the "
                "Sanjeevani Machi and Padmavati Machi, storytelling around "
                "a campfire, and sunrise at Bale Killa."
            ),
            difficulty="Moderate",
            event_date=date.today() + timedelta(days=14),
            duration="2 Days, 1 Night",
            price="₹899",
            total_slots=40,
            slots_filled=18,
            contact_person="Suresh Patil",
            contact_phone="+91 90000 00001",
        ),
        Trek(
            title="Torna Fort Day Trek",
            category="Trek",
            location="Torna Fort, Pune District",
            description=(
                "A day trek to Torna, the first fort captured by Shivaji "
                "Maharaj. Steep but rewarding climb with panoramic views "
                "of the Sahyadri range."
            ),
            difficulty="Difficult",
            event_date=date.today() + timedelta(days=30),
            duration="1 Day",
            price="₹499",
            total_slots=30,
            slots_filled=9,
            contact_person="Anjali Deshmukh",
            contact_phone="+91 90000 00002",
        ),
        Trek(
            title="Gudi Padwa Sanskrutik Sohala",
            category="Cultural Event",
            location="Sevak Sahyadriche Community Hall, Pune",
            description=(
                "Celebrate Gudi Padwa with traditional Maharashtrian "
                "folk dances (Lavani, Koli), a puran poli food stall, "
                "and a talk on the significance of the festival."
            ),
            difficulty="Easy",
            event_date=date.today() + timedelta(days=60),
            duration="Half Day",
            price="Free",
            total_slots=150,
            slots_filled=42,
            contact_person="Meera Joshi",
            contact_phone="+91 90000 00003",
        ),
        Trek(
            title="Sinhagad Fort Heritage Walk",
            category="Trek",
            location="Sinhagad Fort, Pune",
            description=(
                "A completed trek covering the history of Tanaji Malusare "
                "and the Battle of Sinhagad, with a visit to the samadhi."
            ),
            difficulty="Easy",
            event_date=date.today() - timedelta(days=20),
            duration="1 Day",
            price="₹299",
            total_slots=50,
            slots_filled=50,
        ),
    ]

    for s in samples:
        db.session.add(s)
    db.session.commit()
    print(f"Added {len(samples)} sample treks/events.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
    )
