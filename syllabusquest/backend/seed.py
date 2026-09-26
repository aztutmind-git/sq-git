from pathlib import Path
import json
import logging

from sqlalchemy.orm import Session

import models
from database import Base, SessionLocal, engine


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

QUESTIONS_DIR = BASE_DIR / "questions"

# Optional: change these if your project uses different values.
DEFAULT_ADMIN_USERID = "admin"
DEFAULT_ADMIN_NAME = "Administrator"
DEFAULT_ADMIN_EMAIL = "admin@example.com"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# LEVEL / STAGE MAPPING
# ============================================================

STAGE_TO_LEVEL = {
    "foundation": 1,
    "beginner": 1,

    "intermediate": 2,

    "advanced": 3,

    "application": 4,

    "mastery": 5,
    "expert": 5,
}


def get_level(question):
    """
    Convert the JSON stage into the ERP numeric level.

    Example:
        Foundation   -> 1
        Intermediate -> 2
        Advanced     -> 3
        Application  -> 4
        Mastery      -> 5
    """

    stage = question.get("stage")

    if stage:
        stage_key = str(stage).strip().lower()

        if stage_key in STAGE_TO_LEVEL:
            return STAGE_TO_LEVEL[stage_key]

    # If JSON already contains a numeric level, use it.
    if question.get("level") is not None:
        try:
            level = int(question["level"])

            if level >= 1:
                return level

        except (TypeError, ValueError):
            pass

    # Default
    return 1


# ============================================================
# GRADE CONVERSION
# ============================================================

def normalize_grade(value):
    """
    Database Question.grade is String(8).

    Therefore:
        11    -> "11"
        "11"  -> "11"
        None  -> None
    """

    if value is None:
        return None

    return str(value).strip()


# ============================================================
# QUESTION ID
# ============================================================

def normalize_question_id(value):
    """
    JSON question ID such as:

        11021

    or:

        "11021"

    is stored as:

        "11021"
    """

    if value is None:
        return None

    value = str(value).strip()

    return value if value else None


# ============================================================
# CORRECT ANSWER CONVERSION
# ============================================================

CORRECT_MAP = {
    "A": 0,
    "B": 1,
    "C": 2,
    "D": 3,
}


def normalize_correct(value):
    """
    Convert:

        A -> 0
        B -> 1
        C -> 2
        D -> 3

    Also accepts 0, 1, 2, 3.
    """

    if value is None:
        raise ValueError("Missing correct answer")

    # Already numeric
    if isinstance(value, int):
        if value in (0, 1, 2, 3):
            return value

        raise ValueError(
            f"Invalid correct answer index: {value}"
        )

    value = str(value).strip().upper()

    if value in CORRECT_MAP:
        return CORRECT_MAP[value]

    # Handle numeric strings
    try:
        numeric = int(value)

        if numeric in (0, 1, 2, 3):
            return numeric

    except ValueError:
        pass

    raise ValueError(
        f"Invalid correct answer: {value}. "
        f"Expected A, B, C, D or 0, 1, 2, 3."
    )


# ============================================================
# JSON FILE LOADER
# ============================================================

