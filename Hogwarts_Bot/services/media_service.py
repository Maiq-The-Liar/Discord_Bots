from datetime import datetime, timedelta, timezone


class MediaService:
    VOTE_COOLDOWN_MINUTES = 60
    POST_DURATION_HOURS = 2
    POINTS_PER_VOTE = 3

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def now_iso(self) -> str:
        return self.now().isoformat()

    def calculate_closes_at_iso(self) -> str:
        return (self.now() + timedelta(hours=self.POST_DURATION_HOURS)).isoformat()

    def is_supported_image(self, filename: str | None, content_type: str | None) -> bool:
        if content_type:
            lowered = content_type.lower()
            if lowered in {"image/png", "image/jpeg", "image/jpg"}:
                return True

        if not filename:
            return False

        lowered_name = filename.lower()
        return lowered_name.endswith(".png") or lowered_name.endswith(".jpg") or lowered_name.endswith(".jpeg")

    def can_vote_again(self, last_vote_at: str | None) -> tuple[bool, int]:
        if not last_vote_at:
            return True, 0

        last_dt = datetime.fromisoformat(last_vote_at)
        remaining = timedelta(minutes=self.VOTE_COOLDOWN_MINUTES) - (self.now() - last_dt)

        if remaining.total_seconds() <= 0:
            return True, 0

        remaining_minutes = max(1, int(remaining.total_seconds() // 60))
        return False, remaining_minutes

    def is_post_closed(self, closes_at_iso: str, is_closed: bool) -> bool:
        if is_closed:
            return True
        closes_at = datetime.fromisoformat(closes_at_iso)
        return self.now() >= closes_at