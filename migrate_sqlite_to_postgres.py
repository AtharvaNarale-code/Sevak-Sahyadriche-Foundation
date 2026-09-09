import os
import sqlite3

# Set DATABASE_URL in your local .env before running this script.
# The source SQLite database remains the local ./sevak.db.
from app import app, db, Trek, ContactMessage

SOURCE_DB = os.path.join(os.path.dirname(__file__), "sevak.db")

if not os.environ.get("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL must point to your production Postgres database before running this migration.")

if not os.path.exists(SOURCE_DB):
    raise FileNotFoundError(f"Source database not found: {SOURCE_DB}")

with sqlite3.connect(SOURCE_DB) as conn:
    conn.row_factory = sqlite3.Row
    treks = conn.execute("SELECT * FROM treks ORDER BY id").fetchall()
    messages = conn.execute("SELECT * FROM contact_messages ORDER BY id").fetchall()

with app.app_context():
    db.create_all()

    if Trek.query.count() or ContactMessage.query.count():
        raise RuntimeError("Target database is not empty. Aborting to prevent duplicate data.")

    for row in treks:
        db.session.add(Trek(
            id=row["id"],
            title=row["title"],
            category=row["category"],
            location=row["location"],
            description=row["description"],
            difficulty=row["difficulty"],
            event_date=row["event_date"],
            duration=row["duration"],
            price=row["price"],
            total_slots=row["total_slots"],
            slots_filled=row["slots_filled"],
            image_filename=row["image_filename"],
            contact_person=row["contact_person"],
            contact_phone=row["contact_phone"],
            is_published=bool(row["is_published"]),
            created_at=row["created_at"],
        ))

    for row in messages:
        db.session.add(ContactMessage(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            phone=row["phone"],
            message=row["message"],
            submitted_at=row["submitted_at"],
            is_read=bool(row["is_read"]),
        ))

    db.session.commit()
    print(f"Migrated {len(treks)} treks/events and {len(messages)} contact messages.")
