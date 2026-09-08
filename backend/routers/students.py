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


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == student_id, models.User.role == models.Role.student).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(user)  # cascades to progress + reset tokens
    db.commit()
    return None
