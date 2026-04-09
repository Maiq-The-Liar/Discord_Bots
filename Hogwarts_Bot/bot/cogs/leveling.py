import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from domain.constants import HOUSE_COLORS
from domain.role_registry import ROLE_GROUP_YEARS
from repositories.guild_role_repository import GuildRoleRepository
from repositories.user_repository import UserRepository
from services.leveling_service import LevelingService
from services.role_service import RoleService
from bot.cogs.profile import resolve_member_roles, validate_house_context


class LevelingCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
        self.processing_users: set[int] = set()

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )

    async def sync_year_role(self, member: discord.Member, new_level: int) -> bool:
        with self.database.connect() as conn:
            role_repo = GuildRoleRepository(conn)
            role_service = RoleService(role_repo)
            target_role = role_service.get_year_role(member.guild, new_level)
            year_roles = role_service.get_roles_for_group(member.guild, ROLE_GROUP_YEARS)

        if target_role is None:
            return False

        roles_to_remove = [
            role for role in member.roles
            if role in year_roles and role.id != target_role.id
        ]

        changed = False

        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Refreshing school year role")
                changed = True
            except discord.HTTPException:
                pass

        if target_role not in member.roles:
            try:
                await member.add_roles(target_role, reason="Assigning school year role")
                changed = True
            except discord.HTTPException:
                pass

        return changed

    async def ensure_member_year_state(self, member: discord.Member, initialize_from_join: bool = True) -> dict | None:
        role_ctx = resolve_member_roles(member)
        is_valid, _ = validate_house_context(role_ctx)
        if not is_valid:
            return None

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            leveling_service = LevelingService(user_repo)

            if initialize_from_join:
                result = leveling_service.ensure_initialized(member.id, member.joined_at)
                refresh = leveling_service.refresh_user_level(member.id)
                if refresh["level_changed"]:
                    result.update(refresh)
            else:
                result = leveling_service.process_member_message(
                    user_id=member.id,
                    joined_at=member.joined_at,
                )

        await self.sync_year_role(member, result["level"])
        return result

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        await self.ensure_member_year_state(member, initialize_from_join=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if not isinstance(message.author, discord.Member):
            return
        if not message.content.strip():
            return
        if message.author.id in self.processing_users:
            return

        role_ctx = resolve_member_roles(message.author)
        is_valid, _ = validate_house_context(role_ctx)
        if not is_valid:
            return

        self.processing_users.add(message.author.id)
        try:
            with self.database.connect() as conn:
                user_repo = UserRepository(conn)
                leveling_service = LevelingService(user_repo)
                result = leveling_service.process_member_message(
                    user_id=message.author.id,
                    joined_at=message.author.joined_at,
                    message_at=message.created_at,
                )

            if result["leveled_up"]:
                await self.sync_year_role(message.author, result["level"])

                color = HOUSE_COLORS.get(role_ctx.current_house or "", 0x2F3136)
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(result["level"], "th")
                embed = discord.Embed(
                    title="📚 School Year Advanced!",
                    description=(
                        f"{message.author.mention} advanced to **{result['level']}{suffix} Year**!"
                    ),
                    color=color,
                )
                await message.channel.send(embed=embed)
        finally:
            self.processing_users.discard(message.author.id)

    @app_commands.command(
        name="year_initialise",
        description="Admin: initialize school-year progress for existing server members from their join date.",
    )
    async def year_initialise(self, interaction: discord.Interaction) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        initialized = 0
        failed = 0

        for member in interaction.guild.members:
            if member.bot:
                continue
            try:
                await self.ensure_member_year_state(member, initialize_from_join=True)
                initialized += 1
            except Exception:
                failed += 1

        await interaction.followup.send(
            f"Year initialization complete. Processed **{initialized}** members. Failed: **{failed}**.",
            ephemeral=True,
        )
