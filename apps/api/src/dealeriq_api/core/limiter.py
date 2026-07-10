"""Rate limiting (API-003, ADR-020): slowapi, in-memory store. Applied to auth endpoints."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
