from __future__ import annotations

from datetime import datetime, timedelta, timezone

from repositories.quidditch_progress_repository import QuidditchProgressRepository


class QuidditchLevelingService:
    MAX_LEVEL = 120

    # Anti-spam / pacing
    MESSAGE_COOLDOWN_SECONDS = 90
    MIN_MESSAGE_LENGTH = 12
    MIN_WORD_COUNT = 3
    XP_PER_ELIGIBLE_MESSAGE = 6
    DAILY_XP_CAP = 100

    VALID_POSITIONS = {"keeper", "seeker", "beater", "chaser"}

    def __init__(self, progress_repo: QuidditchProgressRepository):
        self.progress_repo = progress_repo

    def ensure_initialized(self, user_id: int) -> None:
        self.progress_repo.ensure_user_positions(user_id)

    def process_message_for_position(
        self,
        *,
        user_id: int,
        position_key: str | None,
        message_content: str,
        message_at: datetime,
    ) -> dict:
        self.ensure_initialized(user_id)

        if position_key not in self.VALID_POSITIONS:
            return {
                "awarded_xp": 0,
                "leveled_up": False,
                "old_level": None,
                "level": None,
                "position_key": None,
            }

        if not self._is_message_eligible(message_content):
            progress = self.progress_repo.get_progress(user_id, position_key)
            return {
                "awarded_xp": 0,
                "leveled_up": False,
                "old_level": int(progress["level"]),
                "level": int(progress["level"]),
                "position_key": position_key,
            }

        now = self._ensure_aware(message_at)
        progress = self.progress_repo.get_progress(user_id, position_key)

        old_level = int(progress["level"])
        level = old_level
        xp = int(progress["xp"])
        daily_xp = int(progress["daily_xp"])
        last_xp_at = self._parse_iso(progress["last_xp_at"])
        daily_reset_on = progress["daily_reset_on"]
        today_key = now.date().isoformat()

        if daily_reset_on != today_key:
            daily_xp = 0
            daily_reset_on = today_key

        if last_xp_at is not None and now - last_xp_at < timedelta(seconds=self.MESSAGE_COOLDOWN_SECONDS):
            return {
                "awarded_xp": 0,
                "leveled_up": False,
                "old_level": old_level,
                "level": level,
                "position_key": position_key,
            }

        if daily_xp >= self.DAILY_XP_CAP:
            return {
                "awarded_xp": 0,
                "leveled_up": False,
                "old_level": old_level,
                "level": level,
                "position_key": position_key,
            }

        xp_gain = min(self.XP_PER_ELIGIBLE_MESSAGE, self.DAILY_XP_CAP - daily_xp)
        xp += xp_gain
        daily_xp += xp_gain

        leveled_up = False
        while level < self.MAX_LEVEL:
            needed = self.xp_needed_for_next_level(level)
            if xp < needed:
                break
            xp -= needed
            level += 1
            leveled_up = True

        if level >= self.MAX_LEVEL:
            level = self.MAX_LEVEL
            xp = 0

        self.progress_repo.save_progress(
            user_id,
            position_key,
            level=level,
            xp=xp,
            last_xp_at=now.isoformat(),
            daily_xp=daily_xp,
            daily_reset_on=daily_reset_on,
        )

        return {
            "awarded_xp": xp_gain,
            "leveled_up": leveled_up,
            "old_level": old_level,
            "level": level,
            "position_key": position_key,
        }

    def xp_needed_for_next_level(self, current_level: int) -> int:
        if current_level >= self.MAX_LEVEL:
            return 0
        return int(round(12 + current_level * 1.0 + (current_level ** 1.12) * 0.8))

    def _is_message_eligible(self, message_content: str) -> bool:
        content = (message_content or "").strip()

        if not content:
            return False
        if content.startswith("/"):
            return False
        if len(content) < self.MIN_MESSAGE_LENGTH:
            return False
        if len(content.split()) < self.MIN_WORD_COUNT:
            return False

        return True

    def _parse_iso(self, value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        return self._ensure_aware(parsed)

    def _ensure_aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)