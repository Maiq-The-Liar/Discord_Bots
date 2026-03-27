import sqlite3


class BirthdayRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_announcement(
        self,
        message_id: int,
        channel_id: int,
        birthday_user_id: int,
        announcement_date: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO birthday_announcements (
                message_id,
                channel_id,
                birthday_user_id,
                announcement_date
            )
            VALUES (?, ?, ?, ?)
            """,
            (message_id, channel_id, birthday_user_id, announcement_date),
        )
        self.conn.commit()

    def get_announcement_by_message_id(self, message_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM birthday_announcements
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()

    def has_announcement_for_user_date(
        self,
        birthday_user_id: int,
        announcement_date: str,
    ) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM birthday_announcements
            WHERE birthday_user_id = ? AND announcement_date = ?
            LIMIT 1
            """,
            (birthday_user_id, announcement_date),
        ).fetchone()

        return row is not None

    def has_user_claimed_gift(
        self,
        message_id: int,
        giver_user_id: int,
    ) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM birthday_gift_claims
            WHERE message_id = ? AND giver_user_id = ?
            LIMIT 1
            """,
            (message_id, giver_user_id),
        ).fetchone()

        return row is not None

    def record_gift_claim(
        self,
        message_id: int,
        giver_user_id: int,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO birthday_gift_claims (message_id, giver_user_id)
            VALUES (?, ?)
            """,
            (message_id, giver_user_id),
        )
        self.conn.commit()