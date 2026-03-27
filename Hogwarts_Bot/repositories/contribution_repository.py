import sqlite3
from datetime import datetime, timezone


def current_year_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


class ContributionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add_monthly_points(
        self,
        user_id: int,
        house_name: str,
        points: int,
        year_month: str | None = None,
    ) -> None:
        if year_month is None:
            year_month = current_year_month()

        self.conn.execute(
            """
            INSERT INTO user_house_monthly_contributions (user_id, house_name, year_month, points)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, house_name, year_month)
            DO UPDATE SET
                points = points + excluded.points,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, house_name, year_month, points),
        )
        self.conn.commit()

    def get_monthly_points_for_user_house(
        self,
        user_id: int,
        house_name: str,
        year_month: str | None = None,
    ) -> int:
        if year_month is None:
            year_month = current_year_month()

        row = self.conn.execute(
            """
            SELECT points
            FROM user_house_monthly_contributions
            WHERE user_id = ? AND house_name = ? AND year_month = ?
            """,
            (user_id, house_name, year_month),
        ).fetchone()

        return int(row["points"]) if row else 0

    def get_monthly_house_total(
        self,
        house_name: str,
        year_month: str | None = None,
    ) -> int:
        if year_month is None:
            year_month = current_year_month()

        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(points), 0) AS total
            FROM user_house_monthly_contributions
            WHERE house_name = ? AND year_month = ?
            """,
            (house_name, year_month),
        ).fetchone()

        return int(row["total"]) if row else 0

    def get_all_house_totals(
        self,
        houses: list[str],
        year_month: str | None = None,
    ) -> dict[str, int]:
        if year_month is None:
            year_month = current_year_month()

        totals: dict[str, int] = {}
        for house in houses:
            totals[house] = self.get_monthly_house_total(house, year_month)

        return totals

    def get_top_contributors(
        self,
        year_month: str,
        limit: int = 3,
    ) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT
                user_id,
                SUM(points) AS total_points
            FROM user_house_monthly_contributions
            WHERE year_month = ?
            GROUP BY user_id
            HAVING SUM(points) > 0
            ORDER BY total_points DESC, user_id ASC
            LIMIT ?
            """,
            (year_month, limit),
        ).fetchall()

        return [
            {"user_id": int(row["user_id"]), "points": int(row["total_points"])}
            for row in rows
        ]

    def get_all_user_monthly_totals(
        self,
        year_month: str,
    ) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT
                user_id,
                SUM(points) AS total_points
            FROM user_house_monthly_contributions
            WHERE year_month = ?
            GROUP BY user_id
            HAVING SUM(points) != 0
            ORDER BY user_id ASC
            """,
            (year_month,),
        ).fetchall()

        return [
            {"user_id": int(row["user_id"]), "points": int(row["total_points"])}
            for row in rows
        ]

    def clear_month(
        self,
        year_month: str,
    ) -> None:
        self.conn.execute(
            """
            DELETE FROM user_house_monthly_contributions
            WHERE year_month = ?
            """,
            (year_month,),
        )
        self.conn.commit()