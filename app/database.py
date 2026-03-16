import hashlib
import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

LOGGER = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "skating.db") -> None:
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def backup_on_startup(self) -> None:
        if not self.db_path.exists():
            return
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"skating_{stamp}.db"
        shutil.copy2(self.db_path, backup_path)
        LOGGER.info("Database backup created: %s", backup_path)

    def init_schema(self) -> None:
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS skaters (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_types (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                rate REAL NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY,
                skater_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                lesson_type_id INTEGER NOT NULL,
                paid INTEGER DEFAULT 0,
                FOREIGN KEY(skater_id) REFERENCES skaters(id) ON DELETE CASCADE,
                FOREIGN KEY(lesson_type_id) REFERENCES lesson_types(id)
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL
            )
            """
        )
        self._migrate_legacy_schema()
        self._seed_default_admin()

    def _migrate_legacy_schema(self) -> None:
        lesson_columns = {row["name"] for row in self.fetchall("PRAGMA table_info(lessons)")}
        if "paid" not in lesson_columns:
            self.execute("ALTER TABLE lessons ADD COLUMN paid INTEGER DEFAULT 0")

        skater_columns = {row["name"] for row in self.fetchall("PRAGMA table_info(skaters)")}
        if "paid" in skater_columns:
            # Legacy field no longer used; keep schema as-is for compatibility.
            LOGGER.info("Legacy skaters.paid column detected; payment now tracked per lesson.")

    def _seed_default_admin(self) -> None:
        existing = self.fetchone("SELECT id FROM admins LIMIT 1")
        if existing:
            return
        username = os.getenv("SKATING_ADMIN_USER", "admin")
        password = os.getenv("SKATING_ADMIN_PASSWORD", "admin123")
        salt = os.urandom(16).hex()
        password_hash = self._hash_password(password, salt)
        self.execute(
            "INSERT INTO admins(username, password_hash, salt) VALUES(?, ?, ?)",
            (username, password_hash, salt),
        )
        LOGGER.warning("Seeded default admin credentials. Change immediately.")

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()

    def verify_admin(self, username: str, password: str) -> bool:
        row = self.fetchone("SELECT password_hash, salt FROM admins WHERE username=?", (username,))
        if not row:
            return False
        return self._hash_password(password, row["salt"]) == row["password_hash"]

    def execute(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        cur = self.conn.cursor()
        cur.execute(query, tuple(params))
        self.conn.commit()
        return cur

    def fetchall(self, query: str, params: Iterable[Any] = ()):
        return self.conn.execute(query, tuple(params)).fetchall()

    def fetchone(self, query: str, params: Iterable[Any] = ()):
        return self.conn.execute(query, tuple(params)).fetchone()

    def close(self) -> None:
        self.conn.close()
