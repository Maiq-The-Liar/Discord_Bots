import sqlite3


class GuildRoleRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_mapping(self, guild_id: int, role_key: str) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT guild_id, role_key, role_id, role_name, updated_at
            FROM guild_role_mappings
            WHERE guild_id = ? AND role_key = ?
            """,
            (guild_id, role_key),
        ).fetchone()

    def upsert_mapping(
        self,
        guild_id: int,
        role_key: str,
        role_id: int,
        role_name: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO guild_role_mappings (guild_id, role_key, role_id, role_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, role_key)
            DO UPDATE SET
                role_id = excluded.role_id,
                role_name = excluded.role_name,
                updated_at = CURRENT_TIMESTAMP
            """,
            (guild_id, role_key, role_id, role_name),
        )
        self.conn.commit()