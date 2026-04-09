from pathlib import Path
from io import BytesIO
import re
import unicodedata
import urllib.error
import urllib.request

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

    CUSTOM_EMOJI_RE = re.compile(r"<a?:[A-Za-z0-9_~]{2,}:(\d+)>")
    _EMOJI_CACHE: dict[str, Image.Image | None] = {}

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
        self.emoji_cache_dir = self.resources_dir / ".emoji_cache"
        self.emoji_cache_dir.mkdir(parents=True, exist_ok=True)

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

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for candidate in self._get_font_candidates():
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

    def _is_variation_selector(self, ch: str) -> bool:
        return 0xFE00 <= ord(ch) <= 0xFE0F

    def _is_skin_tone_modifier(self, ch: str) -> bool:
        return 0x1F3FB <= ord(ch) <= 0x1F3FF

    def _is_regional_indicator(self, ch: str) -> bool:
        return 0x1F1E6 <= ord(ch) <= 0x1F1FF

    def _is_keycap_base(self, ch: str) -> bool:
        return ch.isdigit() or ch in {"#", "*"}

    def _is_emoji_base(self, ch: str) -> bool:
        code = ord(ch)
        return (
            0x1F300 <= code <= 0x1FAFF
            or 0x2600 <= code <= 0x27BF
            or 0x2300 <= code <= 0x23FF
            or 0x2190 <= code <= 0x21FF
            or 0x25A0 <= code <= 0x25FF
        )

    def _emoji_to_codepoint_string(self, emoji: str) -> str:
        codepoints: list[str] = []

        for ch in emoji:
            code = ord(ch)
            if code == 0xFE0F:
                continue
            codepoints.append(f"{code:x}")

        return "-".join(codepoints)

    def _twemoji_cache_path(self, codepoint_string: str) -> Path:
        return self.emoji_cache_dir / f"{codepoint_string}.png"

    def _download_image(self, url: str) -> bytes | None:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 HogwartsBot/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None

    def _load_image_from_bytes(self, data: bytes) -> Image.Image | None:
        try:
            image = Image.open(BytesIO(data)).convert("RGBA")
            image.load()
            return image
        except Exception:
            return None

    def _get_twemoji_image(self, emoji: str) -> Image.Image | None:
        codepoint_string = self._emoji_to_codepoint_string(emoji)
        if not codepoint_string:
            return None

        cache_key = f"twemoji:{codepoint_string}"
        if cache_key in self._EMOJI_CACHE:
            cached = self._EMOJI_CACHE[cache_key]
            return cached.copy() if cached is not None else None

        cache_path = self._twemoji_cache_path(codepoint_string)
        if cache_path.exists():
            try:
                image = Image.open(cache_path).convert("RGBA")
                image.load()
                self._EMOJI_CACHE[cache_key] = image.copy()
                return image
            except Exception:
                pass

        urls = [
            f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14/assets/72x72/{codepoint_string}.png",
            f"https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{codepoint_string}.png",
        ]

        for url in urls:
            data = self._download_image(url)
            if not data:
                continue

            image = self._load_image_from_bytes(data)
            if image is None:
                continue

            try:
                cache_path.write_bytes(data)
            except Exception:
                pass

            self._EMOJI_CACHE[cache_key] = image.copy()
            return image

        self._EMOJI_CACHE[cache_key] = None
        return None

    def _get_custom_emoji_image(self, raw_emoji: str) -> Image.Image | None:
        match = self.CUSTOM_EMOJI_RE.fullmatch(raw_emoji)
        if not match:
            return None

        emoji_id = match.group(1)
        animated = raw_emoji.startswith("<a:")
        ext = "gif" if animated else "png"

        cache_key = f"custom:{emoji_id}:{ext}"
        if cache_key in self._EMOJI_CACHE:
            cached = self._EMOJI_CACHE[cache_key]
            return cached.copy() if cached is not None else None

        cache_path = self.emoji_cache_dir / f"{emoji_id}.{ext}"
        if cache_path.exists():
            try:
                image = Image.open(cache_path).convert("RGBA")
                image.load()
                self._EMOJI_CACHE[cache_key] = image.copy()
                return image
            except Exception:
                pass

        url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}?size=96&quality=lossless"
        data = self._download_image(url)
        if not data:
            self._EMOJI_CACHE[cache_key] = None
            return None

        image = self._load_image_from_bytes(data)
        if image is None:
            self._EMOJI_CACHE[cache_key] = None
            return None

        try:
            cache_path.write_bytes(data)
        except Exception:
            pass

        self._EMOJI_CACHE[cache_key] = image.copy()
        return image

    def _extract_emoji_cluster(self, text: str, start: int) -> tuple[str | None, int]:
        substring = text[start:]

        custom_match = self.CUSTOM_EMOJI_RE.match(substring)
        if custom_match:
            raw = custom_match.group(0)
            return raw, start + len(raw)

        ch = text[start]

        if self._is_regional_indicator(ch):
            end = start + 1
            if end < len(text) and self._is_regional_indicator(text[end]):
                end += 1
            return text[start:end], end

        if self._is_keycap_base(ch):
            end = start + 1
            if end < len(text) and ord(text[end]) == 0xFE0F:
                end += 1
            if end < len(text) and ord(text[end]) == 0x20E3:
                end += 1
                return text[start:end], end

        if not self._is_emoji_base(ch):
            return None, start

        end = start + 1

        while end < len(text) and (
            self._is_variation_selector(text[end]) or self._is_skin_tone_modifier(text[end])
        ):
            end += 1

        while end < len(text) and ord(text[end]) == 0x200D:
            next_pos = end + 1
            if next_pos >= len(text):
                break

            if not self._is_emoji_base(text[next_pos]) and not self._is_regional_indicator(text[next_pos]):
                break

            end = next_pos + 1

            while end < len(text) and (
                self._is_variation_selector(text[end]) or self._is_skin_tone_modifier(text[end])
            ):
                end += 1

        return text[start:end], end

    def _tokenize_banner_text(self, text: str) -> list[dict]:
        tokens: list[dict] = []
        buffer: list[str] = []
        i = 0

        def flush_text_buffer() -> None:
            nonlocal buffer
            if not buffer:
                return
            raw_text = "".join(buffer)
            normalized = self._normalize_banner_text(raw_text)
            if normalized:
                tokens.append(
                    {
                        "kind": "text",
                        "raw": raw_text,
                        "value": normalized,
                    }
                )
            buffer = []

        while i < len(text):
            emoji, next_i = self._extract_emoji_cluster(text, i)
            if emoji is not None and next_i > i:
                flush_text_buffer()

                kind = "custom_emoji" if self.CUSTOM_EMOJI_RE.fullmatch(emoji) else "emoji"
                tokens.append(
                    {
                        "kind": kind,
                        "raw": emoji,
                        "value": emoji,
                    }
                )
                i = next_i
                continue

            buffer.append(text[i])
            i += 1

        flush_text_buffer()
        return tokens

    def _measure_banner_tokens(
        self,
        draw: ImageDraw.ImageDraw,
        tokens: list[dict],
        text_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        stroke_width: int,
        emoji_size: int,
        emoji_gap: int,
    ) -> tuple[int, int]:
        total_width = 0
        max_height = 0

        for idx, token in enumerate(tokens):
            if token["kind"] == "text":
                bbox = draw.textbbox(
                    (0, 0),
                    token["value"],
                    font=text_font,
                    stroke_width=stroke_width,
                )
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
            else:
                width = emoji_size
                height = emoji_size

            total_width += width
            max_height = max(max_height, height)

            if idx < len(tokens) - 1:
                total_width += emoji_gap

        return total_width, max_height

    def _fit_banner_layout(
        self,
        draw: ImageDraw.ImageDraw,
        tokens: list[dict],
        max_width: int,
        max_height: int,
        max_font_size: int = 110,
        min_font_size: int = 28,
    ) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, int, int, int]:
        for size in range(max_font_size, min_font_size - 1, -2):
            font = self._load_font(size)
            stroke_width = max(2, size // 18)
            emoji_size = max(20, int(size * 1.05))
            emoji_gap = max(2, int(size * 0.08))

            width, height = self._measure_banner_tokens(
                draw=draw,
                tokens=tokens,
                text_font=font,
                stroke_width=stroke_width,
                emoji_size=emoji_size,
                emoji_gap=emoji_gap,
            )

            if width <= max_width and height <= max_height:
                return font, stroke_width, emoji_size, emoji_gap

        fallback_size = min_font_size
        return (
            self._load_font(fallback_size),
            max(2, fallback_size // 18),
            max(20, int(fallback_size * 1.05)),
            max(2, int(fallback_size * 0.08)),
        )

    def _resize_emoji_image(self, image: Image.Image, emoji_size: int) -> Image.Image:
        src_w, src_h = image.size
        if src_w <= 0 or src_h <= 0:
            return image

        scale = min(emoji_size / src_w, emoji_size / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))
        return image.resize((new_w, new_h), Image.LANCZOS)

    def _get_token_image(self, token: dict) -> Image.Image | None:
        if token["kind"] == "emoji":
            return self._get_twemoji_image(token["value"])
        if token["kind"] == "custom_emoji":
            return self._get_custom_emoji_image(token["value"])
        return None

    def _draw_banner_tokens(
        self,
        image: Image.Image,
        draw: ImageDraw.ImageDraw,
        x: float,
        y: float,
        tokens: list[dict],
        text_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        style: dict[str, tuple[int, int, int, int]],
        stroke_width: int,
        shadow_offset: int,
        emoji_size: int,
        emoji_gap: int,
    ) -> None:
        current_x = x

        font_bbox = draw.textbbox(
            (0, 0),
            "Ag",
            font=text_font,
            stroke_width=stroke_width,
        )
        text_height = font_bbox[3] - font_bbox[1]

        for idx, token in enumerate(tokens):
            if token["kind"] == "text":
                bbox = draw.textbbox(
                    (0, 0),
                    token["value"],
                    font=text_font,
                    stroke_width=stroke_width,
                )
                token_width = bbox[2] - bbox[0]

                draw.text(
                    (current_x + shadow_offset, y + shadow_offset),
                    token["value"],
                    font=text_font,
                    fill=style["shadow"],
                    stroke_width=0,
                )

                outline_offsets = [
                    (-stroke_width, 0),
                    (stroke_width, 0),
                    (0, -stroke_width),
                    (0, stroke_width),
                    (-stroke_width, -stroke_width),
                    (-stroke_width, stroke_width),
                    (stroke_width, -stroke_width),
                    (stroke_width, stroke_width),
                ]

                for dx, dy in outline_offsets:
                    draw.text(
                        (current_x + dx, y + dy),
                        token["value"],
                        font=text_font,
                        fill=style["stroke"],
                        stroke_width=0,
                    )

                draw.text(
                    (current_x, y),
                    token["value"],
                    font=text_font,
                    fill=style["fill"],
                    stroke_width=0,
                )
                
            else:
                token_width = emoji_size
                emoji_img = self._get_token_image(token)

                if emoji_img is not None:
                    resized = self._resize_emoji_image(emoji_img, emoji_size)
                    paste_x = int(round(current_x + (emoji_size - resized.width) / 2))
                    paste_y = int(round(y + (text_height - resized.height) / 2 + stroke_width * 0.15))
                    image.alpha_composite(resized, (paste_x, paste_y))
                else:
                    fallback = "□"
                    bbox = draw.textbbox(
                        (0, 0),
                        fallback,
                        font=text_font,
                        stroke_width=stroke_width,
                    )
                    fallback_width = bbox[2] - bbox[0]
                    fallback_x = current_x + (emoji_size - fallback_width) / 2

                    draw.text(
                        (fallback_x + shadow_offset, y + shadow_offset),
                        fallback,
                        font=text_font,
                        fill=style["shadow"],
                        stroke_width=0,
                    )
                    draw.text(
                        (fallback_x, y),
                        fallback,
                        font=text_font,
                        fill=style["fill"],
                        stroke_width=stroke_width,
                        stroke_fill=style["stroke"],
                    )

            current_x += token_width
            if idx < len(tokens) - 1:
                current_x += emoji_gap

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
        tokens = self._tokenize_banner_text(raw_text)

        if not tokens:
            tokens = [{"kind": "text", "raw": "Unknown Wizard", "value": "Unknown Wizard"}]

        width, height = image.size

        text_area_left = int(width * 0.14)
        text_area_right = int(width * 0.86)
        text_area_top = int(height * 0.28)
        text_area_bottom = int(height * 0.78)

        max_text_width = text_area_right - text_area_left
        max_text_height = text_area_bottom - text_area_top

        font, stroke_width, emoji_size, emoji_gap = self._fit_banner_layout(
            draw=draw,
            tokens=tokens,
            max_width=max_text_width,
            max_height=max_text_height,
            max_font_size=min(200, int(height * 0.27)),
            min_font_size=30,
        )

        total_width, total_height = self._measure_banner_tokens(
            draw=draw,
            tokens=tokens,
            text_font=font,
            stroke_width=stroke_width,
            emoji_size=emoji_size,
            emoji_gap=emoji_gap,
        )

        approx_size = getattr(font, "size", 48)
        shadow_offset = max(2, approx_size // 20)

        x = (width - total_width) / 2
        y = ((text_area_top + text_area_bottom) / 2 - total_height / 2) + 75

        self._draw_banner_tokens(
            image=image,
            draw=draw,
            x=x,
            y=y,
            tokens=tokens,
            text_font=font,
            style=style,
            stroke_width=stroke_width,
            shadow_offset=shadow_offset,
            emoji_size=emoji_size,
            emoji_gap=emoji_gap,
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
        year_start_at = user_row["year_start_at"]
        if current_level >= 7:
            progress_text = "7th Year reached"
        elif year_start_at:
            from datetime import datetime
            from services.leveling_service import LevelingService
            level_service = LevelingService(self.user_repo)
            progress_text = level_service.progress_to_next_year(
                datetime.fromisoformat(year_start_at),
                current_level,
            )
        else:
            progress_text = "Not initialized"

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