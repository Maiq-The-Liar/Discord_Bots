import discord
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

    async def sync_year_role(
        self,
        member: discord.Member,
        new_level: int,
    ) -> None:
        with self.database.connect() as conn:
            role_repo = GuildRoleRepository(conn)
            role_service = RoleService(role_repo)

            target_role = role_service.get_year_role(member.guild, new_level)
            year_roles = role_service.get_roles_for_group(member.guild, ROLE_GROUP_YEARS)

        if target_role is None:
            return

        roles_to_remove = [
            role
            for role in member.roles
            if role in year_roles and role.id != target_role.id
        ]

        if roles_to_remove:
            try:
                await member.remove_roles(
                    *roles_to_remove,
                    reason="Level up - replacing school year role",
                )
            except discord.HTTPException:
                pass

        if target_role not in member.roles:
            try:
                await member.add_roles(
                    target_role,
                    reason="Level up - assigning new school year role",
                )
            except discord.HTTPException:
                pass

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
                result = leveling_service.process_message_xp(message.author.id)

            if not result["awarded"]:
                return

            if result["leveled_up"]:
                await self.sync_year_role(message.author, result["level"])

                color = HOUSE_COLORS.get(role_ctx.current_house or "", 0x2F3136)
                embed = discord.Embed(
                    title="📚 Level Up!",
                    description=(
                        f"{message.author.mention} advanced to **{result['level']}th school year**!"
                        if result["level"] not in {1, 2, 3}
                        else f"{message.author.mention} advanced to **{result['level']}{'st' if result['level'] == 1 else 'nd' if result['level'] == 2 else 'rd'} school year**!"
                    ),
                    color=color,
                )
                embed.add_field(name="New Level", value=str(result["level"]), inline=True)
                embed.add_field(name="XP Gained", value=str(result["xp_gained"]), inline=True)

                await message.channel.send(embed=embed)

        finally:
            self.processing_users.discard(message.author.id)