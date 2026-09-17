import io
from typing import List, Optional

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from deps import get_current_user, require_admin

router = APIRouter(prefix="/api", tags=["questions"])

LETTER_MAP = {"A": 0, "B": 1, "C": 2, "D": 3, "1": 0, "2": 1, "3": 2, "4": 3}


def _subject_exists(db: Session, subject: str) -> bool:
    """Subjects are now fully admin-manageable (create/edit/delete), so
    validity is whatever's actually in the Subject table — not a fixed set
    of the original 8. This is what lets an admin-created subject like
    "science" or "social_studies" immediately accept questions."""
    return db.query(models.Subject).filter(models.Subject.key == subject).first() is not None


def _is_level_accessible(prog: models.Progress, level: int, is_guest: bool) -> bool:
    """Mirrors routers/progress.py's rule: levels 1-5 (and all of a guest's
    demo range) stay strictly sequential; a non-guest student who has
    cleared level 5 can access every level beyond it in any order."""
    if is_guest or level <= 5:
        return level <= prog.unlocked_level
    return prog.unlocked_level >= 6


# ---------- student-facing: fetch a shuffled set of questions for a level ----------
@router.get("/questions", response_model=List[schemas.QuestionForQuiz])
def get_questions_for_quiz(
    subject: str, level: int,
    db: Session = Depends(get_db), user: models.User = Depends(get_current_user),
):
    if not _subject_exists(db, subject):
        raise HTTPException(status_code=400, detail="Unknown subject")

    prog = db.query(models.Progress).filter(
        models.Progress.user_id == user.id, models.Progress.subject == subject
    ).first()

    # Enrollment now applies uniformly — a guest is only "enrolled" in the
    # one subject they picked on their pre-demo form, same mechanism as a
    # silver/premium student's admin-managed enrollment.
    if prog and not prog.enrolled:
        raise HTTPException(status_code=403, detail="NOT_ENROLLED")

    if user.account_tier == models.AccountTier.guest:
        subj_row = db.query(models.Subject).filter(models.Subject.key == subject).first()
        demo_cap = subj_row.demo_level_cap if subj_row else 5
        if level > demo_cap:
            # Exact string the frontend matches on to show the registration
            # card instead of a generic "locked" toast. Checked before the
            # generic unlocked-level check below, since a guest's
            # unlocked_level is itself capped at demo_cap — meaning the
            # generic check would otherwise always fire first and mask this
            # more specific, actionable reason.
            raise HTTPException(status_code=403, detail="REGISTRATION_REQUIRED")

    if prog and not _is_level_accessible(prog, level, user.account_tier == models.AccountTier.guest):
        raise HTTPException(status_code=403, detail="That level is still locked")

    rows = db.query(models.Question).filter(
        models.Question.subject == subject, models.Question.level == level,
        models.Question.status != "draft",
        # A question with no grade set applies to everyone (all existing
        # content); a question with a grade set only shows to students of
        # that exact grade.
        or_(models.Question.grade.is_(None), models.Question.grade == user.grade),
    ).all()
    return [
        schemas.QuestionForQuiz(
            id=q.id, subject=q.subject, level=q.level, board=q.board, question=q.question,
            options=[q.option_a, q.option_b, q.option_c, q.option_d],
            explanation=q.explanation, correct=q.correct, hint=q.hint, time_limit=q.time_limit,
        )
        for q in rows
    ]


# ---------- admin: list all questions for a subject, grouped by level in the frontend ----------
@router.get("/admin/questions", response_model=List[schemas.QuestionOut])
def admin_list_questions(subject: Optional[str] = None, db: Session = Depends(get_db),
                          _admin: models.User = Depends(require_admin)):
    q = db.query(models.Question)
    if subject:
        q = q.filter(models.Question.subject == subject)
    return q.order_by(models.Question.subject, models.Question.level).all()


