from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from deps import get_current_user
from rate_limit import limiter
from security import (
    verify_password, hash_password, create_access_token,
    generate_reset_token, hash_reset_token,
)
from config import settings
from email_utils import send_password_reset_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=schemas.TokenResponse)
def whoami(user: models.User = Depends(get_current_user)):
    # access_token is left blank here — the client already has its token and
    # just needs the profile fields to resume the session after a reload.
    return schemas.TokenResponse(
        access_token="", role=user.role.value, name=user.name, userid=user.userid,
        avatar=user.avatar, grade=user.grade, board=user.board,
        must_reset_password=user.must_reset_password,
    )


@router.post("/set-password")
def set_password(payload: schemas.SetPasswordRequest, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    """Used by an already-authenticated user to set a new password — this is
    how the forced first-login reset is completed (no old password required,
    since the user already proved identity via their JWT)."""
    user.hashed_password = hash_password(payload.new_password)
    user.must_reset_password = False
    db.commit()
    return {"message": "Password updated."}


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("8/minute")
def login(request: Request, payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.userid.ilike(payload.userid), models.User.is_active == True  # noqa: E712
    ).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect user ID or password")

    token = create_access_token(user.id, user.userid, user.role.value)
    return schemas.TokenResponse(
        access_token=token,
        role=user.role.value,
        name=user.name,
        userid=user.userid,
        avatar=user.avatar,
        grade=user.grade,
        board=user.board,
        must_reset_password=user.must_reset_password,
    )


@router.post("/forgot-password", response_model=schemas.ForgotPasswordResponse)
@limiter.limit("4/minute")
def forgot_password(request: Request, payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.userid.ilike(payload.userid)).first()

    # Always return a 200 with a generic message — never reveal whether a
    # user ID exists, to avoid leaking account information.
    generic = schemas.ForgotPasswordResponse(
        message="If that user ID exists, a password reset link has been generated."
    )
    if not user:
        return generic

    raw_token, token_hash, expires_at = generate_reset_token()
    reset_row = models.PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
    db.add(reset_row)
    db.commit()

    reset_link = f"{settings.FRONTEND_RESET_URL}?token={raw_token}"

    sent = False
    if user.email:
        sent = send_password_reset_email(to_name=user.name, to_email=user.email, reset_link=reset_link)

    if sent:
        return generic

    # No SMTP configured (dev/demo mode) — surface the token/link directly
    # so the flow is testable without an email server. Remove this branch's
    # fields from the response in production once SMTP is set up.
    generic.reset_token = raw_token
    generic.reset_link = reset_link
    return generic


@router.post("/reset-password")
@limiter.limit("10/minute")
def reset_password(request: Request, payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hash_reset_token(payload.token)
    row = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token_hash == token_hash,
        models.PasswordResetToken.used == False,  # noqa: E712
    ).first()

    if not row or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link is invalid or has expired")

    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link is invalid or has expired")

    user.hashed_password = hash_password(payload.new_password)
    row.used = True
    db.commit()
    return {"message": "Password has been reset. You can now log in with your new password."}
