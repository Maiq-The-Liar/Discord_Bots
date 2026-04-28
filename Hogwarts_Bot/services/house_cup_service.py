from repositories.bot_state_repository import BotStateRepository
from repositories.contribution_repository import ContributionRepository, current_year_month
from repositories.user_repository import UserRepository


class HouseCupService:
    ACTIVE_KEY = "house_cup_active"
    ACTIVE_MONTH_KEY = "house_cup_active_month"
    RANKING_CHANNEL_KEY = "house_cup_ranking_channel_id"

    HOUSES = ["Slytherin", "Ravenclaw", "Hufflepuff", "Gryffindor"]
    REWARDS = [100, 50, 20]

    def __init__(
        self,
        user_repo: UserRepository,
        contribution_repo: ContributionRepository,
        bot_state_repo: BotStateRepository,
    ):
        self.user_repo = user_repo
        self.contribution_repo = contribution_repo
        self.bot_state_repo = bot_state_repo

    def is_active(self) -> bool:
        return self.bot_state_repo.get_value(self.ACTIVE_KEY) == "1"

    def get_active_month(self) -> str | None:
        value = self.bot_state_repo.get_value(self.ACTIVE_MONTH_KEY)
        return value if value else None

    def set_ranking_channel_id(self, channel_id: int) -> None:
        self.bot_state_repo.set_value(self.RANKING_CHANNEL_KEY, str(channel_id))

    def get_ranking_channel_id(self) -> int | None:
        value = self.bot_state_repo.get_value(self.RANKING_CHANNEL_KEY)
        return int(value) if value else None

    def start_cup(self) -> str:
        if self.is_active():
            raise ValueError("The House Cup is already running.")

        month = current_year_month()

        # Fresh start for the active month
        self.contribution_repo.clear_month(month)

        self.bot_state_repo.set_value(self.ACTIVE_KEY, "1")
        self.bot_state_repo.set_value(self.ACTIVE_MONTH_KEY, month)

        return month

    def finalize_cup(
        self,
        target_month: str,
        continue_after_reset: bool,
    ) -> dict:
        house_totals = self.contribution_repo.get_all_house_totals(self.HOUSES, target_month)

        sorted_houses = sorted(
            house_totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        winner_house = None
        winner_points = 0
        if sorted_houses and sorted_houses[0][1] > 0:
            winner_house = sorted_houses[0][0]
            winner_points = sorted_houses[0][1]

        top_players = self.contribution_repo.get_top_contributors(target_month, limit=3)

        rewarded_players: list[dict] = []
        for index, player in enumerate(top_players):
            reward_amount = self.REWARDS[index]
            self.user_repo.ensure_user(player["user_id"])
            self.user_repo.add_galleons(player["user_id"], reward_amount)

            rewarded_players.append(
                {
                    "rank": index + 1,
                    "user_id": player["user_id"],
                    "points": player["points"],
                    "reward": reward_amount,
                }
            )

        all_user_totals = self.contribution_repo.get_all_user_monthly_totals(target_month)
        for entry in all_user_totals:
            self.user_repo.ensure_user(entry["user_id"])
            self.user_repo.add_lifetime_house_points(entry["user_id"], entry["points"])

        self.contribution_repo.clear_month(target_month)

        if continue_after_reset:
            new_month = current_year_month()
            self.bot_state_repo.set_value(self.ACTIVE_KEY, "1")
            self.bot_state_repo.set_value(self.ACTIVE_MONTH_KEY, new_month)
        else:
            self.bot_state_repo.set_value(self.ACTIVE_KEY, "0")
            self.bot_state_repo.set_value(self.ACTIVE_MONTH_KEY, "")

        return {
            "month": target_month,
            "winner_house": winner_house,
            "winner_points": winner_points,
            "house_totals": house_totals,
            "top_players": rewarded_players,
            "continued": continue_after_reset,
        }

    def end_cup(self) -> dict:
        if not self.is_active():
            raise ValueError("The House Cup is not currently running.")

        active_month = self.get_active_month()
        if not active_month:
            raise ValueError("No active House Cup month is set.")

        return self.finalize_cup(active_month, continue_after_reset=False)

    def handle_month_rollover(self) -> dict | None:
        if not self.is_active():
            return None

        active_month = self.get_active_month()
        current_month = current_year_month()

        if not active_month or active_month == current_month:
            return None

        return self.finalize_cup(active_month, continue_after_reset=True)