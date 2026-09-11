from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from deps import get_current_user

router = APIRouter(prefix="/api/progress", tags=["progress"])

DEFAULT_MAX_LEVEL = 5  # shown for a subject with zero questions uploaded yet, so the map still renders
DEFAULT_DEMO_CAP = 5   # fallback if a subject has no config row yet


def _max_level_for_subject(db: Session, subject: str) -> int:
    """Highest level with at least one question — this is what makes levels
    open-ended: upload through level 12 in the Excel sheet, and students can
    progress all the way to 12 with no code change needed."""
    highest = db.query(func.max(models.Question.level)).filter(models.Question.subject == subject).scalar()
    return highest or DEFAULT_MAX_LEVEL


def _demo_cap_for_subject(db: Session, subject: str) -> int:
    row = db.query(models.Subject).filter(models.Subject.key == subject).first()
    return row.demo_level_cap if row else DEFAULT_DEMO_CAP


def _to_schema(db: Session, p: models.Progress) -> schemas.SubjectProgress:
    return schemas.SubjectProgress(
        subject=p.subject, unlocked_level=p.unlocked_level,
        max_level=_max_level_for_subject(db, p.subject),
        demo_level_cap=_demo_cap_for_subject(db, p.subject),
        xp=p.xp, stars={str(k): v for k, v in (p.stars or {}).items()},
    )


@router.get("", response_model=List[schemas.SubjectProgress])
def get_my_progress(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    query = db.query(models.Progress).filter(models.Progress.user_id == user.id)
    # Enrollment restrictions only apply to paying (silver/premium) students —
    # guests see every subject during their demo (per-subject level caps
    # already limit them), and this endpoint isn't used by admins for
    # themselves.
    if user.account_tier != models.AccountTier.guest:
        query = query.filter(models.Progress.enrolled == True)  # noqa: E712
    rows = query.all()
    return [_to_schema(db, p) for p in rows]


@router.post("/attempt", response_model=schemas.QuizAttemptResult)
def submit_attempt(payload: schemas.QuizAttemptRequest, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    prog = db.query(models.Progress).filter(
        models.Progress.user_id == user.id, models.Progress.subject == payload.subject
    ).first()
    if not prog:
        raise HTTPException(status_code=404, detail="No progress record for this subject")
    if user.account_tier != models.AccountTier.guest and not prog.enrolled:
        raise HTTPException(status_code=403, detail="NOT_ENROLLED")
    if payload.level > prog.unlocked_level:
        raise HTTPException(status_code=400, detail="That level is still locked")
    if payload.total_questions <= 0:
        raise HTTPException(status_code=400, detail="Invalid attempt")

    max_level = _max_level_for_subject(db, payload.subject)
    if user.account_tier == models.AccountTier.guest:
        # A guest's effective ceiling is whichever is lower — the subject's
        # real content, or their demo cap. This is what stops "unlocked_level"
        # from ever climbing past the cap for a guest account.
        max_level = min(max_level, _demo_cap_for_subject(db, payload.subject))

    pct = payload.correct_count / payload.total_questions
    xp_gained = payload.correct_count * 10

    if payload.out_of_hearts:
        stars = 0
    elif pct >= 0.999:
        stars = 3
    elif pct >= 0.75:
        stars = 2
    elif pct >= 0.5:
        stars = 1
    else:
        stars = 0

    passed = (not payload.out_of_hearts) and stars >= 1

    prog.xp += xp_gained
    stars_dict = dict(prog.stars or {})
    if passed:
        key = str(payload.level)
        stars_dict[key] = max(stars_dict.get(key, 0), stars)
        prog.stars = stars_dict
        if payload.level == prog.unlocked_level and prog.unlocked_level < max_level:
            prog.unlocked_level += 1

    db.commit()
    db.refresh(prog)

    return schemas.QuizAttemptResult(
        passed=passed, stars=stars, xp_gained=xp_gained, progress=_to_schema(db, prog),
    )
