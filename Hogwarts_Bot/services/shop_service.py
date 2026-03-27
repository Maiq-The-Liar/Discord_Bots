from repositories.user_repository import UserRepository
from repositories.owned_item_repository import OwnedItemRepository
from domain.constants import SHOP_ITEMS_BY_KEY


class ShopService:
    def __init__(
        self,
        user_repo: UserRepository,
        owned_item_repo: OwnedItemRepository,
    ):
        self.user_repo = user_repo
        self.owned_item_repo = owned_item_repo

    def buy_item(self, user_id: int, item_key: str) -> dict:
        self.user_repo.ensure_user(user_id)

        item = SHOP_ITEMS_BY_KEY.get(item_key)
        if item is None:
            raise ValueError("Unknown shop item.")

        already_owned = self.owned_item_repo.get_quantity(user_id, item_key)

        if item["type"] == "permanent" and already_owned >= 1:
            raise ValueError("You already own this permanent item.")

        success = self.user_repo.deduct_sickles(user_id, item["price"])
        if not success:
            raise ValueError("You do not have enough Sickles.")

        self.owned_item_repo.add_quantity(user_id, item_key, 1)

        user_row = self.user_repo.get_user(user_id)
        new_quantity = self.owned_item_repo.get_quantity(user_id, item_key)

        return {
            "item_key": item["key"],
            "display_name": item["display_name"],
            "price": item["price"],
            "new_balance": user_row["sickles_balance"],
            "new_quantity": new_quantity,
            "type": item["type"],
        }

    def get_item_state(self, user_id: int, item_key: str) -> dict:
        self.user_repo.ensure_user(user_id)

        item = SHOP_ITEMS_BY_KEY.get(item_key)
        if item is None:
            raise ValueError("Unknown shop item.")

        user_row = self.user_repo.get_user(user_id)
        owned_quantity = self.owned_item_repo.get_quantity(user_id, item_key)

        can_buy = True
        reason = None

        if user_row["sickles_balance"] < item["price"]:
            can_buy = False
            reason = "Not enough Sickles."
        elif item["type"] == "permanent" and owned_quantity >= 1:
            can_buy = False
            reason = "Already owned."

        return {
            "balance": user_row["sickles_balance"],
            "owned_quantity": owned_quantity,
            "can_buy": can_buy,
            "reason": reason,
        }