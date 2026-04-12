from __future__ import annotations

import sqlite3


class QuidditchProgressRepository:
    POSITION_KEYS = ("keeper", "seeker", "beater", "chaser")

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ensure_user_positions(self, user_id: int) -> None:
        for position_key in self.POSITION_KEYS:
            self.conn.execute(
                """
                INSERT INTO quidditch_position_progress (
                    user_id,
                    position_key,
                    level,
                    xp,
                    last_xp_at,
                    daily_xp,
                    daily_reset_on
                )
                VALUES (?, ?, 1, 0, NULL, 0, NULL)
                ON CONFLICT(user_id, position_key) DO NOTHING
                """,
                (user_id, position_key),
            )

    def get_progress(self, user_id: int, position_key: str) -> sqlite3.Row:
        row = self.conn.execute(
            """
            SELECT
                user_id,
                position_key,
                level,
                xp,
                last_xp_at,
                daily_xp,
                daily_reset_on,
                created_at,
                updated_at
            FROM quidditch_position_progress
            WHERE user_id = ? AND position_key = ?
            """,
            (user_id, position_key),
        ).fetchone()

        if row is None:
            raise ValueError(f"Missing Quidditch progress for user_id={user_id}, position={position_key}")

        return row

    def save_progress(
        self,
        user_id: int,
        position_key: str,
        *,
        level: int,
        xp: int,
        last_xp_at: str | None,
        daily_xp: int,
        daily_reset_on: str | None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_position_progress
            SET
                level = ?,
                xp = ?,
                last_xp_at = ?,
                daily_xp = ?,
                daily_reset_on = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND position_key = ?
            """,
            (
                level,
                xp,
                last_xp_at,
                daily_xp,
                daily_reset_on,
                user_id,
                position_key,
            ),
        )

    def get_all_progress_for_user(self, user_id: int) -> dict[str, sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT
                user_id,
                position_key,
                level,
                xp,
                last_xp_at,
                daily_xp,
                daily_reset_on,
                created_at,
                updated_at
            FROM quidditch_position_progress
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchall()

        return {str(row["position_key"]): row for row in rows}