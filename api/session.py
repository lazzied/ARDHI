"""Simple SQLite-backed session storage used to keep per-user workflow state."""
from contextlib import closing
import pickle
import sqlite3
import threading
from pathlib import Path

from ardhi.config import ROOT_DIR


class SessionStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id TEXT PRIMARY KEY,
                    payload BLOB NOT NULL
                )
                """
            )
            conn.commit()

    def get(self, user_id: str, default=None):
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT payload FROM user_sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return default
        return pickle.loads(row[0])

    def __setitem__(self, user_id: str, payload: dict) -> None:
        blob = pickle.dumps(payload)
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO user_sessions (user_id, payload)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET payload = excluded.payload
                """,
                (user_id, blob),
            )
            conn.commit()

    def setdefault(self, user_id: str, default: dict):
        existing = self.get(user_id)
        if existing is not None:
            return existing
        self[user_id] = default
        return default

    def clear(self) -> None:
        with self._lock, closing(self._connect()) as conn:
            conn.execute("DELETE FROM user_sessions")
            conn.commit()


user_sessions = SessionStore(ROOT_DIR / "api_sessions.db")
