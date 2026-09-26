"""
Seed the database with:

1. Database tables
2. Default admin account
3. All question JSON files found recursively under:
       questions/
4. Starter themes
5. Subject configuration

Run:

    python seed.py

Question files can be organized however you like, for example:

    questions/
    ├── CBSE/
    │   ├── grade10/
    │   │   ├── mathematics/
    │   │   │   ├── algebra.json
    │   │   │   └── geometry.json
    │   │   └── science/
    │   │       └── physics.json
    │   │
    │   └── grade11/
    │       └── mathematics/
    │           └── sets.json
    │
    └── ICSE/
        └── grade10/
            └── mathematics.json

Every *.json file under questions/ will be discovered automatically.

Supported question format:

{
    "id": "11021",
    "subject": "Mathematics",
    "grade": 11,
    "board": "CBSE",
    "question": "If A = {2, 4, 6, 8} and B = {4, 6, 10, 12}, what is A ∩ B?",
    "options": {
        "A": "{2, 8}",
        "B": "{4, 6}",
        "C": "{10, 12}",
        "D": "{2, 4, 6, 8, 10, 12}"
    },
    "correct": "B",
    "explanation": "The elements common to both sets are 4 and 6.",
    "world": "Sets and Functions",
    "chapter": "Sets",
    "topic": "Intersection of Sets",
    "stage": "Foundation",
    "cognitive_skill": "Understand",
    "question_type": "MCQ",
    "time_limit": 60,
    "hint": "Find the elements appearing in both sets.",
    "status": "published",
    "version": 1
}

The script is safe to re-run:
- Existing admin is not duplicated.
- Existing subjects/themes are not duplicated.
- Existing questions are skipped.
- New JSON files/questions are imported.
"""


import json
from pathlib import Path

from database import Base, engine, SessionLocal
import models
from config import settings
from security import hash_password


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent

QUESTIONS_DIR = BASE_DIR / "questions"

ASSETS_DIR = BASE_DIR / "seed_assets"


# ============================================================
# SUBJECTS
# ============================================================

SUBJECTS_SEED = [
    ("chemistry", "Chemistry", "🧪"),
    ("physics", "Physics", "⚛️"),
    ("botany", "Botany", "🌿"),
    ("zoology", "Zoology", "🐾"),
    ("commerce", "Commerce", "💼"),
    ("accounts", "Accounts", "📒"),
    ("mathematics", "Mathematics", "📐"),
    ("nutrition", "Nutrition", "🍎"),
]


# ============================================================
# QUESTION VALIDATION
# ============================================================

REQUIRED_QUESTION_FIELDS = [
    "subject",
    "grade",
    "board",
    "question",
    "options",
    "correct",
]


def validate_question(q, filename, index):
    """
    Validate the minimum required fields in a question.

    Returns:
        (True, None)
        or
        (False, error_message)
    """

    if not isinstance(q, dict):
        return (
            False,
            f"Question #{index} is not a JSON object."
        )

    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    for field in REQUIRED_QUESTION_FIELDS:

        if field not in q:

            return (
                False,
                f"Missing required field '{field}'."
            )

    # --------------------------------------------------------
    # Basic fields
    # --------------------------------------------------------

    if not str(q["subject"]).strip():

        return (
            False,
            "Subject cannot be empty."
        )

    if not str(q["board"]).strip():

        return (
            False,
            "Board cannot be empty."
        )

    if not str(q["question"]).strip():

        return (
            False,
            "Question cannot be empty."
        )

    # --------------------------------------------------------
    # Grade
    # --------------------------------------------------------

    try:

        grade = int(q["grade"])

        if grade <= 0:

            return (
                False,
                "Grade must be greater than zero."
            )

    except (TypeError, ValueError):

        return (
            False,
            "Grade must be an integer."
        )

    # --------------------------------------------------------
    # Options
    # --------------------------------------------------------

    options = q["options"]

    if not isinstance(options, dict):

        return (
            False,
            "'options' must be an object containing A/B/C/D."
        )

    required_options = ["A", "B", "C", "D"]

    for option in required_options:

        if option not in options:

            return (
                False,
                f"Missing option '{option}'."
            )

        if not str(options[option]).strip():

            return (
                False,
                f"Option '{option}' cannot be empty."
            )

    # --------------------------------------------------------
    # Correct answer
    # --------------------------------------------------------

    correct = str(q["correct"]).strip().upper()

    if correct not in required_options:

        return (
            False,
            "Correct answer must be A, B, C, or D."
        )

    return True, None


