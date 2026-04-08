from __future__ import annotations

from collections import defaultdict

import discord

from domain.role_registry import (
    ROLE_DEFINITION_BY_KEY,
    ROLE_GROUP_HOUSE_COLOR_GRYFFINDOR,
    ROLE_GROUP_HOUSE_COLOR_HUFFLEPUFF,
    ROLE_GROUP_HOUSE_COLOR_RAVENCLAW,
    ROLE_GROUP_HOUSE_COLOR_SLYTHERIN,
    get_all_managed_role_definitions,
    get_role_definition,
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

        if role is None:
            role = await guild.create_role(
                name=role_def.name,
                colour=discord.Colour(role_def.color),
                mentionable=role_def.mentionable,
                hoist=role_def.hoist,
                reason="Hogwarts Bot role sync",
            )
            self.role_repo.upsert_mapping(guild.id, role_key, role.id, role.name)
            return role, "created"

        if self._needs_edit(role, role_def):
            await role.edit(
                name=role_def.name,
                colour=discord.Colour(role_def.color),
                mentionable=role_def.mentionable,
                hoist=role_def.hoist,
                reason="Hogwarts Bot role sync",
            )
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
        managed_roles: list[tuple[discord.Role, str]] = []

        for role_def in get_all_managed_role_definitions():
            role = self.get_role(guild, role_def.key)
            if role is not None:
                managed_roles.append((role, role_def.group))

        if not managed_roles:
            return

        editable_roles = [
            (role, group)
            for role, group in managed_roles
            if guild.me is not None and role < guild.me.top_role
        ]

        if not editable_roles:
            return

        color_roles = [(role, group) for role, group in editable_roles if group in HOUSE_COLOR_GROUPS]
        other_roles = [(role, group) for role, group in editable_roles if group not in HOUSE_COLOR_GROUPS]

        color_roles.sort(key=lambda item: item[0].name.lower())
        other_roles.sort(key=lambda item: item[0].name.lower())

        # Discord hierarchy: larger position = higher role.
        # We place managed roles as high as possible under the bot's top role,
        # with all house colour roles above the other managed roles.
        ordered_roles = [role for role, _ in other_roles] + [role for role, _ in color_roles]

        base_position = 1
        positions: dict[discord.Role, int] = {}

        for index, role in enumerate(ordered_roles, start=base_position):
            positions[role] = index

        await guild.edit_role_positions(positions=positions)

    def _needs_edit(self, role: discord.Role, role_def) -> bool:
        return any(
            [
                role.name != role_def.name,
                role.colour.value != role_def.color,
                role.mentionable != role_def.mentionable,
                role.hoist != role_def.hoist,
            ]
        )