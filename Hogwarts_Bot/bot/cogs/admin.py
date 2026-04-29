import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from repositories.user_repository import UserRepository
from repositories.contribution_repository import ContributionRepository
from repositories.bot_state_repository import BotStateRepository
from services.economy_service import EconomyService
from services.house_points_service import HousePointsService
from services.house_cup_board_service import HouseCupBoardService
from services.house_cup_service import HouseCupService
from bot.cogs.profile import resolve_member_roles, validate_house_context
from repositories.guild_role_repository import GuildRoleRepository
from services.role_service import RoleService
from services.leveling_service import LevelingService
from bot.permissions import is_admin_member, is_admin_or_head_student


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return is_admin_member(interaction.user)

    def is_moderator(self, interaction: discord.Interaction) -> bool:
        return is_admin_or_head_student(interaction.user)

    async def deny(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True,
        )

    @app_commands.command(name="rewardmoney", description="Admin: give a user Galleons.")
    @app_commands.describe(member="The target user", amount="Amount of Galleons to add")
    async def rewardmoney(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1],
    ) -> None:
        if not self.is_admin(interaction):
            await self.deny(interaction)
            return

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            economy_service = EconomyService(user_repo)
            economy_service.reward_money(member.id, amount)
            updated_user = user_repo.get_user(member.id)

        await interaction.response.send_message(
            f"Added **{amount}** Galleons to {member.mention}. New balance: **{updated_user['galleons_balance']}**."
        )

    async def adjust_housepoints(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        points: int,
        reason: str,
    ) -> None:
        if not self.is_moderator(interaction):
            await self.deny(interaction)
            return

        if points == 0:
            await interaction.response.send_message("Points must not be 0.", ephemeral=True)
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used inside the server.", ephemeral=True
            )
            return

        role_ctx = resolve_member_roles(member)
        is_valid, error = validate_house_context(role_ctx)
        if not is_valid or not role_ctx.current_house:
            await interaction.response.send_message(
                f"Cannot adjust house points: {error}", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            contribution_repo = ContributionRepository(conn)
            bot_state_repo = BotStateRepository(conn)
            house_cup_service = HouseCupService(user_repo, contribution_repo, bot_state_repo)

            if not house_cup_service.is_active():
                await interaction.followup.send(
                    "The House Cup is not currently running.", ephemeral=True
                )
                return

            house_points_service = HousePointsService(user_repo, contribution_repo)
            house_points_service.adjust_monthly_house_points(
                user_id=member.id,
                house_name=role_ctx.current_house,
                points=points,
            )
            monthly_total = contribution_repo.get_monthly_points_for_user_house(
                member.id,
                role_ctx.current_house,
            )
            board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
            _, board_message = await board_service.create_or_update_board(interaction.guild)

        action_word = "Added" if points > 0 else "Removed"
        await interaction.followup.send(
            f"{action_word} **{abs(points)}** monthly house points "
            f"{'to' if points > 0 else 'from'} {member.mention} "
            f"for **{role_ctx.current_house}**.\n"
            f"Reason: **{reason}**\n"
            f"User's monthly contribution is now **{monthly_total}**.\n"
            f"Board status: **{board_message}**",
            ephemeral=True,
        )

    @app_commands.command(
        name="rewardhousepoints",
        description="Admin/Head Student: add monthly house points to a user.",
    )
    @app_commands.describe(member="The target user", points="Points to add", reason="Reason for the reward")
    async def rewardhousepoints(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        points: app_commands.Range[int, 1],
        reason: str,
    ) -> None:
        await self.adjust_housepoints(interaction, member, int(points), reason)

    @app_commands.command(
        name="deducthousepoints",
        description="Admin/Head Student: deduct monthly house points from a user.",
    )
    @app_commands.describe(member="The target user", points="Points to deduct", reason="Reason for the deduction")
    async def deducthousepoints(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        points: app_commands.Range[int, 1],
        reason: str,
    ) -> None:
        await self.adjust_housepoints(interaction, member, -int(points), reason)

    @app_commands.command(
        name="remove_usermessages",
        description="Admin/Head Student: delete all messages from a user that the bot can remove.",
    )
    @app_commands.describe(member="The user whose messages should be removed")
    async def remove_usermessages(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        if not self.is_moderator(interaction):
            await self.deny(interaction)
            return
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used inside the server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        deleted_total = 0
        failed_channels: list[str] = []

        for channel in interaction.guild.text_channels:
            permissions = channel.permissions_for(interaction.guild.me)
            if not permissions.read_message_history or not permissions.manage_messages:
                continue
            try:
                deleted = await channel.purge(
                    limit=None,
                    check=lambda message: message.author.id == member.id,
                    bulk=False,
                    reason=f"Message cleanup requested by {interaction.user}",
                )
                deleted_total += len(deleted)
            except discord.HTTPException:
                failed_channels.append(channel.name)

        message = f"Deleted **{deleted_total}** message(s) from {member.mention}."
        if failed_channels:
            message += "\nCould not fully scan: " + ", ".join(failed_channels[:10])
        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(
        name="remove_last_messages",
        description="Admin/Head Student: delete the last X messages in this channel.",
    )
    @app_commands.describe(number="Number of recent messages to delete")
    async def remove_last_messages(
        self,
        interaction: discord.Interaction,
        number: app_commands.Range[int, 1, 100],
    ) -> None:
        if not self.is_moderator(interaction):
            await self.deny(interaction)
            return
        if interaction.channel is None or not hasattr(interaction.channel, "purge"):
            await interaction.response.send_message(
                "This command can only be used in a message channel.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(
                limit=int(number),
                reason=f"Last-message cleanup requested by {interaction.user}",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.followup.send(f"Could not delete messages: {exc}", ephemeral=True)
            return

        await interaction.followup.send(f"Deleted **{len(deleted)}** message(s).", ephemeral=True)

    @app_commands.command(
        name="sethouseboard",
        description="Admin: set the channel used for the House Cup scoreboard.",
    )
    @app_commands.describe(channel="The text channel for the scoreboard")
    async def sethouseboard(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if not self.is_admin(interaction):
            await self.deny(interaction)
            return
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used inside the server.", ephemeral=True
            )
            return

        with self.database.connect() as conn:
            contribution_repo = ContributionRepository(conn)
            bot_state_repo = BotStateRepository(conn)
            board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
            _, message = await board_service.create_or_update_board(interaction.guild, channel)

        await interaction.response.send_message(f"{message} Channel: {channel.mention}")

