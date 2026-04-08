from __future__ import annotations

from dataclasses import dataclass

from domain.role_registry import (
    ROLE_GROUP_AGES,
    ROLE_GROUP_CONTINENTS,
    ROLE_GROUP_DM,
    ROLE_GROUP_GENDER_IDENTITY,
    ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR,
    ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF,
    ROLE_GROUP_HOUSE_COLOR_RAVENCLAW,
    ROLE_GROUP_HOUSE_COLOR_SLYTHERIN,
    ROLE_GROUP_PINGS,
    ROLE_GROUP_PRONOUNS,
    ROLE_GROUP_RELATIONSHIP,
    ROLE_GROUP_SEXUALITY,
    ROLE_KEY_CHAT_REVIVE,
    ROLE_KEY_DUEL_PING,
    ROLE_KEY_EVENT_PING,
)


@dataclass(frozen=True)
class ReactionRoleOption:
    role_key: str
    emoji_name: str | None = None
    emoji_id: int | None = None
    emoji_unicode: str | None = None
    emoji_animated: bool = False


@dataclass(frozen=True)
class ReactionRoleGroup:
    key: str
    role_group: str
    multi_select: bool
    banner_filename: str
    options: tuple[ReactionRoleOption, ...]
    house_name: str | None = None


AGE_VERIFY_EMOJIS = {
    "redverify": 1491469046074577110,
    "orangeverify": 1491469032350679261,
    "yellowverify": 1491469020384460992,
    "greenverify": 1491468987228491957,
    "blueverify": 1491468956207284264,
    "purpleverify": 1491468937718665358,
    "blackverified": 1491536921170804878,
}

CONTINENT_EMOJIS = {
    "europe": 1491428638107635792,
    "asia": 1491428636040105994,
    "northamerica": 1491428628032913531,
    "africa": 1491428632202055843,
    "southamerica": 1491428634265911428,
    "oceania": 1491428629995852026,
    "antarctica": 1491428626288214056,
}

PRONOUN_EMOJIS = {
    "they_them": 1491531137603076217,
    "shethem": 1491531031570944222,
    "hethem": 1491531029356347523,
    "she_her": 1491531024541155430,
    "he_him": 1491531022548860938,
    "ask": 1491532075273027827,
}

GENDER_IDENTITY_EMOJIS = {
    "nonbinary": 1491498356525240380,
    "demigender": 1491498355216482324,
    "genderfluid": 1491498353761063184,
    "bigender": 1491498352590848070,
    "female": 1491498351294677192,
    "transgender": 1491498349935984830,
    "male": 1491498348467851354,
}

SEXUALITY_EMOJIS = {
    "Bisexual": 1491503728128295135,
    "Demiromantic": 1491503475874595030,
    "aromantic": 1491503473831972875,
    "lesbian": 1491503108591980596,
    "gay": 1491503106939420935,
    "pansexual": 1491503104947126272,
    "omnisexual": 1491503094314569920,
    "asexual": 1491503092984840272,
    "demisexual": 1491503091541872660,
    "heterosexual": 1491503089864278016,
    "Abrosexual": 1491503088278966323,
    "Polyamorus": 1491503086613565511,
}

