from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RESOURCES_DIR = BASE_DIR / "resources"

HOUSE_ROLE_IDS = {
    "Gryffindor": 1079764344717463579,
    "Hufflepuff": 1079764344717463577,
    "Ravenclaw": 1079764344717463576,
    "Slytherin": 1079764344717463578,
}

YEAR_LEVEL_ROLE_IDS: dict[int, int] = {
    1: 1487710450790563890,  # 1st year
    2: 1487710478779154534,  # 2nd year
    3: 1487710626108276777,  # 3rd year
    4: 1487710746581405836,  # 4th year
    5: 1487710846992781463,  # 5th year
    6: 1487711765566590976,  # 6th year
    7: 1487711055336443925,  # 7th year
}

MAX_SCHOOL_LEVEL = 7

ARENA_ROLE_ID = 1485343667089576077

HOUSE_COLORS: dict[str, int] = {
    "Gryffindor": 0xBB0019,
    "Hufflepuff": 0xE6BF23,
    "Ravenclaw": 0x0079A7,
    "Slytherin": 0x269647,
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

AGE_ROLE_IDS: set[int] = {
    1486660629665419355,  # 18-24
    1486660745344323595,  # 25-29
    1486660845495910420,  # 30-34
    1486660973187305512,  # 35-39
    1486661036428759050,  # 40-44
    1486661132008820866,  # 45+
    1487121999024226374,  # n/a
}

PRONOUN_ROLE_IDS: set[int] = {
    1487117307934277663,  # he/him
    1487123654545375242,  # she/her
    1487123773751824596,  # they/them
}

PRONOUN_ROLE_BY_KEY: dict[str, int] = {
    "he_him": 1487117307934277663,
    "she_her": 1487123654545375242,
    "they_them": 1487123773751824596,
}

AGE_ROLE_BY_KEY: dict[str, int] = {
    "18_24": 1486660629665419355,
    "25_29": 1486660745344323595,
    "30_34": 1486660845495910420,
    "35_39": 1486660973187305512,
    "40_44": 1486661036428759050,
    "45_plus": 1486661132008820866,
    "na": 1487121999024226374,
}

CONTINENT_ROLE_IDS: set[int] = {
    1487711781106483320,  # Europe
    1487729735738982442,  # North America
    1487729788205535272,  # South America
    1487729828122722355,  # Asia
    1487729855020925050,  # Australia & Oceania
    1487730509499990088,  # Antarctica (n/a option)
}

CONTINENT_ROLE_BY_KEY: dict[str, int] = {
    "europe": 1487711781106483320,
    "north_america": 1487729735738982442,
    "south_america": 1487729788205535272,
    "asia": 1487729828122722355,
    "australia_oceania": 1487729855020925050,
    "antarctica": 1487730509499990088,
}