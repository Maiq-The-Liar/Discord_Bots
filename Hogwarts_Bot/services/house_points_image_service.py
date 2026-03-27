from __future__ import annotations

from math import sin, pi
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import random


class HousePointsImageService:
    WIDTH = 1600
    HEIGHT = 1000
    BACKGROUND = (0, 0, 0, 0)

    HOUSE_ORDER = ["Slytherin", "Ravenclaw", "Hufflepuff", "Gryffindor"]

    HOUSE_COLORS = {
        "Slytherin": (34, 110, 55, 255),
        "Ravenclaw": (55, 85, 175, 255),
        "Hufflepuff": (205, 170, 70, 255),
        "Gryffindor": (185, 45, 35, 255),
    }

    CREST_FILES = {
        "Slytherin": "sc.png",
        "Ravenclaw": "rc.png",
        "Hufflepuff": "hc.png",
        "Gryffindor": "gc.png",
    }

    GOLD_MAIN = (196, 154, 74, 255)
    GOLD_DARK = (104, 72, 28, 255)

    GLASS_FILL = (240, 240, 245, 35)
    GLASS_OUTLINE = (240, 240, 245, 170)

    CENTER_X = [360, 660, 960, 1260]
    TOP_Y = 120
    BOTTOM_Y = 780

    TOP_CHAMBER_H = 130
    NECK_Y1 = 245
    NECK_Y2 = 310
    BOTTOM_CHAMBER_Y1 = 310
    BOTTOM_CHAMBER_Y2 = 740

    CHAMBER_W = 155
    BOTTOM_W = 145
    SOFT_CAP = 500.0

    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.resources_dir = base_dir / "resources" / "house_points"
        self.font_path = self.resources_dir / "font" / "Crimson-Bold.otf"
        self.generated_dir = base_dir / "resources" / "generated"
        self.generated_dir.mkdir(parents=True, exist_ok=True)

    def load_font(self, size: int):
        try:
            return ImageFont.truetype(str(self.font_path), size)
        except Exception:
            return ImageFont.load_default()

    def clamp(self, v, lo, hi):
        return max(lo, min(hi, v))

    def lerp(self, a, b, t):
        return a + (b - a) * t

    def blend(self, c1, c2, t):
        return tuple(int(self.lerp(c1[i], c2[i], t)) for i in range(4))

    def create_canvas(self):
        return Image.new("RGBA", (self.WIDTH, self.HEIGHT), self.BACKGROUND)

    def alpha_composite(self, base, overlay):
        return Image.alpha_composite(base, overlay)

    def points_to_ratio(self, points: int) -> float:
        points = max(0, points)
        if points == 0:
            return 0.0

        ratio = points / (points + self.SOFT_CAP)
        return max(0.02, ratio)

    def draw_gold_bar(self, img, box, radius=18):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        x1, y1, x2, y2 = box
        draw.rounded_rectangle(box, radius=radius, fill=self.GOLD_MAIN)

        inner = (x1 + 3, y1 + 3, x2 - 3, y2 - 3)
        draw.rounded_rectangle(inner, radius=max(1, radius - 3), outline=self.GOLD_DARK, width=3)

        hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        hdraw = ImageDraw.Draw(hl)
        strip_h = max(3, (y2 - y1) // 4)
        hdraw.rounded_rectangle(
            (x1 + 4, y1 + 4, x2 - 4, y1 + 4 + strip_h),
            radius=max(1, radius - 4),
            fill=(255, 245, 205, 65),
        )
        hl = hl.filter(ImageFilter.GaussianBlur(2))
        layer = self.alpha_composite(layer, hl)

        return self.alpha_composite(img, layer)

    def draw_gold_rod(self, img, x, y1, y2, width=14):
        return self.draw_gold_bar(img, (x - width // 2, y1, x + width // 2, y2), radius=width // 2)

    def draw_gold_cap(self, img, cx, cy, r):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=self.GOLD_MAIN, outline=self.GOLD_DARK, width=2)
        d.ellipse(
            (cx - int(r * 0.6), cy - int(r * 0.75), cx + int(r * 0.35), cy - int(r * 0.1)),
            fill=(255, 240, 190, 70),
        )
        layer = layer.filter(ImageFilter.GaussianBlur(0.5))
        return self.alpha_composite(img, layer)

    def hourglass_masks(self, size, cx):
        top_mask = Image.new("L", size, 0)
        bot_mask = Image.new("L", size, 0)

        dt = ImageDraw.Draw(top_mask)
        db = ImageDraw.Draw(bot_mask)

        top_pts = [
            (cx - self.CHAMBER_W // 2, self.TOP_Y + 14),
            (cx + self.CHAMBER_W // 2, self.TOP_Y + 14),
            (cx + self.CHAMBER_W // 2 - 10, self.TOP_Y + self.TOP_CHAMBER_H - 25),
            (cx + 18, self.NECK_Y1),
            (cx, self.NECK_Y1 + 8),
            (cx - 18, self.NECK_Y1),
            (cx - self.CHAMBER_W // 2 + 10, self.TOP_Y + self.TOP_CHAMBER_H - 25),
        ]
        dt.polygon(top_pts, fill=255)

        bot_pts = [
            (cx - 16, self.NECK_Y2),
            (cx, self.NECK_Y2 - 8),
            (cx + 16, self.NECK_Y2),
            (cx + self.BOTTOM_W // 2 - 6, self.BOTTOM_CHAMBER_Y1 + 40),
            (cx + self.BOTTOM_W // 2, self.BOTTOM_CHAMBER_Y2 - 24),
            (cx + self.BOTTOM_W // 2 - 18, self.BOTTOM_CHAMBER_Y2),
            (cx - self.BOTTOM_W // 2 + 18, self.BOTTOM_CHAMBER_Y2),
            (cx - self.BOTTOM_W // 2, self.BOTTOM_CHAMBER_Y2 - 24),
            (cx - self.BOTTOM_W // 2 + 6, self.BOTTOM_CHAMBER_Y1 + 40),
        ]
        db.polygon(bot_pts, fill=255)

        top_mask = top_mask.filter(ImageFilter.GaussianBlur(1.2))
        bot_mask = bot_mask.filter(ImageFilter.GaussianBlur(1.2))
        return top_mask, bot_mask

    def draw_glass_outline(self, img, cx):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)

        top_pts = [
            (cx - self.CHAMBER_W // 2, self.TOP_Y + 14),
            (cx + self.CHAMBER_W // 2, self.TOP_Y + 14),
            (cx + self.CHAMBER_W // 2 - 10, self.TOP_Y + self.TOP_CHAMBER_H - 25),
            (cx + 18, self.NECK_Y1),
            (cx, self.NECK_Y1 + 8),
            (cx - 18, self.NECK_Y1),
            (cx - self.CHAMBER_W // 2 + 10, self.TOP_Y + self.TOP_CHAMBER_H - 25),
        ]
        bot_pts = [
            (cx - 16, self.NECK_Y2),
            (cx, self.NECK_Y2 - 8),
            (cx + 16, self.NECK_Y2),
            (cx + self.BOTTOM_W // 2 - 6, self.BOTTOM_CHAMBER_Y1 + 40),
            (cx + self.BOTTOM_W // 2, self.BOTTOM_CHAMBER_Y2 - 24),
            (cx + self.BOTTOM_W // 2 - 18, self.BOTTOM_CHAMBER_Y2),
            (cx - self.BOTTOM_W // 2 + 18, self.BOTTOM_CHAMBER_Y2),
            (cx - self.BOTTOM_W // 2, self.BOTTOM_CHAMBER_Y2 - 24),
            (cx - self.BOTTOM_W // 2 + 6, self.BOTTOM_CHAMBER_Y1 + 40),
        ]

        d.polygon(top_pts, fill=self.GLASS_FILL, outline=self.GLASS_OUTLINE)
        d.polygon(bot_pts, fill=self.GLASS_FILL, outline=self.GLASS_OUTLINE)
        d.line((cx, self.NECK_Y1 + 4, cx, self.NECK_Y2 - 4), fill=(240, 240, 245, 170), width=5)

        for offset, alpha in [(0.24, 75), (0.36, 30)]:
            x = int(cx - self.CHAMBER_W * 0.5 + self.CHAMBER_W * offset)
            d.rounded_rectangle((x, self.TOP_Y + 28, x + 10, self.NECK_Y1 - 16), radius=6, fill=(255, 255, 255, alpha))

        for offset, alpha in [(0.22, 75), (0.34, 30)]:
            x = int(cx - self.BOTTOM_W * 0.5 + self.BOTTOM_W * offset)
            d.rounded_rectangle(
                (x, self.BOTTOM_CHAMBER_Y1 + 36, x + 10, self.BOTTOM_CHAMBER_Y2 - 56),
                radius=6,
                fill=(255, 255, 255, alpha),
            )

        layer = layer.filter(ImageFilter.GaussianBlur(0.4))
        return self.alpha_composite(img, layer)

    def fill_masked_region(self, img, mask, region_box, color, grain_seed=0):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rectangle(region_box, fill=color)

        x1, y1, x2, y2 = region_box
        rng = random.Random(grain_seed)

        grain = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(grain)
        for _ in range(max(600, (x2 - x1) * (y2 - y1) // 25)):
            x = rng.randint(x1, x2)
            y = rng.randint(y1, y2)
            a = rng.randint(8, 28)
            gd.point((x, y), fill=(255, 255, 255, a))
        grain = grain.filter(ImageFilter.GaussianBlur(0.4))
        layer = self.alpha_composite(layer, grain)

        shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shade)
        width = x2 - x1
        sd.rectangle((x1 + int(width * 0.72), y1, x2, y2), fill=(0, 0, 0, 22))
        shade = shade.filter(ImageFilter.GaussianBlur(6))
        layer = self.alpha_composite(layer, shade)

        clipped = Image.new("RGBA", img.size, (0, 0, 0, 0))
        clipped.paste(layer, (0, 0), mask)
        return self.alpha_composite(img, clipped)

    def draw_sand_surface(self, img, mask, x1, x2, y, amplitude, color):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)

        pts = []
        for x in range(x1, x2 + 1, 4):
            t = (x - x1) / max(1, (x2 - x1))
            yy = y + sin(t * pi) * amplitude
            pts.append((x, yy))

        polygon = [(x1, self.HEIGHT), *pts, (x2, self.HEIGHT)]
        d.polygon(polygon, fill=color)

        clipped = Image.new("RGBA", img.size, (0, 0, 0, 0))
        clipped.paste(layer, (0, 0), mask)
        return self.alpha_composite(img, clipped)

    def draw_points_in_tube(self, img, cx, points):
        font_points = self.load_font(90)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)

        text = str(points)
        bbox = d.textbbox((0, 0), text, font=font_points)
        text_w = bbox[2] - bbox[0]

        text_x = cx - text_w / 2
        text_y = self.BOTTOM_CHAMBER_Y1 + 320

        d.text((text_x + 2, text_y + 2), text, font=font_points, fill=(0, 0, 0, 120))
        d.text((text_x, text_y), text, font=font_points, fill=(255, 255, 255, 255))

        return self.alpha_composite(img, layer)

    def load_and_resize_crest(self, house_name, max_size=(180, 180)):
        path = self.resources_dir / self.CREST_FILES[house_name]

        if not path.exists():
            return None

        crest = Image.open(path).convert("RGBA")
        crest.thumbnail(max_size, Image.LANCZOS)
        return crest

    def draw_top_crest(self, img, cx, house_name):
        crest = self.load_and_resize_crest(house_name)
        if crest is None:
            return img

        x = int(cx - crest.width / 2)
        y = 30

        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse(
            (x + 12, y + crest.height - 10, x + crest.width - 12, y + crest.height + 10),
            fill=(0, 0, 0, 35),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(8))
        img = self.alpha_composite(img, shadow)

        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        layer.paste(crest, (x, y), crest)
        return self.alpha_composite(img, layer)

    def draw_hourglass_frame(self, img, cx):
        left = cx - 100
        right = cx + 100

        img = self.draw_gold_rod(img, left, self.TOP_Y - 8, self.BOTTOM_Y - 40, width=14)
        img = self.draw_gold_rod(img, right, self.TOP_Y - 8, self.BOTTOM_Y - 40, width=14)

        img = self.draw_gold_bar(img, (left - 18, self.TOP_Y - 18, right + 18, self.TOP_Y + 20), radius=18)
        img = self.draw_gold_bar(img, (left - 18, self.BOTTOM_Y - 48, right + 18, self.BOTTOM_Y - 14), radius=18)

        img = self.draw_gold_cap(img, left, self.TOP_Y - 20, 18)
        img = self.draw_gold_cap(img, right, self.TOP_Y - 20, 18)

        img = self.draw_gold_cap(img, left, self.BOTTOM_Y - 18, 14)
        img = self.draw_gold_cap(img, right, self.BOTTOM_Y - 18, 14)

        return img

    def draw_single_hourglass(self, img, cx, house_name, points):
        ratio = self.clamp(self.points_to_ratio(points), 0.0, 1.0)

        img = self.draw_hourglass_frame(img, cx)

        top_mask, bot_mask = self.hourglass_masks(img.size, cx)
        img = self.draw_glass_outline(img, cx)

        color = self.HOUSE_COLORS[house_name]

        bot_h = self.BOTTOM_CHAMBER_Y2 - (self.BOTTOM_CHAMBER_Y1 + 10)
        fill_h = int(bot_h * ratio)

        if fill_h > 0:
            fill_top = self.BOTTOM_CHAMBER_Y2 - fill_h
            region = (cx - self.BOTTOM_W // 2, fill_top, cx + self.BOTTOM_W // 2, self.BOTTOM_CHAMBER_Y2)
            img = self.fill_masked_region(
                img,
                bot_mask,
                region,
                color,
                grain_seed=hash((house_name, points, "bot")) & 0xFFFFFFFF,
            )
            img = self.draw_sand_surface(
                img,
                bot_mask,
                cx - self.BOTTOM_W // 2,
                cx + self.BOTTOM_W // 2,
                fill_top - 8,
                amplitude=7,
                color=self.blend(color, (255, 255, 255, 255), 0.13),
            )

        remaining = 1.0 - ratio
        top_h = self.TOP_CHAMBER_H - 20
        rem_h = int(top_h * remaining)

        if rem_h > 0:
            region = (cx - self.CHAMBER_W // 2, self.TOP_Y + 18, cx + self.CHAMBER_W // 2, self.TOP_Y + 18 + rem_h)
            img = self.fill_masked_region(
                img,
                top_mask,
                region,
                color,
                grain_seed=hash((house_name, points, "top")) & 0xFFFFFFFF,
            )

        if 0 < ratio < 1:
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            d.line((cx, self.NECK_Y1 + 8, cx, self.NECK_Y2 + 12), fill=self.blend(color, (255, 255, 255, 255), 0.2), width=3)
            d.ellipse((cx - 5, self.NECK_Y2 + 10, cx + 5, self.NECK_Y2 + 20), fill=self.blend(color, (255, 255, 255, 255), 0.15))
            layer = layer.filter(ImageFilter.GaussianBlur(1))
            img = self.alpha_composite(img, layer)

        img = self.draw_points_in_tube(img, cx, points)
        img = self.draw_top_crest(img, cx, house_name)

        return img
    
    def crop_transparent_border(self, img: Image.Image, padding: int = 5) -> Image.Image:
        alpha = img.getchannel("A")
        bbox = alpha.getbbox()

        if bbox is None:
            return img

        left, top, right, bottom = bbox

        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(img.width, right + padding)
        bottom = min(img.height, bottom + padding)

        return img.crop((left, top, right, bottom))

    def generate_image(
        self,
        slytherin: int,
        ravenclaw: int,
        hufflepuff: int,
        gryffindor: int,
        output_filename: str = "house_points_board.png",
    ) -> Path:
        values = {
            "Slytherin": max(0, int(slytherin)),
            "Ravenclaw": max(0, int(ravenclaw)),
            "Hufflepuff": max(0, int(hufflepuff)),
            "Gryffindor": max(0, int(gryffindor)),
        }

        img = self.create_canvas()

        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        for cx in self.CENTER_X:
            sd.ellipse((cx - 115, self.BOTTOM_Y - 26, cx + 115, self.BOTTOM_Y + 12), fill=(0, 0, 0, 28))
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))
        img = self.alpha_composite(img, shadow)

        for cx, house in zip(self.CENTER_X, self.HOUSE_ORDER):
            img = self.draw_single_hourglass(img, cx, house, values[house])

        img = self.crop_transparent_border(img, padding=20)

        output_path = self.generated_dir / output_filename
        img.save(output_path)
        return output_path