# ============================================================
# NORMALIZE QUESTION
# ============================================================

def normalize_question(q):
    """
    Convert a JSON question into a consistent internal format.
    """

    options = q.get("options", {})

    return {
        "question_id": (
            str(q["id"]).strip()
            if q.get("id") is not None
            else None
        ),

        "subject": str(
            q.get("subject", "")
        ).strip(),

        "grade": int(
            q.get("grade")
        ),

        "board": str(
            q.get("board", "")
        ).strip(),

        "question": str(
            q.get("question", "")
        ).strip(),

        "option_a": str(
            options.get("A", "")
        ).strip(),

        "option_b": str(
            options.get("B", "")
        ).strip(),

        "option_c": str(
            options.get("C", "")
        ).strip(),

        "option_d": str(
            options.get("D", "")
        ).strip(),

        "correct": str(
            q.get("correct", "")
        ).strip().upper(),

        "explanation": str(
            q.get("explanation", "")
        ).strip(),

        "world": str(
            q.get("world", "")
        ).strip(),

        "chapter": str(
            q.get("chapter", "")
        ).strip(),

        "topic": str(
            q.get("topic", "")
        ).strip(),

        "stage": str(
            q.get("stage", "Foundation")
        ).strip(),

        "cognitive_skill": str(
            q.get("cognitive_skill", "Understand")
        ).strip(),

        "question_type": str(
            q.get("question_type", "MCQ")
        ).strip(),

        "time_limit": int(
            q.get("time_limit", 60)
        ),

        "hint": str(
            q.get("hint", "")
        ).strip(),

        "status": str(
            q.get("status", "published")
        ).strip(),

        "version": int(
            q.get("version", 1)
        ),
    }


# ============================================================
# DUPLICATE CHECK
# ============================================================

def question_already_exists(db, question):
    """
    Determine whether this question is already in the database.

    Primary check:
        question_id

    Fallback check:
        subject + board + grade + question text
    """

    question_id = question.get("question_id")

    # --------------------------------------------------------
    # Check generated question ID
    # --------------------------------------------------------

    if question_id:

        existing = (
            db.query(models.Question)
            .filter(
                models.Question.question_id
                == question_id
            )
            .first()
        )

        if existing:
            return True

    # --------------------------------------------------------
    # Check question text
    # --------------------------------------------------------

    existing = (
        db.query(models.Question)
        .filter(
            models.Question.subject
            == question["subject"],

            models.Question.board
            == question["board"],

            models.Question.grade
            == question["grade"],

            models.Question.question
            == question["question"],
        )
        .first()
    )

    return existing is not None


# ============================================================
# IMPORT ONE JSON FILE
# ============================================================

