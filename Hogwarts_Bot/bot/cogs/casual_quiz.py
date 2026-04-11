from pathlib import Path
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from repositories.bot_state_repository import BotStateRepository
from repositories.casual_quiz_repository import CasualQuizRepository
from repositories.contribution_repository import ContributionRepository
from repositories.quiz_repository import QuizRepository
from repositories.user_repository import UserRepository
from services.casual_quiz_service import CasualQuizService
from services.economy_service import EconomyService
from services.house_cup_board_service import HouseCupBoardService
from services.house_points_service import HousePointsService
from domain.constants import HOUSE_COLORS
from bot.cogs.profile import resolve_member_roles, validate_house_context


class CasualQuizCog(commands.Cog):
    QUIZ_CHANNEL_KEY = "casual_quiz_channel_id"

    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
        self.processing_channels: set[int] = set()
        self.quiz_channel_id: int | None = None

        with self.database.connect() as conn:
            bot_state_repo = BotStateRepository(conn)
            configured_channel_id = bot_state_repo.get_value(self.QUIZ_CHANNEL_KEY)
            self.quiz_channel_id = int(configured_channel_id) if configured_channel_id is not None else None

        base_dir = Path(__file__).resolve().parents[2]
        self.quiz_repo = QuizRepository(
            str(base_dir / "resources" / "quiz_questions.json")
        )

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )

    def build_question_embed(self, question: dict, color: int) -> discord.Embed:
        embed = discord.Embed(
            title="Casual Quiz",
            description=question["question"],
            color=color,
        )

        image_url = question.get("image_url")
        if image_url:
            embed.set_image(url=image_url)

        embed.set_footer(text=f"Question #{question['id']}")
        return embed

    async def post_next_question(self, channel: discord.TextChannel) -> None:
        with self.database.connect() as conn:
            casual_quiz_repo = CasualQuizRepository(conn)
            service = CasualQuizService(self.quiz_repo, casual_quiz_repo)
            question = service.get_next_question(channel.id)

        embed = self.build_question_embed(question, 0x5865F2)
        await channel.send(embed=embed)

    @app_commands.command(
        name="setup_casual_quiz_channel",
        description="Admin: set the channel used for casual quiz mode.",
    )
    @app_commands.describe(channel="The text channel for casual quiz")
    async def setup_casual_quiz_channel(
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
            bot_state_repo = BotStateRepository(conn)
            casual_quiz_repo = CasualQuizRepository(conn)

            bot_state_repo.set_value(self.QUIZ_CHANNEL_KEY, str(channel.id))
            casual_quiz_repo.upsert_channel(channel.id)

        self.quiz_channel_id = channel.id

        await interaction.response.send_message(
            f"Casual quiz channel set to {channel.mention}."
        )

    @app_commands.command(
        name="start_casual_quiz",
        description="Admin: start casual quiz mode in the configured channel.",
    )
    async def start_casual_quiz(
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

        await interaction.response.defer(ephemeral=True)

        with self.database.connect() as conn:
            bot_state_repo = BotStateRepository(conn)
            casual_quiz_repo = CasualQuizRepository(conn)

            channel_id = bot_state_repo.get_value(self.QUIZ_CHANNEL_KEY)
            if channel_id is None:
                await interaction.followup.send(
                    "No casual quiz channel is configured yet.",
                    ephemeral=True,
                )
                return

            channel = interaction.guild.get_channel(int(channel_id))
            if not isinstance(channel, discord.TextChannel):
                await interaction.followup.send(
                    "Configured casual quiz channel could not be found.",
                    ephemeral=True,
                )
                return

            casual_quiz_repo.upsert_channel(channel.id)
            casual_quiz_repo.set_active(channel.id, True)

        await self.post_next_question(channel)

        await interaction.followup.send(
            f"Casual quiz started in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="stop_casual_quiz",
        description="Admin: stop casual quiz mode.",
    )
    async def stop_casual_quiz(
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
            bot_state_repo = BotStateRepository(conn)
            casual_quiz_repo = CasualQuizRepository(conn)

            channel_id = bot_state_repo.get_value(self.QUIZ_CHANNEL_KEY)
            if channel_id is None:
                await interaction.response.send_message(
                    "No casual quiz channel is configured yet.",
                    ephemeral=True,
                )
                return

            channel = interaction.guild.get_channel(int(channel_id))
            if not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message(
                    "Configured casual quiz channel could not be found.",
                    ephemeral=True,
                )
                return

            casual_quiz_repo.set_active(channel.id, False)
            casual_quiz_repo.set_current_question(channel.id, None)

        await interaction.response.send_message(
            f"Casual quiz stopped in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="skip_question",
        description="Admin: skip the current casual quiz question.",
    )
    async def skip_question(
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

        await interaction.response.defer(ephemeral=True)

        with self.database.connect() as conn:
            bot_state_repo = BotStateRepository(conn)
            casual_quiz_repo = CasualQuizRepository(conn)
            service = CasualQuizService(self.quiz_repo, casual_quiz_repo)

            channel_id = bot_state_repo.get_value(self.QUIZ_CHANNEL_KEY)
            if channel_id is None:
                await interaction.followup.send(
                    "No casual quiz channel is configured yet.",
                    ephemeral=True,
                )
                return

            channel = interaction.guild.get_channel(int(channel_id))
            if not isinstance(channel, discord.TextChannel):
                await interaction.followup.send(
                    "Configured casual quiz channel could not be found.",
                    ephemeral=True,
                )
                return

            state = casual_quiz_repo.get_channel_state(channel.id)
            if state is None or not bool(state["is_active"]):
                await interaction.followup.send(
                    "Casual quiz is not active.",
                    ephemeral=True,
                )
                return

            current_question = service.get_current_question(channel.id)

        if current_question is not None:
            await channel.send(
                f"⏭️ Question skipped. Correct answer(s): **{', '.join(current_question['answers'])}**"
            )

        await asyncio.sleep(2)
        await self.post_next_question(channel)

        await interaction.followup.send("Question skipped.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        if not isinstance(message.author, discord.Member):
            return

        if self.quiz_channel_id != message.channel.id:
            return

        if message.channel.id in self.processing_channels:
            return

        with self.database.connect() as conn:
            casual_quiz_repo = CasualQuizRepository(conn)
            state = casual_quiz_repo.get_channel_state(message.channel.id)

            if state is None or not bool(state["is_active"]):
                return

            service = CasualQuizService(self.quiz_repo, casual_quiz_repo)
            current_question = service.get_current_question(message.channel.id)
            if current_question is None:
                return

            is_correct = service.is_correct_answer(current_question, message.content)

        if not is_correct:
            try:
                await message.add_reaction("❌")
            except discord.HTTPException:
                pass
            return

        self.processing_channels.add(message.channel.id)
        try:
            try:
                await message.add_reaction("✅")
            except discord.HTTPException:
                pass

            role_ctx = resolve_member_roles(message.author)
            is_valid, _ = validate_house_context(role_ctx)
            if not is_valid or not role_ctx.current_house:
                return

            with self.database.connect() as conn:
                bot_state_repo = BotStateRepository(conn)
                contribution_repo = ContributionRepository(conn)
                user_repo = UserRepository(conn)

                economy_service = EconomyService(user_repo)
                house_points_service = HousePointsService(user_repo, contribution_repo)

                economy_service.reward_money(message.author.id, 5)
                house_points_service.adjust_monthly_house_points(
                    user_id=message.author.id,
                    house_name=role_ctx.current_house,
                    points=2,
                )

                board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
                await board_service.create_or_update_board(message.guild)

            reward_embed = discord.Embed(
                title=f'{message.author.display_name} got it! 2 Points for {role_ctx.current_house}!',
                color=HOUSE_COLORS.get(role_ctx.current_house or "", 0x57F287),
            )
            reward_embed.set_footer(text="And also 5 Galleons.")

            await message.channel.send(embed=reward_embed)

            await asyncio.sleep(2)
            await self.post_next_question(message.channel)

        finally:
            self.processing_channels.discard(message.channel.id)