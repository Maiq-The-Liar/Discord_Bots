from repositories.user_repository import UserRepository
from repositories.contribution_repository import ContributionRepository


class HousePointsService:
    def __init__(self, user_repo: UserRepository, contribution_repo: ContributionRepository):
        self.user_repo = user_repo
        self.contribution_repo = contribution_repo

    def adjust_monthly_house_points(self, user_id: int, house_name: str, points: int) -> None:
        if points == 0:
            raise ValueError("Points must not be 0.")

        self.user_repo.ensure_user(user_id)
        self.contribution_repo.add_monthly_points(user_id, house_name, points)