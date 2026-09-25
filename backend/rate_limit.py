"""
Shared rate-limiter instance, kept in its own module so both `main.py`
(which registers it) and individual routers (which apply `@limiter.limit(...)`
to specific endpoints) can import it without a circular import.

Limits are keyed by client IP address. This is deliberately applied only to
the auth endpoints most attractive to brute-forcing or spamming (login,
forgot-password) — not globally, so normal use of the app is unaffected.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
