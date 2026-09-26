import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    ForeignKey,
    DateTime,
    JSON,
    Enum,
    UniqueConstraint,
    LargeBinary,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ============================================================
# ENUMS
# ============================================================

class Role(str, enum.Enum):
    student = "student"
    admin = "admin"


class AccountTier(str, enum.Enum):
    guest = "guest"
    silver = "silver"
    premium = "premium"


# ============================================================
# USER
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=gen_uuid
    )

    userid = Column(
        String(64),
        unique=True,
        nullable=False,
        index=True
    )

    email = Column(
        String(255),
        nullable=True,
        index=True
    )

    hashed_password = Column(
        String(255),
        nullable=True
    )

    name = Column(
        String(120),
        nullable=False
    )

    role = Column(
        Enum(Role),
        nullable=False,
        default=Role.student
    )

    account_tier = Column(
        Enum(AccountTier),
        nullable=False,
        default=AccountTier.silver
    )

    grade = Column(
        String(8),
        nullable=True
    )

    board = Column(
        String(16),
        nullable=True
    )

    avatar = Column(
        String(8),
        nullable=True,
        default="🦊"
    )

    theme = Column(
        String(32),
        nullable=False,
        default="classic"
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    must_reset_password = Column(
        Boolean,
        default=False,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    progress = relationship(
        "Progress",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    reset_tokens = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )


# ============================================================
# SUBJECT
# ============================================================

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    key = Column(
        String(32),
        unique=True,
        nullable=False,
        index=True
    )

    name = Column(
        String(64),
        nullable=False
    )

    icon = Column(
        String(8),
        nullable=True
    )

    demo_level_cap = Column(
        Integer,
        nullable=False,
        default=5
    )


# ============================================================
# GRADE / SUBJECT
# ============================================================

class GradeSubject(Base):
    __tablename__ = "grade_subjects"

    __table_args__ = (
        UniqueConstraint(
            "grade",
            "subject_key",
            name="uq_grade_subject"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    grade = Column(
        String(8),
        nullable=False,
        index=True
    )

    subject_key = Column(
        String(32),
        nullable=False
    )


# ============================================================
# QUESTION
# ============================================================

class Question(Base):
    __tablename__ = "questions"

    # --------------------------------------------------------
    # Database internal ID
    # --------------------------------------------------------

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # --------------------------------------------------------
    # Question-bank ID
    #
    # Example:
    # "11021"
    #
    # This is separate from the database primary key.
    # --------------------------------------------------------

    question_id = Column(
        String(64),
        unique=True,
        nullable=True,
        index=True
    )

    # --------------------------------------------------------
    # Curriculum information
    # --------------------------------------------------------

    subject = Column(
        String(32),
        nullable=False,
        index=True
    )

    board = Column(
        String(16),
        nullable=False,
        default="CBSE",
        index=True
    )

    grade = Column(
        String(8),
        nullable=True,
        index=True
    )

    # --------------------------------------------------------
    # Difficulty / learning level
    #
    # 1 = Foundation
    # 2 = Intermediate
    # 3 = Advanced
    # 4 = Application
    # 5 = Mastery
    #
    # Adjust these values if your ERP uses a different
    # learning-level system.
    # --------------------------------------------------------

    level = Column(
        Integer,
        nullable=False,
        index=True
    )

    # --------------------------------------------------------
    # Question content
    # --------------------------------------------------------

    question = Column(
        String(1000),
        nullable=False
    )

    option_a = Column(
        String(500),
        nullable=False
    )

    option_b = Column(
        String(500),
        nullable=False
    )

    option_c = Column(
        String(500),
        nullable=False
    )

    option_d = Column(
        String(500),
        nullable=False
    )

    # 0 = A
    # 1 = B
    # 2 = C
    # 3 = D

    correct = Column(
        Integer,
        nullable=False
    )

    explanation = Column(
        String(1000),
        nullable=True,
        default=""
    )

    # --------------------------------------------------------
    # Curriculum metadata
    # --------------------------------------------------------

    world = Column(
        String(64),
        nullable=True
    )

    chapter = Column(
        String(64),
        nullable=True
    )

    topic = Column(
        String(64),
        nullable=True
    )

    stage = Column(
        String(32),
        nullable=True
    )

    cognitive_skill = Column(
        String(32),
        nullable=True
    )

    question_type = Column(
        String(16),
        nullable=False,
        default="mcq"
    )

    # --------------------------------------------------------
    # Question timing / assistance
    # --------------------------------------------------------

    time_limit = Column(
        Integer,
        nullable=True
    )

    hint = Column(
        String(500),
        nullable=True
    )

    # --------------------------------------------------------
    # Publishing/versioning
    # --------------------------------------------------------

    status = Column(
        String(16),
        nullable=False,
        default="published"
    )

    version = Column(
        Integer,
        nullable=False,
        default=1
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ============================================================
# PROGRESS
# ============================================================

class Progress(Base):
    __tablename__ = "progress"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "subject",
            name="uq_progress_user_subject"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    subject = Column(
        String(32),
        nullable=False
    )

    unlocked_level = Column(
        Integer,
        nullable=False,
        default=1
    )

    xp = Column(
        Integer,
        nullable=False,
        default=0
    )

    stars = Column(
        JSON,
        nullable=False,
        default=dict
    )

    enrolled = Column(
        Boolean,
        nullable=False,
        default=True
    )

    user = relationship(
        "User",
        back_populates="progress"
    )


# ============================================================
# PASSWORD RESET TOKEN
# ============================================================

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    token_hash = Column(
        String(255),
        nullable=False,
        index=True
    )

    expires_at = Column(
        DateTime,
        nullable=False
    )

    used = Column(
        Boolean,
        default=False,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    user = relationship(
        "User",
        back_populates="reset_tokens"
    )


# ============================================================
# THEME
# ============================================================

class Theme(Base):
    __tablename__ = "themes"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    key = Column(
        String(32),
        unique=True,
        nullable=False,
        index=True
    )

    name = Column(
        String(64),
        nullable=False
    )

    background_image = Column(
        LargeBinary,
        nullable=False
    )

    background_mime = Column(
        String(64),
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    icons = relationship(
        "ThemeIcon",
        back_populates="theme",
        cascade="all, delete-orphan",
        order_by="ThemeIcon.sort_order"
    )


# ============================================================
# THEME ICON
# ============================================================

class ThemeIcon(Base):
    __tablename__ = "theme_icons"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    theme_id = Column(
        Integer,
        ForeignKey(
            "themes.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    image = Column(
        LargeBinary,
        nullable=False
    )

    mime = Column(
        String(64),
        nullable=False
    )

    sort_order = Column(
        Integer,
        nullable=False,
        default=0
    )

    theme = relationship(
        "Theme",
        back_populates="icons"
    )

