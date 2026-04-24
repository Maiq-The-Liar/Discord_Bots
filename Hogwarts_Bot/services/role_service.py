from __future__ import annotations

from collections import defaultdict

import discord

from domain.role_registry import (
    HOUSE_NAMES,
    ROLE_DEFINITION_BY_KEY,
    ROLE_GROUP_AGES,
    ROLE_GROUP_CONTINENTS,
    ROLE_GROUP_DM,
    ROLE_GROUP_GENDER_IDENTITY,
    ROLE_GROUP_HOUSE,
    ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR,
    ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF,
    ROLE_GROUP_HOUSE_COLOR_RAVENCLAW,
    ROLE_GROUP_HOUSE_COLOR_SLYTHERIN,
    ROLE_GROUP_MODERATION,
    ROLE_GROUP_PINGS,
    ROLE_GROUP_PRONOUNS,
    ROLE_GROUP_QUIDDITCH_POSITIONS,
    ROLE_GROUP_RELATIONSHIP,
    ROLE_GROUP_SEXUALITY,
    ROLE_GROUP_SYSTEM,
    ROLE_GROUP_YEARS,
    ROLE_GROUP_ZODIAC,
    ROLE_KEY_HEAD_STUDENT,
    get_all_managed_role_definitions,
    get_role_definition,
    house_color_group_for_name,
    house_role_key_for_name,
    role_keys_for_group,
    year_role_key_for_level,
    zodiac_role_key_for_sign,
)
from repositories.guild_role_repository import GuildRoleRepository


HOUSE_COLOR_GROUPS = {
    ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR,
    ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF,
    ROLE_GROUP_HOUSE_COLOR_RAVENCLAW,
    ROLE_GROUP_HOUSE_COLOR_SLYTHERIN,
}

# Lower number = lower in hierarchy
# Higher number = higher in hierarchy
GROUP_ORDER = {
    ROLE_GROUP_SYSTEM: 10,
    ROLE_GROUP_YEARS: 20,
    ROLE_GROUP_ZODIAC: 30,
    ROLE_GROUP_PINGS: 40,
    ROLE_GROUP_DM: 50,
    ROLE_GROUP_CONTINENTS: 60,
    ROLE_GROUP_AGES: 70,
    ROLE_GROUP_RELATIONSHIP: 80,
    ROLE_GROUP_SEXUALITY: 90,
    ROLE_GROUP_GENDER_IDENTITY: 100,
    ROLE_GROUP_PRONOUNS: 110,
    ROLE_GROUP_QUIDDITCH_POSITIONS: 120,
    ROLE_GROUP_HOUSE: 130,
    ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR: 140,
    ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF: 150,
    ROLE_GROUP_HOUSE_COLOR_RAVENCLAW: 160,
    ROLE_GROUP_HOUSE_COLOR_SLYTHERIN: 170,
    ROLE_GROUP_MODERATION: 180,
}

# Preserve the exact order defined in role_registry.py
ROLE_KEY_ORDER = {
    role_def.key: index
    for index, role_def in enumerate(get_all_managed_role_definitions())
}


