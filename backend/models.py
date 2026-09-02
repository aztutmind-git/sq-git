import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, ForeignKey, DateTime, JSON, Enum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    student = "student"
    admin = "admin"


class User(Base):
    """Both students and admins live here, distinguished by `role`."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    userid = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)  # real address (Gmail/Yahoo/etc.) for password-reset emails
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(120), nullable=False)
    role = Column(Enum(Role), nullable=False, default=Role.student)

    # student-only profile fields (nullable for admins)
    grade = Column(String(8), nullable=True)
    board = Column(String(16), nullable=True)
    avatar = Column(String(8), nullable=True, default="🦊")

    is_active = Column(Boolean, default=True, nullable=False)
    must_reset_password = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    progress = relationship("Progress", back_populates="user", cascade="all, delete-orphan")
    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject = Column(String(32), nullable=False, index=True)
    level = Column(Integer, nullable=False, index=True)  # 1..5 — level a student must clear
    board = Column(String(16), nullable=False, default="CBSE")
    question = Column(String(1000), nullable=False)
    option_a = Column(String(500), nullable=False)
    option_b = Column(String(500), nullable=False)
    option_c = Column(String(500), nullable=False)
    option_d = Column(String(500), nullable=False)
    correct = Column(Integer, nullable=False)  # 0=A, 1=B, 2=C, 3=D
    explanation = Column(String(1000), nullable=True, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Progress(Base):
    """Per-student, per-subject progress: which level is unlocked, xp, stars per level."""
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("user_id", "subject", name="uq_progress_user_subject"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject = Column(String(32), nullable=False)
    unlocked_level = Column(Integer, nullable=False, default=1)
    xp = Column(Integer, nullable=False, default=0)
    stars = Column(JSON, nullable=False, default=dict)  # {"1": 3, "2": 2, ...}

    user = relationship("User", back_populates="progress")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reset_tokens")
