import sqlite3


class BotStateRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_value(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM bot_state WHERE key = ?",
            (key,),
        ).fetchone()

        return row["value"] if row else None

    def set_value(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO bot_state (key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        self.conn.commit()