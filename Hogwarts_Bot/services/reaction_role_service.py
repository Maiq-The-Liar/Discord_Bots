from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import discord

from domain.constants import HOUSE_ROLE_IDS
from domain.reaction_role_registry import (
    ReactionRoleGroup,
    ReactionRoleOption,
    get_reaction_role_group,
    get_reaction_role_groups,
)
from domain.role_registry import get_role_definition
from repositories.guild_role_repository import GuildRoleRepository
from repositories.reaction_role_repository import ReactionRoleRepository
from services.role_service import RoleService


class ReactionRoleService:
    def __init__(
        self,
        bot,
        reaction_repo: ReactionRoleRepository,
        guild_role_repo: GuildRoleRepository,
    ):
        self.bot = bot
        self.reaction_repo = reaction_repo
        self.role_service = RoleService(guild_role_repo)
        self.roles_image_dir = Path(__file__).resolve().parents[1] / "resources" / "roles"

    async def setup_channel(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
    ) -> dict[str, int]:
        await self.role_service.sync_all_managed_roles(guild)
        self.reaction_repo.set_channel(guild.id, channel.id)

        deleted = await self._clear_channel(channel)
        self.reaction_repo.clear_message_mappings(guild.id)

        posted = 0
        for group in get_reaction_role_groups():
            file, embeds = self.build_message_payload(guild, group.key)
            message = await channel.send(
                file=file,
                embeds=embeds,
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
            )
            self.reaction_repo.add_message_mapping(guild.id, group.key, channel.id, message.id)

            for option in group.options:
                try:
                    await message.add_reaction(self._emoji_for_reaction(option))
                except discord.HTTPException:
                    pass

            posted += 1

        return {"deleted_messages": deleted, "posted_messages": posted}

    def build_message_payload(self, guild: discord.Guild, group_key: str) -> tuple[discord.File, list[discord.Embed]]:
        group = get_reaction_role_group(group_key)

        banner_path = self.roles_image_dir / group.banner_filename
        file = discord.File(banner_path, filename=group.banner_filename)

        banner_embed = discord.Embed(color=0x2F3136)
        banner_embed.set_image(url=f"attachment://{group.banner_filename}")

        text_embed = discord.Embed(
            description=self._build_description(guild, group),
            color=0x2F3136,
        )
        text_embed.set_footer(text="Select multiple" if group.multi_select else "Select only one")

        return file, [banner_embed, text_embed]

    async def refresh_group_message(self, guild: discord.Guild, group_key: str) -> None:
        mapping = self.reaction_repo.get_message_mapping_for_group(guild.id, group_key)
        if mapping is None:
            return

        channel = guild.get_channel(int(mapping["channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(int(mapping["message_id"]))
        except discord.HTTPException:
            return

        _, embeds = self.build_message_payload(guild, group_key)
        try:
            await message.edit(
                embeds=embeds,
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
            )
        except discord.HTTPException:
            return

    async def handle_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        mapping = self.reaction_repo.get_message_mapping_by_message_id(payload.message_id)
        if mapping is None:
            return

        guild = self.bot.get_guild(int(mapping["guild_id"]))
        if guild is None:
            return

        member = payload.member
        if member is None or member.bot:
            return

        group = get_reaction_role_group(mapping["group_key"])
        option = self._match_option(group, payload.emoji)
        if option is None:
            return

        channel = guild.get_channel(int(mapping["channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(int(mapping["message_id"]))
        except discord.HTTPException:
            return

        if not self._member_can_use_group(member, group):
            try:
                await message.remove_reaction(self._emoji_for_reaction(option), member)
            except discord.HTTPException:
                pass
            return

        role = self.role_service.get_role(guild, option.role_key)
        if role is None:
            try:
                await message.remove_reaction(self._emoji_for_reaction(option), member)
            except discord.HTTPException:
                pass
            return

        if not group.multi_select:
            existing = self.reaction_repo.list_user_memberships_in_group(guild.id, member.id, group.key)
            for row in existing:
                existing_role_key = row["role_key"]
                if existing_role_key == option.role_key:
                    continue

                old_role = self.role_service.get_role(guild, existing_role_key)
                if old_role is not None and old_role in member.roles:
                    try:
                        await member.remove_roles(old_role, reason="Reaction role swap")
                    except discord.HTTPException:
                        pass

                self.reaction_repo.delete_membership(guild.id, member.id, group.key, existing_role_key)

                old_option = self._get_option_by_role_key(group, existing_role_key)
                if old_option is not None:
                    try:
                        await message.remove_reaction(self._emoji_for_reaction(old_option), member)
                    except discord.HTTPException:
                        pass

        self.reaction_repo.upsert_membership(guild.id, member.id, group.key, option.role_key)

        if role not in member.roles:
            try:
                await member.add_roles(role, reason="Reaction role selected")
            except discord.HTTPException:
                self.reaction_repo.delete_membership(guild.id, member.id, group.key, option.role_key)
                try:
                    await message.remove_reaction(self._emoji_for_reaction(option), member)
                except discord.HTTPException:
                    pass
                return

        await self.clear_invalid_house_color_roles(member)
        await self.refresh_group_message(guild, group.key)

    async def handle_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        mapping = self.reaction_repo.get_message_mapping_by_message_id(payload.message_id)
        if mapping is None:
            return

        guild = self.bot.get_guild(int(mapping["guild_id"]))
        if guild is None or guild.me is None:
            return

        if payload.user_id == guild.me.id:
            return

        group = get_reaction_role_group(mapping["group_key"])
        option = self._match_option(group, payload.emoji)
        if option is None:
            return

        if not self.reaction_repo.membership_exists(guild.id, payload.user_id, group.key, option.role_key):
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.HTTPException:
                member = None

        self.reaction_repo.delete_membership(guild.id, payload.user_id, group.key, option.role_key)

        if member is not None:
            role = self.role_service.get_role(guild, option.role_key)
            if role is not None and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Reaction role removed")
                except discord.HTTPException:
                    pass

        await self.refresh_group_message(guild, group.key)

    async def clear_invalid_house_color_roles(self, member: discord.Member) -> None:
        member_house = self._member_house(member)
        if member_house is None:
            return

        for group in get_reaction_role_groups():
            if not group.house_name or group.house_name == member_house:
                continue

            for option in group.options:
                role = self.role_service.get_role(member.guild, option.role_key)
                if role is not None and role in member.roles:
                    try:
                        await member.remove_roles(role, reason="Removing other-house colour role")
                    except discord.HTTPException:
                        pass

    async def _clear_channel(self, channel: discord.TextChannel) -> int:
        deleted = 0
        now = datetime.now(timezone.utc)

        while True:
            batch = [message async for message in channel.history(limit=100)]
            if not batch:
                break

            recent = []
            older = []

            for message in batch:
                age_seconds = (now - message.created_at).total_seconds()
                if age_seconds < 14 * 24 * 60 * 60:
                    recent.append(message)
                else:
                    older.append(message)

            if recent:
                if len(recent) == 1:
                    try:
                        await recent[0].delete()
                        deleted += 1
                    except discord.HTTPException:
                        pass
                else:
                    try:
                        await channel.delete_messages(recent)
                        deleted += len(recent)
                    except discord.HTTPException:
                        for message in recent:
                            try:
                                await message.delete()
                                deleted += 1
                            except discord.HTTPException:
                                pass

            for message in older:
                try:
                    await message.delete()
                    deleted += 1
                    await asyncio.sleep(0.35)
                except discord.HTTPException:
                    pass

            if len(batch) < 100:
                break

        return deleted

    def _build_description(self, guild: discord.Guild, group: ReactionRoleGroup) -> str:
        counts = self.reaction_repo.count_memberships_for_group(guild.id, group.key)
        lines: list[str] = []

        for option in group.options:
            role_def = get_role_definition(option.role_key)
            count = counts.get(option.role_key, 0)
            emoji_text = self._emoji_for_display(option)

            if group.house_name:
                role = self.role_service.get_role(guild, option.role_key)
                label = role.mention if role is not None else role_def.name
            else:
                label = role_def.name

            lines.append(f"{emoji_text} {label} — `{count}`")

        return "\n".join(lines)

    def _emoji_for_display(self, option: ReactionRoleOption) -> str:
        if option.emoji_id and option.emoji_name:
            prefix = "a" if option.emoji_animated else ""
            return f"<{prefix}:{option.emoji_name}:{option.emoji_id}>"
        return option.emoji_unicode or "•"

    def _emoji_for_reaction(self, option: ReactionRoleOption):
        if option.emoji_id and option.emoji_name:
            return discord.PartialEmoji(
                name=option.emoji_name,
                id=option.emoji_id,
                animated=option.emoji_animated,
            )
        return option.emoji_unicode or "•"

    def _match_option(
        self,
        group: ReactionRoleGroup,
        emoji: discord.PartialEmoji,
    ) -> ReactionRoleOption | None:
        for option in group.options:
            if option.emoji_id is not None and emoji.id == option.emoji_id:
                return option
            if option.emoji_unicode is not None and str(emoji) == option.emoji_unicode:
                return option
        return None

    def _get_option_by_role_key(
        self,
        group: ReactionRoleGroup,
        role_key: str,
    ) -> ReactionRoleOption | None:
        for option in group.options:
            if option.role_key == role_key:
                return option
        return None

    def _member_house(self, member: discord.Member) -> str | None:
        role_ids = {role.id for role in member.roles}
        role_names_lower = {role.name.strip().lower() for role in member.roles}

        for house_name, role_id in HOUSE_ROLE_IDS.items():
            if role_id in role_ids:
                return house_name

        for house_name in HOUSE_ROLE_IDS.keys():
            if house_name.strip().lower() in role_names_lower:
                return house_name

        return None

    def _member_can_use_group(self, member: discord.Member, group: ReactionRoleGroup) -> bool:
        if group.house_name is None:
            return True

        member_house = self._member_house(member)
        if member_house is None:
            return False

        return member_house.strip().lower() == group.house_name.strip().lower()