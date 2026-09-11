from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from deps import get_current_user, require_admin

router = APIRouter(prefix="/api", tags=["subjects"])


@router.get("/subjects", response_model=list[schemas.SubjectOut])
def list_subjects(db: Session = Depends(get_db), _user: models.User = Depends(get_current_user)):
    return db.query(models.Subject).order_by(models.Subject.name).all()


@router.get("/admin/subjects", response_model=list[schemas.SubjectOut])
def admin_list_subjects(db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    return db.query(models.Subject).order_by(models.Subject.name).all()


@router.put("/admin/subjects/{key}", response_model=schemas.SubjectOut)
def admin_update_subject(key: str, payload: schemas.SubjectUpdate, db: Session = Depends(get_db),
                          _admin: models.User = Depends(require_admin)):
    subject = db.query(models.Subject).filter(models.Subject.key == key).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    subject.demo_level_cap = payload.demo_level_cap
    db.commit()
    db.refresh(subject)
    return subject
