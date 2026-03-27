import random

from repositories.user_repository import UserRepository
from repositories.owned_item_repository import OwnedItemRepository
from repositories.frog_collection_repository import FrogCollectionRepository
from repositories.chocolate_frog_repository import ChocolateFrogRepository


class ChocolateFrogService:
    FROG_ITEM_KEY = "chocolate_frog"

    def __init__(
        self,
        user_repo: UserRepository,
        owned_item_repo: OwnedItemRepository,
        frog_collection_repo: FrogCollectionRepository,
        frog_repo: ChocolateFrogRepository,
    ):
        self.user_repo = user_repo
        self.owned_item_repo = owned_item_repo
        self.frog_collection_repo = frog_collection_repo
        self.frog_repo = frog_repo

    def open_frog(self, user_id: int) -> dict:
        self.user_repo.ensure_user(user_id)

        owned = self.owned_item_repo.get_quantity(user_id, self.FROG_ITEM_KEY)
        if owned <= 0:
            raise ValueError("You do not have any Chocolate Frogs to open.")

        removed = self.owned_item_repo.remove_item(user_id, self.FROG_ITEM_KEY, 1)
        if not removed:
            raise ValueError("You do not have any Chocolate Frogs to open.")

        all_cards = self.frog_repo.get_all()
        if not all_cards:
            raise ValueError("No Chocolate Frog cards are available.")

        chosen = random.choice(all_cards)
        card_id = int(chosen["id"])

        previous_quantity = self.frog_collection_repo.get_card_quantity(user_id, card_id)
        is_new = previous_quantity == 0

        self.frog_collection_repo.add_card(user_id, card_id, 1)

        return {
            "card": chosen,
            "is_new": is_new,
            "new_card_quantity": previous_quantity + 1,
            "remaining_frogs": self.owned_item_repo.get_quantity(user_id, self.FROG_ITEM_KEY),
            "unique_cards": self.frog_collection_repo.get_unique_count(user_id),
            "total_cards": self.frog_repo.get_total_count(),
        }

    def get_album_page(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
    ) -> dict:
        self.user_repo.ensure_user(user_id)

        owned_cards = self.frog_collection_repo.get_all_cards_for_user(user_id)
        total_unique = len(owned_cards)
        total_cards = self.frog_repo.get_total_count()

        if total_unique == 0:
            return {
                "entries": [],
                "page": 1,
                "total_pages": 1,
                "total_unique": 0,
                "total_cards": total_cards,
            }

        total_pages = max(1, (total_unique + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))

        start = (page - 1) * page_size
        end = start + page_size
        page_entries = owned_cards[start:end]

        enriched_entries = []
        for entry in page_entries:
            card = self.frog_repo.get_by_id(entry["card_id"])
            if card is None:
                continue

            enriched_entries.append(
                {
                    "id": entry["card_id"],
                    "name": card["name"],
                    "description": card["description"],
                    "url": card["url"],
                    "quantity": entry["quantity"],
                }
            )

        return {
            "entries": enriched_entries,
            "page": page,
            "total_pages": total_pages,
            "total_unique": total_unique,
            "total_cards": total_cards,
        }

    def get_collection_progress(self, user_id: int) -> tuple[int, int]:
        self.user_repo.ensure_user(user_id)
        unique_cards = self.frog_collection_repo.get_unique_count(user_id)
        total_cards = self.frog_repo.get_total_count()
        return unique_cards, total_cards