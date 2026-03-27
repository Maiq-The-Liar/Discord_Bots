import random

from repositories.user_repository import UserRepository
from repositories.owned_item_repository import OwnedItemRepository
from repositories.patronus_repository import PatronusRepository


class PatronusService:
    def __init__(
        self,
        user_repo: UserRepository,
        owned_item_repo: OwnedItemRepository,
        patronus_repo: PatronusRepository,
    ):
        self.user_repo = user_repo
        self.owned_item_repo = owned_item_repo
        self.patronus_repo = patronus_repo

    def discover_patronus(self, user_id: int) -> dict:
        self.user_repo.ensure_user(user_id)

        # 🔥 CHECK ITEM FROM SHOP SYSTEM
        item_key = "patronus_spell_book"

        owned = self.owned_item_repo.get_quantity(user_id, item_key)

        if owned <= 0:
            raise ValueError(
                "You need a Patronus Spell Book to discover or change your Patronus."
            )

        # 🔥 CONSUME ITEM
        self.owned_item_repo.remove_item(user_id, item_key, 1)

        # 🎲 ROLL RARITY
        rarity = random.choices(
            population=["common", "uncommon", "rare"],
            weights=[70, 25, 5],
            k=1,
        )[0]

        pool = self.patronus_repo.get_by_rarity(rarity)
        chosen = random.choice(pool)

        # 🔥 OVERWRITE OLD PATRONUS
        self.user_repo.set_patronus_id(user_id, int(chosen["id"]))

        return chosen