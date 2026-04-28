from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from repositories.quidditch_repository import QuidditchRepository


class QuidditchService:
    TZ = ZoneInfo("Europe/Zurich")
    HOUSES = ("Slytherin", "Ravenclaw", "Hufflepuff", "Gryffindor")

    def __init__(self, repo: QuidditchRepository):
        self.repo = repo

    def season_key_for(self, year: int, month: int) -> str:
        return f"{year:04d}-{month:02d}"

    def set_match_channel(self, guild_id: int, channel_id: int) -> None:
        self.repo.upsert_config(guild_id, match_channel_id=channel_id)

    def set_scoreboard_channel(self, guild_id: int, channel_id: int) -> None:
        self.repo.upsert_config(guild_id, scoreboard_channel_id=channel_id)

    def set_scoreboard_message_id(self, guild_id: int, message_id: int) -> None:
        self.repo.upsert_config(guild_id, scoreboard_message_id=message_id)

    def get_config(self, guild_id: int):
        return self.repo.get_config(guild_id)

    def stop_loop(self, guild_id: int) -> None:
        self.repo.set_loop_enabled(guild_id, False)

    def enable_loop(self, guild_id: int) -> None:
        self.repo.set_loop_enabled(guild_id, True)

    def is_loop_enabled(self, guild_id: int) -> bool:
        return self.repo.is_loop_enabled(guild_id)

    def build_month_schedule(
        self,
        *,
        guild_id: int,
        now: datetime | None = None,
    ) -> dict:
        current = now.astimezone(self.TZ) if now else datetime.now(self.TZ)
        year = current.year
        month = current.month
        season_key = self.season_key_for(year, month)

        existing = self.repo.get_season_by_key(guild_id, season_key)
        if existing is not None:
            return {
                "season_id": int(existing["id"]),
                "season_key": season_key,
                "created": False,
                "is_reduced": bool(existing["is_reduced"]),
                "fixtures": self.repo.list_fixtures_for_season(int(existing["id"])),
            }

        # Fixed monthly format: 12 round-robin games on the 2nd, 4th, ... 24th,
        # then the Bronze Medal Match on the 26th and the Championship Game on the 28th.
        game_days = self._build_game_days(year, month)
        full_regular = self._full_regular_fixtures()
        is_reduced = False

        season_id = self.repo.create_season(
            guild_id,
            season_key=season_key,
            year=year,
            month=month,
            is_reduced=is_reduced,
        )

        regular_fixtures = full_regular
        usable_days = game_days

        for match_day, (home, away) in enumerate(regular_fixtures, start=1):
            starts_at = self._day_start_iso(year, month, usable_days[match_day - 1])
            self.repo.create_fixture(
                season_id,
                match_day=match_day,
                stage="regular",
                starts_at=starts_at,
                home_house=home,
                away_house=away,
            )

        placement_start_index = len(regular_fixtures)
        placement_days = usable_days[placement_start_index:placement_start_index + 2]
        while len(placement_days) < 2:
            placement_days.append(usable_days[-1])

        self.repo.create_fixture(
            season_id,
            match_day=placement_start_index + 1,
            stage="third_place",
            starts_at=self._day_start_iso(year, month, placement_days[0]),
            home_house="TBD",
            away_house="TBD",
        )
        self.repo.create_fixture(
            season_id,
            match_day=placement_start_index + 2,
            stage="final",
            starts_at=self._day_start_iso(year, month, placement_days[1]),
            home_house="TBD",
            away_house="TBD",
        )

        return {
            "season_id": season_id,
            "season_key": season_key,
            "created": True,
            "is_reduced": is_reduced,
            "fixtures": self.repo.list_fixtures_for_season(season_id),
        }

    def can_start_manual_now(
        self,
        *,
        guild_id: int,
        now: datetime | None = None,
    ) -> tuple[bool, str]:
        current = now.astimezone(self.TZ) if now else datetime.now(self.TZ)

        season = self.repo.get_season_by_key(
            guild_id,
            self.season_key_for(current.year, current.month),
        )
        if season is None:
            return False, "No Quidditch season exists yet. Run `/start_quidditch_loop` first."

        active = self.repo.get_active_fixture(int(season["id"]))
        if active is not None:
            return False, "There is already an active Quidditch game."

        if self.repo.get_active_test_match(guild_id) is not None:
            return False, "There is already an active Quidditch test game."

        next_fixture = self.repo.get_next_scheduled_fixture(int(season["id"]))
        if next_fixture is None:
            return False, "There is no scheduled Quidditch game left this month."

        scheduled_start = datetime.fromisoformat(str(next_fixture["starts_at"])).astimezone(self.TZ)
        if current.date() != scheduled_start.date():
            return False, "You can only use `/quidditch_now` on the same calendar day as the scheduled game."

        if current >= scheduled_start:
            return False, "It is already too late to start this game early. The scheduled start time has passed."

        return True, "ok"

    def start_manual_now(
        self,
        *,
        guild_id: int,
        now: datetime | None = None,
    ) -> dict:
        current = now.astimezone(self.TZ) if now else datetime.now(self.TZ)
        allowed, reason = self.can_start_manual_now(guild_id=guild_id, now=current)
        if not allowed:
            raise ValueError(reason)

        season = self.repo.get_season_by_key(
            guild_id,
            self.season_key_for(current.year, current.month),
        )
        if season is None:
            raise ValueError("Season not found.")

        fixture = self.repo.get_next_scheduled_fixture(int(season["id"]))
        if fixture is None:
            raise ValueError("No scheduled fixture found.")

        started_at = current.isoformat()
        ends_at = (current + timedelta(hours=10)).isoformat()
        snitch_unlocked_at = (current + timedelta(hours=8)).isoformat()

        self.repo.set_fixture_active(int(fixture["id"]), starts_at=started_at)
        self.repo.upsert_live_match_state(
            int(fixture["id"]),
            channel_id=None,
            message_id=None,
            image_path=None,
            log_entries=[],
            started_at=started_at,
            ends_at=ends_at,
            snitch_unlocked_at=snitch_unlocked_at,
            started_manually=True,
        )

        return {
            "season": season,
            "fixture": self.repo.get_fixture(int(fixture["id"])),
            "started_at": started_at,
            "ends_at": ends_at,
        }

    def stop_manual_now(
        self,
        *,
        guild_id: int,
        now: datetime | None = None,
    ) -> dict:
        current = now.astimezone(self.TZ) if now else datetime.now(self.TZ)
        season = self.repo.get_season_by_key(
            guild_id,
            self.season_key_for(current.year, current.month),
        )
        if season is None:
            raise ValueError("No active Quidditch season found.")

        active = self.repo.get_active_fixture(int(season["id"]))
        if active is None:
            raise ValueError("There is no active Quidditch game to stop.")

        live_state = self.repo.get_live_match_state(int(active["id"]))
        if live_state is None or not bool(live_state["started_manually"]):
            raise ValueError("The current game was not started with `/quidditch_now`.")

        original_scheduled = self._day_start_iso_from_fixture(active)
        self.repo.set_fixture_scheduled(int(active["id"]), starts_at=original_scheduled)
        self.repo.delete_live_match_state(int(active["id"]))

        return {
            "season": season,
            "fixture": self.repo.get_fixture(int(active["id"])),
        }

    def start_test_game(
        self,
        *,
        guild_id: int,
        now: datetime | None = None,
    ) -> dict:
        current = now.astimezone(self.TZ) if now else datetime.now(self.TZ)

        active_test = self.repo.get_active_test_match(guild_id)
        if active_test is not None:
            raise ValueError("There is already an active Quidditch test game.")

        season = self.repo.get_season_by_key(
            guild_id,
            self.season_key_for(current.year, current.month),
        )
        if season is not None and self.repo.get_active_fixture(int(season["id"])) is not None:
            raise ValueError("There is already an active official Quidditch game.")

        home_house, away_house = self.repo.random_house_pair()
        started_at = current.isoformat()
        ends_at = (current + timedelta(hours=10)).isoformat()
        snitch_unlocked_at = (current + timedelta(hours=8)).isoformat()

        test_match_id = self.repo.create_test_match(
            guild_id=guild_id,
            home_house=home_house,
            away_house=away_house,
            started_at=started_at,
            ends_at=ends_at,
            snitch_unlocked_at=snitch_unlocked_at,
            log_entries=[
                f"{current.strftime('%H:%M')} — Unofficial test game started.",
                f"{current.strftime('%H:%M')} — This game will not affect standings or House Cup points.",
            ],
        )

        return {
            "test_match_id": test_match_id,
            "home_house": home_house,
            "away_house": away_house,
            "started_at": started_at,
            "ends_at": ends_at,
        }

    def stop_test_game(
        self,
        *,
        guild_id: int,
    ) -> dict:
        active_test = self.repo.get_active_test_match(guild_id)
        if active_test is None:
            raise ValueError("There is no active Quidditch test game.")

        self.repo.cancel_test_match(int(active_test["id"]))
        return {
            "test_match": active_test,
        }

    def build_scoreboard_embed(self, season_row, standings_rows) -> tuple[str, str]:
        month_name = datetime(int(season_row["year"]), int(season_row["month"]), 1).strftime("%B")
        title = f"{month_name} League {int(season_row['year'])} — Round Robin Leaderboard"
        win_loss = self.repo.get_regular_win_loss_counts(int(season_row["id"]))

        rows: list[tuple[str, int, int, int, int]] = []
        for row in standings_rows:
            house_name = str(row["house_name"])
            wins, losses = win_loss.get(house_name, (0, 0))
            rows.append((
                house_name,
                int(row["matches_played"]),
                int(wins),
                int(losses),
                int(row["points_scored"]),
            ))

        if not rows:
            return title, "```text\nNo Quidditch season data yet.\n```"

        # Compact monospace block for mobile: no ranks, sorted by monthly round-robin points.
        table_lines = [
            "House        GP   W   L   Pts",
            "------------------------------",
        ]
        for house_name, played, wins, losses, points in rows:
            table_lines.append(
                f"{house_name[:11]:<11} {played:>1}/6 {wins:>3} {losses:>3} {points:>5}"
            )
        return title, "```text\n" + "\n".join(table_lines) + "\n```"

    def _build_game_days(self, year: int, month: int) -> list[int]:
        # Every month has at least 28 days. This gives 12 round-robin dates
        # plus two placement dates: 2, 4, ..., 24, 26, 28.
        return list(range(2, 29, 2))

    def _day_start_iso(self, year: int, month: int, day: int) -> str:
        return datetime(year, month, day, 13, 0, 0, tzinfo=self.TZ).isoformat()

    def _day_start_iso_from_fixture(self, fixture_row) -> str:
        dt = datetime.fromisoformat(str(fixture_row["starts_at"])).astimezone(self.TZ)
        return datetime(dt.year, dt.month, dt.day, 13, 0, 0, tzinfo=self.TZ).isoformat()

    def _full_regular_fixtures(self) -> list[tuple[str, str]]:
        houses = list(self.HOUSES)
        fixtures: list[tuple[str, str]] = []
        for i, home in enumerate(houses):
            for away in houses[i + 1:]:
                fixtures.append((home, away))
                fixtures.append((away, home))
        return fixtures

    def _reduced_regular_fixtures(self) -> list[tuple[str, str]]:
        return [
            ("Slytherin", "Ravenclaw"),
            ("Hufflepuff", "Gryffindor"),
            ("Slytherin", "Hufflepuff"),
            ("Ravenclaw", "Gryffindor"),
            ("Slytherin", "Gryffindor"),
            ("Ravenclaw", "Hufflepuff"),
        ]