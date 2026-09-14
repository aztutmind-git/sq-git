from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from deps import require_admin
from security import hash_password

router = APIRouter(prefix="/api/admin/students", tags=["admin-students"])

SUBJECT_KEYS = ["chemistry", "physics", "botany", "zoology", "commerce", "accounts", "mathematics", "nutrition"]


def _fresh_progress_rows(user_id: str) -> List[models.Progress]:
    return [models.Progress(user_id=user_id, subject=s, unlocked_level=1, xp=0, stars={}) for s in SUBJECT_KEYS]


@router.get("", response_model=List[schemas.StudentOut])
def list_students(db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    return db.query(models.User).filter(models.User.role == models.Role.student).order_by(models.User.name).all()


@router.post("", response_model=schemas.StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(payload: schemas.StudentCreate, db: Session = Depends(get_db),
                    _admin: models.User = Depends(require_admin)):
    exists = db.query(models.User).filter(models.User.userid.ilike(payload.userid)).first()
    if exists:
        raise HTTPException(status_code=400, detail="That user ID is already taken")

    user = models.User(
        userid=payload.userid,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
        role=models.Role.student,
        account_tier=models.AccountTier(payload.account_tier),
        grade=payload.grade,
        board=payload.board,
        avatar=payload.avatar,
        must_reset_password=payload.require_password_reset,
    )
    db.add(user)
    db.flush()  # get user.id
    for row in _fresh_progress_rows(user.id):
        db.add(row)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{student_id}/upgrade", response_model=schemas.StudentOut)
def upgrade_guest(student_id: str, payload: schemas.UpgradeGuestRequest, db: Session = Depends(get_db),
                   _admin: models.User = Depends(require_admin)):
    """Converts a guest account to Silver/Premium — sets a real password and
    tier while leaving their existing progress (levels, XP, stars) untouched,
    since it's the same underlying account, not a new one."""
    user = db.query(models.User).filter(models.User.id == student_id, models.User.role == models.Role.student).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found")
    if user.account_tier != models.AccountTier.guest:
        raise HTTPException(status_code=400, detail="This account is not a guest account")

    user.hashed_password = hash_password(payload.password)
    user.account_tier = models.AccountTier(payload.account_tier)
    user.must_reset_password = payload.require_password_reset
    if payload.email:
        user.email = payload.email
    if payload.name:
        user.name = payload.name
    if payload.grade:
        user.grade = payload.grade
    if payload.board:
        user.board = payload.board

    db.commit()
    db.refresh(user)
    return user


def _enrollment_response(db: Session, student_id: str) -> List[schemas.EnrollmentItem]:
    progress_by_subject = {p.subject: p for p in
                            db.query(models.Progress).filter(models.Progress.user_id == student_id).all()}
    subjects = db.query(models.Subject).order_by(models.Subject.name).all()
    return [
        schemas.EnrollmentItem(
            subject=s.key, name=s.name, icon=s.icon,
            # A subject with no Progress row at all (shouldn't normally
            # happen, since every subject gets one at student creation) is
            # treated as enrolled — same safe default as the column itself.
            enrolled=progress_by_subject[s.key].enrolled if s.key in progress_by_subject else True,
        )
        for s in subjects
    ]


@router.get("/{student_id}/enrollment", response_model=List[schemas.EnrollmentItem])
def get_enrollment(student_id: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == student_id, models.User.role == models.Role.student).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found")
    return _enrollment_response(db, student_id)


@router.put("/{student_id}/enrollment", response_model=List[schemas.EnrollmentItem])
def update_enrollment(student_id: str, payload: schemas.EnrollmentUpdate, db: Session = Depends(get_db),
                       _admin: models.User = Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == student_id, models.User.role == models.Role.student).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found")

    enrolled_set = set(payload.enrolled_subjects)
    rows = db.query(models.Progress).filter(models.Progress.user_id == student_id).all()
    for row in rows:
        row.enrolled = row.subject in enrolled_set
    db.commit()

    return _enrollment_response(db, student_id)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == student_id, models.User.role == models.Role.student).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(user)  # cascades to progress + reset tokens
    db.commit()
    return None
