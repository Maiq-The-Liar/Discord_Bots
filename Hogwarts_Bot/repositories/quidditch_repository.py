from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime

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

    def set_strategy_channel(self, guild_id: int, house_name: str, channel_id: int) -> None:
        self.conn.execute(
            """
            INSERT INTO quidditch_strategy_channels (guild_id, house_name, channel_id, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id, house_name) DO UPDATE SET
                channel_id = excluded.channel_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (guild_id, house_name, channel_id),
        )

    def get_strategy_channel(self, guild_id: int, house_name: str) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT guild_id, house_name, channel_id, updated_at
            FROM quidditch_strategy_channels
            WHERE guild_id = ? AND house_name = ?
            """,
            (guild_id, house_name),
        ).fetchone()

    def list_strategy_channels(self, guild_id: int) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT guild_id, house_name, channel_id, updated_at
            FROM quidditch_strategy_channels
            WHERE guild_id = ?
            ORDER BY house_name ASC
            """,
            (guild_id,),
        ).fetchall()
        return list(rows)

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

    def get_regular_win_loss_counts(self, season_id: int) -> dict[str, tuple[int, int]]:
        rows = self.conn.execute(
            """
            SELECT home_house, away_house, home_score, away_score, winner_house
            FROM quidditch_fixtures
            WHERE season_id = ?
              AND stage = 'regular'
              AND status = 'completed'
            """,
            (season_id,),
        ).fetchall()

        totals: dict[str, list[int]] = {house: [0, 0] for house in self.HOUSES}
        for row in rows:
            home = str(row["home_house"])
            away = str(row["away_house"])
            winner = str(row["winner_house"] or "")
            if winner == home:
                totals.setdefault(home, [0, 0])[0] += 1
                totals.setdefault(away, [0, 0])[1] += 1
            elif winner == away:
                totals.setdefault(away, [0, 0])[0] += 1
                totals.setdefault(home, [0, 0])[1] += 1
            else:
                # Draws should not normally happen, but do not count either side as a loss.
                totals.setdefault(home, [0, 0])
                totals.setdefault(away, [0, 0])

        return {house: (values[0], values[1]) for house, values in totals.items()}

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

    def cancel_active_fixtures_except_season(self, guild_id: int, current_season_id: int) -> list[int]:
        rows = self.conn.execute(
            """
            SELECT qf.id
            FROM quidditch_fixtures qf
            JOIN quidditch_seasons qs ON qs.id = qf.season_id
            WHERE qs.guild_id = ?
              AND qf.season_id <> ?
              AND qf.status = 'active'
            """,
            (guild_id, current_season_id),
        ).fetchall()
        fixture_ids = [int(row["id"]) for row in rows]
        if not fixture_ids:
            return []

        placeholders = ",".join("?" for _ in fixture_ids)
        self.conn.execute(
            f"""
            UPDATE quidditch_fixtures
            SET status = 'cancelled',
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
            """,
            fixture_ids,
        )
        self.conn.execute(
            f"""
            DELETE FROM quidditch_live_match_state
            WHERE fixture_id IN ({placeholders})
            """,
            fixture_ids,
        )
        self.conn.execute(
            f"""
            DELETE FROM quidditch_match_runtime_state
            WHERE match_scope = 'official'
              AND match_id IN ({placeholders})
            """,
            fixture_ids,
        )
        self.conn.execute(
            f"""
            DELETE FROM quidditch_match_cheers
            WHERE match_scope = 'official'
              AND match_id IN ({placeholders})
            """,
            fixture_ids,
        )
        return fixture_ids

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
    ) -> bool:
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
        if str(fixture["status"]) == "completed":
            return False

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

        if str(fixture["stage"]) != "regular":
            return True

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

        return True

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

    def get_test_match(self, test_match_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM quidditch_test_matches
            WHERE id = ?
            """,
            (test_match_id,),
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

    def set_test_match_message(
        self,
        test_match_id: int,
        *,
        channel_id: int,
        message_id: int,
    ) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_test_matches
            SET channel_id = ?, message_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (channel_id, message_id, test_match_id),
        )

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

    def cancel_test_match(self, test_match_id: int) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_test_matches
            SET status = 'cancelled',
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


    def get_runtime_state(self, match_scope: str, match_id: int) -> dict | None:
        row = self.conn.execute(
            """
            SELECT state_json
            FROM quidditch_match_runtime_state
            WHERE match_scope = ? AND match_id = ?
            """,
            (match_scope, match_id),
        ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(str(row["state_json"]))
        except json.JSONDecodeError:
            return None

    def upsert_runtime_state(
        self,
        match_scope: str,
        match_id: int,
        state: dict,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO quidditch_match_runtime_state (
                match_scope,
                match_id,
                state_json,
                updated_at
            )
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(match_scope, match_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (match_scope, match_id, json.dumps(state)),
        )

    def delete_runtime_state(self, match_scope: str, match_id: int) -> None:
        self.conn.execute(
            """
            DELETE FROM quidditch_match_runtime_state
            WHERE match_scope = ? AND match_id = ?
            """,
            (match_scope, match_id),
        )

    def get_rotation_cycle(
        self,
        guild_id: int,
        house_name: str,
        position_key: str,
    ) -> list[int]:
        row = self.conn.execute(
            """
            SELECT cycle_json
            FROM quidditch_house_position_rotation
            WHERE guild_id = ? AND house_name = ? AND position_key = ?
            """,
            (guild_id, house_name, position_key),
        ).fetchone()
        if row is None:
            return []
        try:
            raw = json.loads(str(row["cycle_json"]))
            return [int(value) for value in raw]
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    def save_rotation_cycle(
        self,
        guild_id: int,
        house_name: str,
        position_key: str,
        cycle_user_ids: list[int],
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO quidditch_house_position_rotation (
                guild_id,
                house_name,
                position_key,
                cycle_json,
                updated_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id, house_name, position_key) DO UPDATE SET
                cycle_json = excluded.cycle_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (guild_id, house_name, position_key, json.dumps(cycle_user_ids)),
        )

    def clear_rotation_cycle(
        self,
        guild_id: int,
        house_name: str,
        position_key: str,
    ) -> None:
        self.conn.execute(
            """
            DELETE FROM quidditch_house_position_rotation
            WHERE guild_id = ? AND house_name = ? AND position_key = ?
            """,
            (guild_id, house_name, position_key),
        )

    def get_user_cheer(
        self,
        match_scope: str,
        match_id: int,
        user_id: int,
    ) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM quidditch_match_cheers
            WHERE match_scope = ? AND match_id = ? AND user_id = ?
            """,
            (match_scope, match_id, user_id),
        ).fetchone()

    def record_cheer(
        self,
        match_scope: str,
        match_id: int,
        user_id: int,
        cheering_house: str,
        cheered_at_iso: str,
    ) -> None:
        existing = self.get_user_cheer(match_scope, match_id, user_id)
        if existing is None:
            self.conn.execute(
                """
                INSERT INTO quidditch_match_cheers (
                    match_scope,
                    match_id,
                    user_id,
                    cheering_house,
                    last_cheered_at,
                    cheer_count,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """,
                (match_scope, match_id, user_id, cheering_house, cheered_at_iso),
            )
            return

        self.conn.execute(
            """
            UPDATE quidditch_match_cheers
            SET cheering_house = ?,
                last_cheered_at = ?,
                cheer_count = cheer_count + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE match_scope = ? AND match_id = ? AND user_id = ?
            """,
            (cheering_house, cheered_at_iso, match_scope, match_id, user_id),
        )

    def clear_match_cheers(self, match_scope: str, match_id: int) -> None:
        self.conn.execute(
            """
            DELETE FROM quidditch_match_cheers
            WHERE match_scope = ? AND match_id = ?
            """,
            (match_scope, match_id),
        )

    def get_cheer_totals(self, match_scope: str, match_id: int) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT cheering_house, COUNT(*) AS cheerers
            FROM quidditch_match_cheers
            WHERE match_scope = ? AND match_id = ?
            GROUP BY cheering_house
            """,
            (match_scope, match_id),
        ).fetchall()
        return {str(row["cheering_house"]): int(row["cheerers"]) for row in rows}

    def get_all_active_test_matches(self) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM quidditch_test_matches
            WHERE status = 'active'
            ORDER BY started_at ASC, id ASC
            """
        ).fetchall()
        return list(rows)

    def get_all_active_fixtures(self) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM quidditch_fixtures
            WHERE status = 'active'
            ORDER BY starts_at ASC, id ASC
            """
        ).fetchall()
        return list(rows)

    def append_live_match_log(
        self,
        fixture_id: int,
        log_line: str,
    ) -> list[str]:
        state = self.get_live_match_state(fixture_id)
        entries: list[str] = []
        if state is not None:
            try:
                entries = json.loads(str(state["log_json"]))
            except json.JSONDecodeError:
                entries = []

        entries.append(log_line)

        self.conn.execute(
            """
            UPDATE quidditch_live_match_state
            SET log_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE fixture_id = ?
            """,
            (json.dumps(entries), fixture_id),
        )
        return entries

    def replace_live_match_log(
        self,
        fixture_id: int,
        log_entries: list[str],
    ) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_live_match_state
            SET log_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE fixture_id = ?
            """,
            (json.dumps(log_entries), fixture_id),
        )

    def replace_test_match_log(
        self,
        test_match_id: int,
        log_entries: list[str],
    ) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_test_matches
            SET log_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(log_entries), test_match_id),
        )

    def set_test_match_image_path(
        self,
        test_match_id: int,
        image_path: str | None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_test_matches
            SET image_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (image_path, test_match_id),
        )

    def set_live_match_image_path(
        self,
        fixture_id: int,
        image_path: str | None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_live_match_state
            SET image_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE fixture_id = ?
            """,
            (image_path, fixture_id),
        )

    def update_test_match_message(
        self,
        test_match_id: int,
        *,
        channel_id: int | None,
        message_id: int | None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_test_matches
            SET channel_id = ?, message_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (channel_id, message_id, test_match_id),
        )

    def can_user_cheer_again(
        self,
        match_scope: str,
        match_id: int,
        user_id: int,
        now: datetime,
        *,
        cooldown_minutes: int = 20,
    ) -> bool:
        existing = self.get_user_cheer(match_scope, match_id, user_id)
        if existing is None:
            return True

        try:
            last_cheered_at = datetime.fromisoformat(str(existing["last_cheered_at"]))
        except ValueError:
            return True

        elapsed = now - last_cheered_at
        return elapsed.total_seconds() >= cooldown_minutes * 60
    
    def update_fixture_matchup(
        self,
        fixture_id: int,
        *,
        home_house: str,
        away_house: str,
    ) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_fixtures
            SET home_house = ?, away_house = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (home_house, away_house, fixture_id),
        )
    def get_betting_state(self, fixture_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM quidditch_fixture_betting_state
            WHERE fixture_id = ?
            """,
            (fixture_id,),
        ).fetchone()

    def upsert_betting_state(
        self,
        fixture_id: int,
        *,
        status: str,
        announced_at: str | None,
        cleanup_at: str | None,
        preview_state: dict,
        odds_home: float,
        odds_away: float,
        image_message_id: int | None = None,
        embed_message_id: int | None = None,
        final_message_id: int | None = None,
        results_message_id: int | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO quidditch_fixture_betting_state (
                fixture_id, status, announced_at, cleanup_at, image_message_id,
                embed_message_id, final_message_id, results_message_id,
                preview_state_json, odds_home, odds_away, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(fixture_id) DO UPDATE SET
                status = excluded.status,
                announced_at = excluded.announced_at,
                cleanup_at = excluded.cleanup_at,
                image_message_id = COALESCE(excluded.image_message_id, quidditch_fixture_betting_state.image_message_id),
                embed_message_id = COALESCE(excluded.embed_message_id, quidditch_fixture_betting_state.embed_message_id),
                final_message_id = COALESCE(excluded.final_message_id, quidditch_fixture_betting_state.final_message_id),
                results_message_id = COALESCE(excluded.results_message_id, quidditch_fixture_betting_state.results_message_id),
                preview_state_json = excluded.preview_state_json,
                odds_home = excluded.odds_home,
                odds_away = excluded.odds_away,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                fixture_id,
                status,
                announced_at,
                cleanup_at,
                image_message_id,
                embed_message_id,
                final_message_id,
                results_message_id,
                json.dumps(preview_state),
                float(odds_home),
                float(odds_away),
            ),
        )

    def update_betting_preview_state(self, fixture_id: int, preview_state: dict) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_fixture_betting_state
            SET preview_state_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE fixture_id = ?
            """,
            (json.dumps(preview_state), fixture_id),
        )

    def mark_betting_announced(
        self,
        fixture_id: int,
        *,
        image_message_id: int,
        embed_message_id: int,
    ) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_fixture_betting_state
            SET status = 'announced',
                image_message_id = ?,
                embed_message_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE fixture_id = ?
            """,
            (image_message_id, embed_message_id, fixture_id),
        )

    def mark_betting_closed(self, fixture_id: int) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_fixture_betting_state
            SET status = 'closed', updated_at = CURRENT_TIMESTAMP
            WHERE fixture_id = ?
            """,
            (fixture_id,),
        )

    def set_betting_final_message(self, fixture_id: int, message_id: int) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_fixture_betting_state
            SET final_message_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE fixture_id = ?
            """,
            (message_id, fixture_id),
        )

    def set_betting_results_message(self, fixture_id: int, message_id: int) -> None:
        self.conn.execute(
            """
            UPDATE quidditch_fixture_betting_state
            SET results_message_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE fixture_id = ?
            """,
            (message_id, fixture_id),
        )

    def list_pending_betting_announcements(self, now_iso: str) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT qbs.*, qf.home_house, qf.away_house, qf.starts_at, qf.status AS fixture_status
            FROM quidditch_fixture_betting_state qbs
            JOIN quidditch_fixtures qf ON qf.id = qbs.fixture_id
            WHERE qbs.status = 'pending'
              AND qbs.announced_at IS NOT NULL
              AND qbs.announced_at <= ?
              AND qf.status = 'scheduled'
            ORDER BY qbs.announced_at ASC, qbs.fixture_id ASC
            """,
            (now_iso,),
        ).fetchall()
        return list(rows)

    def list_betting_to_cleanup(self, now_iso: str) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT qbs.*, qf.home_house, qf.away_house, qf.starts_at, qf.status AS fixture_status
            FROM quidditch_fixture_betting_state qbs
            JOIN quidditch_fixtures qf ON qf.id = qbs.fixture_id
            WHERE qbs.status = 'announced'
              AND qbs.cleanup_at IS NOT NULL
              AND qbs.cleanup_at <= ?
            ORDER BY qbs.cleanup_at ASC, qbs.fixture_id ASC
            """,
            (now_iso,),
        ).fetchall()
        return list(rows)

    def create_bet(self, fixture_id: int, user_id: int, picked_house: str, stake: int, odds: float) -> None:
        self.conn.execute(
            """
            INSERT INTO quidditch_match_bets (
                fixture_id, user_id, picked_house, stake, odds, payout, result, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, 'pending', CURRENT_TIMESTAMP)
            """,
            (fixture_id, user_id, picked_house, stake, float(odds)),
        )

    def get_bet_for_user(self, fixture_id: int, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT * FROM quidditch_match_bets
            WHERE fixture_id = ? AND user_id = ?
            """,
            (fixture_id, user_id),
        ).fetchone()

    def list_bets_for_fixture(self, fixture_id: int) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT * FROM quidditch_match_bets
            WHERE fixture_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (fixture_id,),
        ).fetchall()
        return list(rows)

    def settle_pending_bets_for_fixture(self, fixture_id: int, winner_house: str) -> list[sqlite3.Row]:
        pending_bets = self.conn.execute(
            """
            SELECT * FROM quidditch_match_bets
            WHERE fixture_id = ? AND result = 'pending'
            ORDER BY created_at ASC, id ASC
            """,
            (fixture_id,),
        ).fetchall()

        settled_ids: list[int] = []
        for bet in pending_bets:
            won = str(bet["picked_house"]) == winner_house
            payout = int(round(int(bet["stake"]) * float(bet["odds"]))) if won else 0
            cur = self.conn.execute(
                """
                UPDATE quidditch_match_bets
                SET result = ?, payout = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND result = 'pending'
                """,
                ("won" if won else "lost", payout, int(bet["id"])),
            )
            if cur.rowcount > 0:
                settled_ids.append(int(bet["id"]))

        if not settled_ids:
            return []

        placeholders = ",".join("?" for _ in settled_ids)
        rows = self.conn.execute(
            f"""
            SELECT * FROM quidditch_match_bets
            WHERE id IN ({placeholders})
            ORDER BY created_at ASC, id ASC
            """,
            settled_ids,
        ).fetchall()
        return list(rows)
