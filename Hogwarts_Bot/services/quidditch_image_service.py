from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class QuidditchImageService:
    RESOURCE_DIR = Path(__file__).resolve().parent.parent / "resources" / "stands_matchup"
    FONT_DIR = Path(__file__).resolve().parent.parent / "resources" / "house_banners"

    LEFT_X = 250
    RIGHT_X = 790

    SEEKER_Y = 340
    CHASER_1_Y = 470
    CHASER_2_Y = 530
    CHASER_3_Y = 590
    BEATER_1_Y = 720
    BEATER_2_Y = 780
    KEEPER_Y = 1025

    SCORE_LEFT = (285, 62)
    SCORE_RIGHT = (735, 62)

    SIDE_TEXT_MAX_WIDTH = 470

    def get_display_order(self, home_house: str, away_house: str) -> tuple[str, str]:
        _, reverse_sides = self._resolve_matchup_path(home_house, away_house)
        if reverse_sides:
            return away_house, home_house
        return home_house, away_house

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
        base_path, reverse_sides = self._resolve_matchup_path(home_house, away_house)

        image = Image.open(base_path).convert("RGBA")
        draw = ImageDraw.Draw(image)

        if reverse_sides:
            left_house = away_house
            right_house = home_house
            left_score = away_score
            right_score = home_score
            left_lineup = away_lineup
            right_lineup = home_lineup
        else:
            left_house = home_house
            right_house = away_house
            left_score = home_score
            right_score = away_score
            left_lineup = home_lineup
            right_lineup = away_lineup

        score_font = self._load_score_font(96)

        self._draw_centered_text(
            draw,
            self.SCORE_LEFT,
            self._format_score(left_score),
            score_font,
        )
        self._draw_centered_text(
            draw,
            self.SCORE_RIGHT,
            self._format_score(right_score),
            score_font,
        )

        self._draw_side_lineup(draw=draw, lineup=left_lineup, x_center=self.LEFT_X)
        self._draw_side_lineup(draw=draw, lineup=right_lineup, x_center=self.RIGHT_X)

        output_path = (
            Path(tempfile.gettempdir())
            / f"quidditch_{left_house}_{right_house}_{left_score}_{right_score}.png"
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

    def _resolve_matchup_path(self, home_house: str, away_house: str) -> tuple[Path, bool]:
        exact_candidates = [
            self.RESOURCE_DIR / f"{home_house}_{away_house}.png",
            self.RESOURCE_DIR / f"{home_house}-{away_house}.png",
        ]
        for path in exact_candidates:
            if path.exists():
                return path, False

        reverse_candidates = [
            self.RESOURCE_DIR / f"{away_house}_{home_house}.png",
            self.RESOURCE_DIR / f"{away_house}-{home_house}.png",
        ]
        for path in reverse_candidates:
            if path.exists():
                return path, True

        raise FileNotFoundError(
            f"No Quidditch matchup image found for {home_house} vs {away_house}."
        )

    def _draw_side_lineup(
        self,
        *,
        draw: ImageDraw.ImageDraw,
        lineup: list[dict[str, Any]],
        x_center: int,
    ) -> None:
        ordered = self._order_lineup(lineup)
        y_positions = [
            self.SEEKER_Y,
            self.CHASER_1_Y,
            self.CHASER_2_Y,
            self.CHASER_3_Y,
            self.BEATER_1_Y,
            self.BEATER_2_Y,
            self.KEEPER_Y,
        ]

        for player, y in zip(ordered, y_positions):
            label = self._player_label(player)
            font = self._fit_name_font(
                draw,
                label,
                self.SIDE_TEXT_MAX_WIDTH,
                start_size=30,
                min_size=22,
            )
            self._draw_centered_text(draw, (x_center, y), label, font)

    def _player_label(self, player: dict[str, Any]) -> str:
        username = str(
            player.get("display_name")
            or player.get("username")
            or player.get("name")
            or "Unknown"
        ).strip()

        position = str(player.get("position", "")).lower().strip()
        level = int(player.get("level", 1))
        return f"{username} ({position} lv. {level})"

    def _order_lineup(self, lineup: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seekers = [p for p in lineup if str(p.get("position", "")).lower() == "seeker"]
        chasers = [p for p in lineup if str(p.get("position", "")).lower() == "chaser"]
        beaters = [p for p in lineup if str(p.get("position", "")).lower() == "beater"]
        keepers = [p for p in lineup if str(p.get("position", "")).lower() == "keeper"]
        return seekers[:1] + chasers[:3] + beaters[:2] + keepers[:1]

    def _format_score(self, score: int) -> str:
        return f"{score:04d}"

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

    def _fit_name_font(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        max_width: int,
        *,
        start_size: int,
        min_size: int,
    ):
        size = start_size
        while size >= min_size:
            font = self._load_name_font(size)
            bbox = draw.textbbox((0, 0), text, font=font, stroke_width=2)
            width = bbox[2] - bbox[0]
            if width <= max_width:
                return font
            size -= 1
        return self._load_name_font(min_size)

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