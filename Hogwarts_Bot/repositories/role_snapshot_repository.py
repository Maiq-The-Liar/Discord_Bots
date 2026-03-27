import sqlite3


class RoleSnapshotRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def replace_user_roles(self, user_id: int, roles: list[tuple[int, str]]) -> None:
        self.conn.execute("DELETE FROM user_role_snapshots WHERE user_id = ?", (user_id,))

        if roles:
            self.conn.executemany(
                """
                INSERT INTO user_role_snapshots (user_id, role_id, role_name, captured_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [(user_id, role_id, role_name) for role_id, role_name in roles],
            )

        self.conn.execute(
            """
            INSERT INTO user_role_sync_state (user_id, last_synced_at)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id)
            DO UPDATE SET last_synced_at = CURRENT_TIMESTAMP
            """,
            (user_id,),
        )
        self.conn.commit()