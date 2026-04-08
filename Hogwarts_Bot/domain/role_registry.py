from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManagedRoleDefinition:
    key: str
    name: str
    color: int
    group: str
    mentionable: bool = False
    hoist: bool = False


ROLE_GROUP_YEARS = "years"
ROLE_GROUP_ZODIAC = "zodiac"
ROLE_GROUP_SYSTEM = "system"

ROLE_GROUP_AGES = "ages"
ROLE_GROUP_PRONOUNS = "pronouns"
ROLE_GROUP_GENDER_IDENTITY = "gender_identity"
ROLE_GROUP_CONTINENTS = "continents"
ROLE_GROUP_SEXUALITY = "sexuality"
ROLE_GROUP_PINGS = "pings"
ROLE_GROUP_DM = "dm"
ROLE_GROUP_RELATIONSHIP = "relationship"

ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR = "house_colors_gryffindor"
ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF = "house_colors_hufflepuff"
ROLE_GROUP_HOUSE_COLOR_RAVENCLAW = "house_colors_ravenclaw"
ROLE_GROUP_HOUSE_COLOR_SLYTHERIN = "house_colors_slytherin"

ROLE_KEY_BIRTHDAY = "birthday"
ROLE_KEY_DUEL_PING = "duel_ping"
ROLE_KEY_EVENT_PING = "event_ping"
ROLE_KEY_CHAT_REVIVE = "chat_revive"
ROLE_KEY_DUELLING = "duelling"

YEAR_ROLE_KEYS_BY_LEVEL: dict[int, str] = {
    1: "year_1",
    2: "year_2",
    3: "year_3",
    4: "year_4",
    5: "year_5",
    6: "year_6",
    7: "year_7",
}

YEAR_ROLE_NAMES_BY_LEVEL: dict[int, str] = {
    1: "1st Year",
    2: "2nd Year",
    3: "3rd Year",
    4: "4th Year",
    5: "5th Year",
    6: "6th Year",
    7: "7th Year",
}

ZODIAC_ROLE_KEYS_BY_SIGN: dict[str, str] = {
    "Aries": "zodiac_aries",
    "Taurus": "zodiac_taurus",
    "Gemini": "zodiac_gemini",
    "Cancer": "zodiac_cancer",
    "Leo": "zodiac_leo",
    "Virgo": "zodiac_virgo",
    "Libra": "zodiac_libra",
    "Scorpio": "zodiac_scorpio",
    "Sagittarius": "zodiac_sagittarius",
    "Capricorn": "zodiac_capricorn",
    "Aquarius": "zodiac_aquarius",
    "Pisces": "zodiac_pisces",
}


