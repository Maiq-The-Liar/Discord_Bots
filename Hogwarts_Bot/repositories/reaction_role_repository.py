import sqlite3


class ReactionRoleRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def set_channel(self, guild_id: int, channel_id: int) -> None:
        self.conn.execute(
            """
            INSERT INTO reaction_role_channels (guild_id, channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET channel_id = excluded.channel_id, updated_at = CURRENT_TIMESTAMP
            """,
            (guild_id, channel_id),
        )
        self.conn.commit()

    def get_channel(self, guild_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT guild_id, channel_id, updated_at
            FROM reaction_role_channels
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()

    def clear_message_mappings(self, guild_id: int) -> None:
        self.conn.execute(
            "DELETE FROM reaction_role_messages WHERE guild_id = ?",
            (guild_id,),
        )
        self.conn.commit()

    def add_message_mapping(
        self,
        guild_id: int,
        group_key: str,
        channel_id: int,
        message_id: int,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO reaction_role_messages (guild_id, group_key, channel_id, message_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, group_key)
            DO UPDATE SET
                channel_id = excluded.channel_id,
                message_id = excluded.message_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (guild_id, group_key, channel_id, message_id),
        )
        self.conn.commit()

    def get_message_mapping_by_message_id(self, message_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT guild_id, group_key, channel_id, message_id, updated_at
            FROM reaction_role_messages
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()

    def get_message_mapping_for_group(self, guild_id: int, group_key: str) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT guild_id, group_key, channel_id, message_id, updated_at
            FROM reaction_role_messages
            WHERE guild_id = ? AND group_key = ?
            """,
            (guild_id, group_key),
        ).fetchone()

    def upsert_membership(
        self,
        guild_id: int,
        user_id: int,
        group_key: str,
        role_key: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO reaction_role_memberships (guild_id, user_id, group_key, role_key)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id, group_key, role_key)
            DO UPDATE SET created_at = CURRENT_TIMESTAMP
            """,
            (guild_id, user_id, group_key, role_key),
        )
        self.conn.commit()

    def delete_membership(
        self,
        guild_id: int,
        user_id: int,
        group_key: str,
        role_key: str,
    ) -> None:
        self.conn.execute(
            """
            DELETE FROM reaction_role_memberships
            WHERE guild_id = ? AND user_id = ? AND group_key = ? AND role_key = ?
            """,
            (guild_id, user_id, group_key, role_key),
        )
        self.conn.commit()

    def list_user_memberships_in_group(
        self,
        guild_id: int,
        user_id: int,
        group_key: str,
    ) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT guild_id, user_id, group_key, role_key, created_at
            FROM reaction_role_memberships
            WHERE guild_id = ? AND user_id = ? AND group_key = ?
            ORDER BY role_key
            """,
            (guild_id, user_id, group_key),
        ).fetchall()

    def membership_exists(
        self,
        guild_id: int,
        user_id: int,
        group_key: str,
        role_key: str,
    ) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM reaction_role_memberships
            WHERE guild_id = ? AND user_id = ? AND group_key = ? AND role_key = ?
            """,
            (guild_id, user_id, group_key, role_key),
        ).fetchone()
        return row is not None

    def count_memberships_for_group(self, guild_id: int, group_key: str) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT role_key, COUNT(*) AS total
            FROM reaction_role_memberships
            WHERE guild_id = ? AND group_key = ?
            GROUP BY role_key
            """,
            (guild_id, group_key),
        ).fetchall()
        return {row["role_key"]: int(row["total"]) for row in rows}
    def replace_memberships_for_guild(self, guild_id: int, memberships: list[tuple[int, str, str]]) -> None:
        self.conn.execute(
            "DELETE FROM reaction_role_memberships WHERE guild_id = ?",
            (guild_id,),
        )
        self.conn.executemany(
            """
            INSERT INTO reaction_role_memberships (guild_id, user_id, group_key, role_key)
            VALUES (?, ?, ?, ?)
            """,
            [(guild_id, user_id, group_key, role_key) for user_id, group_key, role_key in memberships],
        )
        self.conn.commit()
