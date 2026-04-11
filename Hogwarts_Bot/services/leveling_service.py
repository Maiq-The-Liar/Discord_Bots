from __future__ import annotations

import calendar
from datetime import datetime, timezone, timedelta

from domain.constants import MAX_SCHOOL_LEVEL
from repositories.user_repository import UserRepository


class LevelingService:
    ACTIVITY_WINDOW_DAYS = 7
    YEAR_MONTH_THRESHOLDS: dict[int, int] = {
        1: 0,
        2: 1,
        3: 2,
        4: 4,
        5: 6,
        6: 9,
        7: 12,
    }

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def ensure_initialized(self, user_id: int, joined_at: datetime | None) -> dict:
        self.user_repo.ensure_user(user_id)

        tracking = self.user_repo.get_year_tracking(user_id)
        if tracking["year_initialized_at"] and tracking["year_start_at"]:
            return self._build_state_from_tracking(tracking, self.utc_now())

        now = self.utc_now()
        start_at = self._ensure_aware(joined_at) if joined_at else now
        default_last_message_at = start_at
        if now - start_at > timedelta(days=self.ACTIVITY_WINDOW_DAYS):
            default_last_message_at = now

        return self.initialize_year_tracking(
            user_id=user_id,
            start_at=start_at,
            last_message_at=default_last_message_at,
        )

    def initialize_year_tracking(
        self,
        user_id: int,
        start_at: datetime,
        last_message_at: datetime | None = None,
    ) -> dict:
        start_at = self._ensure_aware(start_at)
        last_message_at = self._ensure_aware(last_message_at) if last_message_at else start_at
        now = self.utc_now()
        level = self.calculate_level(start_at, now)

        self.user_repo.set_year_tracking(
            user_id=user_id,
            year_start_at=start_at.isoformat(),
            last_year_message_at=last_message_at.isoformat(),
            year_initialized_at=now.isoformat(),
            level=level,
            xp=0,
        )

        return {
            "initialized": True,
            "leveled_up": False,
            "level_changed": False,
            "old_level": level,
            "level": level,
            "year_start_at": start_at.isoformat(),
            "last_year_message_at": last_message_at.isoformat(),
        }

    def process_member_message(
        self,
        user_id: int,
        joined_at: datetime | None,
        message_at: datetime | None = None,
    ) -> dict:
        state = self.ensure_initialized(user_id, joined_at)

        now = self._ensure_aware(message_at) if message_at else self.utc_now()
        tracking = self.user_repo.get_year_tracking(user_id)

        start_at = self._parse_iso(tracking["year_start_at"]) or now
        last_message_at = self._parse_iso(tracking["last_year_message_at"]) or start_at
        old_level = int(tracking["level"] or 1)

        if now > last_message_at:
            allowed_gap = timedelta(days=self.ACTIVITY_WINDOW_DAYS)
            gap = now - last_message_at
            if gap > allowed_gap:
                start_at += gap - allowed_gap

        new_level = self.calculate_level(start_at, now)

        self.user_repo.set_year_tracking(
            user_id=user_id,
            year_start_at=start_at.isoformat(),
            last_year_message_at=now.isoformat(),
            year_initialized_at=tracking["year_initialized_at"] or now.isoformat(),
            level=new_level,
            xp=0,
        )

        return {
            "initialized": state.get("initialized", False),
            "leveled_up": new_level > old_level,
            "level_changed": new_level != old_level,
            "old_level": old_level,
            "level": new_level,
            "year_start_at": start_at.isoformat(),
            "last_year_message_at": now.isoformat(),
        }

    def refresh_user_level(self, user_id: int) -> dict:
        tracking = self.user_repo.get_year_tracking(user_id)
        now = self.utc_now()
        start_at = self._parse_iso(tracking["year_start_at"]) or now
        old_level = int(tracking["level"] or 1)
        new_level = self.calculate_level(start_at, now)

        self.user_repo.set_level_only(user_id=user_id, level=new_level, xp=0)

        return {
            "leveled_up": new_level > old_level,
            "level_changed": new_level != old_level,
            "old_level": old_level,
            "level": new_level,
        }

    def calculate_level(self, year_start_at: datetime, as_of: datetime | None = None) -> int:
        year_start_at = self._ensure_aware(year_start_at)
        as_of = self._ensure_aware(as_of) if as_of else self.utc_now()

        level = 1
        for candidate_level, months_required in self.YEAR_MONTH_THRESHOLDS.items():
            if as_of >= self.add_months(year_start_at, months_required):
                level = candidate_level
        return min(level, MAX_SCHOOL_LEVEL)

    def progress_to_next_year(self, year_start_at: datetime, current_level: int, as_of: datetime | None = None) -> str:
        current_level = max(1, min(MAX_SCHOOL_LEVEL, current_level))
        if current_level >= MAX_SCHOOL_LEVEL:
            return "Completed"

        as_of = self._ensure_aware(as_of) if as_of else self.utc_now()
        next_level = current_level + 1
        threshold = self.add_months(year_start_at, self.YEAR_MONTH_THRESHOLDS[next_level])
        remaining = threshold - as_of
        if remaining.total_seconds() <= 0:
            return "Ready now"

        days = remaining.days
        if days >= 30:
            months = days // 30
            extra_days = days % 30
            return f"{months} month{'s' if months != 1 else ''}{f' {extra_days} day' if extra_days == 1 else f' {extra_days} days' if extra_days else ''}"
        return f"{days} day{'s' if days != 1 else ''}"

    def add_months(self, dt: datetime, months: int) -> datetime:
        dt = self._ensure_aware(dt)
        month_index = (dt.month - 1) + months
        year = dt.year + month_index // 12
        month = (month_index % 12) + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)

    def _build_state_from_tracking(self, tracking: dict, as_of: datetime) -> dict:
        start_at = self._parse_iso(tracking["year_start_at"]) or as_of
        level = self.calculate_level(start_at, as_of)
        return {
            "initialized": False,
            "leveled_up": False,
            "level_changed": False,
            "old_level": level,
            "level": level,
            "year_start_at": start_at.isoformat(),
            "last_year_message_at": tracking["last_year_message_at"],
        }

    def _parse_iso(self, value: str | None) -> datetime | None:
        if not value:
            return None
        return self._ensure_aware(datetime.fromisoformat(value))

    def _ensure_aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