def _build_role_definitions() -> list[ManagedRoleDefinition]:
    defs: list[ManagedRoleDefinition] = []

    # System / auto-managed
    defs.extend(
        [
            ManagedRoleDefinition(
                key=YEAR_ROLE_KEYS_BY_LEVEL[level],
                name=YEAR_ROLE_NAMES_BY_LEVEL[level],
                color=0x6B7280,
                group=ROLE_GROUP_YEARS,
            )
            for level in range(1, 8)
        ]
    )

    defs.extend(
        [
            ManagedRoleDefinition("zodiac_aries", "Aries", 0xE76F51, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_taurus", "Taurus", 0x6A994E, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_gemini", "Gemini", 0xF4A261, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_cancer", "Cancer", 0x577590, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_leo", "Leo", 0xE9C46A, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_virgo", "Virgo", 0x84A59D, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_libra", "Libra", 0xCDB4DB, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_scorpio", "Scorpio", 0x7B2CBF, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_sagittarius", "Sagittarius", 0xF77F00, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_capricorn", "Capricorn", 0x4D908E, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_aquarius", "Aquarius", 0x219EBC, ROLE_GROUP_ZODIAC),
            ManagedRoleDefinition("zodiac_pisces", "Pisces", 0x3A86FF, ROLE_GROUP_ZODIAC),
        ]
    )

    defs.extend(
        [
            ManagedRoleDefinition(ROLE_KEY_BIRTHDAY, "Birthday", 0xFF69B4, ROLE_GROUP_SYSTEM),
            ManagedRoleDefinition(ROLE_KEY_DUEL_PING, "Arena Ping", 0xB22222, ROLE_GROUP_PINGS, mentionable=True),
            ManagedRoleDefinition(ROLE_KEY_EVENT_PING, "Event Ping", 0x6A4C93, ROLE_GROUP_PINGS, mentionable=True),
            ManagedRoleDefinition(ROLE_KEY_CHAT_REVIVE, "Chat Revive", 0x4D908E, ROLE_GROUP_PINGS, mentionable=True),
            ManagedRoleDefinition(ROLE_KEY_DUELLING, "Duelling", 0x8B0000, ROLE_GROUP_SYSTEM),
        ]
    )

    # Reaction role groups
    defs.extend(
        [
            ManagedRoleDefinition("age_below_21", "Below 21", 0xA8DADC, ROLE_GROUP_AGES),
            ManagedRoleDefinition("age_21_25", "21-25", 0x8ECAE6, ROLE_GROUP_AGES),
            ManagedRoleDefinition("age_26_30", "26-30", 0x219EBC, ROLE_GROUP_AGES),
            ManagedRoleDefinition("age_31_35", "31-35", 0x126782, ROLE_GROUP_AGES),
            ManagedRoleDefinition("age_36_40", "36-40", 0x6D597A, ROLE_GROUP_AGES),
            ManagedRoleDefinition("age_41_45", "41-45", 0xB56576, ROLE_GROUP_AGES),
            ManagedRoleDefinition("age_46_plus", "46+", 0xE56B6F, ROLE_GROUP_AGES),
        ]
    )

    defs.extend(
        [
            ManagedRoleDefinition("pronouns_she_her", "She/Her", 0xFFAFCC, ROLE_GROUP_PRONOUNS),
            ManagedRoleDefinition("pronouns_she_they", "She/They", 0xFFC8DD, ROLE_GROUP_PRONOUNS),
            ManagedRoleDefinition("pronouns_he_him", "He/Him", 0xA2D2FF, ROLE_GROUP_PRONOUNS),
            ManagedRoleDefinition("pronouns_he_they", "He/They", 0xBDE0FE, ROLE_GROUP_PRONOUNS),
            ManagedRoleDefinition("pronouns_they_them", "They/Them", 0xCDEAC0, ROLE_GROUP_PRONOUNS),
            ManagedRoleDefinition("pronouns_ask", "Ask Pronouns", 0xD9D9D9, ROLE_GROUP_PRONOUNS),
        ]
    )

    defs.extend(
        [
            ManagedRoleDefinition("gender_male", "Male", 0x7B8CFF, ROLE_GROUP_GENDER_IDENTITY),
            ManagedRoleDefinition("gender_female", "Female", 0xFF73E6, ROLE_GROUP_GENDER_IDENTITY),
            ManagedRoleDefinition("gender_transgender", "Transgender", 0xFF3B30, ROLE_GROUP_GENDER_IDENTITY),
            ManagedRoleDefinition("gender_bigender", "Bigender", 0xB65DFF, ROLE_GROUP_GENDER_IDENTITY),
            ManagedRoleDefinition("gender_genderfluid", "Genderfluid", 0x00D84A, ROLE_GROUP_GENDER_IDENTITY),
            ManagedRoleDefinition("gender_demigender", "Demigender", 0x11C5D9, ROLE_GROUP_GENDER_IDENTITY),
            ManagedRoleDefinition("gender_nonbinary", "Nonbinary", 0xF2D200, ROLE_GROUP_GENDER_IDENTITY),
        ]
    )

    defs.extend(
        [
            ManagedRoleDefinition("continent_africa", "Africa", 0xF4A261, ROLE_GROUP_CONTINENTS),
            ManagedRoleDefinition("continent_antarctica", "Antarctica", 0xD9EDFF, ROLE_GROUP_CONTINENTS),
            ManagedRoleDefinition("continent_asia", "Asia", 0xE76F51, ROLE_GROUP_CONTINENTS),
            ManagedRoleDefinition("continent_australia_oceania", "Australia & Oceania", 0x2A9D8F, ROLE_GROUP_CONTINENTS),
            ManagedRoleDefinition("continent_europe", "Europe", 0x3A86FF, ROLE_GROUP_CONTINENTS),
            ManagedRoleDefinition("continent_north_america", "North America", 0x8ECAE6, ROLE_GROUP_CONTINENTS),
            ManagedRoleDefinition("continent_south_america", "South America", 0x6A994E, ROLE_GROUP_CONTINENTS),
        ]
    )

    defs.extend(
        [
            ManagedRoleDefinition("sexuality_lesbian", "Lesbian", 0xD62828, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_gay", "Gay", 0x2A9D8F, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_bisexual", "Bisexual", 0x9D4EDD, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_pansexual", "Pansexual", 0xFFB703, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_omnisexual", "Omnisexual", 0x8338EC, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_asexual", "Asexual", 0x6C757D, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_aromantic", "Aromantic", 0x588157, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_demisexual", "Demisexual", 0x495057, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_demiromantic", "Demiromantic", 0x7F5539, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_heterosexual", "Heterosexual", 0x457B9D, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_abrosexual", "Abrosexual", 0x52B788, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_polyamorous", "Polyamorous", 0xE63946, ROLE_GROUP_SEXUALITY),
            ManagedRoleDefinition("sexuality_questioning", "Questioning", 0xADB5BD, ROLE_GROUP_SEXUALITY),
        ]
    )

    defs.extend(
        [
            ManagedRoleDefinition("dm_open", "Open DM", 0x52B788, ROLE_GROUP_DM),
            ManagedRoleDefinition("dm_closed", "Closed DM", 0xD62828, ROLE_GROUP_DM),
            ManagedRoleDefinition("dm_ask", "Ask DM", 0xADB5BD, ROLE_GROUP_DM),
        ]
    )

    defs.extend(
        [
            ManagedRoleDefinition("relationship_taken", "Taken", 0xE63946, ROLE_GROUP_RELATIONSHIP),
            ManagedRoleDefinition("relationship_single", "Single", 0x2A9D8F, ROLE_GROUP_RELATIONSHIP),
            ManagedRoleDefinition("relationship_complicated", "It's Complicated", 0x9D4EDD, ROLE_GROUP_RELATIONSHIP),
        ]
    )

    # Gryffindor colours
    defs.extend(
        [
            ManagedRoleDefinition("gryff_color_crimson", "Gryffindor • Crimson", 0x7F1D1D, ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR),
            ManagedRoleDefinition("gryff_color_scarlet", "Gryffindor • Scarlet", 0xB91C1C, ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR),
            ManagedRoleDefinition("gryff_color_ember", "Gryffindor • Ember", 0xDC2626, ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR),
            ManagedRoleDefinition("gryff_color_ruby", "Gryffindor • Ruby", 0xBE123C, ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR),
            ManagedRoleDefinition("gryff_color_garnet", "Gryffindor • Garnet", 0x9F1239, ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR),
            ManagedRoleDefinition("gryff_color_burgundy", "Gryffindor • Burgundy", 0x881337, ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR),
            ManagedRoleDefinition("gryff_color_wine", "Gryffindor • Wine", 0x7A1F2A, ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR),
            ManagedRoleDefinition("gryff_color_rosewood", "Gryffindor • Rosewood", 0xA61E4D, ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR),
            ManagedRoleDefinition("gryff_color_brick", "Gryffindor • Brick", 0xB45309, ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR),
            ManagedRoleDefinition("gryff_color_phoenix", "Gryffindor • Phoenix", 0xE85D04, ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR),
        ]
    )

    # Hufflepuff colours
    defs.extend(
        [
            ManagedRoleDefinition("huff_color_gold", "Hufflepuff • Gold", 0xD4A017, ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF),
            ManagedRoleDefinition("huff_color_honey", "Hufflepuff • Honey", 0xE9B949, ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF),
            ManagedRoleDefinition("huff_color_amber", "Hufflepuff • Amber", 0xFFB703, ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF),
            ManagedRoleDefinition("huff_color_mustard", "Hufflepuff • Mustard", 0xC99700, ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF),
            ManagedRoleDefinition("huff_color_saffron", "Hufflepuff • Saffron", 0xF4A261, ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF),
            ManagedRoleDefinition("huff_color_sunburst", "Hufflepuff • Sunburst", 0xF6BD60, ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF),
            ManagedRoleDefinition("huff_color_wheat", "Hufflepuff • Wheat", 0xE9C46A, ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF),
            ManagedRoleDefinition("huff_color_butter", "Hufflepuff • Butter", 0xF7E08C, ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF),
            ManagedRoleDefinition("huff_color_bronze", "Hufflepuff • Bronze", 0xB08968, ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF),
            ManagedRoleDefinition("huff_color_caramel", "Hufflepuff • Caramel", 0xBC6C25, ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF),
        ]
    )

    # Ravenclaw colours
    defs.extend(
        [
            ManagedRoleDefinition("raven_color_royal", "Ravenclaw • Royal Blue", 0x1D4ED8, ROLE_GROUP_HOUSE_COLOR_RAVENCLAW),
            ManagedRoleDefinition("raven_color_sapphire", "Ravenclaw • Sapphire", 0x2563EB, ROLE_GROUP_HOUSE_COLOR_RAVENCLAW),
            ManagedRoleDefinition("raven_color_cobalt", "Ravenclaw • Cobalt", 0x1E40AF, ROLE_GROUP_HOUSE_COLOR_RAVENCLAW),
            ManagedRoleDefinition("raven_color_azure", "Ravenclaw • Azure", 0x3A86FF, ROLE_GROUP_HOUSE_COLOR_RAVENCLAW),
            ManagedRoleDefinition("raven_color_cerulean", "Ravenclaw • Cerulean", 0x219EBC, ROLE_GROUP_HOUSE_COLOR_RAVENCLAW),
            ManagedRoleDefinition("raven_color_midnight", "Ravenclaw • Midnight", 0x1E3A8A, ROLE_GROUP_HOUSE_COLOR_RAVENCLAW),
            ManagedRoleDefinition("raven_color_storm", "Ravenclaw • Storm Blue", 0x4C6FFF, ROLE_GROUP_HOUSE_COLOR_RAVENCLAW),
            ManagedRoleDefinition("raven_color_ice", "Ravenclaw • Ice Blue", 0x90CAF9, ROLE_GROUP_HOUSE_COLOR_RAVENCLAW),
            ManagedRoleDefinition("raven_color_steel", "Ravenclaw • Steel Blue", 0x577590, ROLE_GROUP_HOUSE_COLOR_RAVENCLAW),
            ManagedRoleDefinition("raven_color_twilight", "Ravenclaw • Twilight", 0x5E60CE, ROLE_GROUP_HOUSE_COLOR_RAVENCLAW),
        ]
    )

    # Slytherin colours
    defs.extend(
        [
            ManagedRoleDefinition("slyth_color_emerald", "Slytherin • Emerald", 0x10B981, ROLE_GROUP_HOUSE_COLOR_SLYTHERIN),
            ManagedRoleDefinition("slyth_color_jade", "Slytherin • Jade", 0x00A86B, ROLE_GROUP_HOUSE_COLOR_SLYTHERIN),
            ManagedRoleDefinition("slyth_color_forest", "Slytherin • Forest", 0x166534, ROLE_GROUP_HOUSE_COLOR_SLYTHERIN),
            ManagedRoleDefinition("slyth_color_moss", "Slytherin • Moss", 0x4CAF50, ROLE_GROUP_HOUSE_COLOR_SLYTHERIN),
            ManagedRoleDefinition("slyth_color_serpent", "Slytherin • Serpent", 0x2D6A4F, ROLE_GROUP_HOUSE_COLOR_SLYTHERIN),
            ManagedRoleDefinition("slyth_color_pine", "Slytherin • Pine", 0x1B4332, ROLE_GROUP_HOUSE_COLOR_SLYTHERIN),
            ManagedRoleDefinition("slyth_color_olive", "Slytherin • Olive", 0x6B8E23, ROLE_GROUP_HOUSE_COLOR_SLYTHERIN),
            ManagedRoleDefinition("slyth_color_malachite", "Slytherin • Malachite", 0x0BDA51, ROLE_GROUP_HOUSE_COLOR_SLYTHERIN),
            ManagedRoleDefinition("slyth_color_sea", "Slytherin • Sea Green", 0x2A9D8F, ROLE_GROUP_HOUSE_COLOR_SLYTHERIN),
            ManagedRoleDefinition("slyth_color_sage", "Slytherin • Sage", 0x84A98C, ROLE_GROUP_HOUSE_COLOR_SLYTHERIN),
        ]
    )

    return defs


ALL_ROLE_DEFINITIONS = _build_role_definitions()
ROLE_DEFINITION_BY_KEY = {role.key: role for role in ALL_ROLE_DEFINITIONS}


def get_all_managed_role_definitions() -> list[ManagedRoleDefinition]:
    return list(ALL_ROLE_DEFINITIONS)


def get_role_definition(role_key: str) -> ManagedRoleDefinition:
    return ROLE_DEFINITION_BY_KEY[role_key]


def role_names_for_group(group: str) -> set[str]:
    return {
        role.name
        for role in ALL_ROLE_DEFINITIONS
        if role.group == group
    }


def role_keys_for_group(group: str) -> list[str]:
    return [
        role.key
        for role in ALL_ROLE_DEFINITIONS
        if role.group == group
    ]


def zodiac_role_key_for_sign(sign: str) -> str:
    return ZODIAC_ROLE_KEYS_BY_SIGN[sign]


def year_role_key_for_level(level: int) -> str:
    return YEAR_ROLE_KEYS_BY_LEVEL[level]