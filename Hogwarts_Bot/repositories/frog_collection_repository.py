import sqlite3


class FrogCollectionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_card_quantity(self, user_id: int, card_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT quantity
            FROM user_chocolate_frog_cards
            WHERE user_id = ? AND card_id = ?
            """,
            (user_id, card_id),
        ).fetchone()

        return int(row["quantity"]) if row else 0

    def add_card(self, user_id: int, card_id: int, amount: int = 1) -> None:
        self.conn.execute(
            """
            INSERT INTO user_chocolate_frog_cards (user_id, card_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, card_id)
            DO UPDATE SET
                quantity = quantity + excluded.quantity,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, card_id, amount),
        )
        self.conn.commit()

    def remove_card(self, user_id: int, card_id: int, amount: int = 1) -> bool:
        current_quantity = self.get_card_quantity(user_id, card_id)
        if current_quantity < amount:
            return False

        new_quantity = current_quantity - amount

        if new_quantity > 0:
            self.conn.execute(
                """
                UPDATE user_chocolate_frog_cards
                SET quantity = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND card_id = ?
                """,
                (new_quantity, user_id, card_id),
            )
        else:
            self.conn.execute(
                """
                DELETE FROM user_chocolate_frog_cards
                WHERE user_id = ? AND card_id = ?
                """,
                (user_id, card_id),
            )

        self.conn.commit()
        return True

    def get_unique_count(self, user_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM user_chocolate_frog_cards
            WHERE user_id = ? AND quantity > 0
            """,
            (user_id,),
        ).fetchone()

        return int(row["total"]) if row else 0

    def get_all_cards_for_user(self, user_id: int) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT card_id, quantity, first_discovered_at
            FROM user_chocolate_frog_cards
            WHERE user_id = ? AND quantity > 0
            ORDER BY card_id ASC
            """,
            (user_id,),
        ).fetchall()

        return [
            {
                "card_id": int(row["card_id"]),
                "quantity": int(row["quantity"]),
                "first_discovered_at": row["first_discovered_at"],
            }
            for row in rows
        ]