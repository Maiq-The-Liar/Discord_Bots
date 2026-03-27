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


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )

    @app_commands.command(name="rewardmoney", description="Admin: give a user Sickles.")
    @app_commands.describe(member="The target user", amount="Amount of Sickles to add")
    async def rewardmoney(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1],
    ) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            economy_service = EconomyService(user_repo)
            economy_service.reward_money(member.id, amount)
            updated_user = user_repo.get_user(member.id)

        await interaction.response.send_message(
            f"Added **{amount}** Sickles to {member.mention}. "
            f"New balance: **{updated_user['sickles_balance']}**."
        )

    @app_commands.command(
        name="rewardhousepoints",
        description="Admin: add or remove monthly house points from a user.",
    )
    @app_commands.describe(
        member="The target user",
        points="Positive adds points, negative removes points",
    )
    async def rewardhousepoints(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        points: int,
    ) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if points == 0:
            await interaction.response.send_message(
                "Points must not be 0.",
                ephemeral=True,
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        role_ctx = resolve_member_roles(member)
        is_valid, error = validate_house_context(role_ctx)

        if not is_valid or not role_ctx.current_house:
            await interaction.response.send_message(
                f"Cannot adjust house points: {error}",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            contribution_repo = ContributionRepository(conn)
            bot_state_repo = BotStateRepository(conn)

            house_cup_service = HouseCupService(user_repo, contribution_repo, bot_state_repo)
            if not house_cup_service.is_active():
                await interaction.response.send_message(
                    "The House Cup is not currently running.",
                    ephemeral=True,
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
        await interaction.response.send_message(
            f"{action_word} **{abs(points)}** monthly house points "
            f"{'to' if points > 0 else 'from'} {member.mention} "
            f"for **{role_ctx.current_house}**.\n"
            f"User's monthly contribution is now **{monthly_total}**.\n"
            f"Board status: **{board_message}**"
        )

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
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            contribution_repo = ContributionRepository(conn)
            bot_state_repo = BotStateRepository(conn)
            board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
            _, message = await board_service.create_or_update_board(interaction.guild, channel)

        await interaction.response.send_message(
            f"{message} Channel: {channel.mention}"
        )

    @app_commands.command(
        name="refreshhouseboard",
        description="Admin: manually refresh the House Cup scoreboard.",
    )
    async def refreshhouseboard(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            contribution_repo = ContributionRepository(conn)
            bot_state_repo = BotStateRepository(conn)
            board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
            _, message = await board_service.create_or_update_board(interaction.guild)

        await interaction.response.send_message(message)