class RoleService:
    def __init__(self, role_repo: GuildRoleRepository):
        self.role_repo = role_repo

    async def sync_all_managed_roles(self, guild: discord.Guild) -> dict[str, list[str]]:
        created: list[str] = []
        updated: list[str] = []
        found: list[str] = []
        failed: list[str] = []

        for role_def in get_all_managed_role_definitions():
            try:
                _, status = await self.ensure_role(guild, role_def.key)
                if status == "created":
                    created.append(role_def.name)
                elif status == "updated":
                    updated.append(role_def.name)
                else:
                    found.append(role_def.name)
            except discord.Forbidden:
                failed.append(f"{role_def.name} (missing permissions or bad role hierarchy)")
            except discord.HTTPException as exc:
                failed.append(f"{role_def.name} ({exc})")

        try:
            await self.reorder_managed_roles(guild)
        except discord.Forbidden:
            failed.append("Role hierarchy reorder failed (missing permissions or bad role hierarchy)")
        except discord.HTTPException as exc:
            failed.append(f"Role hierarchy reorder failed ({exc})")

        return {
            "created": created,
            "updated": updated,
            "found": found,
            "failed": failed,
        }

    async def ensure_role(
        self,
        guild: discord.Guild,
        role_key: str,
    ) -> tuple[discord.Role, str]:
        role_def = get_role_definition(role_key)
        role = self.get_role(guild, role_key)

        desired_permissions = self._permissions_for_role(role_def.key)
        role_kwargs = {
            "name": role_def.name,
            "colour": discord.Colour(role_def.color),
            "mentionable": role_def.mentionable,
            "hoist": role_def.hoist,
            "reason": "Hogwarts Bot role sync",
        }
        if desired_permissions is not None:
            role_kwargs["permissions"] = desired_permissions

        if role is None:
            role = await guild.create_role(**role_kwargs)
            self.role_repo.upsert_mapping(guild.id, role_key, role.id, role.name)
            return role, "created"

        if self._needs_edit(role, role_def):
            await role.edit(**role_kwargs)
            self.role_repo.upsert_mapping(guild.id, role_key, role.id, role.name)
            return role, "updated"

        self.role_repo.upsert_mapping(guild.id, role_key, role.id, role.name)
        return role, "found"

    def get_role(self, guild: discord.Guild, role_key: str) -> discord.Role | None:
        mapping = self.role_repo.get_mapping(guild.id, role_key)
        if mapping is not None:
            mapped_role = guild.get_role(int(mapping["role_id"]))
            if mapped_role is not None:
                return mapped_role

        role_def = ROLE_DEFINITION_BY_KEY[role_key]
        matches = [role for role in guild.roles if role.name == role_def.name]
        if matches:
            chosen = sorted(matches, key=lambda r: r.id)[0]
            self.role_repo.upsert_mapping(guild.id, role_key, chosen.id, chosen.name)
            return chosen

        return None

    def get_roles_for_group(self, guild: discord.Guild, group: str) -> list[discord.Role]:
        roles: list[discord.Role] = []
        for role_key in role_keys_for_group(group):
            role = self.get_role(guild, role_key)
            if role is not None:
                roles.append(role)
        return roles

    def get_year_role(self, guild: discord.Guild, level: int) -> discord.Role | None:
        return self.get_role(guild, year_role_key_for_level(level))

    def get_zodiac_role(self, guild: discord.Guild, sign: str) -> discord.Role | None:
        return self.get_role(guild, zodiac_role_key_for_sign(sign))

    async def cleanup_duplicate_managed_roles(self, guild: discord.Guild) -> dict[str, list[str]]:
        managed_defs = get_all_managed_role_definitions()
        managed_by_name = {role_def.name: role_def for role_def in managed_defs}

        roles_by_name: dict[str, list[discord.Role]] = defaultdict(list)
        for role in guild.roles:
            if role.name in managed_by_name:
                roles_by_name[role.name].append(role)

        deleted: list[str] = []
        failed: list[str] = []

        for role_name, roles in roles_by_name.items():
            if len(roles) <= 1:
                continue

            roles_sorted = sorted(roles, key=lambda r: r.id)
            keep_role = roles_sorted[0]
            extras = roles_sorted[1:]

            role_def = managed_by_name[role_name]
            self.role_repo.upsert_mapping(guild.id, role_def.key, keep_role.id, keep_role.name)

            for extra in extras:
                try:
                    await extra.delete(reason="Hogwarts Bot cleanup duplicate managed role")
                    deleted.append(f"{role_name} → deleted {extra.id}")
                except discord.Forbidden:
                    failed.append(f"{role_name} → could not delete {extra.id} (permissions/hierarchy)")
                except discord.HTTPException as exc:
                    failed.append(f"{role_name} → could not delete {extra.id} ({exc})")

        return {"deleted": deleted, "failed": failed}

    async def reorder_managed_roles(self, guild: discord.Guild) -> None:
        bot_member = self._get_bot_member(guild)
        if bot_member is None:
            return

        managed_roles: list[tuple[discord.Role, str, str]] = []
        for role_def in get_all_managed_role_definitions():
            role = self.get_role(guild, role_def.key)
            if role is None:
                continue
            if role >= bot_member.top_role:
                continue
            managed_roles.append((role, role_def.group, role_def.key))

        if not managed_roles:
            return

        # Exact desired order from low -> high in Discord hierarchy:
        # system / years / zodiac / pings / dm / continents / ages / relationship /
        # sexuality / gender / pronouns / quidditch /
        # house role first, then that house's colour block above it
        #
        # Because higher position means "above", we assign increasing numbers in the order below.

        ordered_role_keys: list[str] = []

        # Base groups in the exact order you wanted
        for group_name in [
            ROLE_GROUP_SYSTEM,
            ROLE_GROUP_YEARS,
            ROLE_GROUP_ZODIAC,
            ROLE_GROUP_PINGS,
            ROLE_GROUP_DM,
            ROLE_GROUP_CONTINENTS,
            ROLE_GROUP_AGES,
            ROLE_GROUP_RELATIONSHIP,
            ROLE_GROUP_SEXUALITY,
            ROLE_GROUP_GENDER_IDENTITY,
            ROLE_GROUP_PRONOUNS,
            ROLE_GROUP_QUIDDITCH_POSITIONS,
        ]:
            ordered_role_keys.extend(role_keys_for_group(group_name))

        # House role first, then its colour block above it
        for house_name in HOUSE_NAMES:
            ordered_role_keys.append(house_role_key_for_name(house_name))
            ordered_role_keys.extend(role_keys_for_group(house_color_group_for_name(house_name)))

        ordered_role_keys.append(ROLE_KEY_HEAD_STUDENT)

        key_to_role: dict[str, discord.Role] = {
            role_key: role
            for role, _, role_key in managed_roles
        }

        ordered_roles: list[discord.Role] = [
            key_to_role[role_key]
            for role_key in ordered_role_keys
            if role_key in key_to_role
        ]

        if not ordered_roles:
            return

        positions: dict[discord.Role, int] = {}
        for index, role in enumerate(ordered_roles, start=1):
            positions[role] = index

        await guild.edit_role_positions(positions=positions)

    def get_house_role(self, guild: discord.Guild, house_name: str) -> discord.Role | None:
        return self.get_role(guild, house_role_key_for_name(house_name))

    def get_house_roles(self, guild: discord.Guild) -> dict[str, discord.Role]:
        roles: dict[str, discord.Role] = {}
        for house_name in HOUSE_NAMES:
            role = self.get_house_role(guild, house_name)
            if role is not None:
                roles[house_name] = role
        return roles

    def get_member_house(self, guild: discord.Guild, member: discord.Member) -> str | None:
        member_role_ids = {role.id for role in member.roles}
        matching_houses = [
            house_name
            for house_name, role in self.get_house_roles(guild).items()
            if role.id in member_role_ids
        ]

        if len(matching_houses) == 1:
            return matching_houses[0]

        return None

    def member_has_house(self, guild: discord.Guild, member: discord.Member) -> bool:
        return self.get_member_house(guild, member) is not None

    def _get_bot_member(self, guild: discord.Guild) -> discord.Member | None:
        return getattr(guild, "self_member", None) or guild.me

    def _permissions_for_role(self, role_key: str) -> discord.Permissions | None:
        if role_key != ROLE_KEY_HEAD_STUDENT:
            return None

        permissions = discord.Permissions.none()
        permissions.view_audit_log = True
        permissions.kick_members = True
        permissions.ban_members = True
        permissions.manage_roles = True
        permissions.manage_messages = True
        permissions.read_message_history = True
        permissions.manage_nicknames = True
        permissions.moderate_members = True
        permissions.mute_members = True
        permissions.deafen_members = True
        permissions.move_members = True
        return permissions

    def _needs_edit(self, role: discord.Role, role_def) -> bool:
        return any(
            [
                role.name != role_def.name,
                role.colour.value != role_def.color,
                role.mentionable != role_def.mentionable,
                role.hoist != role_def.hoist,
                self._permissions_for_role(role_def.key) is not None
                and role.permissions.value != self._permissions_for_role(role_def.key).value,
            ]
        )