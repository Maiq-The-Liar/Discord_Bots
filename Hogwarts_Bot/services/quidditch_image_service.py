from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class QuidditchImageService:
    RESOURCE_DIR = Path(__file__).resolve().parent.parent / "resources" / "stands_matchup"
    FONT_DIR = Path(__file__).resolve().parent.parent / "resources" / "house_banners"

    LEFT_COORDS = {
        "seeker": (240, 250),
        "chaser_1": (120, 405),
        "chaser_2": (240, 470),
        "chaser_3": (360, 405),
        "beater_1": (170, 585),
        "beater_2": (310, 585),
        "keeper": (240, 760),
    }
    RIGHT_COORDS = {
        "seeker": (784, 250),
        "chaser_1": (664, 405),
        "chaser_2": (784, 470),
        "chaser_3": (904, 405),
        "beater_1": (714, 585),
        "beater_2": (854, 585),
        "keeper": (784, 760),
    }

    SCORE_LEFT = (360, 72)
    SCORE_RIGHT = (664, 72)

    def render_match_image(
        self,
        *,
        home_house: str,
        away_house: str,
        home_score: int,
        away_score: int,
        home_lineup: list[dict[str, Any]],
        away_lineup: list[dict[str, Any]],
    ) -> Path:
        base_path = self._resolve_matchup_path(home_house, away_house)
        image = Image.open(base_path).convert("RGBA")
        draw = ImageDraw.Draw(image)

        score_font = self._load_score_font(78)
        name_font = self._load_name_font(18)

        self._draw_centered_text(draw, self.SCORE_LEFT, f"{home_score:04d}", score_font)
        self._draw_centered_text(draw, self.SCORE_RIGHT, f"{away_score:04d}", score_font)

        self._draw_lineup(draw, home_lineup, self.LEFT_COORDS, name_font)
        self._draw_lineup(draw, away_lineup, self.RIGHT_COORDS, name_font)

        output_path = (
            Path(tempfile.gettempdir())
            / f"quidditch_{home_house}_{away_house}_{home_score}_{away_score}.png"
        )
        image.save(output_path)
        return output_path

    def build_demo_lineup(self, house_name: str) -> list[dict[str, Any]]:
        prefix = house_name.lower()
        return [
            {"username": f"{prefix}_hawk", "position": "seeker", "level": 31},
            {"username": f"{prefix}_flash", "position": "chaser", "level": 27},
            {"username": f"{prefix}_comet", "position": "chaser", "level": 24},
            {"username": f"{prefix}_arrow", "position": "chaser", "level": 29},
            {"username": f"{prefix}_drum", "position": "beater", "level": 22},
            {"username": f"{prefix}_forge", "position": "beater", "level": 25},
            {"username": f"{prefix}_wall", "position": "keeper", "level": 28},
        ]

    def _resolve_matchup_path(self, home_house: str, away_house: str) -> Path:
        candidates = [
            f"{home_house}_{away_house}.png",
            f"{home_house}-{away_house}.png",
            f"{away_house}_{home_house}.png",
            f"{away_house}-{home_house}.png",
        ]

        for name in candidates:
            path = self.RESOURCE_DIR / name
            if path.exists():
                return path

        raise FileNotFoundError(
            f"No Quidditch matchup image found for {home_house} vs {away_house}."
        )

    def _draw_lineup(
        self,
        draw: ImageDraw.ImageDraw,
        lineup: list[dict[str, Any]],
        coord_map: dict[str, tuple[int, int]],
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> None:
        ordered = self._order_lineup(lineup)
        slots = [
            "seeker",
            "chaser_1",
            "chaser_2",
            "chaser_3",
            "beater_1",
            "beater_2",
            "keeper",
        ]

        for slot, player in zip(slots, ordered):
            label = (
                f"{player['username']} "
                f"({str(player['position']).lower()} lv. {int(player['level'])})"
            )
            self._draw_centered_text(draw, coord_map[slot], label, font)

    def _order_lineup(self, lineup: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seekers = [p for p in lineup if str(p.get("position", "")).lower() == "seeker"]
        chasers = [p for p in lineup if str(p.get("position", "")).lower() == "chaser"]
        beaters = [p for p in lineup if str(p.get("position", "")).lower() == "beater"]
        keepers = [p for p in lineup if str(p.get("position", "")).lower() == "keeper"]
        return seekers[:1] + chasers[:3] + beaters[:2] + keepers[:1]

    def _load_score_font(self, size: int):
        harry_font = self.FONT_DIR / "HARRYP__.TTF"
        try:
            return ImageFont.truetype(str(harry_font), size=size)
        except OSError:
            return self._load_name_font(size)

    def _load_name_font(self, size: int):
        for candidate in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _draw_centered_text(self, draw, center, text, font) -> None:
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        pos = (center[0] - width / 2, center[1] - height / 2)

        draw.text(
            pos,
            text,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 255),
        )