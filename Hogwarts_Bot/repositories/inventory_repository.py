import sqlite3


class InventoryRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_inventory(self, user_id: int) -> sqlite3.Row:
        row = self.conn.execute(
            "SELECT * FROM inventories WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Inventory for user {user_id} not found.")
        return row

    def add_chocolate_frogs(self, user_id: int, amount: int) -> None:
        self.conn.execute(
            """
            UPDATE inventories
            SET chocolate_frogs = chocolate_frogs + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (amount, user_id),
        )
        self.conn.commit()

    def add_patronus_lessons(self, user_id: int, amount: int) -> None:
        self.conn.execute(
            """
            UPDATE inventories
            SET patronus_lessons = patronus_lessons + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (amount, user_id),
        )
        self.conn.commit()

    def consume_patronus_lesson(self, user_id: int, amount: int = 1) -> bool:
        cur = self.conn.execute(
            """
            UPDATE inventories
            SET patronus_lessons = patronus_lessons - ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
              AND patronus_lessons >= ?
            """,
            (amount, user_id, amount),
        )
        self.conn.commit()
        return cur.rowcount > 0