# Sevak Sahyadriche Foundation — Website

A Flask website for a Maharashtrian-culture / trekking foundation, with a
public site and a protected admin panel for managing upcoming treks and
cultural events.

## Features

**Public site**
- Home page with hero, stats, and upcoming treks preview
- About page (mission, values)
- Treks & Events listing with Upcoming / Past / All filters
- Trek/event detail page (location, date, difficulty, price, slots, coordinator)
- Gallery of past events
- Contact form (messages are stored and visible in the admin panel)

**Admin panel** (`/admin`)
- Secure login (Flask-Login, hashed passwords)
- Dashboard with counts (total treks, upcoming, unread messages)
- Full CRUD for treks/events: add, edit, delete, publish/unpublish
- Image upload per trek
- View & manage contact form submissions
- Change admin password

## Tech stack

- Flask 3
- Flask-SQLAlchemy (SQLite database, file: `sevak.db`)
- Flask-Login (admin authentication)
- Werkzeug (password hashing, file uploads)
- Plain HTML/CSS (no frontend framework) — templates in `templates/`, styles in `static/css/style.css`

## Setup

```bash
# 1. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize the database and create the default admin account
flask --app app.py init-db

# 4. (Optional) Add sample treks/events so the site isn't empty
flask --app app.py seed-demo

# 5. Run the app
python app.py
```

The site will be available at **http://127.0.0.1:5000**.

## Default admin login

```
URL:      http://127.0.0.1:5000/admin/login
Username: admin
Password: sahyadri@123
```

**Change this password immediately** after first login via
*Admin Panel → Change Password*.

## Project structure

```
sevak-sahyadriche/
├── app.py                     # All routes, models, admin logic
├── requirements.txt
├── sevak.db                   # SQLite database (created on init-db)
├── static/
│   ├── css/style.css
│   └── img/treks/             # Uploaded trek images land here
└── templates/
    ├── base.html
    ├── index.html
    ├── about.html
    ├── treks.html
    ├── trek_detail.html
    ├── gallery.html
    ├── contact.html
    └── admin/
        ├── login.html
        ├── base_admin.html
        ├── dashboard.html
        ├── trek_list.html
        ├── trek_form.html
        ├── messages.html
        └── change_password.html
```

## Notes on the data model

Each trek/event record (`Trek` model) has:
`title, category (Trek / Cultural Event / Fort Visit / Workshop), location,
description, difficulty (Easy/Moderate/Difficult), event_date, duration,
price, total_slots, slots_filled, image, coordinator contact, is_published`.

Whether a trek shows as "Upcoming" or "Past" on the public site is computed
automatically from `event_date` vs. today's date — no manual toggle needed
for that part.

## Deploying

This ships with Flask's built-in dev server (`app.run(debug=True)`), which
is **not** meant for production. For real deployment:
- Turn off debug mode
- Serve with a WSGI server (e.g. `gunicorn app:app`)
- Put it behind Nginx (or similar) and use HTTPS
- Swap the `SECRET_KEY` in `app.py` for a real secret (environment variable)
- Consider moving from SQLite to PostgreSQL if traffic grows
