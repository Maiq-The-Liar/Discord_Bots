from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RESOURCES_DIR = BASE_DIR / "resources"

HOUSE_ROLE_IDS: dict[int, str] = {
    1079764344717463579: "Gryffindor",
    1079764344717463577: "Hufflepuff",
    1079764344717463576: "Ravenclaw",
    1079764344717463578: "Slytherin",
}

ARENA_ROLE_ID = 1485343667089576077

HOUSE_COLORS: dict[str, int] = {
    "Gryffindor": 0xAE0001,
    "Hufflepuff": 0xFFDB00,
    "Ravenclaw": 0x0E1A40,
    "Slytherin": 0x1A472A,
}

HOUSE_EMOJIS: dict[str, str] = {
    "Gryffindor": "<:Gryffindor_Crest:1485316446996398220>",
    "Hufflepuff": "<:Huflepuff_Crest:1485316473382502712>",
    "Ravenclaw": "<:Ravenclaw_Crest:1485316498871550104>",
    "Slytherin": "<:Slitherin_Crest:1485316536783605790>",
}

HOUSE_PROFILE_BANNERS: dict[str, str] = {
    "Gryffindor": str(RESOURCES_DIR / "Gryffindor.png"),
    "Hufflepuff": str(RESOURCES_DIR / "Hufflepuff.png"),
    "Ravenclaw": str(RESOURCES_DIR / "Ravenclaw.png"),
    "Slytherin": str(RESOURCES_DIR / "Slytherin.png"),
}

HOGWARTS_CREST_EMOJI = "<:Hogwarts_Crest:1485317296519123027>"

GALLEONS_ICON = "<:Gelleons:1485318482802249808>"
CHOCOLATE_FROG_ICON = "<:Chocolate_Frog:1485321897708093570>"
PATRONUS_LESSON_ICON = "<:Patronus_Lession:1485323562964488272>"

ARROW_LEFT_EMOJI = "<:ArrowHand_Left:1485320656298971189>"
ARROW_RIGHT_EMOJI = "<:ArrowHand_Right:1485320634220286066>"
BUY_EMOJI = "<:Gelleons:1485318482802249808>"
CLOSE_EMOJI = "❌"

AGE_ROLE_IDS: set[int] = {
    1486660629665419355,
    1486661132008820866,
    1486661036428759050,
    1486660973187305512,
    1486660845495910420,
    1486660745344323595,
}

PRONOUN_ROLE_IDS: set[int] = {
    1487117307934277663,
    1487123654545375242,
}

SHOP_ITEMS = [
    {
        "key": "chocolate_frog",
        "display_name": "Chocolate Frogs",
        "description": "A collectible magical treat. Consumable item.",
        "price": 25,
        "type": "consumable",
        "image_path": str(RESOURCES_DIR / "Shop1.png"),
        "emoji": CHOCOLATE_FROG_ICON,
    },
    {
        "key": "patronus_spell_book",
        "display_name": "Patronus Spell Book",
        "description": "A spell book for Patronus training. Consumable item.",
        "price": 100,
        "type": "consumable",
        "image_path": str(RESOURCES_DIR / "Shop2.png"),
        "emoji": PATRONUS_LESSON_ICON,
    },
    {
        "key": "spew_badge",
        "display_name": "S.P.E.W. Badge",
        "description": "A permanent collectible badge. Can only be bought once.",
        "price": 75,
        "type": "permanent",
        "image_path": str(RESOURCES_DIR / "Shop3.png"),
        "emoji": "🟢",
    },
]

SHOP_ITEMS_BY_KEY = {item["key"]: item for item in SHOP_ITEMS}


ZODIAC_ROLE_IDS: dict[str, int] = {
    "Aries": 1487207873103528046,
    "Taurus": 1487207885778718750,
    "Gemini": 1487207889444802670,
    "Cancer": 1487207892477149185,
    "Leo": 1487207895753035776,
    "Virgo": 1487207898449707218,
    "Libra": 1487207901042049084,
    "Scorpio": 1487207903545790516,
    "Sagittarius": 1487207906020556890,
    "Capricorn": 1487207908541337688,
    "Aquarius": 1487207910705729661,
    "Pisces": 1487207914623205547,
}

ZODIAC_DISPLAY: dict[str, str] = {
    "Aries": ":aries: Aries",
    "Taurus": ":taurus: Taurus",
    "Gemini": ":gemini: Gemini",
    "Cancer": ":cancer: Cancer",
    "Leo": ":leo: Leo",
    "Virgo": ":virgo: Virgo",
    "Libra": ":libra: Libra",
    "Scorpio": ":scorpius: Scorpio",
    "Sagittarius": ":sagittarius: Sagittarius",
    "Capricorn": ":capricorn: Capricorn",
    "Aquarius": ":aquarius: Aquarius",
    "Pisces": ":pisces: Pisces",
}

BIRTHDAY_ROLE_ID = 1487209766232260780