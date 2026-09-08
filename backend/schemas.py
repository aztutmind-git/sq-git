from typing import Optional, List, Dict
from pydantic import BaseModel, EmailStr, Field


# ---------- auth ----------
class LoginRequest(BaseModel):
    userid: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    userid: str
    avatar: Optional[str] = None
    grade: Optional[str] = None
    board: Optional[str] = None
    must_reset_password: bool = False
    theme: str = "classic"


class ForgotPasswordRequest(BaseModel):
    userid: str


class ForgotPasswordResponse(BaseModel):
    message: str
    # Only populated when no SMTP is configured, so the demo/dev flow still works
    # without an email server. In production, remove this from the response and
    # rely solely on the emailed link.
    reset_token: Optional[str] = None
    reset_link: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


# ---------- students (admin-managed) ----------
class StudentCreate(BaseModel):
    userid: str
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    grade: str
    board: str
    avatar: str = "🦊"
    require_password_reset: bool = True


class SetPasswordRequest(BaseModel):
    """Used by an already-logged-in user to set a new password — e.g. the
    forced first-login reset, distinct from the token-based forgot-password flow."""
    new_password: str = Field(min_length=6)


class SetEmailRequest(BaseModel):
    email: EmailStr


class ThemeOut(BaseModel):
    key: str
    name: str
    icon_count: int


class SetThemeRequest(BaseModel):
    # "classic" is always valid (the permanent built-in, no image needed).
    # Anything else is checked against the themes table in the endpoint itself,
    # since Pydantic validators don't have DB access — see routers/auth.py.
    theme: str = Field(min_length=1, max_length=32)


class StudentOut(BaseModel):
    id: str
    userid: str
    email: Optional[str]
    name: str
    grade: Optional[str]
    board: Optional[str]
    avatar: Optional[str]

    class Config:
        from_attributes = True


# ---------- questions ----------
class QuestionCreate(BaseModel):
    subject: str
    level: int = Field(ge=1, le=1000)  # no real ceiling — a subject's max level is just however high its questions go
    board: str = "CBSE"
    question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct: int = Field(ge=0, le=3)
    explanation: str = ""


class QuestionOut(BaseModel):
    id: int
    subject: str
    level: int
    board: str
    question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct: int
    explanation: Optional[str]

    class Config:
        from_attributes = True


class QuestionForQuiz(BaseModel):
    """Version sent to students — options as a list, no leaking of extra fields."""
    id: int
    subject: str
    level: int
    board: str
    question: str
    options: List[str]
    explanation: Optional[str]
    correct: int  # kept server-side authoritative; fine to send since quiz is not proctored


class ExcelUploadResult(BaseModel):
    added: int
    skipped: int
    errors: List[str] = []


# ---------- progress ----------
class SubjectProgress(BaseModel):
    subject: str
    unlocked_level: int
    max_level: int  # highest level with any questions uploaded — drives the level map, no longer hardcoded
    xp: int
    stars: Dict[str, int]


class QuizAttemptRequest(BaseModel):
    subject: str
    level: int
    correct_count: int
    total_questions: int
    out_of_hearts: bool = False


class QuizAttemptResult(BaseModel):
    passed: bool
    stars: int
    xp_gained: int
    progress: SubjectProgress
