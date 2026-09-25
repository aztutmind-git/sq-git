# SyllabusQuest — FastAPI + PostgreSQL backend

This converts the original single-file demo into a real client/server app:

- **Backend**: FastAPI, with passwords hashed via `bcrypt` (never stored in
  plaintext), JWT-based login, and a password-reset flow (request link →
  reset). Data is read from/written to **PostgreSQL** via SQLAlchemy.
- **Frontend**: the same student/admin UI, now calling the backend over
  `fetch()` instead of keeping everything in an in-memory JS array.

```
syllabusquest/
├── backend/
│   ├── main.py              # FastAPI app + router registration
│   ├── config.py            # settings, read from .env
│   ├── database.py          # SQLAlchemy engine/session (PostgreSQL)
│   ├── models.py            # User, Question, Progress, PasswordResetToken
│   ├── schemas.py           # Pydantic request/response models
│   ├── security.py          # bcrypt hashing + JWT + reset-token helpers
│   ├── deps.py               # get_current_user / require_admin
│   ├── email_utils.py       # optional SMTP sender for reset emails
│   ├── routers/
│   │   ├── auth.py          # /api/auth/login, /forgot-password, /reset-password, /me
│   │   ├── students.py      # /api/admin/students (admin-managed accounts)
│   │   ├── questions.py     # /api/questions, /api/admin/questions (+ Excel upload)
│   │   └── progress.py      # /api/progress, /api/progress/attempt
│   ├── seed.py               # creates tables + default admin + starter question bank
│   ├── seed_questions.json  # 160 starter questions (8 subjects × 5 levels)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html            # the app (login → subjects → level map → quiz → admin)
    └── reset-password.html  # page the emailed reset link points to
```

## 1. Set up PostgreSQL

```sql
CREATE DATABASE syllabusquest;
CREATE USER syllabusquest WITH PASSWORD 'syllabusquest';
GRANT ALL PRIVILEGES ON DATABASE syllabusquest TO syllabusquest;
```
(Use your own values — just make sure they match `DATABASE_URL` in `.env`.)

## 2. Configure the backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env
```
Edit `.env`:
- `DATABASE_URL` — your Postgres connection string
- `SECRET_KEY` — generate one with `openssl rand -hex 32`
- `DEFAULT_ADMIN_USERID` / `DEFAULT_ADMIN_PASSWORD` — the admin account
  `seed.py` will create if none exists yet (**change the password after
  first login**)
- SMTP settings — optional. If left blank, `POST /api/auth/forgot-password`
  returns the reset link directly in its JSON response instead of emailing
  it, so the whole flow is testable without an email server.

## 3. Create tables + load the starter question bank

```bash
python seed.py
```
This creates all tables, the default admin account, and the 160 starter
questions (from `seed_questions.json`, converted from the original app's
built-in question bank). Safe to re-run — it skips anything that already
exists.

## 4. Run the API

```bash
uvicorn main:app --reload --port 8000
```
Interactive API docs: http://localhost:8000/docs

## 5. Serve the frontend

The frontend is static — serve it with anything, e.g.:
```bash
cd ../frontend
python -m http.server 5500
```
Then open http://localhost:5500/index.html.

If your backend isn't on `http://localhost:8000`, set it before the page's
scripts run, e.g. by adding this line before `index.html`'s closing
`</head>`:
```html
<script>window.SQ_API_BASE = 'https://your-api.example.com';</script>
```
Do the same for `reset-password.html`.

Also update `FRONTEND_RESET_URL` in `.env` to point at wherever
`reset-password.html` is actually hosted, so emailed reset links work.

## How login/registration works now

- There is **no self-registration or payment screen** — a student account
  can only be created by an admin, from the admin console's "Student
  accounts" panel (user ID + password + name + grade + board + avatar).
- Students log in with **user ID + password** directly on the home screen.
- "Forgot password?" is available on both the student and admin login
  screens. It requests a reset link (emailed if SMTP is configured,
  otherwise shown in-app for local testing) and lets the user set a new
  password, which is bcrypt-hashed before being stored.

## Uploading questions + level thresholds from Excel

In the admin console → "Upload questions from Excel": each row needs
`Subject, Level (1–5), Board, Question, OptionA, OptionB, OptionC, OptionD,
Correct (A–D or 1–4), Explanation (optional)`. Use "Download template" for a
starter file with the exact headers. The **Level** column is what decides
which level on a student's map the question appears in — and therefore how
many correct answers (≥50% to pass, 100% for 3 stars) they need to clear
that level and unlock the next one. Scoring and level-unlocking are
computed **server-side** (`/api/progress/attempt`) so a student can't fake
a pass from the browser console.

## Notes / next steps for production

- Replace `Base.metadata.create_all()` with **Alembic** migrations once the
  schema needs to evolve without dropping data.
- Set `CORS_ORIGINS` to your real frontend origin(s) instead of `*`.
- Put the app behind HTTPS — JWTs and passwords should never travel over
  plain HTTP outside of local development.
- Consider shortening `ACCESS_TOKEN_EXPIRE_MINUTES` and adding refresh
  tokens if you want tighter session control.
