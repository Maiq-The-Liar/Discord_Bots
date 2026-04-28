import sqlite3


class UserRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ensure_user(self, user_id: int) -> None:
        self.conn.execute(
            """
            INSERT INTO users (user_id)
            VALUES (?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id,),
        )
        self.conn.execute(
            """
            INSERT INTO inventories (user_id)
            VALUES (?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id,),
        )

    def get_user(self, user_id: int) -> sqlite3.Row:
        row = self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"User {user_id} not found.")
        return row

    def add_galleons(self, user_id: int, amount: int) -> None:
        self.conn.execute(
            """
            UPDATE users
            SET galleons_balance = galleons_balance + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (amount, user_id),
        )

    def deduct_galleons(self, user_id: int, amount: int) -> bool:
        cur = self.conn.execute(
            """
            UPDATE users
            SET galleons_balance = galleons_balance - ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
              AND galleons_balance >= ?
            """,
            (amount, user_id, amount),
        )
        return cur.rowcount > 0

    def transfer_galleons(self, from_user_id: int, to_user_id: int, amount: int) -> bool:
        if amount <= 0:
            raise ValueError("Amount must be greater than 0.")

        self.ensure_user(from_user_id)
        self.ensure_user(to_user_id)

        deducted = self.conn.execute(
            """
            UPDATE users
            SET galleons_balance = galleons_balance - ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
              AND galleons_balance >= ?
            """,
            (amount, from_user_id, amount),
        )

        if deducted.rowcount <= 0:
            return False

        self.conn.execute(
            """
            UPDATE users
            SET galleons_balance = galleons_balance + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (amount, to_user_id),
        )
        return True

    def add_lifetime_house_points(self, user_id: int, points: int) -> None:
        self.conn.execute(
            """
            UPDATE users
            SET lifetime_house_points = lifetime_house_points + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (points, user_id),
        )

    def set_patronus_id(self, user_id: int, patronus_id: int) -> None:
        self.conn.execute(
            """
            UPDATE users
            SET patronus_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (str(patronus_id), user_id),
        )

    def get_patronus_id(self, user_id: int) -> int | None:
        row = self.conn.execute(
            "SELECT patronus_id FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row is None or row["patronus_id"] is None:
            return None

        return int(row["patronus_id"])

    def set_bio(self, user_id: int, bio: str) -> None:
        self.conn.execute(
            """
            UPDATE users
            SET bio = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (bio, user_id),
        )

    def get_bio(self, user_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT bio FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            return None

        return row["bio"]

    def set_birthday(self, user_id: int, day: int, month: int) -> None:
        self.conn.execute(
            """
            UPDATE users
            SET birth_day = ?,
                birth_month = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (day, month, user_id),
        )

    def clear_birthday(self, user_id: int) -> None:
        self.conn.execute(
            """
            UPDATE users
            SET birth_day = NULL,
                birth_month = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )

    def get_birthday(self, user_id: int) -> tuple[int | None, int | None]:
        row = self.conn.execute(
            """
            SELECT birth_day, birth_month
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            return None, None

        return row["birth_day"], row["birth_month"]

    def get_users_with_birthday(self, day: int, month: int) -> list[int]:
        rows = self.conn.execute(
            """
            SELECT user_id
            FROM users
            WHERE birth_day = ? AND birth_month = ?
            """,
            (day, month),
        ).fetchall()

        return [int(row["user_id"]) for row in rows]

    # -----------------------------
    # Legacy XP compatibility
    # -----------------------------
    def set_xp_and_level(
        self,
        user_id: int,
        xp: int,
        level: int,
        last_xp_at: str | None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE users
            SET xp = ?,
                level = ?,
                last_xp_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (xp, level, last_xp_at, user_id),
        )

    def get_xp_and_level(self, user_id: int) -> tuple[int, int, str | None]:
        row = self.conn.execute(
            """
            SELECT xp, level, last_xp_at
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            return 0, 1, None

        return int(row["xp"]), int(row["level"]), row["last_xp_at"]

    # -----------------------------
    # New year tracking
    # -----------------------------
    def get_year_tracking(self, user_id: int) -> sqlite3.Row:
        row = self.conn.execute(
            """
            SELECT
                user_id,
                xp,
                level,
                year_start_at,
                last_year_message_at,
                year_initialized_at
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"User {user_id} not found.")

        return row

    def set_year_tracking(
        self,
        user_id: int,
        year_start_at: str | None,
        last_year_message_at: str | None,
        year_initialized_at: str | None,
        level: int,
        xp: int = 0,
    ) -> None:
        self.conn.execute(
            """
            UPDATE users
            SET xp = ?,
                level = ?,
                year_start_at = ?,
                last_year_message_at = ?,
                year_initialized_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                xp,
                level,
                year_start_at,
                last_year_message_at,
                year_initialized_at,
                user_id,
            ),
        )

    def set_level_only(self, user_id: int, level: int, xp: int = 0) -> None:
        self.conn.execute(
            """
            UPDATE users
            SET xp = ?,
                level = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (xp, level, user_id),
        )