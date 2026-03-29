import random
from datetime import datetime, timezone

from domain.constants import MAX_SCHOOL_LEVEL
from repositories.user_repository import UserRepository


class LevelingService:
    XP_COOLDOWN_SECONDS = 120
    XP_MIN = 5
    XP_MAX = 10


def xp_required_for_next_level(self, level: int) -> int:
    return 20 * (level ** 2) + 100 * level + 200

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def xp_required_for_next_level(self, level: int) -> int:
        return 5 * (level ** 2) + 50 * level + 100

    def can_gain_xp(self, last_xp_at: str | None) -> bool:
        if not last_xp_at:
            return True

        last_dt = datetime.fromisoformat(last_xp_at)
        now = datetime.now(timezone.utc)

        return (now - last_dt).total_seconds() >= self.XP_COOLDOWN_SECONDS

    def process_message_xp(self, user_id: int) -> dict:
        self.user_repo.ensure_user(user_id)

        xp, level, last_xp_at = self.user_repo.get_xp_and_level(user_id)

        if not self.can_gain_xp(last_xp_at):
            return {
                "awarded": False,
                "leveled_up": False,
                "xp": xp,
                "level": level,
                "xp_gained": 0,
            }

        xp_gain = random.randint(self.XP_MIN, self.XP_MAX)
        xp += xp_gain

        leveled_up = False
        old_level = level

        while level < MAX_SCHOOL_LEVEL:
            needed = self.xp_required_for_next_level(level)
            if xp < needed:
                break
            xp -= needed
            level += 1
            leveled_up = True

        now_iso = datetime.now(timezone.utc).isoformat()

        self.user_repo.set_xp_and_level(
            user_id=user_id,
            xp=xp,
            level=level,
            last_xp_at=now_iso,
        )

        return {
            "awarded": True,
            "leveled_up": leveled_up,
            "old_level": old_level,
            "level": level,
            "xp": xp,
            "xp_gained": xp_gain,
            "xp_needed_next": None if level >= MAX_SCHOOL_LEVEL else self.xp_required_for_next_level(level),
        }