REACTION_ROLE_GROUPS: tuple[ReactionRoleGroup, ...] = (
    ReactionRoleGroup(
        key="pronouns",
        role_group=ROLE_GROUP_PRONOUNS,
        multi_select=False,
        banner_filename="select_pronouns.png",
        options=(
            ReactionRoleOption("pronouns_she_her", "she_her", PRONOUN_EMOJIS["she_her"], emoji_animated=True),
            ReactionRoleOption("pronouns_she_they", "shethem", PRONOUN_EMOJIS["shethem"], emoji_animated=True),
            ReactionRoleOption("pronouns_he_him", "he_him", PRONOUN_EMOJIS["he_him"], emoji_animated=True),
            ReactionRoleOption("pronouns_he_they", "hethem", PRONOUN_EMOJIS["hethem"], emoji_animated=True),
            ReactionRoleOption("pronouns_they_them", "they_them", PRONOUN_EMOJIS["they_them"], emoji_animated=True),
            ReactionRoleOption("pronouns_ask", "ask", PRONOUN_EMOJIS["ask"], emoji_animated=True),
        ),
    ),
    ReactionRoleGroup(
        key="gender_identity",
        role_group=ROLE_GROUP_GENDER_IDENTITY,
        multi_select=False,
        banner_filename="select_gender.png",
        options=(
            ReactionRoleOption("gender_male", "male", GENDER_IDENTITY_EMOJIS["male"]),
            ReactionRoleOption("gender_female", "female", GENDER_IDENTITY_EMOJIS["female"]),
            ReactionRoleOption("gender_transgender", "transgender", GENDER_IDENTITY_EMOJIS["transgender"]),
            ReactionRoleOption("gender_bigender", "bigender", GENDER_IDENTITY_EMOJIS["bigender"]),
            ReactionRoleOption("gender_genderfluid", "genderfluid", GENDER_IDENTITY_EMOJIS["genderfluid"]),
            ReactionRoleOption("gender_demigender", "demigender", GENDER_IDENTITY_EMOJIS["demigender"]),
            ReactionRoleOption("gender_nonbinary", "nonbinary", GENDER_IDENTITY_EMOJIS["nonbinary"]),
        ),
    ),
    ReactionRoleGroup(
        key="sexuality",
        role_group=ROLE_GROUP_SEXUALITY,
        multi_select=True,
        banner_filename="select_orientation.png",
        options=(
            ReactionRoleOption("sexuality_lesbian", "lesbian", SEXUALITY_EMOJIS["lesbian"]),
            ReactionRoleOption("sexuality_gay", "gay", SEXUALITY_EMOJIS["gay"]),
            ReactionRoleOption("sexuality_bisexual", "Bisexual", SEXUALITY_EMOJIS["Bisexual"]),
            ReactionRoleOption("sexuality_pansexual", "pansexual", SEXUALITY_EMOJIS["pansexual"]),
            ReactionRoleOption("sexuality_omnisexual", "omnisexual", SEXUALITY_EMOJIS["omnisexual"]),
            ReactionRoleOption("sexuality_asexual", "asexual", SEXUALITY_EMOJIS["asexual"]),
            ReactionRoleOption("sexuality_aromantic", "aromantic", SEXUALITY_EMOJIS["aromantic"]),
            ReactionRoleOption("sexuality_demisexual", "demisexual", SEXUALITY_EMOJIS["demisexual"]),
            ReactionRoleOption("sexuality_demiromantic", "Demiromantic", SEXUALITY_EMOJIS["Demiromantic"]),
            ReactionRoleOption("sexuality_heterosexual", "heterosexual", SEXUALITY_EMOJIS["heterosexual"]),
            ReactionRoleOption("sexuality_abrosexual", "Abrosexual", SEXUALITY_EMOJIS["Abrosexual"]),
            ReactionRoleOption("sexuality_polyamorous", "Polyamorus", SEXUALITY_EMOJIS["Polyamorus"]),
            ReactionRoleOption("sexuality_questioning", emoji_unicode="❔"),
        ),
    ),
    ReactionRoleGroup(
        key="relationship",
        role_group=ROLE_GROUP_RELATIONSHIP,
        multi_select=False,
        banner_filename="select_relationship.png",
        options=(
            ReactionRoleOption("relationship_taken", emoji_unicode="❤️"),
            ReactionRoleOption("relationship_single", emoji_unicode="✨"),
            ReactionRoleOption("relationship_complicated", emoji_unicode="🌀"),
        ),
    ),
    ReactionRoleGroup(
        key="ages",
        role_group=ROLE_GROUP_AGES,
        multi_select=False,
        banner_filename="select_age.png",
        options=(
            ReactionRoleOption("age_below_21", "redverify", AGE_VERIFY_EMOJIS["redverify"]),
            ReactionRoleOption("age_21_25", "orangeverify", AGE_VERIFY_EMOJIS["orangeverify"]),
            ReactionRoleOption("age_26_30", "yellowverify", AGE_VERIFY_EMOJIS["yellowverify"]),
            ReactionRoleOption("age_31_35", "greenverify", AGE_VERIFY_EMOJIS["greenverify"]),
            ReactionRoleOption("age_36_40", "blueverify", AGE_VERIFY_EMOJIS["blueverify"]),
            ReactionRoleOption("age_41_45", "purpleverify", AGE_VERIFY_EMOJIS["purpleverify"]),
            ReactionRoleOption("age_46_plus", "blackverified", AGE_VERIFY_EMOJIS["blackverified"]),
        ),
    ),
    ReactionRoleGroup(
        key="continents",
        role_group=ROLE_GROUP_CONTINENTS,
        multi_select=False,
        banner_filename="select_location.png",
        options=(
            ReactionRoleOption("continent_europe", "europe", CONTINENT_EMOJIS["europe"]),
            ReactionRoleOption("continent_asia", "asia", CONTINENT_EMOJIS["asia"]),
            ReactionRoleOption("continent_north_america", "northamerica", CONTINENT_EMOJIS["northamerica"]),
            ReactionRoleOption("continent_africa", "africa", CONTINENT_EMOJIS["africa"]),
            ReactionRoleOption("continent_south_america", "southamerica", CONTINENT_EMOJIS["southamerica"]),
            ReactionRoleOption("continent_australia_oceania", "oceania", CONTINENT_EMOJIS["oceania"]),
            ReactionRoleOption("continent_antarctica", "antarctica", CONTINENT_EMOJIS["antarctica"]),
        ),
    ),
    ReactionRoleGroup(
        key="pings",
        role_group=ROLE_GROUP_PINGS,
        multi_select=True,
        banner_filename="select_pings.png",
        options=(
            ReactionRoleOption(ROLE_KEY_DUEL_PING, emoji_unicode="⚔️"),
            ReactionRoleOption(ROLE_KEY_EVENT_PING, emoji_unicode="🎉"),
            ReactionRoleOption(ROLE_KEY_CHAT_REVIVE, emoji_unicode="💬"),
        ),
    ),
    ReactionRoleGroup(
        key="dm_status",
        role_group=ROLE_GROUP_DM,
        multi_select=False,
        banner_filename="select_DM.png",
        options=(
            ReactionRoleOption("dm_open", emoji_unicode="📬"),
            ReactionRoleOption("dm_closed", emoji_unicode="🔒"),
            ReactionRoleOption("dm_ask", emoji_unicode="❓"),
        ),
    ),
    ReactionRoleGroup(
        key="gryffindor_colors",
        role_group=ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR,
        multi_select=False,
        banner_filename="gryffindor_colours.png",
        house_name="Gryffindor",
        options=(
            ReactionRoleOption("gryff_color_crimson", emoji_unicode="1️⃣"),
            ReactionRoleOption("gryff_color_scarlet", emoji_unicode="2️⃣"),
            ReactionRoleOption("gryff_color_ember", emoji_unicode="3️⃣"),
            ReactionRoleOption("gryff_color_ruby", emoji_unicode="4️⃣"),
            ReactionRoleOption("gryff_color_garnet", emoji_unicode="5️⃣"),
            ReactionRoleOption("gryff_color_burgundy", emoji_unicode="6️⃣"),
            ReactionRoleOption("gryff_color_wine", emoji_unicode="7️⃣"),
            ReactionRoleOption("gryff_color_rosewood", emoji_unicode="8️⃣"),
            ReactionRoleOption("gryff_color_brick", emoji_unicode="9️⃣"),
            ReactionRoleOption("gryff_color_phoenix", emoji_unicode="🔟"),
        ),
    ),
    ReactionRoleGroup(
        key="hufflepuff_colors",
        role_group=ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF,
        multi_select=False,
        banner_filename="hufflepuff_colours.png",
        house_name="Hufflepuff",
        options=(
            ReactionRoleOption("huff_color_gold", emoji_unicode="1️⃣"),
            ReactionRoleOption("huff_color_honey", emoji_unicode="2️⃣"),
            ReactionRoleOption("huff_color_amber", emoji_unicode="3️⃣"),
            ReactionRoleOption("huff_color_mustard", emoji_unicode="4️⃣"),
            ReactionRoleOption("huff_color_saffron", emoji_unicode="5️⃣"),
            ReactionRoleOption("huff_color_sunburst", emoji_unicode="6️⃣"),
            ReactionRoleOption("huff_color_wheat", emoji_unicode="7️⃣"),
            ReactionRoleOption("huff_color_butter", emoji_unicode="8️⃣"),
            ReactionRoleOption("huff_color_bronze", emoji_unicode="9️⃣"),
            ReactionRoleOption("huff_color_caramel", emoji_unicode="🔟"),
        ),
    ),
    ReactionRoleGroup(
        key="ravenclaw_colors",
        role_group=ROLE_GROUP_HOUSE_COLOR_RAVENCLAW,
        multi_select=False,
        banner_filename="ravenclaw_colours.png",
        house_name="Ravenclaw",
        options=(
            ReactionRoleOption("raven_color_royal", emoji_unicode="1️⃣"),
            ReactionRoleOption("raven_color_sapphire", emoji_unicode="2️⃣"),
            ReactionRoleOption("raven_color_cobalt", emoji_unicode="3️⃣"),
            ReactionRoleOption("raven_color_azure", emoji_unicode="4️⃣"),
            ReactionRoleOption("raven_color_cerulean", emoji_unicode="5️⃣"),
            ReactionRoleOption("raven_color_midnight", emoji_unicode="6️⃣"),
            ReactionRoleOption("raven_color_storm", emoji_unicode="7️⃣"),
            ReactionRoleOption("raven_color_ice", emoji_unicode="8️⃣"),
            ReactionRoleOption("raven_color_steel", emoji_unicode="9️⃣"),
            ReactionRoleOption("raven_color_twilight", emoji_unicode="🔟"),
        ),
    ),
    ReactionRoleGroup(
        key="slytherin_colors",
        role_group=ROLE_GROUP_HOUSE_COLOR_SLYTHERIN,
        multi_select=False,
        banner_filename="slytherin_colours.png",
        house_name="Slytherin",
        options=(
            ReactionRoleOption("slyth_color_emerald", emoji_unicode="1️⃣"),
            ReactionRoleOption("slyth_color_jade", emoji_unicode="2️⃣"),
            ReactionRoleOption("slyth_color_forest", emoji_unicode="3️⃣"),
            ReactionRoleOption("slyth_color_moss", emoji_unicode="4️⃣"),
            ReactionRoleOption("slyth_color_serpent", emoji_unicode="5️⃣"),
            ReactionRoleOption("slyth_color_pine", emoji_unicode="6️⃣"),
            ReactionRoleOption("slyth_color_olive", emoji_unicode="7️⃣"),
            ReactionRoleOption("slyth_color_malachite", emoji_unicode="8️⃣"),
            ReactionRoleOption("slyth_color_sea", emoji_unicode="9️⃣"),
            ReactionRoleOption("slyth_color_sage", emoji_unicode="🔟"),
        ),
    ),
)

REACTION_ROLE_GROUP_BY_KEY = {group.key: group for group in REACTION_ROLE_GROUPS}


def get_reaction_role_groups() -> list[ReactionRoleGroup]:
    return list(REACTION_ROLE_GROUPS)


def get_reaction_role_group(group_key: str) -> ReactionRoleGroup:
    return REACTION_ROLE_GROUP_BY_KEY[group_key]