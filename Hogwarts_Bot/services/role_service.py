from __future__ import annotations

import discord

from domain.role_registry import (
    ROLE_DEFINITION_BY_KEY,
    get_all_managed_role_definitions,
    get_role_definition,
    role_keys_for_group,
    year_role_key_for_level,
    zodiac_role_key_for_sign,
)
from repositories.guild_role_repository import GuildRoleRepository


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

    def get_role(
        self,
        guild: discord.Guild,
        role_key: str,
    ) -> discord.Role | None:
        mapping = self.role_repo.get_mapping(guild.id, role_key)
        if mapping is not None:
            mapped_role = guild.get_role(int(mapping["role_id"]))
            if mapped_role is not None:
                return mapped_role

        role_def = ROLE_DEFINITION_BY_KEY[role_key]
        by_name = discord.utils.get(guild.roles, name=role_def.name)
        if by_name is not None:
            self.role_repo.upsert_mapping(guild.id, role_key, by_name.id, by_name.name)
            return by_name

        return None

    def get_roles_for_group(
        self,
        guild: discord.Guild,
        group: str,
    ) -> list[discord.Role]:
        roles: list[discord.Role] = []
        for role_key in role_keys_for_group(group):
            role = self.get_role(guild, role_key)
            if role is not None:
                roles.append(role)
        return roles

    def get_year_role(
        self,
        guild: discord.Guild,
        level: int,
    ) -> discord.Role | None:
        return self.get_role(guild, year_role_key_for_level(level))

    def get_zodiac_role(
        self,
        guild: discord.Guild,
        sign: str,
    ) -> discord.Role | None:
        return self.get_role(guild, zodiac_role_key_for_sign(sign))

    def _needs_edit(self, role: discord.Role, role_def) -> bool:
        return any(
            [
                role.name != role_def.name,
                role.colour.value != role_def.color,
                role.mentionable != role_def.mentionable,
                role.hoist != role_def.hoist,
            ]
        )