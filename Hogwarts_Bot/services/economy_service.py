from repositories.user_repository import UserRepository


class EconomyService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def reward_money(self, user_id: int, amount: int) -> None:
        if amount <= 0:
            raise ValueError("Amount must be greater than 0.")
        self.user_repo.ensure_user(user_id)
        self.user_repo.add_sickles(user_id, amount)