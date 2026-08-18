import hashlib
import json
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional


DB_PATH = os.path.join(os.path.dirname(__file__), "app_data.db")


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10, factory=_ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    """Create and safely migrate the local SQLite schema."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('patient', 'doctor')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                total_xp INTEGER NOT NULL DEFAULT 0,
                current_streak INTEGER NOT NULL DEFAULT 0,
                last_session_date TEXT,
                total_sessions INTEGER NOT NULL DEFAULT 0,
                best_form_quality REAL NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                date TEXT NOT NULL,
                duration INTEGER NOT NULL,
                exercise_name TEXT,
                total_reps INTEGER NOT NULL DEFAULT 0,
                form_quality REAL NOT NULL DEFAULT 100,
                speed_warnings_count INTEGER NOT NULL DEFAULT 0,
                xp_earned INTEGER NOT NULL DEFAULT 0,
                landmarks_data TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS care_relationships (
                doctor_id TEXT NOT NULL,
                patient_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                PRIMARY KEY (doctor_id, patient_id),
                FOREIGN KEY(doctor_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY(patient_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS plan_assignments (
                assignment_id TEXT PRIMARY KEY,
                doctor_id TEXT NOT NULL,
                patient_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                plan_snapshot TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                assigned_at TEXT NOT NULL,
                start_date TEXT NOT NULL,
                completed_sessions INTEGER NOT NULL DEFAULT 0,
                last_completed_at TEXT,
                FOREIGN KEY(doctor_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY(patient_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS session_exercises (
                session_exercise_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                exercise_name TEXT NOT NULL,
                total_reps INTEGER NOT NULL DEFAULT 0,
                good_form_reps INTEGER NOT NULL DEFAULT 0,
                form_quality REAL NOT NULL DEFAULT 100,
                speed_warnings_count INTEGER NOT NULL DEFAULT 0,
                sets_completed INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_date ON sessions(user_id, date DESC);
            CREATE INDEX IF NOT EXISTS idx_assignments_patient ON plan_assignments(patient_id, status, assigned_at DESC);
            CREATE INDEX IF NOT EXISTS idx_assignments_doctor ON plan_assignments(doctor_id, status, assigned_at DESC);
            """
        )
        _add_column_if_missing(conn, "sessions", "plan_id", "TEXT")
        _add_column_if_missing(conn, "sessions", "assignment_id", "TEXT")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 210_000
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return f"{salt}${iterations}${password_hash.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        parts = password_hash.split("$")
        if len(parts) == 2:
            salt, hash_hex = parts
            iterations = 100_000
        elif len(parts) == 3:
            salt, iterations_text, hash_hex = parts
            iterations = int(iterations_text)
        else:
            return False
        password_check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
        return secrets.compare_digest(password_check.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def create_user(username: str, password: str, role: str) -> Optional[str]:
    username = username.strip()
    if not username or role not in {"patient", "doctor"}:
        return None
    try:
        user_id = f"{role}_{secrets.token_hex(8)}"
        now = datetime.now().isoformat()
        with _connect() as conn:
            conn.execute(
                "INSERT INTO users (user_id, username, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, hash_password(password), role, now, now),
            )
            conn.execute("INSERT INTO user_profiles (user_id) VALUES (?)", (user_id,))
        return user_id
    except sqlite3.IntegrityError:
        return None


def authenticate_user(username: str, password: str) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id, password_hash FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),)
        ).fetchone()
    return row["user_id"] if row and verify_password(password, row["password_hash"]) else None


def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT u.user_id, u.username, u.role, up.total_xp, up.current_streak,
                   up.total_sessions, up.best_form_quality, up.last_session_date
            FROM users u JOIN user_profiles up ON u.user_id = up.user_id
            WHERE u.user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def calculate_xp(total_reps: int, form_quality: float, speed_warnings: int) -> int:
    base_xp = max(total_reps, 0) * 10
    form_bonus = total_reps * 5 if form_quality >= 80 else 0
    speed_bonus = total_reps * 3 if speed_warnings == 0 else 0
    return int(base_xp + form_bonus + speed_bonus)