def import_question_file(db, json_path):
    """
    Import all questions from one JSON file.

    Supports:

        [
            {...},
            {...}
        ]

    OR:

        {
            "questions": [
                {...},
                {...}
            ]
        }
    """

    print()
    print(f"Processing: {json_path.relative_to(BASE_DIR)}")

    # --------------------------------------------------------
    # Read JSON
    # --------------------------------------------------------

    try:

        with open(
            json_path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

    except json.JSONDecodeError as e:

        print(
            f"  ERROR: Invalid JSON: {e}"
        )

        return 0, 0, 1

    except OSError as e:

        print(
            f"  ERROR: Could not read file: {e}"
        )

        return 0, 0, 1

    # --------------------------------------------------------
    # Extract question list
    # --------------------------------------------------------

    if isinstance(data, dict):

        data = data.get("questions", [])

    if not isinstance(data, list):

        print(
            "  ERROR: JSON must contain a list "
            "of questions."
        )

        return 0, 0, 1

    # --------------------------------------------------------
    # Process questions
    # --------------------------------------------------------

    loaded = 0
    skipped = 0
    errors = 0

    for index, q in enumerate(data, start=1):

        valid, error = validate_question(
            q,
            json_path.name,
            index
        )

        if not valid:

            print(
                f"  WARNING: Question #{index}: "
                f"{error}"
            )

            errors += 1
            continue

        try:

            normalized = normalize_question(q)

            # ------------------------------------------------
            # Duplicate check
            # ------------------------------------------------

            if question_already_exists(
                db,
                normalized
            ):

                skipped += 1
                continue

            # ------------------------------------------------
            # Create database record
            # ------------------------------------------------

            question_model = models.Question(
                question_id=normalized["question_id"],

                subject=normalized["subject"],

                grade=normalized["grade"],

                level=normalized["stage"],

                board=normalized["board"],

                question=normalized["question"],

                option_a=normalized["option_a"],

                option_b=normalized["option_b"],

                option_c=normalized["option_c"],

                option_d=normalized["option_d"],

                correct=normalized["correct"],

                explanation=normalized["explanation"],

                world=normalized["world"],

                chapter=normalized["chapter"],

                topic=normalized["topic"],

                stage=normalized["stage"],

                cognitive_skill=normalized[
                    "cognitive_skill"
                ],

                question_type=normalized[
                    "question_type"
                ],

                time_limit=normalized[
                    "time_limit"
                ],

                hint=normalized["hint"],

                status=normalized["status"],

                version=normalized["version"],
            )

            db.add(question_model)

            loaded += 1

        except Exception as e:

            print(
                f"  ERROR: Question #{index}: {e}"
            )

            errors += 1

    # --------------------------------------------------------
    # Commit this file
    # --------------------------------------------------------

    try:

        db.commit()

    except Exception as e:

        db.rollback()

        print(
            f"  ERROR committing file: {e}"
        )

        return 0, 0, 1

    print(
        f"  Loaded: {loaded} | "
        f"Skipped: {skipped} | "
        f"Errors: {errors}"
    )

    return loaded, skipped, errors


# ============================================================
# IMPORT ALL QUESTION FILES
# ============================================================

def seed_questions(db):
    """
    Find and import every JSON file recursively under
    the questions directory.
    """

    print()
    print("=" * 60)
    print("QUESTION BANK")
    print("=" * 60)

    if not QUESTIONS_DIR.exists():

        print(
            f"Questions directory does not exist:\n"
            f"  {QUESTIONS_DIR}"
        )

        print(
            "\nCreate the directory and put your "
            "question JSON files inside it."
        )

        return

    # --------------------------------------------------------
    # rglob searches all subdirectories
    # --------------------------------------------------------

    json_files = sorted(
        QUESTIONS_DIR.rglob("*.json")
    )

    if not json_files:

        print(
            f"No JSON files found under:\n"
            f"  {QUESTIONS_DIR}"
        )

        return

    print(
        f"Found {len(json_files)} JSON question file(s)."
    )

    total_loaded = 0
    total_skipped = 0
    total_errors = 0

    for json_path in json_files:

        loaded, skipped, errors = (
            import_question_file(
                db,
                json_path
            )
        )

        total_loaded += loaded
        total_skipped += skipped
        total_errors += errors

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("-" * 60)
    print("QUESTION IMPORT SUMMARY")
    print("-" * 60)

    print(
        f"Files found       : {len(json_files)}"
    )

    print(
        f"Questions loaded   : {total_loaded}"
    )

    print(
        f"Questions skipped  : {total_skipped}"
    )

    print(
        f"Questions errors   : {total_errors}"
    )

    print("-" * 60)


# ============================================================
# DEFAULT ADMIN
# ============================================================

def seed_admin(db):

    existing_admin = (
        db.query(models.User)
        .filter(
            models.User.role
            == models.Role.admin
        )
        .first()
    )

    if not existing_admin:

        admin = models.User(
            userid=settings.DEFAULT_ADMIN_USERID,

            email=settings.DEFAULT_ADMIN_EMAIL,

            hashed_password=hash_password(
                settings.DEFAULT_ADMIN_PASSWORD
            ),

            name="Administrator",

            role=models.Role.admin,
        )

        db.add(admin)

        db.commit()

        print(
            f"Created default admin "
            f"'{settings.DEFAULT_ADMIN_USERID}' "
            f"— log in with the password you set "
            f"in DEFAULT_ADMIN_PASSWORD."
        )

    else:

        print(
            "Admin account already exists, skipping."
        )


# ============================================================
# THEMES
# ============================================================

def seed_themes(db):

    def seed_theme(
        key: str,
        name: str,
        bg_filename: str,
        icon_dir: str | None = None
    ):

        # ----------------------------------------------------
        # Existing theme
        # ----------------------------------------------------

        if (
            db.query(models.Theme)
            .filter(
                models.Theme.key == key
            )
            .first()
        ):

            print(
                f"Theme '{key}' already exists, "
                f"skipping."
            )

            return

        # ----------------------------------------------------
        # Background
        # ----------------------------------------------------

        bg_path = (
            ASSETS_DIR
            / bg_filename
        )

        if not bg_path.exists():

            print(
                f"Skipping theme '{key}' — "
                f"{bg_path} not found."
            )

            return

        # ----------------------------------------------------
        # Create theme
        # ----------------------------------------------------

        theme = models.Theme(
            key=key,

            name=name,

            background_image=(
                bg_path.read_bytes()
            ),

            background_mime="image/jpeg",
        )

        db.add(theme)

        db.flush()

        # ----------------------------------------------------
        # Icons
        # ----------------------------------------------------

        if icon_dir:

            icon_directory = (
                ASSETS_DIR
                / icon_dir
            )

            icon_files = sorted(
                icon_directory.glob("*.jpg")
            )

            for i, icon_path in enumerate(
                icon_files
            ):

                db.add(
                    models.ThemeIcon(
                        theme_id=theme.id,

                        image=icon_path.read_bytes(),

                        mime="image/jpeg",

                        sort_order=i,
                    )
                )

            print(
                f"Seeded theme '{key}' "
                f"with {len(icon_files)} icons."
            )

        else:

            print(
                f"Seeded theme '{key}' "
                f"(background only, "
                f"no icons yet)."
            )

        db.commit()

    # --------------------------------------------------------
    # Themes
    # --------------------------------------------------------

    seed_theme(
        "garden",
        "Garden",
        "garden_background.jpg"
    )

    seed_theme(
        "ocean",
        "Ocean",
        "ocean_background.jpg",
        icon_dir="ocean_icons"
    )


# ============================================================
# SUBJECT CONFIG
# ============================================================

def seed_subjects(db):

    existing_subject_keys = {
        subject.key
        for subject in (
            db.query(models.Subject).all()
        )
    }

    added = 0

    for key, name, icon in SUBJECTS_SEED:

        if key in existing_subject_keys:

            continue

        db.add(
            models.Subject(
                key=key,

                name=name,

                icon=icon,

                demo_level_cap=5,
            )
        )

        added += 1

    if added:

        db.commit()

        print(
            f"Seeded {added} subject config "
            f"row(s) (demo_level_cap=5 each)."
        )

    else:

        print(
            "Subject config already present, "
            "skipping."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print("DATABASE SEED")
    print("=" * 60)

    # --------------------------------------------------------
    # Create tables
    # --------------------------------------------------------

    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    try:

        # ----------------------------------------------------
        # Admin
        # ----------------------------------------------------

        print()
        print("[1/4] Default admin")

        seed_admin(db)

        # ----------------------------------------------------
        # Questions
        # ----------------------------------------------------

        print()
        print("[2/4] Question bank")

        seed_questions(db)

        # ----------------------------------------------------
        # Themes
        # ----------------------------------------------------

        print()
        print("[3/4] Themes")

        seed_themes(db)

        # ----------------------------------------------------
        # Subjects
        # ----------------------------------------------------

        print()
        print("[4/4] Subject configuration")

        seed_subjects(db)

        # ----------------------------------------------------
        # Final count
        # ----------------------------------------------------

        question_count = (
            db.query(models.Question).count()
        )

        print()
        print("=" * 60)
        print("SEED COMPLETE")
        print("=" * 60)

        print(
            f"Total questions in database: "
            f"{question_count}"
        )

    finally:

        db.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

