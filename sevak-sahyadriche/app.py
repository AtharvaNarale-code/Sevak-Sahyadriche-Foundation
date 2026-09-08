#pythonpython -m pip install Flask-Login 
"""
Sevak Sahyadriche Foundation - Website Backend
Flask application powering the public site (home, about, treks/events,
gallery, contact) and a protected admin panel for managing upcoming
treks and events.
"""

import os
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
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "img", "treks")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "sevak-sahyadriche-dev-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "sevak.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB uploads

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "admin_login"
login_manager.login_message = "Please log in to access the admin panel."
login_manager.login_message_category = "warning"


# ---------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------

class Admin(UserMixin, db.Model):
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


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
        return url_for("static", filename="img/trek-placeholder.jpg")


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)


@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


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
    upcoming = (
        Trek.query.filter(Trek.is_published.is_(True), Trek.event_date >= date.today())
        .order_by(Trek.event_date.asc())
        .limit(3)
        .all()
    )
    return render_template("index.html", upcoming=upcoming)


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
        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            login_user(admin)
            flash("Welcome back!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("admin_dashboard"))

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

@app.route("/admin/change-password", methods=["GET", "POST"])
@login_required
def admin_change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
        elif len(new_password) < 6:
            flash("New password must be at least 6 characters.", "danger")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "danger")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Password updated successfully.", "success")
            return redirect(url_for("admin_dashboard"))

    return render_template("admin/change_password.html")


# ---------------------------------------------------------------------
# CLI / SETUP HELPERS
# ---------------------------------------------------------------------

@app.cli.command("init-db")
def init_db():
    """Create tables and a default admin account.
    Usage: flask --app app.py init-db
    """
    db.create_all()

    if not Admin.query.filter_by(username="admin").first():
        default_admin = Admin(username="admin")
        default_admin.set_password("sahyadri@123")
        db.session.add(default_admin)
        db.session.commit()
        print("Default admin created -> username: admin | password: sahyadri@123")
        print("IMPORTANT: log in and change this password immediately.")
    else:
        print("Admin already exists. Skipping.")

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
        if not Admin.query.filter_by(username="admin").first():
            default_admin = Admin(username="admin")
            default_admin.set_password("sahyadri@123")
            db.session.add(default_admin)
            db.session.commit()
            print("Default admin created -> username: admin | password: sahyadri@123")
    app.run(debug=True, host="0.0.0.0", port=5000)