@router.post("/admin/questions", response_model=schemas.QuestionOut, status_code=status.HTTP_201_CREATED)
def admin_add_question(payload: schemas.QuestionCreate, db: Session = Depends(get_db),
                        _admin: models.User = Depends(require_admin)):
    if not _subject_exists(db, payload.subject):
        raise HTTPException(status_code=400, detail="Unknown subject")
    q = models.Question(
        subject=payload.subject, level=payload.level, board=payload.board, grade=payload.grade,
        question=payload.question,
        option_a=payload.option_a, option_b=payload.option_b, option_c=payload.option_c, option_d=payload.option_d,
        correct=payload.correct, explanation=payload.explanation,
        world=payload.world, chapter=payload.chapter, topic=payload.topic, stage=payload.stage,
        cognitive_skill=payload.cognitive_skill, question_type=payload.question_type,
        time_limit=payload.time_limit, hint=payload.hint, status=payload.status, version=payload.version,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.delete("/admin/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_question(question_id: int, db: Session = Depends(get_db),
                           _admin: models.User = Depends(require_admin)):
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(q)
    db.commit()
    return None


# ---------- admin: bulk upload from an Excel sheet ----------
# Expected columns (case-insensitive, order doesn't matter):
#   Subject | Level (1-5) | Board | Question | OptionA | OptionB | OptionC | OptionD | Correct (A-D or 1-4) | Explanation
# The Level column is what decides which level on the student's map a question
# belongs to, and therefore the score the student must clear to pass that level.
@router.post("/admin/questions/upload", response_model=schemas.ExcelUploadResult)
def admin_upload_excel(file: UploadFile = File(...), db: Session = Depends(get_db),
                        _admin: models.User = Depends(require_admin)):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Please upload a .xlsx or .xls file")

    content = file.file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read that file — is it a valid Excel file?")

    sheet = wb[wb.sheetnames[0]]
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=400, detail="The sheet is empty")

    header = [str(h).strip().lower() if h is not None else "" for h in rows[0]]

    def col(*names):
        for n in names:
            if n in header:
                return header.index(n)
        return None

    idx = {
        "subject": col("subject"),
        "level": col("level"),
        "board": col("board"),
        "grade": col("grade"),
        "question": col("question", "q"),
        "a": col("optiona", "option a", "a"),
        "b": col("optionb", "option b", "b"),
        "c": col("optionc", "option c", "c"),
        "d": col("optiond", "option d", "d"),
        "correct": col("correct", "answer"),
        "explanation": col("explanation", "expl"),
        "world": col("world"),
        "chapter": col("chapter"),
        "topic": col("topic"),
        "stage": col("stage"),
        "cognitive_skill": col("cognitiveskill", "cognitive skill"),
        "question_type": col("questiontype", "question type"),
        "time_limit": col("timelimit", "time limit"),
        "hint": col("hint"),
        "status": col("status"),
        "version": col("version"),
    }
    required = ["subject", "level", "question", "a", "b", "c", "d", "correct"]
    missing = [r for r in required if idx[r] is None]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required column(s): {', '.join(missing)}")

    added, skipped, errors = 0, 0, []
    valid_subjects = {s.key for s in db.query(models.Subject).all()}
    for row_num, row in enumerate(rows[1:], start=2):
        def get(key):
            i = idx[key]
            if i is None or i >= len(row) or row[i] is None:
                return ""
            return str(row[i]).strip()

        subject = get("subject").lower()
        level_raw = get("level")
        board = get("board") or "CBSE"
        grade = get("grade") or None
        question_text = get("question")
        a, b, c, d = get("a"), get("b"), get("c"), get("d")
        explanation = get("explanation")
        correct_raw = get("correct").upper()
        world = get("world") or None
        chapter = get("chapter") or None
        topic = get("topic") or None
        stage = get("stage") or None
        cognitive_skill = get("cognitive_skill") or None
        question_type = (get("question_type") or "mcq").lower()
        hint = get("hint") or None
        status_val = (get("status") or "published").lower()

        if subject not in valid_subjects:
            skipped += 1
            errors.append(f"Row {row_num}: unknown subject '{subject}'")
            continue
        try:
            level = int(float(level_raw))
        except ValueError:
            skipped += 1
            errors.append(f"Row {row_num}: invalid level '{level_raw}'")
            continue
        if level < 1:
            skipped += 1
            errors.append(f"Row {row_num}: level must be 1 or higher")
            continue
        if not (question_text and a and b and c and d):
            skipped += 1
            errors.append(f"Row {row_num}: missing question text or options")
            continue
        correct = LETTER_MAP.get(correct_raw)
        if correct is None:
            skipped += 1
            errors.append(f"Row {row_num}: invalid correct answer '{correct_raw}'")
            continue
        if status_val not in ("draft", "published"):
            skipped += 1
            errors.append(f"Row {row_num}: status must be 'draft' or 'published', got '{status_val}'")
            continue

        time_limit_raw = get("time_limit")
        time_limit = None
        if time_limit_raw:
            try:
                time_limit = int(float(time_limit_raw))
            except ValueError:
                skipped += 1
                errors.append(f"Row {row_num}: invalid time limit '{time_limit_raw}'")
                continue

        version_raw = get("version")
        version = 1
        if version_raw:
            try:
                version = int(float(version_raw))
            except ValueError:
                skipped += 1
                errors.append(f"Row {row_num}: invalid version '{version_raw}'")
                continue

        db.add(models.Question(
            subject=subject, level=level, board=board, grade=grade, question=question_text,
            option_a=a, option_b=b, option_c=c, option_d=d, correct=correct, explanation=explanation,
            world=world, chapter=chapter, topic=topic, stage=stage, cognitive_skill=cognitive_skill,
            question_type=question_type, time_limit=time_limit, hint=hint, status=status_val, version=version,
        ))
        added += 1

    db.commit()
    return schemas.ExcelUploadResult(added=added, skipped=skipped, errors=errors[:50])
