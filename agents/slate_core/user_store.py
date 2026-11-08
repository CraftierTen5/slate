"""Per-user durable state.

Replaces the single-tenant SqlSnapshot for authenticated serving: one row per
user in slate_user_state, so each user's resumes, drafts/approvals and
interview sessions live under their own key. Isolation is structural - a
service built for user A only ever reads and writes A's row - and every
user's data survives restarts when the store is backed by a database URL.

The document shape is the same snapshot SlateService already persists
(resumes/texts/drafts/sessions). Normalized tables remain future work; the
guarantees that matter tonight (per-user durability and isolation) do not
depend on normalization.
"""
import json
import threading
from contextlib import contextmanager

SCHEMA = "CREATE TABLE IF NOT EXISTS slate_user_state (user_id TEXT PRIMARY KEY, doc TEXT NOT NULL)"

_LOCKS = {}
_LOCKS_GUARD = threading.Lock()

@contextmanager
def locked(user_id: str):
    """Process-wide per-user lock. One user's requests mutate their document
    load -> change -> save, so two concurrent requests from the SAME user could
    otherwise lose updates; this serializes them. Valid for the single-process
    serving model this app already assumes (uvicorn's sync threadpool included).
    Multi-process deployments would need real row locks instead - not claimed."""
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(user_id, threading.Lock())
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


class SqlUserStore:
    """Postgres or SQLite (anything SQLAlchemy speaks). Requires TLS in
    production: pass the provider's pooled connection URL with sslmode."""

    def __init__(self, url: str):
        from sqlalchemy import create_engine, text
        self._text = text
        self.engine = create_engine(url, future=True)
        with self.engine.begin() as c:
            c.execute(text(SCHEMA))

    def load(self, user_id: str):
        with self.engine.begin() as c:
            row = c.execute(self._text("SELECT doc FROM slate_user_state WHERE user_id = :u"),
                            {"u": user_id}).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, user_id: str, state: dict):
        doc = json.dumps(state)
        with self.engine.begin() as c:
            c.execute(self._text("DELETE FROM slate_user_state WHERE user_id = :u"), {"u": user_id})
            c.execute(self._text("INSERT INTO slate_user_state (user_id, doc) VALUES (:u, :d)"),
                      {"u": user_id, "d": doc})

    def delete(self, user_id: str):
        with self.engine.begin() as c:
            c.execute(self._text("DELETE FROM slate_user_state WHERE user_id = :u"), {"u": user_id})


class MemUserStore:
    """Ephemeral per-user store for runs with no database configured. Same
    interface and same isolation, but nothing survives a restart - the run
    instructions must say so."""

    def __init__(self):
        self._docs = {}

    def load(self, user_id: str):
        doc = self._docs.get(user_id)
        return json.loads(doc) if doc else None

    def save(self, user_id: str, state: dict):
        self._docs[user_id] = json.dumps(state)

    def delete(self, user_id: str):
        self._docs.pop(user_id, None)


class UserSnapshot:
    """Adapter: makes one user's slice of a UserStore look like the store
    SlateService already takes (load()/save(state)), so the service code and
    its tests are unchanged."""

    def __init__(self, store, user_id: str):
        self._store, self._user_id = store, user_id

    def load(self):
        return self._store.load(self._user_id)

    def save(self, state: dict):
        self._store.save(self._user_id, state)
