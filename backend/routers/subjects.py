from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from deps import get_current_user, require_admin

router = APIRouter(prefix="/api", tags=["subjects"])


def get_subjects_for_grade(db: Session, grade: str) -> List[models.Subject]:
    """Subjects mapped to this grade. Falls back to every subject that
    exists if this grade has no mapping configured yet, so nothing breaks
    while the admin is still setting up grade\u2192subject mappings for new
    grade bands."""
    keys = [gs.subject_key for gs in
            db.query(models.GradeSubject).filter(models.GradeSubject.grade == grade).all()]
    if not keys:
        return db.query(models.Subject).order_by(models.Subject.name).all()
    return db.query(models.Subject).filter(models.Subject.key.in_(keys)).order_by(models.Subject.name).all()


# ---------- public (used by the guest pre-demo form and student home screen) ----------
@router.get("/grades")
def list_grades(db: Session = Depends(get_db)):
    """Every grade that has at least one subject mapped — powers the guest
    pre-demo form's Grade dropdown. No auth required, since a guest doesn't
    have an account yet at this point."""
    rows = db.query(models.GradeSubject.grade).distinct().order_by(models.GradeSubject.grade).all()
    return [r[0] for r in rows]


@router.get("/subjects", response_model=List[schemas.SubjectOut])
def list_subjects(grade: Optional[str] = None, db: Session = Depends(get_db)):
    """All subjects, or only those mapped to `grade` if given. Public (no
    auth) so the guest pre-demo form can populate its Subject dropdown
    before an account exists."""
    if grade:
        return get_subjects_for_grade(db, grade)
    return db.query(models.Subject).order_by(models.Subject.name).all()


# ---------- admin: master subject list ----------
@router.get("/admin/subjects", response_model=List[schemas.SubjectOut])
def admin_list_subjects(db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    return db.query(models.Subject).order_by(models.Subject.name).all()


@router.post("/admin/subjects", response_model=schemas.SubjectOut, status_code=201)
def admin_create_subject(payload: schemas.SubjectCreate, db: Session = Depends(get_db),
                          _admin: models.User = Depends(require_admin)):
    existing = db.query(models.Subject).filter(models.Subject.key == payload.key).first()
    if existing:
        raise HTTPException(status_code=400, detail="A subject with that key already exists")
    subject = models.Subject(
        key=payload.key, name=payload.name, icon=payload.icon, demo_level_cap=payload.demo_level_cap,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.put("/admin/subjects/{key}", response_model=schemas.SubjectOut)
def admin_update_subject(key: str, payload: schemas.SubjectUpdate, db: Session = Depends(get_db),
                          _admin: models.User = Depends(require_admin)):
    subject = db.query(models.Subject).filter(models.Subject.key == key).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    if payload.name is not None:
        subject.name = payload.name
    if payload.icon is not None:
        subject.icon = payload.icon
    if payload.demo_level_cap is not None:
        subject.demo_level_cap = payload.demo_level_cap
    db.commit()
    db.refresh(subject)
    return subject


@router.delete("/admin/subjects/{key}", status_code=204)
def admin_delete_subject(key: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    subject = db.query(models.Subject).filter(models.Subject.key == key).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    # Clean up grade mappings that reference it (no DB-level FK here, since
    # subject_key is a plain string column, not a foreign key).
    db.query(models.GradeSubject).filter(models.GradeSubject.subject_key == key).delete()
    db.delete(subject)
    db.commit()
    return None


# ---------- admin: grade \u2192 subject mapping ----------
@router.get("/admin/grade-subjects", response_model=List[schemas.GradeSubjectsOut])
def admin_list_grade_subjects(db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    grades = [r[0] for r in db.query(models.GradeSubject.grade).distinct().order_by(models.GradeSubject.grade).all()]
    return [schemas.GradeSubjectsOut(grade=g, subjects=get_subjects_for_grade(db, g)) for g in grades]


@router.put("/admin/grade-subjects/{grade}", response_model=schemas.GradeSubjectsOut)
def admin_update_grade_subjects(grade: str, payload: schemas.GradeSubjectsUpdate, db: Session = Depends(get_db),
                                 _admin: models.User = Depends(require_admin)):
    valid_keys = {s.key for s in db.query(models.Subject).all()}
    unknown = set(payload.subject_keys) - valid_keys
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown subject key(s): {', '.join(sorted(unknown))}")

    db.query(models.GradeSubject).filter(models.GradeSubject.grade == grade).delete()
    for key in payload.subject_keys:
        db.add(models.GradeSubject(grade=grade, subject_key=key))
    db.commit()

    return schemas.GradeSubjectsOut(grade=grade, subjects=get_subjects_for_grade(db, grade))


@router.delete("/admin/grade-subjects/{grade}", status_code=204)
def admin_delete_grade(grade: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    """Removes an entire grade band (e.g. if it was added by mistake)."""
    db.query(models.GradeSubject).filter(models.GradeSubject.grade == grade).delete()
    db.commit()
    return None
