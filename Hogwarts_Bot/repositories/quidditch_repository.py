from __future__ import annotations

import json
import random
import sqlite3


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

    def ensure_loop_control(self, guild_id: int) -> None:
        self.conn.execute(
            """
            INSERT INTO quidditch_loop_control (guild_id, is_enabled)
            VALUES (?, 1)
            ON CONFLICT(guild_id) DO NOTHING
            """,
            (guild_id,),
        )

    def set_loop_enabled(self, guild_id: int, is_enabled: bool) -> None:
        self.ensure_loop_control(guild_id)
        self.conn.execute(
            """
            UPDATE quidditch_loop_control
            SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (1 if is_enabled else 0, guild_id),
        )

    def is_loop_enabled(self, guild_id: int) -> bool:
        self.ensure_loop_control(guild_id)
        row = self.conn.execute(
            """
            SELECT is_enabled
            FROM quidditch_loop_control
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()
        return bool(row["is_enabled"]) if row is not None else True

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

    def get_next_scheduled_fixture(self, season_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM quidditch_fixtures
            WHERE season_id = ? AND status = 'scheduled'
            ORDER BY match_day ASC, starts_at ASC, id ASC
            LIMIT 1
            """,
            (season_id,),
        ).fetchone()

    def get_active_fixture(self, season_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM quidditch_fixtures
            WHERE season_id = ? AND status = 'active'
            ORDER BY match_day ASC, starts_at ASC, id ASC
            LIMIT 1
            """,
            (season_id,),
        ).fetchone()

    def get_fixture(self, fixture_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM quidditch_fixtures
            WHERE id = ?
            """,
            (fixture_id,),
        ).fetchone()

    def set_fixture_active(self, fixture_id: int, *, starts_at: str) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_fixtures
            SET status = 'active',
                starts_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (starts_at, fixture_id),
        )

    def set_fixture_scheduled(self, fixture_id: int, *, starts_at: str) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_fixtures
            SET status = 'scheduled',
                starts_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (starts_at, fixture_id),
        )

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

    def upsert_live_match_state(
        self,
        fixture_id: int,
        *,
        channel_id: int | None,
        message_id: int | None,
        image_path: str | None,
        log_entries: list[str],
        started_at: str | None,
        ends_at: str | None,
        snitch_unlocked_at: str | None,
        started_manually: bool,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO quidditch_live_match_state (
                fixture_id,
                channel_id,
                message_id,
                image_path,
                log_json,
                started_at,
                ends_at,
                snitch_unlocked_at,
                started_manually,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(fixture_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                message_id = excluded.message_id,
                image_path = excluded.image_path,
                log_json = excluded.log_json,
                started_at = excluded.started_at,
                ends_at = excluded.ends_at,
                snitch_unlocked_at = excluded.snitch_unlocked_at,
                started_manually = excluded.started_manually,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                fixture_id,
                channel_id,
                message_id,
                image_path,
                json.dumps(log_entries),
                started_at,
                ends_at,
                snitch_unlocked_at,
                1 if started_manually else 0,
            ),
        )

    def get_live_match_state(self, fixture_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM quidditch_live_match_state
            WHERE fixture_id = ?
            """,
            (fixture_id,),
        ).fetchone()

    def delete_live_match_state(self, fixture_id: int) -> None:
        self.conn.execute(
            """
            DELETE FROM quidditch_live_match_state
            WHERE fixture_id = ?
            """,
            (fixture_id,),
        )

    def get_active_test_match(self, guild_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM quidditch_test_matches
            WHERE guild_id = ? AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (guild_id,),
        ).fetchone()

    def create_test_match(
        self,
        *,
        guild_id: int,
        home_house: str,
        away_house: str,
        started_at: str,
        ends_at: str,
        snitch_unlocked_at: str,
        channel_id: int | None = None,
        message_id: int | None = None,
        image_path: str | None = None,
        log_entries: list[str] | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO quidditch_test_matches (
                guild_id,
                channel_id,
                message_id,
                home_house,
                away_house,
                status,
                log_json,
                image_path,
                started_at,
                ends_at,
                snitch_unlocked_at
            )
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                channel_id,
                message_id,
                home_house,
                away_house,
                json.dumps(log_entries or []),
                image_path,
                started_at,
                ends_at,
                snitch_unlocked_at,
            ),
        )
        return int(cur.lastrowid)

    def complete_test_match(self, test_match_id: int) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_test_matches
            SET status = 'completed',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (test_match_id,),
        )

    def random_house_pair(self) -> tuple[str, str]:
        houses = list(self.HOUSES)
        home = random.choice(houses)
        away = random.choice([h for h in houses if h != home])
        return home, away