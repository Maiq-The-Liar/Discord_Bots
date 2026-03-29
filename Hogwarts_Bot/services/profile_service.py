from pathlib import Path
import os

import discord

from domain.constants import (
    AGE_ROLE_IDS,
    HOUSE_COLORS,
    HOUSE_PROFILE_BANNERS,
    HOGWARTS_CREST_EMOJI,
    PRONOUN_ROLE_IDS,
)
from domain.role_context import MemberRoleContext
from repositories.user_repository import UserRepository
from repositories.inventory_repository import InventoryRepository
from repositories.contribution_repository import ContributionRepository
from repositories.patronus_repository import PatronusRepository
from repositories.chocolate_frog_repository import ChocolateFrogRepository
from repositories.frog_collection_repository import FrogCollectionRepository
from services.birthday_service import BirthdayService


class ProfileService:
    def __init__(
        self,
        user_repo: UserRepository,
        inventory_repo: InventoryRepository,
        contribution_repo: ContributionRepository,
        frog_collection_repo: FrogCollectionRepository,
    ):
        self.user_repo = user_repo
        self.inventory_repo = inventory_repo
        self.contribution_repo = contribution_repo
        self.frog_collection_repo = frog_collection_repo
        self.birthday_service = BirthdayService()

        base_dir = Path(__file__).resolve().parents[1]
        self.patronus_repo = PatronusRepository(
            str(base_dir / "resources" / "patronus.json")
        )
        self.chocolate_frog_repo = ChocolateFrogRepository(
            str(base_dir / "resources" / "chocolate_frogs.json")
        )

    def _resolve_age_text(self, member: discord.Member) -> str:
        for role in member.roles:
            if role.id in AGE_ROLE_IDS:
                return role.name
        return "n/a"

    def _resolve_pronouns_text(self, member: discord.Member) -> str:
        for role in member.roles:
            if role.id in PRONOUN_ROLE_IDS:
                return role.name
        return "n/a"

    def build_profile_message(
        self,
        member: discord.Member,
        role_ctx: MemberRoleContext,
    ) -> tuple[list[discord.Embed], list[discord.File]]:
        self.user_repo.ensure_user(member.id)

        user_row = self.user_repo.get_user(member.id)

        monthly_points = 0
        if role_ctx.current_house:
            monthly_points = self.contribution_repo.get_monthly_points_for_user_house(
                member.id,
                role_ctx.current_house,
            )

        color = HOUSE_COLORS.get(role_ctx.current_house or "", 0x2F3136)

        patronus_name = "No Patronus yet"
        patronus_rarity = "-"
        patronus_gif_url = None

        patronus_id = self.user_repo.get_patronus_id(member.id)
        if patronus_id is not None:
            patronus = self.patronus_repo.get_by_id(patronus_id)
            if patronus is not None:
                patronus_name = patronus.get("name", "Unknown")
                patronus_rarity = patronus.get("rarity", "Unknown").capitalize()
                patronus_gif_url = patronus.get("gif_url")

        pronouns = self._resolve_pronouns_text(member)
        age_text = self._resolve_age_text(member)
        bio_text = user_row["bio"] if user_row["bio"] else "n/a"

        birth_day, birth_month = self.user_repo.get_birthday(member.id)
        if birth_day and birth_month:
            birthday_text = self.birthday_service.format_birthday(birth_day, birth_month)
            zodiac_sign = self.birthday_service.get_zodiac_sign(birth_day, birth_month)
            zodiac_text = self.birthday_service.get_zodiac_display(zodiac_sign)
        else:
            birthday_text = "n/a"
            zodiac_text = "n/a"

        collected_frogs = self.frog_collection_repo.get_unique_count(member.id)
        total_possible_frogs = self.chocolate_frog_repo.get_total_count()

        files: list[discord.File] = []

        banner_embed = discord.Embed(color=color)

        banner_path = HOUSE_PROFILE_BANNERS.get(role_ctx.current_house or "")
        if banner_path:
            banner_filename = os.path.basename(banner_path)
            files.append(discord.File(banner_path, filename=banner_filename))
            banner_embed.set_image(url=f"attachment://{banner_filename}")
        else:
            banner_embed.description = f"# {member.display_name}'s Profile"

        info_lines = [
            f"╭ • **Name:** {member.display_name}",
            f"│ • **Pronouns:** {pronouns}",
            f"│ • **Birthday:** {birthday_text}",
            f"│ • **Zodiac Sign:** {zodiac_text}",
            f"│ • **Age:** {age_text}",
            f"╰ • **Bio:** {bio_text}",
        ]

        current_level = int(user_row["level"])
        current_xp = int(user_row["xp"])

        if current_level >= 7:
            xp_progress_text = "MAX"
        else:
            needed_xp = 5 * (current_level ** 2) + 50 * current_level + 100
            xp_progress_text = f"{current_xp} / {needed_xp}"

        stats_lines = [
            f"╭ • **Monthly Housepoints:** {monthly_points}",
            f"│ • **Total collected Housepoints:** {user_row['lifetime_house_points']}",
            f"│ • **Balance:** {user_row['sickles_balance']} Galleons",
            f"│ • **School Year Level:** {current_level}",
            f"│ • **XP Progress:** {xp_progress_text}",
            f"╰ • **Collected Chocolate Frogs:** {collected_frogs} / {total_possible_frogs}",
        ]

        patronus_lines = [
            f"╭ • **Patronus Name:** {patronus_name}",
            f"╰ • **Rarity:** {patronus_rarity}",
        ]

        main_description = (
            f"{HOGWARTS_CREST_EMOJI} **─────Info─────** {HOGWARTS_CREST_EMOJI}\n"
            + "\n".join(info_lines)
            + "\n\n"
            + f"{HOGWARTS_CREST_EMOJI} **─────Stats─────** {HOGWARTS_CREST_EMOJI}\n"
            + "\n".join(stats_lines)
            + "\n\n"
            + f"{HOGWARTS_CREST_EMOJI} **─────Patronus─────** {HOGWARTS_CREST_EMOJI}\n"
            + "\n".join(patronus_lines)
        )

        main_embed = discord.Embed(
            description=main_description,
            color=color,
        )
        main_embed.set_thumbnail(url=member.display_avatar.url)

        if patronus_gif_url:
            main_embed.set_image(url=patronus_gif_url)

        if role_ctx.has_arena_role:
            main_embed.set_footer(text="Arena role active")

        return [banner_embed, main_embed], files