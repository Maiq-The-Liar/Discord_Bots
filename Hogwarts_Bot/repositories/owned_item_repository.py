import sqlite3


class OwnedItemRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_quantity(self, user_id: int, item_key: str) -> int:
        row = self.conn.execute(
            """
            SELECT quantity
            FROM user_owned_items
            WHERE user_id = ? AND item_key = ?
            """,
            (user_id, item_key),
        ).fetchone()

        return int(row["quantity"]) if row else 0

    def add_quantity(self, user_id: int, item_key: str, amount: int) -> None:
        self.conn.execute(
            """
            INSERT INTO user_owned_items (user_id, item_key, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, item_key)
            DO UPDATE SET
                quantity = quantity + excluded.quantity,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, item_key, amount),
        )
        self.conn.commit()

    def set_quantity(self, user_id: int, item_key: str, quantity: int) -> None:
        self.conn.execute(
            """
            INSERT INTO user_owned_items (user_id, item_key, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, item_key)
            DO UPDATE SET
                quantity = excluded.quantity,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, item_key, quantity),
        )
        self.conn.commit()

    def remove_item(self, user_id: int, item_key: str, amount: int) -> bool:
        cur = self.conn.execute(
            """
            UPDATE user_owned_items
            SET quantity = quantity - ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
              AND item_key = ?
              AND quantity >= ?
            """,
            (amount, user_id, item_key, amount),
        )
        self.conn.commit()
        return cur.rowcount > 0