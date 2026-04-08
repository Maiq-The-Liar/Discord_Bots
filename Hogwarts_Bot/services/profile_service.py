from pathlib import Path
from io import BytesIO
import unicodedata

import discord
from PIL import Image, ImageDraw, ImageFont

from domain.constants import (
    HOUSE_COLORS,
    HOUSE_PROFILE_BANNERS,
    HOGWARTS_CREST_EMOJI,
)
from domain.role_registry import (
    ROLE_GROUP_AGES,
    ROLE_GROUP_CONTINENTS,
    ROLE_GROUP_PRONOUNS,
    role_names_for_group,
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
        valid_names = role_names_for_group(ROLE_GROUP_CONTINENTS)
        for role in member.roles:
            if role.name in valid_names:
                return role.name
        return "n/a"

    def _resolve_age_text(self, member: discord.Member) -> str:
        valid_names = role_names_for_group(ROLE_GROUP_AGES)
        for role in member.roles:
            if role.name in valid_names:
                return role.name
        return "n/a"

    def _resolve_pronouns_text(self, member: discord.Member) -> str:
        valid_names = role_names_for_group(ROLE_GROUP_PRONOUNS)
        for role in member.roles:
            if role.name in valid_names:
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

    def _get_emoji_font_candidates(self) -> list[Path]:
        return [
            Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"),
            Path("/usr/share/fonts/noto/NotoColorEmoji.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        ]

    def _load_font(
        self,
        size: int,
        candidates: list[Path] | None = None,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_candidates = candidates or self._get_font_candidates()
        for candidate in font_candidates:
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size=size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def _normalize_banner_text(self, text: str) -> str:
        replacements = {
            "ß": "ss",
            "ẞ": "SS",
            "æ": "ae",
            "Æ": "AE",
            "œ": "oe",
            "Œ": "OE",
            "ø": "o",
            "Ø": "O",
            "ł": "l",
            "Ł": "L",
            "đ": "d",
            "Đ": "D",
            "þ": "th",
            "Þ": "Th",
            "ð": "d",
            "Ð": "D",
        }

        for src, dst in replacements.items():
            text = text.replace(src, dst)

        decomposed = unicodedata.normalize("NFKD", text)
        return "".join(ch for ch in decomposed if not unicodedata.combining(ch))

    def _is_emoji_char(self, ch: str) -> bool:
        code = ord(ch)
        return (
            0x1F300 <= code <= 0x1FAFF
            or 0x2600 <= code <= 0x27BF
            or 0xFE00 <= code <= 0xFE0F
        )

    def _split_banner_runs(self, text: str) -> list[tuple[str, str]]:
        runs: list[tuple[str, str]] = []
        buffer: list[str] = []
        current_kind: str | None = None

        for ch in text:
            kind = "emoji" if self._is_emoji_char(ch) else "text"

            if current_kind is None:
                current_kind = kind

            if kind != current_kind:
                run_text = "".join(buffer)
                if current_kind == "text":
                    run_text = self._normalize_banner_text(run_text)
                if run_text:
                    runs.append((run_text, current_kind))
                buffer = [ch]
                current_kind = kind
            else:
                buffer.append(ch)

        if buffer:
            run_text = "".join(buffer)
            if current_kind == "text":
                run_text = self._normalize_banner_text(run_text)
            if run_text:
                runs.append((run_text, current_kind))

        return runs

    def _measure_text_runs(
        self,
        draw: ImageDraw.ImageDraw,
        runs: list[tuple[str, str]],
        text_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        emoji_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        stroke_width: int,
    ) -> tuple[int, int]:
        total_width = 0
        max_height = 0

        for run_text, kind in runs:
            font = emoji_font if kind == "emoji" else text_font
            current_stroke = 0 if kind == "emoji" else stroke_width

            try:
                bbox = draw.textbbox(
                    (0, 0),
                    run_text,
                    font=font,
                    stroke_width=current_stroke,
                    embedded_color=(kind == "emoji"),
                )
            except TypeError:
                bbox = draw.textbbox(
                    (0, 0),
                    run_text,
                    font=font,
                    stroke_width=current_stroke,
                )

            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]

            total_width += width
            max_height = max(max_height, height)

        return total_width, max_height

    def _fit_text_font(
        self,
        draw: ImageDraw.ImageDraw,
        runs: list[tuple[str, str]],
        max_width: int,
        max_height: int,
        max_font_size: int = 110,
        min_font_size: int = 28,
    ) -> tuple[
        ImageFont.FreeTypeFont | ImageFont.ImageFont,
        ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ]:
        for size in range(max_font_size, min_font_size - 1, -2):
            text_font = self._load_font(size, self._get_font_candidates())
            emoji_font = self._load_font(size, self._get_emoji_font_candidates())
            stroke_width = max(2, size // 18)

            width, height = self._measure_text_runs(
                draw=draw,
                runs=runs,
                text_font=text_font,
                emoji_font=emoji_font,
                stroke_width=stroke_width,
            )
            if width <= max_width and height <= max_height:
                return text_font, emoji_font

        return (
            self._load_font(min_font_size, self._get_font_candidates()),
            self._load_font(min_font_size, self._get_emoji_font_candidates()),
        )

    def _draw_text_runs(
        self,
        draw: ImageDraw.ImageDraw,
        x: float,
        y: float,
        runs: list[tuple[str, str]],
        text_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        emoji_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        style: dict[str, tuple[int, int, int, int]],
        stroke_width: int,
        shadow_offset: int,
    ) -> None:
        current_x = x

        for run_text, kind in runs:
            font = emoji_font if kind == "emoji" else text_font
            current_stroke = 0 if kind == "emoji" else stroke_width

            try:
                bbox = draw.textbbox(
                    (0, 0),
                    run_text,
                    font=font,
                    stroke_width=current_stroke,
                    embedded_color=(kind == "emoji"),
                )
            except TypeError:
                bbox = draw.textbbox(
                    (0, 0),
                    run_text,
                    font=font,
                    stroke_width=current_stroke,
                )

            run_width = bbox[2] - bbox[0]

            if kind == "text":
                draw.text(
                    (current_x + shadow_offset, y + shadow_offset),
                    run_text,
                    font=font,
                    fill=style["shadow"],
                    stroke_width=0,
                )
                draw.text(
                    (current_x, y),
                    run_text,
                    font=font,
                    fill=style["fill"],
                    stroke_width=stroke_width,
                    stroke_fill=style["stroke"],
                )
            else:
                try:
                    draw.text(
                        (current_x, y),
                        run_text,
                        font=font,
                        embedded_color=True,
                    )
                except TypeError:
                    draw.text(
                        (current_x, y),
                        run_text,
                        font=font,
                        fill=style["fill"],
                    )

            current_x += run_width

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

        raw_text = display_name.strip() if display_name.strip() else "Unknown Wizard"
        runs = self._split_banner_runs(raw_text)

        if not runs:
            runs = [("Unknown Wizard", "text")]

        width, height = image.size

        # Central empty panel area where the username should sit.
        # Tuned for the new banner shapes.
        text_area_left = int(width * 0.14)
        text_area_right = int(width * 0.86)
        text_area_top = int(height * 0.28)
        text_area_bottom = int(height * 0.78)

        max_text_width = text_area_right - text_area_left
        max_text_height = text_area_bottom - text_area_top

        text_font, emoji_font = self._fit_text_font(
            draw=draw,
            runs=runs,
            max_width=max_text_width,
            max_height=max_text_height,
            max_font_size=min(200, int(height * 0.27)),
            min_font_size=30,
        )

        approx_size = getattr(text_font, "size", 48)
        stroke_width = max(2, approx_size // 18)

        text_width, text_height = self._measure_text_runs(
            draw=draw,
            runs=runs,
            text_font=text_font,
            emoji_font=emoji_font,
            stroke_width=stroke_width,
        )

        x = (width - text_width) / 2
        y = ((text_area_top + text_area_bottom) / 2 - text_height / 2) + 75

        shadow_offset = max(2, approx_size // 20)

        self._draw_text_runs(
            draw=draw,
            x=x,
            y=y,
            runs=runs,
            text_font=text_font,
            emoji_font=emoji_font,
            style=style,
            stroke_width=stroke_width,
            shadow_offset=shadow_offset,
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
            zodiac_display = self.birthday_service.get_zodiac_display(zodiac_sign)
            zodiac_text = (
                zodiac_display.split(" ", 1)[1]
                if " " in zodiac_display
                else zodiac_display
            )
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

        profile_embed = discord.Embed(color=color)
        profile_embed.set_thumbnail(url=member.display_avatar.url)

        profile_embed.add_field(
            name="👤 __Profile__",
            value=(
                f"**Name:** {member.display_name}\n"
                f"**Patronus:** {patronus_name}\n"
                f"**School Year:** {current_level}\n"
                f"**Pronouns:** {pronouns}"
            ),
            inline=True,
        )
        profile_embed.add_field(
            name="🧭 __Details__",
            value=(
                f"**Birthday:** {birthday_text}\n"
                f"**Zodiac:** {zodiac_text}\n"
                f"**Age:** {age_text}\n"
                f"**Continent:** {continent_text}"
            ),
            inline=True,
        )

        profile_embed.add_field(
            name="🏰 __Hogwarts Progress__",
            value=(
                f"**Monthly Points:** {monthly_points}\n"
                f"**Total Points:** {user_row['lifetime_house_points']}\n"
                f"**XP:** {xp_progress_text}"
            ),
            inline=False,
        )

        profile_embed.add_field(
            name="💰 __Collection & Economy__",
            value=(
                f"**Balance:** {user_row['sickles_balance']} Galleons\n"
                f"**Chocolate Frogs:** {collected_frogs} / {total_possible_frogs}"
            ),
            inline=False,
        )

        profile_embed.add_field(
            name="✒️ __Bio__",
            value=bio_text,
            inline=False,
        )

        embeds: list[discord.Embed] = [banner_embed, profile_embed]

        if patronus_gif_url:
            patronus_embed = discord.Embed(color=color)
            patronus_embed.set_image(url=patronus_gif_url)
            patronus_embed.set_footer(text=f"{patronus_name} ({patronus_rarity})")
            embeds.append(patronus_embed)

        return embeds, files