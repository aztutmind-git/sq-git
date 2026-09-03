from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from config import settings
import seed
import models  # noqa: F401  (ensures models are registered on Base before create_all)
from rate_limit import limiter
from routers import auth, students, questions, progress

app = FastAPI(title="SyllabusQuest API", version="1.0.0")

# ---- rate limiting (applied per-endpoint in routers/auth.py) ----
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ---- CORS ----
wide_open = settings.CORS_ORIGINS.strip() == "*"
origins = ["*"] if wide_open else [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

if wide_open:
    # allow_credentials + a literal "*" origin is actually rejected by
    # browsers anyway, so this combination silently breaks cookie/auth-header
    # requests. Loud warning here so a forgotten "*" gets caught in logs
    # before it gets caught by a confused support ticket.
    print(
        "[main] WARNING: CORS_ORIGINS is '*' — any website can call this API "
        "from a browser. Fine for local development; set CORS_ORIGINS to "
        "your real frontend domain(s) before deploying to production."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=not wide_open,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(questions.router)
app.include_router(progress.router)


@app.on_event("startup")
def on_startup():
    # For production, prefer Alembic migrations over create_all().
    seed.main()

@app.get("/api/health")
def health():
    return {"status": "ok"}
