import calendar
import random
from datetime import datetime

from domain.constants import ZODIAC_DISPLAY


class BirthdayService:
    def validate_birthday(self, day: int, month: int) -> None:
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12.")

        max_day = calendar.monthrange(2000, month)[1]
        if day < 1 or day > max_day:
            raise ValueError(f"Day must be between 1 and {max_day} for this month.")

    def format_birthday(self, day: int, month: int) -> str:
        month_name = calendar.month_name[month].upper()
        return f"{day:02d} / {month_name}"

    def get_zodiac_sign(self, day: int, month: int) -> str:
        if (month == 3 and day >= 21) or (month == 4 and day <= 19):
            return "Aries"
        if (month == 4 and day >= 20) or (month == 5 and day <= 20):
            return "Taurus"
        if (month == 5 and day >= 21) or (month == 6 and day <= 20):
            return "Gemini"
        if (month == 6 and day >= 21) or (month == 7 and day <= 22):
            return "Cancer"
        if (month == 7 and day >= 23) or (month == 8 and day <= 22):
            return "Leo"
        if (month == 8 and day >= 23) or (month == 9 and day <= 22):
            return "Virgo"
        if (month == 9 and day >= 23) or (month == 10 and day <= 22):
            return "Libra"
        if (month == 10 and day >= 23) or (month == 11 and day <= 21):
            return "Scorpio"
        if (month == 11 and day >= 22) or (month == 12 and day <= 21):
            return "Sagittarius"
        if (month == 12 and day >= 22) or (month == 1 and day <= 19):
            return "Capricorn"
        if (month == 1 and day >= 20) or (month == 2 and day <= 18):
            return "Aquarius"
        return "Pisces"

    def get_zodiac_display(self, sign: str) -> str:
        return ZODIAC_DISPLAY.get(sign, sign)

    def today_parts(self) -> tuple[int, int, str]:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        return now.day, now.month, date_str

    def roll_birthday_gift(self) -> dict:
        roll = random.random()

        if roll < 0.70:
            return {
                "item_key": "chocolate_frog",
                "quantity": 1,
                "label": "1 Chocolate Frog",
            }
        if roll < 0.90:
            return {
                "item_key": "chocolate_frog",
                "quantity": 2,
                "label": "2 Chocolate Frogs",
            }
        if roll < 0.98:
            return {
                "item_key": "chocolate_frog",
                "quantity": 3,
                "label": "3 Chocolate Frogs",
            }

        return {
            "item_key": "patronus_spell_book",
            "quantity": 1,
            "label": "1 Patronus Lesson Book",
        }