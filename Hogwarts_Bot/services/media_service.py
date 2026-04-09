from datetime import datetime, timedelta, timezone


class MediaService:
    VOTE_WINDOW_MINUTES = 60
    MAX_VOTES_PER_WINDOW = 3
    POST_DURATION_HOURS = 2
    POINTS_PER_VOTE = 3

    SUPPORTED_IMAGE_TYPES = {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
    }

    SUPPORTED_VIDEO_TYPES = {
        "video/mp4",
        "video/quicktime",   # .mov
        "video/webm",
        "video/x-matroska",  # .mkv (sometimes)
    }

    SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
    SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def now_iso(self) -> str:
        return self.now().isoformat()

    def calculate_closes_at_iso(self) -> str:
        return (self.now() + timedelta(hours=self.POST_DURATION_HOURS)).isoformat()

    def is_supported_media(self, filename: str | None, content_type: str | None) -> bool:
        if content_type:
            lowered = content_type.lower()
            if lowered in self.SUPPORTED_IMAGE_TYPES or lowered in self.SUPPORTED_VIDEO_TYPES:
                return True

        if not filename:
            return False

        lowered_name = filename.lower()
        return any(lowered_name.endswith(ext) for ext in (
            *self.SUPPORTED_IMAGE_EXTENSIONS,
            *self.SUPPORTED_VIDEO_EXTENSIONS,
        ))

    def calculate_vote_window_start_iso(self) -> str:
        return (self.now() - timedelta(minutes=self.VOTE_WINDOW_MINUTES)).isoformat()

    def can_vote_in_window(self, recent_vote_count: int) -> tuple[bool, int]:
        remaining_votes = self.MAX_VOTES_PER_WINDOW - recent_vote_count
        if remaining_votes > 0:
            return True, remaining_votes
        return False, 0

    def is_post_closed(self, closes_at_iso: str, is_closed: bool) -> bool:
        if is_closed:
            return True
        closes_at = datetime.fromisoformat(closes_at_iso)
        return self.now() >= closes_at