"""
Run once after configuring your .env and creating the Postgres database:

    python seed.py

This will:
  1. Create all tables (same as the app's startup hook, safe to re-run).
  2. Create the default admin account, if none exists yet (userid/password
     from settings.DEFAULT_ADMIN_USERID / DEFAULT_ADMIN_PASSWORD).
  3. Load the starter question bank from seed_questions.json (160 questions
     across all 8 subjects x 5 levels), if the questions table is empty.

Re-running this script is safe — it won't duplicate the admin account or
the question bank once they exist.
"""
import json
from pathlib import Path

from database import Base, engine, SessionLocal
import models
from config import settings
from security import hash_password

SUBJECT_KEYS = ["chemistry", "physics", "botany", "zoology", "commerce", "accounts", "mathematics", "nutrition"]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # ---- default admin ----
        existing_admin = db.query(models.User).filter(models.User.role == models.Role.admin).first()
        if not existing_admin:
            admin = models.User(
                userid=settings.DEFAULT_ADMIN_USERID,
                email=settings.DEFAULT_ADMIN_EMAIL,
                hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                name="Administrator",
                role=models.Role.admin,
            )
            db.add(admin)
            db.commit()
            # Deliberately NOT printing the password here — you already set it
            # via the DEFAULT_ADMIN_PASSWORD env var, and this runs on every
            # startup, so echoing it would put it in your host's log history
            # every single deploy.
            print(f"Created default admin '{settings.DEFAULT_ADMIN_USERID}' "
                  f"— log in with the password you set in DEFAULT_ADMIN_PASSWORD.")
        else:
            print("Admin account already exists, skipping.")

        # ---- starter question bank ----
        question_count = db.query(models.Question).count()
        if question_count == 0:
            seed_path = Path(__file__).parent / "seed_questions.json"
            with open(seed_path, encoding="utf-8") as f:
                data = json.load(f)
            for q in data:
                db.add(models.Question(
                    subject=q["subject"],
                    level=q["level"],
                    board=q["board"],
                    question=q["question"],
                    option_a=q["options"][0],
                    option_b=q["options"][1],
                    option_c=q["options"][2],
                    option_d=q["options"][3],
                    correct=q["correct"],
                    explanation=q.get("explanation", ""),
                ))
            db.commit()
            print(f"Loaded {len(data)} starter questions.")
        else:
            print(f"Questions table already has {question_count} rows, skipping starter load.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
