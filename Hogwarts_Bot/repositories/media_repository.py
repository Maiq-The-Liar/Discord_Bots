import sqlite3


class MediaRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add_media_channel(self, channel_id: int) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO media_channels (channel_id)
            VALUES (?)
            """,
            (channel_id,),
        )
        self.conn.commit()

    def remove_media_channel(self, channel_id: int) -> None:
        self.conn.execute(
            "DELETE FROM media_channels WHERE channel_id = ?",
            (channel_id,),
        )
        self.conn.commit()

    def is_media_channel(self, channel_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM media_channels WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
        return row is not None

    def create_media_post(
        self,
        message_id: int,
        channel_id: int,
        author_user_id: int,
        closes_at: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO media_posts (
                message_id,
                channel_id,
                author_user_id,
                closes_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (message_id, channel_id, author_user_id, closes_at),
        )
        self.conn.commit()

    def get_media_post(self, message_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM media_posts
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()

    def get_expired_open_posts(self, current_time_iso: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT *
            FROM media_posts
            WHERE is_closed = 0
              AND closes_at <= ?
            """,
            (current_time_iso,),
        ).fetchall()

    def get_open_post_for_user(self, author_user_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM media_posts
            WHERE author_user_id = ?
              AND is_closed = 0
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (author_user_id,),
        ).fetchone()

    def close_media_post(
        self,
        message_id: int,
        rewarded_points: int,
    ) -> None:
        self.conn.execute(
            """
            UPDATE media_posts
            SET is_closed = 1,
                rewarded_points = ?
            WHERE message_id = ?
            """,
            (rewarded_points, message_id),
        )
        self.conn.commit()

    def has_user_voted(self, message_id: int, voter_user_id: int) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM media_votes
            WHERE message_id = ? AND voter_user_id = ?
            LIMIT 1
            """,
            (message_id, voter_user_id),
        ).fetchone()
        return row is not None

    def add_vote(self, message_id: int, voter_user_id: int, voted_at: str) -> None:
        self.conn.execute(
            """
            INSERT INTO media_votes (message_id, voter_user_id, created_at)
            VALUES (?, ?, ?)
            """,
            (message_id, voter_user_id, voted_at),
        )
        self.conn.commit()

    def get_vote_count(self, message_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM media_votes
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()
        return int(row["total"]) if row else 0

    def get_last_vote_time(self, voter_user_id: int) -> str | None:
        row = self.conn.execute(
            """
            SELECT last_vote_at
            FROM media_vote_cooldowns
            WHERE voter_user_id = ?
            """,
            (voter_user_id,),
        ).fetchone()
        return row["last_vote_at"] if row else None

    def set_vote_cooldown(self, voter_user_id: int, last_vote_at: str) -> None:
        self.conn.execute(
            """
            INSERT INTO media_vote_cooldowns (voter_user_id, last_vote_at)
            VALUES (?, ?)
            ON CONFLICT(voter_user_id)
            DO UPDATE SET
                last_vote_at = excluded.last_vote_at
            """,
            (voter_user_id, last_vote_at),
        )
        self.conn.commit()