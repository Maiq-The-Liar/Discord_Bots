from __future__ import annotations

import sqlite3
from typing import Iterable


class QuidditchRepository:
    HOUSES = ("Slytherin", "Ravenclaw", "Hufflepuff", "Gryffindor")

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert_config(
        self,
        guild_id: int,
        *,
        match_channel_id: int | None = None,
        scoreboard_channel_id: int | None = None,
        scoreboard_message_id: int | None = None,
    ) -> None:
        row = self.get_config(guild_id)
        if row is None:
            self.conn.execute(
                """
                INSERT INTO quidditch_config (
                    guild_id,
                    match_channel_id,
                    scoreboard_channel_id,
                    scoreboard_message_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (guild_id, match_channel_id, scoreboard_channel_id, scoreboard_message_id),
            )
            return

        self.conn.execute(
            """
            UPDATE quidditch_config
            SET
                match_channel_id = COALESCE(?, match_channel_id),
                scoreboard_channel_id = COALESCE(?, scoreboard_channel_id),
                scoreboard_message_id = COALESCE(?, scoreboard_message_id),
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (match_channel_id, scoreboard_channel_id, scoreboard_message_id, guild_id),
        )

    def clear_scoreboard_message_id(self, guild_id: int) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_config
            SET scoreboard_message_id = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (guild_id,),
        )

    def get_config(self, guild_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT guild_id, match_channel_id, scoreboard_channel_id, scoreboard_message_id, updated_at
            FROM quidditch_config
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()

    def create_season(
        self,
        guild_id: int,
        *,
        season_key: str,
        year: int,
        month: int,
        is_reduced: bool,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO quidditch_seasons (
                guild_id,
                season_key,
                year,
                month,
                is_reduced,
                status
            )
            VALUES (?, ?, ?, ?, ?, 'scheduled')
            """,
            (guild_id, season_key, year, month, 1 if is_reduced else 0),
        )
        season_id = int(cur.lastrowid)

        for house_name in self.HOUSES:
            self.conn.execute(
                """
                INSERT INTO quidditch_house_standings (
                    season_id,
                    house_name,
                    points_scored,
                    points_conceded,
                    matches_played
                )
                VALUES (?, ?, 0, 0, 0)
                """,
                (season_id, house_name),
            )

        return season_id

    def get_season_by_key(self, guild_id: int, season_key: str) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM quidditch_seasons
            WHERE guild_id = ? AND season_key = ?
            """,
            (guild_id, season_key),
        ).fetchone()

    def get_latest_season(self, guild_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM quidditch_seasons
            WHERE guild_id = ?
            ORDER BY year DESC, month DESC, id DESC
            LIMIT 1
            """,
            (guild_id,),
        ).fetchone()

    def set_season_status(self, season_id: int, status: str) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_seasons
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, season_id),
        )

    def create_fixture(
        self,
        season_id: int,
        *,
        match_day: int,
        stage: str,
        starts_at: str,
        home_house: str,
        away_house: str,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO quidditch_fixtures (
                season_id,
                match_day,
                stage,
                starts_at,
                home_house,
                away_house,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'scheduled')
            """,
            (season_id, match_day, stage, starts_at, home_house, away_house),
        )
        return int(cur.lastrowid)

    def list_fixtures_for_season(self, season_id: int) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM quidditch_fixtures
            WHERE season_id = ?
            ORDER BY match_day ASC, starts_at ASC, id ASC
            """,
            (season_id,),
        ).fetchall()
        return list(rows)

    def get_standings(self, season_id: int) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM quidditch_house_standings
            WHERE season_id = ?
            ORDER BY points_scored DESC, points_conceded ASC, house_name ASC
            """,
            (season_id,),
        ).fetchall()
        return list(rows)

    def apply_fixture_result(
        self,
        fixture_id: int,
        *,
        home_score: int,
        away_score: int,
        winner_house: str,
    ) -> None:
        fixture = self.conn.execute(
            """
            SELECT *
            FROM quidditch_fixtures
            WHERE id = ?
            """,
            (fixture_id,),
        ).fetchone()
        if fixture is None:
            raise ValueError("Fixture not found.")

        self.conn.execute(
            """
            UPDATE quidditch_fixtures
            SET
                home_score = ?,
                away_score = ?,
                winner_house = ?,
                status = 'completed',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (home_score, away_score, winner_house, fixture_id),
        )

        self.conn.execute(
            """
            UPDATE quidditch_house_standings
            SET
                points_scored = points_scored + ?,
                points_conceded = points_conceded + ?,
                matches_played = matches_played + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE season_id = ? AND house_name = ?
            """,
            (home_score, away_score, int(fixture["season_id"]), str(fixture["home_house"])),
        )

        self.conn.execute(
            """
            UPDATE quidditch_house_standings
            SET
                points_scored = points_scored + ?,
                points_conceded = points_conceded + ?,
                matches_played = matches_played + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE season_id = ? AND house_name = ?
            """,
            (away_score, home_score, int(fixture["season_id"]), str(fixture["away_house"])),
        )