def load_json_file(path):
    """
    Supports either:

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

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        questions = data.get("questions")

        if isinstance(questions, list):
            return questions

    raise ValueError(
        "JSON must contain either a list of questions "
        "or an object with a 'questions' array."
    )


# ============================================================
# QUESTION VALIDATION
# ============================================================

REQUIRED_FIELDS = [
    "subject",
    "board",
    "grade",
    "question",
    "options",
    "correct",
]


def validate_question(question):
    """
    Validate the minimum structure required by Question.
    """

    if not isinstance(question, dict):
        raise ValueError(
            "Question must be a JSON object."
        )

    # Required top-level fields
    for field in REQUIRED_FIELDS:

        if field not in question:
            raise ValueError(
                f"Missing required field: {field}"
            )

    # Options
    options = question.get("options")

    if not isinstance(options, dict):
        raise ValueError(
            "'options' must be an object."
        )

    for option in ("A", "B", "C", "D"):

        if option not in options:
            raise ValueError(
                f"Missing option: {option}"
            )

        if options[option] is None:
            raise ValueError(
                f"Option {option} cannot be null."
            )

    # Correct answer
    normalize_correct(
        question.get("correct")
    )

    # Question text
    if not str(question.get("question", "")).strip():
        raise ValueError(
            "Question text cannot be empty."
        )


# ============================================================
# DUPLICATE CHECK
# ============================================================

def find_existing_question(db: Session, question):
    """
    Check for duplicates using two strategies.

    1. Generated question_id
    2. subject + board + grade + question text

    Returns:
        Existing Question object
        or None
    """

    question_id = normalize_question_id(
        question.get("id")
    )

    # --------------------------------------------------------
    # First: check question_id
    # --------------------------------------------------------

    if question_id:

        existing = (
            db.query(models.Question)
            .filter(
                models.Question.question_id == question_id
            )
            .first()
        )

        if existing:
            return existing

    # --------------------------------------------------------
    # Second: check content identity
    # --------------------------------------------------------

    subject = str(
        question.get("subject", "")
    ).strip()

    board = str(
        question.get("board", "")
    ).strip()

    grade = normalize_grade(
        question.get("grade")
    )

    question_text = str(
        question.get("question", "")
    ).strip()

    existing = (
        db.query(models.Question)
        .filter(
            models.Question.subject == subject,
            models.Question.board == board,
            models.Question.grade == grade,
            models.Question.question == question_text,
        )
        .first()
    )

    return existing


# ============================================================
# CREATE QUESTION OBJECT
# ============================================================

def build_question_model(question):
    """
    Convert JSON question into models.Question.
    """

    validate_question(question)

    options = question["options"]

    # --------------------------------------------------------
    # Normalize values
    # --------------------------------------------------------

    question_id = normalize_question_id(
        question.get("id")
    )

    subject = str(
        question["subject"]
    ).strip()

    board = str(
        question["board"]
    ).strip()

    # IMPORTANT:
    # Question.grade is String(8)
    grade = normalize_grade(
        question["grade"]
    )

    question_text = str(
        question["question"]
    ).strip()

    correct = normalize_correct(
        question["correct"]
    )

    level = get_level(
        question
    )

    # --------------------------------------------------------
    # Create SQLAlchemy object
    # --------------------------------------------------------

    return models.Question(

        # Generated question-bank ID
        question_id=question_id,

        # Curriculum
        subject=subject,
        board=board,
        grade=grade,

        # ERP level
        level=level,

        # Question
        question=question_text,

        option_a=str(
            options["A"]
        ),

        option_b=str(
            options["B"]
        ),

        option_c=str(
            options["C"]
        ),

        option_d=str(
            options["D"]
        ),

        # 0=A, 1=B, 2=C, 3=D
        correct=correct,

        explanation=str(
            question.get(
                "explanation",
                ""
            ) or ""
        ),

        # Metadata
        world=question.get("world"),
        chapter=question.get("chapter"),
        topic=question.get("topic"),
        stage=question.get("stage"),
        cognitive_skill=question.get(
            "cognitive_skill"
        ),

        question_type=str(
            question.get(
                "question_type",
                "mcq"
            )
        ).strip().lower(),

        # Timing
        time_limit=(
            int(question["time_limit"])
            if question.get("time_limit") is not None
            else None
        ),

        hint=question.get("hint"),

        # Publishing
        status=str(
            question.get(
                "status",
                "published"
            )
        ).strip().lower(),

        version=int(
            question.get(
                "version",
                1
            )
        ),
    )


# ============================================================
# SEED QUESTIONS FROM ONE FILE
# ============================================================

def seed_question_file(db: Session, json_path: Path):
    """
    Process one JSON file.

    Returns:
        (inserted, skipped, errors)
    """

    print()
    print("=" * 70)
    print(f"Processing: {json_path}")
    print("=" * 70)

    try:
        questions = load_json_file(
            json_path
        )

    except Exception as exc:
        print(
            f"  ERROR: Could not read JSON file: {exc}"
        )

        return 0, 0, 1

    inserted = 0
    skipped = 0
    errors = 0

    print(
        f"  Found {len(questions)} question(s)"
    )

    for index, question in enumerate(
        questions,
        start=1
    ):

        try:

            # ------------------------------------------------
            # Validate
            # ------------------------------------------------

            validate_question(
                question
            )

            # ------------------------------------------------
            # Duplicate check
            # ------------------------------------------------

            existing = find_existing_question(
                db,
                question
            )

            if existing:

                question_id = normalize_question_id(
                    question.get("id")
                )

                if question_id and existing.question_id == question_id:
                    reason = (
                        f"question_id '{question_id}' "
                        f"already exists"
                    )
                else:
                    reason = (
                        "same subject + board + grade "
                        "+ question already exists"
                    )

                print(
                    f"  SKIP #{index}: {reason}"
                )

                skipped += 1
                continue

            # ------------------------------------------------
            # Build model
            # ------------------------------------------------

            question_obj = build_question_model(
                question
            )

            # ------------------------------------------------
            # Insert
            # ------------------------------------------------

            db.add(
                question_obj
            )

            # Flush so PostgreSQL validates the record
            # immediately and generates the DB ID.
            db.flush()

            print(
                f"  OK   #{index}: "
                f"{question_obj.question_id or question_obj.id}"
            )

            inserted += 1

        except Exception as exc:

            # Roll back only this failed transaction state.
            # Then continue processing remaining questions.
            db.rollback()

            print(
                f"  ERROR #{index}: {exc}"
            )

            errors += 1

    # --------------------------------------------------------
    # Commit successfully added questions
    # --------------------------------------------------------

    try:

        db.commit()

    except Exception as exc:

        db.rollback()

        print(
            f"  ERROR: Commit failed: {exc}"
        )

        # The whole batch could not be committed.
        errors += inserted
        inserted = 0

    print()
    print(
        f"  Inserted : {inserted}"
    )
    print(
        f"  Skipped  : {skipped}"
    )
    print(
        f"  Errors   : {errors}"
    )

    return inserted, skipped, errors


# ============================================================
# SEED ALL QUESTION FILES
# ============================================================

def seed_all_questions(db: Session):
    """
    Recursively find and process every JSON file
    under the questions directory.
    """

    if not QUESTIONS_DIR.exists():

        print()
        print(
            f"Questions directory does not exist:"
        )
        print(
            f"  {QUESTIONS_DIR}"
        )
        print()
        print(
            "Create the directory and put your JSON "
            "question files inside it."
        )

        return

    # --------------------------------------------------------
    # Recursive JSON discovery
    # --------------------------------------------------------

    json_files = sorted(
        QUESTIONS_DIR.rglob("*.json")
    )

    if not json_files:

        print()
        print(
            f"No JSON files found in:"
        )
        print(
            f"  {QUESTIONS_DIR}"
        )

        return

    print()
    print("=" * 70)
    print("QUESTION SEEDING")
    print("=" * 70)

    print(
        f"Questions directory: {QUESTIONS_DIR}"
    )

    print(
        f"JSON files found: {len(json_files)}"
    )

    total_inserted = 0
    total_skipped = 0
    total_errors = 0

    # --------------------------------------------------------
    # Process every file
    # --------------------------------------------------------

    for json_path in json_files:

        inserted, skipped, errors = (
            seed_question_file(
                db,
                json_path
            )
        )

        total_inserted += inserted
        total_skipped += skipped
        total_errors += errors

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("QUESTION SEEDING COMPLETE")
    print("=" * 70)

    print(
        f"Files processed : {len(json_files)}"
    )

    print(
        f"Questions added : {total_inserted}"
    )

    print(
        f"Questions skipped: {total_skipped}"
    )

    print(
        f"Errors          : {total_errors}"
    )

    print("=" * 70)


# ============================================================
# DEFAULT ADMIN
# ============================================================

def seed_admin(db: Session):
    """
    Create the default admin if it does not exist.

    Adjust password handling here to match your
    existing authentication implementation.
    """

    existing = (
        db.query(models.User)
        .filter(
            models.User.userid
            == DEFAULT_ADMIN_USERID
        )
        .first()
    )

    if existing:
        print(
            "Admin already exists - skipping."
        )
        return

    # --------------------------------------------------------
    # IMPORTANT
    # --------------------------------------------------------
    # Replace this with your application's password hashing
    # function if the admin should have a login password.
    #
    # Example:
    #
    # hashed_password = hash_password("your-password")
    #
    # --------------------------------------------------------

    admin = models.User(
        userid=DEFAULT_ADMIN_USERID,
        email=DEFAULT_ADMIN_EMAIL,
        name=DEFAULT_ADMIN_NAME,
        role=models.Role.admin,
        account_tier=models.AccountTier.premium,
        grade=None,
        board=None,
        avatar="🦊",
        theme="classic",
        is_active=True,
        must_reset_password=False,
    )

    db.add(admin)

    try:
        db.commit()

        print(
            f"Created admin: {DEFAULT_ADMIN_USERID}"
        )

    except Exception as exc:

        db.rollback()

        print(
            f"ERROR creating admin: {exc}"
        )


# ============================================================
# SUBJECTS
# ============================================================

def seed_subjects(db: Session):
    """
    Add standard subjects if they don't already exist.

    Modify this list to match your ERP.
    """
	subjects = [ 
		{
		 	"key": "chemistry", 
			"name": "Chemistry", 
			"icon": "🧪", 
		}, 
		{ 	
			"key": "physics", 
			"name": "Physics", 
			"icon": "⚛️", 
		}, 
		{ 
			"key": "botany", 
			"name": "Botany", 
			"icon": "🌿", 
		}, 
		{ 
			"key": "zoology", 
			"name": "Zoology", 
			"icon": "🐾", 
		},
		{ 
			"key": "commerce", 
			"name": "Commerce", 
			"icon": "💼", 
		}, 
		{ 	
			"key": "accounts", 
			"name": "Accounts", 
			"icon": "📒", 
		}, 
		{ 
			"key": "mathematics", 
			"name": "Mathematics", 
			"icon": "📐", 
		}, 
		{ 
			"key": "nutrition", 
			"name": "Nutrition", 
			"icon": "🍎", 
		}, 
		{ 
			"key": "science", 
			"name": "Science", 
			"icon": "🧪", 
		}, 
		{ 
			"key": "social", 
			"name": "Social Studies", 
			"icon": "📒", 
		}, 
		{ 
			"key": "english", 
			"name": "English", 
			"icon": "A", 
		}, 
		{ 
			"key": "computer_science", 
			"name": "Computer Science", 
			"icon": "A", 
		}, 
		]
		print() 
		print("=" * 70) 
		print("CHECKING SUBJECTS") 
		print("=" * 70)

    for item in subjects:

        existing = (
            db.query(models.Subject)
            .filter(
                models.Subject.key
                == item["key"]
            )
            .first()
        )

        if existing:
		print( f" EXISTS: {item['name']} " f"(id={existing.id})" )
		continue
	try:
        	subject = models.Subject(
            	key=item["key"],
            	name=item["name"],
            	icon=item["icon"],
       	        demo_level_cap=5,
        	)

        db.add(subject)

    try:

        db.commit()

        print(
            "Subjects seeded."
        )

    except Exception as exc:

        db.rollback()

        print(
            f"ERROR seeding subjects: {exc}"
        )

def repair_sequences(db):
    """
    Synchronize PostgreSQL sequences with MAX(id).
    """

    tables = [
        ("subjects", "id"),
        ("grade_subjects", "id"),
        ("questions", "id"),
        ("progress", "id"),
        ("password_reset_tokens", "id"),
        ("themes", "id"),
        ("theme_icons", "id"),
    ]

    from sqlalchemy import text

    for table, column in tables:

        try:
            db.execute(
                text(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence(
                            '{table}',
                            '{column}'
                        ),
                        COALESCE(
                            (SELECT MAX({column}) FROM {table}),
                            1
                        ),
                        true
                    )
                    """
                )
            )

        except Exception as exc:

            print(
                f"  WARNING: Could not repair "
                f"{table}.{column}: {exc}"
            )

    db.commit()

    print("Database sequences synchronized.")
# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("ERP DATABASE SEEDER")
    print("=" * 70)

    # --------------------------------------------------------
    # Create tables if they don't exist
    # --------------------------------------------------------

    print()
    print("Checking database tables...")

    Base.metadata.create_all(
        bind=engine
    )

    print(
        "Database tables ready."
    )

    # --------------------------------------------------------
    # Database session
    # --------------------------------------------------------

    db = SessionLocal()

    try:

        # ----------------------------------------------------
        # Admin
        # ----------------------------------------------------

        print()
        print("Checking admin...")

        seed_admin(
            db
        )

        # ----------------------------------------------------
        # Subjects
        # ----------------------------------------------------

        print()
        print("Checking subjects...")
        repair_sequences(db)

        seed_subjects(
            db
        )

        # ----------------------------------------------------
        # Questions
        # ----------------------------------------------------

        seed_all_questions(
            db
        )

    finally:

        db.close()

    print()
    print("=" * 70)
    print("SEEDER FINISHED")
    print("=" * 70)
    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
