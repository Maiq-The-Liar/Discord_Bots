from pathlib import Path
from io import BytesIO
import os

import discord
from PIL import Image, ImageDraw, ImageFont

from domain.constants import (
    AGE_ROLE_IDS,
    HOUSE_COLORS,
    HOUSE_PROFILE_BANNERS,
    HOGWARTS_CREST_EMOJI,
    PRONOUN_ROLE_IDS,
    CONTINENT_ROLE_IDS,
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
    # Adjustable banner text styling per house:
    # fill = main text color
    # stroke = outline color
    # shadow = soft shadow color
    HOUSE_BANNER_TEXT_STYLES: dict[str, dict[str, tuple[int, int, int, int]]] = {
        "Gryffindor": {
            "fill": (214, 167, 86, 255),
            "stroke": (74, 20, 16, 255),
            "shadow": (20, 6, 6, 185),
        },
        "Hufflepuff": {
            "fill": (214, 176, 52, 255),
            "stroke": (24, 24, 24, 255),
            "shadow": (0, 0, 0, 180),
        },
        "Ravenclaw": {
            "fill": (214, 191, 160, 255),
            "stroke": (58, 36, 24, 255),
            "shadow": (0, 0, 0, 185),
        },
        "Slytherin": {
            "fill": (196, 210, 198, 255),
            "stroke": (30, 30, 30, 255),
            "shadow": (0, 0, 0, 185),
        },
    }

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
        self.base_dir = base_dir
        self.resources_dir = base_dir / "resources"
        self.profile_banners_dir = self.resources_dir / "house_banners"

        self.patronus_repo = PatronusRepository(
            str(base_dir / "resources" / "patronus.json")
        )
        self.chocolate_frog_repo = ChocolateFrogRepository(
            str(base_dir / "resources" / "chocolate_frogs.json")
        )

    def _resolve_continent_text(self, member: discord.Member) -> str:
        for role in member.roles:
            if role.id in CONTINENT_ROLE_IDS:
                return role.name
        return "n/a"

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

    def _get_banner_path(self, house_name: str | None) -> Path | None:
        if not house_name:
            return None

        preferred_map = {
            "Gryffindor": self.profile_banners_dir / "gryffindor.png",
            "Hufflepuff": self.profile_banners_dir / "hufflepuff.png",
            "Ravenclaw": self.profile_banners_dir / "ravenclaw.png",
            "Slytherin": self.profile_banners_dir / "slytherin.png",
        }

        preferred_path = preferred_map.get(house_name)
        if preferred_path and preferred_path.exists():
            return preferred_path

        fallback = HOUSE_PROFILE_BANNERS.get(house_name)
        if fallback:
            fallback_path = Path(fallback)
            if fallback_path.exists():
                return fallback_path

        return None

    def _get_font_candidates(self) -> list[Path]:
        return [
            self.resources_dir / "house_banners" / "HARRYP__.TTF",
            self.resources_dir / "house_points" / "font" / "Crimson-Bold.otf",
            self.resources_dir / "house_points" / "font" / "Crimson-Bold.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        ]

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for candidate in self._get_font_candidates():
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size=size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def _fit_text_font(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        max_width: int,
        max_height: int,
        max_font_size: int = 110,
        min_font_size: int = 28,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for size in range(max_font_size, min_font_size - 1, -2):
            font = self._load_font(size)
            bbox = draw.textbbox((0, 0), text, font=font, stroke_width=max(2, size // 18))
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            if width <= max_width and height <= max_height:
                return font
        return self._load_font(min_font_size)

    def _render_profile_banner(
        self,
        house_name: str | None,
        display_name: str,
    ) -> discord.File | None:
        banner_path = self._get_banner_path(house_name)
        if banner_path is None or not banner_path.exists():
            return None

        image = Image.open(banner_path).convert("RGBA")
        draw = ImageDraw.Draw(image)

        style = self.HOUSE_BANNER_TEXT_STYLES.get(
            house_name or "",
            {
                "fill": (255, 255, 255, 255),
                "stroke": (0, 0, 0, 255),
                "shadow": (0, 0, 0, 170),
            },
        )

        text = display_name.strip() if display_name.strip() else "Unknown Wizard"

        width, height = image.size

        # Central empty panel area where the username should sit.
        # Tuned for the new banner shapes.
        text_area_left = int(width * 0.14)
        text_area_right = int(width * 0.86)
        text_area_top = int(height * 0.28)
        text_area_bottom = int(height * 0.78)

        max_text_width = text_area_right - text_area_left
        max_text_height = text_area_bottom - text_area_top

        font = self._fit_text_font(
            draw=draw,
            text=text,
            max_width=max_text_width,
            max_height=max_text_height,
            max_font_size=min(200, int(height * 0.27)),
            min_font_size=30,
        )

        # Recompute with final font.
        approx_size = getattr(font, "size", 48)
        stroke_width = max(2, approx_size // 18)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (width - text_width) / 2 - bbox[0]
        y = ((text_area_top + text_area_bottom) / 2 - text_height / 2) - bbox[1] + 75

        shadow_offset = max(2, approx_size // 20)

        draw.text(
            (x + shadow_offset, y + shadow_offset),
            text,
            font=font,
            fill=style["shadow"],
            stroke_width=0,
        )
        draw.text(
            (x, y),
            text,
            font=font,
            fill=style["fill"],
            stroke_width=stroke_width,
            stroke_fill=style["stroke"],
        )

        output = BytesIO()
        image.save(output, format="PNG")
        output.seek(0)

        safe_house = (house_name or "profile").lower()
        filename = f"{safe_house}_profile_banner.png"
        return discord.File(fp=output, filename=filename)

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
        patronus_rarity = "—"
        patronus_gif_url = None

        patronus_id = self.user_repo.get_patronus_id(member.id)
        if patronus_id is not None:
            patronus = self.patronus_repo.get_by_id(patronus_id)
            if patronus is not None:
                patronus_name = patronus.get("name", "Unknown")
                patronus_rarity = patronus.get("rarity", "Unknown").capitalize()
                patronus_gif_url = patronus.get("gif_url")

        pronouns = self._resolve_pronouns_text(member)
        continent_text = self._resolve_continent_text(member)
        age_text = self._resolve_age_text(member)
        bio_text = user_row["bio"].strip() if user_row["bio"] else "No bio set."

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

        current_level = int(user_row["level"])
        current_xp = int(user_row["xp"])

        if current_level >= 7:
            xp_progress_text = "MAX"
        else:
            needed_xp = 5 * (current_level ** 2) + 50 * current_level + 100
            xp_progress_text = f"{current_xp} / {needed_xp}"

        files: list[discord.File] = []

        # 1) Banner embed
        banner_embed = discord.Embed(color=color)

        banner_file = self._render_profile_banner(
            house_name=role_ctx.current_house,
            display_name=member.display_name,
        )

        if banner_file is not None:
            files.append(banner_file)
            banner_embed.set_image(url=f"attachment://{banner_file.filename}")
        else:
            banner_embed.title = f"{member.display_name}'s Profile"

        # 2) Main profile embed
        profile_embed = discord.Embed(
            description=(
                f"**House:** {role_ctx.current_house or 'None'}\n"
                f"**Patronus:** {patronus_name}"
            ),
            color=color,
        )
        profile_embed.set_thumbnail(url=member.display_avatar.url)

        profile_embed.add_field(
            name="About",
            value=(
                f"**Pronouns:** {pronouns}\n"
                f"**Birthday:** {birthday_text}\n"
                f"**Zodiac:** {zodiac_text}\n"
                f"**Continent:** {continent_text}\n"
                f"**Age:** {age_text}"
            ),
            inline=False,
        )

        profile_embed.add_field(
            name="Progress",
            value=(
                f"**Monthly Housepoints:** {monthly_points}\n"
                f"**Total Housepoints:** {user_row['lifetime_house_points']}\n"
                f"**Balance:** {user_row['sickles_balance']} Galleons\n"
                f"**School Year:** {current_level}\n"
                f"**XP:** {xp_progress_text}"
            ),
            inline=False,
        )

        profile_embed.add_field(
            name="Collection",
            value=(
                f"**Chocolate Frogs:** {collected_frogs} / {total_possible_frogs}\n"
                f"**Patronus Rarity:** {patronus_rarity}"
            ),
            inline=False,
        )

        profile_embed.add_field(
            name="Bio",
            value=bio_text,
            inline=False,
        )

        footer_parts = []
        if role_ctx.current_house:
            footer_parts.append(role_ctx.current_house)
        if role_ctx.has_arena_role:
            footer_parts.append("Arena active")

        if footer_parts:
            profile_embed.set_footer(text=" • ".join(footer_parts))

        embeds: list[discord.Embed] = [banner_embed, profile_embed]

        # 3) Patronus embed only if there is a patronus image
        if patronus_gif_url:
            patronus_embed = discord.Embed(
                title="Patronus",
                description=f"**{patronus_name}** • {patronus_rarity}",
                color=color,
            )
            patronus_embed.set_image(url=patronus_gif_url)
            embeds.append(patronus_embed)

        return embeds, files