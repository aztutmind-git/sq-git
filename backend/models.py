import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, ForeignKey, DateTime, JSON, Enum, UniqueConstraint, LargeBinary
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    student = "student"
    admin = "admin"


class AccountTier(str, enum.Enum):
    guest = "guest"       # auto-created via "Try Demo" — no password, capped levels per subject
    silver = "silver"     # registered/paid — full concept-level access, unlimited levels
    premium = "premium"   # everything Silver has, plus the analytics dashboard (future)


class User(Base):
    """Both students and admins live here, distinguished by `role`."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    userid = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)  # real address (Gmail/Yahoo/etc.) for password-reset emails
    hashed_password = Column(String(255), nullable=True)  # null for guest accounts — they never log in with a password
    name = Column(String(120), nullable=False)
    role = Column(Enum(Role), nullable=False, default=Role.student)
    account_tier = Column(Enum(AccountTier), nullable=False, default=AccountTier.silver)

    # student-only profile fields (nullable for admins)
    grade = Column(String(8), nullable=True)
    board = Column(String(16), nullable=True)
    avatar = Column(String(8), nullable=True, default="🦊")
    theme = Column(String(32), nullable=False, default="classic")

    is_active = Column(Boolean, default=True, nullable=False)
    must_reset_password = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    progress = relationship("Progress", back_populates="user", cascade="all, delete-orphan")
    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")


class Subject(Base):
    """Config for each of the 8 subjects — mainly the guest-tier demo level
    cap, which the admin can set per subject. Subjects themselves are still
    a fixed set of 8 keys (not admin-creatable) for this phase."""
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(64), nullable=False)
    icon = Column(String(8), nullable=True)
    demo_level_cap = Column(Integer, nullable=False, default=5)


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
    # Whether this subject shows up for the student at all. Every student
    # gets a Progress row per subject at creation time (so their stats are
    # ready to go the moment they're enrolled) — this flag is what actually
    # controls visibility. Defaults True so nothing changes for any student
    # created before this feature existed.
    enrolled = Column(Boolean, nullable=False, default=True)

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


class Theme(Base):
    """An admin-uploaded visual theme: one background image plus zero or more
    character icons for level nodes. Images are stored as bytes directly in
    Postgres (not on local disk) since Render's free web service filesystem
    is wiped on every redeploy/restart — the database is the only durable
    storage available without adding a separate file-hosting service."""
    __tablename__ = "themes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(32), unique=True, nullable=False, index=True)  # slug, e.g. "ocean"
    name = Column(String(64), nullable=False)  # display name, e.g. "Ocean"
    background_image = Column(LargeBinary, nullable=False)
    background_mime = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    icons = relationship("ThemeIcon", back_populates="theme", cascade="all, delete-orphan",
                          order_by="ThemeIcon.sort_order")


class ThemeIcon(Base):
    """One character icon belonging to a Theme, used to decorate level nodes
    on the map (cycled through in order as levels go up)."""
    __tablename__ = "theme_icons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    theme_id = Column(Integer, ForeignKey("themes.id", ondelete="CASCADE"), nullable=False)
    image = Column(LargeBinary, nullable=False)
    mime = Column(String(64), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    theme = relationship("Theme", back_populates="icons")