def _update_user_profile(
    conn: sqlite3.Connection, user_id: str, xp_earned: int, form_quality: float, session_day: date
) -> None:
    profile = conn.execute(
        "SELECT total_xp, current_streak, last_session_date, total_sessions, best_form_quality FROM user_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not profile:
        return

    last_day: Optional[date] = None
    if profile["last_session_date"]:
        try:
            last_day = datetime.fromisoformat(profile["last_session_date"]).date()
        except ValueError:
            last_day = None

    if last_day == session_day:
        streak = profile["current_streak"]
    elif last_day == session_day - timedelta(days=1):
        streak = profile["current_streak"] + 1
    else:
        streak = 1

    conn.execute(
        """
        UPDATE user_profiles
        SET total_xp = ?, current_streak = ?, last_session_date = ?,
            total_sessions = ?, best_form_quality = ?
        WHERE user_id = ?
        """,
        (
            profile["total_xp"] + xp_earned,
            streak,
            datetime.now().isoformat(),
            profile["total_sessions"] + 1,
            max(profile["best_form_quality"], form_quality),
            user_id,
        ),
    )


def save_session(user_id: str, session_data: Dict[str, Any]) -> Optional[str]:
    """Persist a session and its per-exercise results in one transaction."""
    session_id = f"session_{secrets.token_hex(12)}"
    now = datetime.now()
    total_reps = max(int(session_data.get("total_reps", 0)), 0)
    form_quality = min(max(float(session_data.get("form_quality", 100)), 0), 100)
    speed_warnings = max(int(session_data.get("speed_warnings_count", 0)), 0)
    xp_earned = calculate_xp(total_reps, form_quality, speed_warnings)

    try:
        with _connect() as conn:
            user = conn.execute("SELECT role FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not user or user["role"] != "patient":
                return None

            conn.execute(
                """
                INSERT INTO sessions
                (session_id, user_id, date, duration, exercise_name, total_reps,
                 form_quality, speed_warnings_count, xp_earned, landmarks_data, plan_id, assignment_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    now.isoformat(),
                    max(int(session_data.get("duration", 0)), 0),
                    session_data.get("exercise_name", "Unknown"),
                    total_reps,
                    form_quality,
                    speed_warnings,
                    xp_earned,
                    json.dumps(session_data.get("landmarks", [])),
                    session_data.get("plan_id"),
                    session_data.get("assignment_id"),
                ),
            )

            for result in session_data.get("exercise_results", []):
                conn.execute(
                    """
                    INSERT INTO session_exercises
                    (session_exercise_id, session_id, exercise_name, total_reps, good_form_reps,
                     form_quality, speed_warnings_count, sets_completed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"result_{secrets.token_hex(10)}",
                        session_id,
                        result.get("exercise_name", "Unknown"),
                        max(int(result.get("total_reps", 0)), 0),
                        max(int(result.get("good_form_reps", 0)), 0),
                        min(max(float(result.get("form_quality", 100)), 0), 100),
                        max(int(result.get("speed_warnings_count", 0)), 0),
                        max(int(result.get("sets_completed", 0)), 0),
                    ),
                )

            assignment_id = session_data.get("assignment_id")
            if assignment_id:
                conn.execute(
                    """
                    UPDATE plan_assignments
                    SET completed_sessions = completed_sessions + 1, last_completed_at = ?
                    WHERE assignment_id = ? AND patient_id = ? AND status = 'active'
                    """,
                    (now.isoformat(), assignment_id, user_id),
                )

            _update_user_profile(conn, user_id, xp_earned, form_quality, now.date())
        return session_id
    except (sqlite3.Error, ValueError, TypeError) as exc:
        print(f"Error saving session: {exc}")
        return None


def _exercise_results(conn: sqlite3.Connection, session_id: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT exercise_name, total_reps, good_form_reps, form_quality,
               speed_warnings_count, sets_completed
        FROM session_exercises WHERE session_id = ? ORDER BY rowid
        """,
        (session_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_user_sessions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT session_id, date, duration, exercise_name, total_reps, form_quality,
                   speed_warnings_count, xp_earned, plan_id, assignment_id
            FROM sessions WHERE user_id = ? ORDER BY date DESC LIMIT ?
            """,
            (user_id, max(1, min(limit, 200))),
        ).fetchall()
        sessions = [dict(row) for row in rows]
        for session in sessions:
            session["exercises"] = _exercise_results(conn, session["session_id"])
        return sessions


def search_patient_by_username(username: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT u.user_id, u.username, up.total_xp, up.current_streak,
                   up.total_sessions, up.best_form_quality
            FROM users u JOIN user_profiles up ON u.user_id = up.user_id
            WHERE u.role = 'patient' AND u.username = ? COLLATE NOCASE
            """,
            (username.strip(),),
        ).fetchone()
    return dict(row) if row else None


def create_care_relationship(doctor_id: str, patient_id: str) -> bool:
    try:
        with _connect() as conn:
            roles = {
                row["user_id"]: row["role"]
                for row in conn.execute("SELECT user_id, role FROM users WHERE user_id IN (?, ?)", (doctor_id, patient_id))
            }
            if roles.get(doctor_id) != "doctor" or roles.get(patient_id) != "patient":
                return False
            conn.execute(
                """
                INSERT INTO care_relationships (doctor_id, patient_id, status, created_at)
                VALUES (?, ?, 'active', ?)
                ON CONFLICT(doctor_id, patient_id) DO UPDATE SET status = 'active'
                """,
                (doctor_id, patient_id, datetime.now().isoformat()),
            )
        return True
    except sqlite3.Error:
        return False


def remove_care_relationship(doctor_id: str, patient_id: str) -> bool:
    """Deactivate a care link and pause its active plans without deleting history."""
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                UPDATE care_relationships
                SET status = 'inactive'
                WHERE doctor_id = ? AND patient_id = ? AND status = 'active'
                """,
                (doctor_id, patient_id),
            )
            if cursor.rowcount != 1:
                return False
            conn.execute(
                """
                UPDATE plan_assignments
                SET status = 'paused'
                WHERE doctor_id = ? AND patient_id = ? AND status = 'active'
                """,
                (doctor_id, patient_id),
            )
        return True
    except sqlite3.Error:
        return False


def is_doctor_for_patient(doctor_id: str, patient_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM care_relationships WHERE doctor_id = ? AND patient_id = ? AND status = 'active'",
            (doctor_id, patient_id),
        ).fetchone()
    return row is not None


def get_doctor_patients(doctor_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT u.user_id, u.username, up.total_xp, up.current_streak,
                   up.total_sessions, up.best_form_quality, cr.created_at
            FROM care_relationships cr
            JOIN users u ON u.user_id = cr.patient_id
            JOIN user_profiles up ON up.user_id = u.user_id
            WHERE cr.doctor_id = ? AND cr.status = 'active'
            ORDER BY u.username COLLATE NOCASE
            """,
            (doctor_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_plan_assignment(
    doctor_id: str, patient_id: str, plan: Dict[str, Any], notes: str = "", start_date: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    if not is_doctor_for_patient(doctor_id, patient_id):
        return None
    assignment_id = f"assignment_{secrets.token_hex(10)}"
    assigned_at = datetime.now().isoformat()
    start = start_date or date.today().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO plan_assignments
            (assignment_id, doctor_id, patient_id, plan_id, plan_snapshot, notes, assigned_at, start_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (assignment_id, doctor_id, patient_id, plan["planId"], json.dumps(plan), notes.strip(), assigned_at, start),
        )
    return get_assignment(assignment_id)


def get_assignment(assignment_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT pa.*, d.username AS doctor_username, p.username AS patient_username
            FROM plan_assignments pa
            JOIN users d ON d.user_id = pa.doctor_id
            JOIN users p ON p.user_id = pa.patient_id
            WHERE pa.assignment_id = ?
            """,
            (assignment_id,),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["plan"] = json.loads(result.pop("plan_snapshot"))
    return result


def get_patient_assignments(patient_id: str, active_only: bool = False) -> List[Dict[str, Any]]:
    query = "SELECT assignment_id FROM plan_assignments WHERE patient_id = ?"
    params: List[Any] = [patient_id]
    if active_only:
        query += " AND status = 'active'"
    query += " ORDER BY assigned_at DESC"
    with _connect() as conn:
        ids = [row["assignment_id"] for row in conn.execute(query, params).fetchall()]
    return [assignment for assignment_id in ids if (assignment := get_assignment(assignment_id))]


def update_assignment_status(assignment_id: str, patient_id: str, status: str) -> bool:
    if status not in {"active", "completed", "paused"}:
        return False
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE plan_assignments SET status = ? WHERE assignment_id = ? AND patient_id = ?",
            (status, assignment_id, patient_id),
        )
    return cursor.rowcount == 1


def get_patient_analytics(user_id: str, days: int = 30) -> Dict[str, Any]:
    profile = get_user_profile(user_id)
    if not profile or profile["role"] != "patient":
        return {}
    days = max(1, min(days, 3650))
    since = (datetime.now() - timedelta(days=days)).isoformat()
    with _connect() as conn:
        total_reps_all_time = conn.execute(
            "SELECT COALESCE(SUM(total_reps), 0) AS total FROM sessions WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"]
        rows = conn.execute(
            """
            SELECT session_id, date, duration, exercise_name, total_reps, form_quality,
                   speed_warnings_count, xp_earned, plan_id, assignment_id
            FROM sessions WHERE user_id = ? AND date >= ? ORDER BY date DESC
            """,
            (user_id, since),
        ).fetchall()
        sessions = [dict(row) for row in rows]
        for session in sessions:
            session["exercises"] = _exercise_results(conn, session["session_id"])

    avg_quality = sum(session["form_quality"] for session in sessions) / len(sessions) if sessions else 0
    return {
        "profile": profile,
        "sessions": sessions,
        "total_reps_all_time": total_reps_all_time,
        "avg_form_quality": round(avg_quality, 2),
        "total_sessions": len(sessions),
        "days": days,
        "assignments": get_patient_assignments(user_id),
    }
