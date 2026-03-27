import sqlite3


class CasualQuizRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert_channel(self, channel_id: int) -> None:
        self.conn.execute(
            """
            INSERT INTO casual_quiz_channels (channel_id, is_active, current_question_id)
            VALUES (?, 0, NULL)
            ON CONFLICT(channel_id)
            DO UPDATE SET updated_at = CURRENT_TIMESTAMP
            """,
            (channel_id,),
        )
        self.conn.commit()

    def set_active(self, channel_id: int, is_active: bool) -> None:
        self.conn.execute(
            """
            INSERT INTO casual_quiz_channels (channel_id, is_active, current_question_id)
            VALUES (?, ?, NULL)
            ON CONFLICT(channel_id)
            DO UPDATE SET
                is_active = excluded.is_active,
                updated_at = CURRENT_TIMESTAMP
            """,
            (channel_id, 1 if is_active else 0),
        )
        self.conn.commit()

    def set_current_question(self, channel_id: int, question_id: int | None) -> None:
        self.conn.execute(
            """
            INSERT INTO casual_quiz_channels (channel_id, is_active, current_question_id)
            VALUES (?, 1, ?)
            ON CONFLICT(channel_id)
            DO UPDATE SET
                current_question_id = excluded.current_question_id,
                last_asked_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """,
            (channel_id, question_id),
        )
        self.conn.commit()

    def get_channel_state(self, channel_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM casual_quiz_channels
            WHERE channel_id = ?
            """,
            (channel_id,),
        ).fetchone()

    def get_active_channels(self) -> list[int]:
        rows = self.conn.execute(
            """
            SELECT channel_id
            FROM casual_quiz_channels
            WHERE is_active = 1
            """
        ).fetchall()

        return [int(row["channel_id"]) for row in rows]

    def mark_question_asked(self, channel_id: int, question_id: int) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO quiz_question_history (channel_id, question_id)
            VALUES (?, ?)
            """,
            (channel_id, question_id),
        )
        self.conn.commit()

    def get_asked_question_ids(self, channel_id: int) -> set[int]:
        rows = self.conn.execute(
            """
            SELECT question_id
            FROM quiz_question_history
            WHERE channel_id = ?
            """,
            (channel_id,),
        ).fetchall()

        return {int(row["question_id"]) for row in rows}

    def clear_history(self, channel_id: int) -> None:
        self.conn.execute(
            "DELETE FROM quiz_question_history WHERE channel_id = ?",
            (channel_id,),
        )
        self.conn.commit()