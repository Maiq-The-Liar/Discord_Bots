import discord
from discord import app_commands
from discord.ext import commands, tasks

from db.database import Database
from repositories.bot_state_repository import BotStateRepository
from repositories.contribution_repository import ContributionRepository
from repositories.user_repository import UserRepository
from services.house_cup_service import HouseCupService
from services.house_cup_board_service import HouseCupBoardService


class HouseCupCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

    async def cog_load(self) -> None:
        if not self.monthly_reset_loop.is_running():
            self.monthly_reset_loop.start()
        if not self.house_board_update_loop.is_running():
            self.house_board_update_loop.start()

    async def cog_unload(self) -> None:
        if self.monthly_reset_loop.is_running():
            self.monthly_reset_loop.cancel()
        if self.house_board_update_loop.is_running():
            self.house_board_update_loop.cancel()

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )

    def build_congratulations_embed(
        self,
        summary: dict,
    ) -> discord.Embed:
        winner_house = summary["winner_house"]
        winner_points = summary["winner_points"]
        month = summary["month"]

        if winner_house is None:
            description = (
                f"The House Cup for **{month}** has ended.\n"
                f"No house scored any points this round."
            )
        else:
            description = (
                f"🎉 Congratulations to **{winner_house}** for winning the House Cup for **{month}** "
                f"with **{winner_points}** points!"
            )

        embed = discord.Embed(
            title="House Cup Results",
            description=description,
            color=0xD4AF37,
        )

        top_players = summary["top_players"]
        if top_players:
            lines = []
            for player in top_players:
                lines.append(
                    f"**#{player['rank']}** • <@{player['user_id']}> — "
                    f"**{player['points']}** points — Reward: **{player['reward']} Galleons**"
                )

            embed.add_field(
                name="Top 3 Players",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="Top 3 Players",
                value="No players earned any points this round.",
                inline=False,
            )

        return embed

    async def send_congratulations_message(
        self,
        guild: discord.Guild,
        summary: dict,
    ) -> None:
        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            contribution_repo = ContributionRepository(conn)
            bot_state_repo = BotStateRepository(conn)
            house_cup_service = HouseCupService(user_repo, contribution_repo, bot_state_repo)
            ranking_channel_id = house_cup_service.get_ranking_channel_id()

        if ranking_channel_id is None:
            return

        channel = guild.get_channel(ranking_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        embed = self.build_congratulations_embed(summary)
        await channel.send(embed=embed)

    @tasks.loop(minutes=5)
    async def monthly_reset_loop(self) -> None:
        for guild in self.bot.guilds:
            summary = None

            with self.database.connect() as conn:
                user_repo = UserRepository(conn)
                contribution_repo = ContributionRepository(conn)
                bot_state_repo = BotStateRepository(conn)

                house_cup_service = HouseCupService(
                    user_repo,
                    contribution_repo,
                    bot_state_repo,
                )
                summary = house_cup_service.handle_month_rollover()

            if summary is not None:
                await self.send_congratulations_message(guild, summary)

                with self.database.connect() as conn:
                    contribution_repo = ContributionRepository(conn)
                    bot_state_repo = BotStateRepository(conn)
                    HouseCupBoardService.mark_dirty(guild.id)

    @monthly_reset_loop.before_loop
    async def before_monthly_reset_loop(self) -> None:
        await self.bot.wait_until_ready()


    @tasks.loop(minutes=1)
    async def house_board_update_loop(self) -> None:
        for guild in self.bot.guilds:
            if not HouseCupBoardService.consume_dirty(guild.id):
                continue

            try:
                with self.database.connect() as conn:
                    contribution_repo = ContributionRepository(conn)
                    bot_state_repo = BotStateRepository(conn)
                    board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
                    await board_service.create_or_update_board(guild)
            except Exception:
                HouseCupBoardService.mark_dirty(guild.id)

    @house_board_update_loop.before_loop
    async def before_house_board_update_loop(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="setup_housecup_rankingmessage",
        description="Admin: set the channel used for the House Cup congratulations message.",
    )
    @app_commands.describe(channel="The channel where congratulations messages should be sent")
    async def setup_housecup_rankingmessage(
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

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            contribution_repo = ContributionRepository(conn)
            bot_state_repo = BotStateRepository(conn)
            house_cup_service = HouseCupService(user_repo, contribution_repo, bot_state_repo)
            house_cup_service.set_ranking_channel_id(channel.id)

        await interaction.response.send_message(
            f"House Cup congratulations channel set to {channel.mention}."
        )

    @app_commands.command(
        name="start_housecup",
        description="Admin: start the House Cup.",
    )
    async def start_housecup(
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
            user_repo = UserRepository(conn)
            contribution_repo = ContributionRepository(conn)
            bot_state_repo = BotStateRepository(conn)

            house_cup_service = HouseCupService(
                user_repo,
                contribution_repo,
                bot_state_repo,
            )

            try:
                started_month = house_cup_service.start_cup()
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

            board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
            _, board_message = await board_service.create_or_update_board(interaction.guild)

        await interaction.response.send_message(
            f"The House Cup has started for **{started_month}**.\n"
            f"Board status: **{board_message}**"
        )

    @app_commands.command(
        name="end_cup",
        description="Admin: end the current House Cup immediately.",
    )
    async def end_cup(
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
            user_repo = UserRepository(conn)
            contribution_repo = ContributionRepository(conn)
            bot_state_repo = BotStateRepository(conn)

            house_cup_service = HouseCupService(
                user_repo,
                contribution_repo,
                bot_state_repo,
            )

            try:
                summary = house_cup_service.end_cup()
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

        await self.send_congratulations_message(interaction.guild, summary)

        with self.database.connect() as conn:
            contribution_repo = ContributionRepository(conn)
            bot_state_repo = BotStateRepository(conn)
            board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
            _, board_message = await board_service.create_or_update_board(interaction.guild)

        await interaction.response.send_message(
            f"The House Cup has been ended.\n"
            f"Congratulations message sent.\n"
            f"Board status: **{board_message}**"
        )