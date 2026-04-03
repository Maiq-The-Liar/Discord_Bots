from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.profile import resolve_member_roles, validate_house_context
from db.database import Database
from domain.constants import HOUSE_COLORS
from repositories.bot_state_repository import BotStateRepository
from repositories.contribution_repository import ContributionRepository
from repositories.inventory_repository import InventoryRepository
from repositories.quiz_repository import QuizRepository
from repositories.user_repository import UserRepository
from services.casual_quiz_service import CasualQuizService
from services.house_cup_board_service import HouseCupBoardService
from services.house_points_service import HousePointsService

DUEL_PING_ROLE_ID = 1489701585411117207
DUELLING_ROLE_ID = 1489701423582150877

START_IMAGE_URL = "https://github.com/Maiq-The-Liar/Bot_Quiz_Images/blob/main/00_quiz_gifs/duel.png?raw=true"
LOBBY_IMAGE_URL = "https://github.com/Maiq-The-Liar/Bot_Quiz_Images/blob/main/00_quiz_gifs/waiting.gif?raw=true"
COUNTDOWN_IMAGE_URL = "https://github.com/Maiq-The-Liar/Bot_Quiz_Images/blob/main/00_quiz_gifs/countdown.gif?raw=true"

MIN_PLAYERS = 2
MAX_PLAYERS = 7
LOBBY_DURATION_SECONDS = 30
COUNTDOWN_DURATION_SECONDS = 11
QUESTION_DURATION_SECONDS = 10
CORRECT_ANSWER_DELAY_SECONDS = 1
RESULTS_DURATION_SECONDS = 5
QUESTIONS_PER_DUEL = 10


@dataclass
class DuelSession:
    channel_id: int
    participants: list[int] = field(default_factory=list)
    participant_houses: dict[int, str] = field(default_factory=dict)
    scores: dict[int, int] = field(default_factory=dict)
    phase: str = "lobby"
    cancelled: bool = False
    lobby_message: discord.Message | None = None
    current_question: dict | None = None
    current_question_number: int = 0
    round_event: asyncio.Event | None = None
    round_winner_id: int | None = None
    answer_locked: bool = False
    lobby_full_event: asyncio.Event = field(default_factory=asyncio.Event)
    runner_task: asyncio.Task | None = None


class StartDuelView(discord.ui.View):
    def __init__(self, cog: "DuelCog", disabled: bool = False):
        super().__init__(timeout=None)
        self.cog = cog
        self.start_button.disabled = disabled

    @discord.ui.button(label="Start Duel", style=discord.ButtonStyle.danger)
    async def start_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_start_button(interaction)


class DuelLobbyView(discord.ui.View):
    def __init__(self, cog: "DuelCog", channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.success)
    async def join_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_join_button(interaction, self.channel_id)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary)
    async def leave_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_leave_button(interaction, self.channel_id)


class DuelCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
        self.sessions: dict[int, DuelSession] = {}
        self.processing_channels: set[int] = set()
        self.configured_channels: set[int] = set()

        base_dir = Path(__file__).resolve().parents[2]
        self.quiz_repo = QuizRepository(str(base_dir / "resources" / "quiz_questions.json"))
        self.answer_service = CasualQuizService(self.quiz_repo, None)  # type: ignore[arg-type]

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )

    def is_session_current(self, session: DuelSession) -> bool:
        return self.sessions.get(session.channel_id) is session and not session.cancelled

    def get_start_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⚔️ Dueling Club",
            description=(
                "Press **Start Duel** to open a new lobby.\n\n"
                f"• The player who starts the duel **automatically joins** the lobby\n"
                f"• Up to **{MAX_PLAYERS}** players can join\n"
                f"• At least **{MIN_PLAYERS}** players are needed\n"
                f"• The lobby stays open for **{LOBBY_DURATION_SECONDS} seconds** unless it fills early\n"
                f"• The duel then starts after a **{COUNTDOWN_DURATION_SECONDS}-second countdown**\n"
                f"• The game asks **{QUESTIONS_PER_DUEL} questions** from the quiz pool\n"
                f"• The **first correct answer** wins each round and earns **2 house points**\n"
                "• Final podium rewards scale with the number of participants\n"
                "• Chocolate Frog rewards stay the same"
            ),
            color=0xB22222,
        )
        embed.set_image(url=START_IMAGE_URL)
        embed.set_footer(text="Ready your wand.")
        return embed

    def build_lobby_embed(self, channel: discord.TextChannel, session: DuelSession) -> discord.Embed:
        player_lines: list[str] = []
        for index, user_id in enumerate(session.participants, start=1):
            member = channel.guild.get_member(user_id)
            display_name = member.display_name if member else f"User {user_id}"
            player_lines.append(f"**{index}.** {display_name}")

        players_text = "\n".join(player_lines) if player_lines else "*No one joined yet.*"

        ping_role = channel.guild.get_role(DUEL_PING_ROLE_ID)
        ping_text = ping_role.mention if ping_role else "A new duel lobby has opened!"

        embed = discord.Embed(
            title="🪄 A new duel is forming!",
            description=(
                f"{ping_text}\n\n"
                "Press **Join Game** to enter the lobby.\n"
                "Pressed **Start Duel**? You are already in.\n"
                "Changed your mind? Use **Leave** before the countdown begins."
            ),
            color=0x5865F2,
        )
        embed.add_field(name="👥 Joined Players", value=players_text, inline=False)
        embed.add_field(name="📌 Lobby Size", value=f"**{len(session.participants)}/{MAX_PLAYERS}**", inline=True)
        embed.add_field(name="✅ Minimum Needed", value=f"**{MIN_PLAYERS}**", inline=True)
        embed.add_field(name="⏳ Time Remaining", value=f"**{LOBBY_DURATION_SECONDS}s max**", inline=True)
        embed.set_image(url=LOBBY_IMAGE_URL)
        embed.set_footer(text="The duel starts early if the lobby reaches 7/7.")
        return embed

    def build_countdown_embed(self, channel: discord.TextChannel, session: DuelSession) -> discord.Embed:
        player_lines: list[str] = []
        for index, user_id in enumerate(session.participants, start=1):
            member = channel.guild.get_member(user_id)
            display_name = member.display_name if member else f"User {user_id}"
            house_name = session.participant_houses.get(user_id, "Unknown")
            player_lines.append(f"**{index}.** {display_name} — {house_name}")

        embed = discord.Embed(
            title="⏱️ Duel starting soon!",
            description="The lobby is now locked. Get ready to answer fast.",
            color=0xF1C40F,
        )
        embed.add_field(
            name="⚔️ Duelists",
            value="\n".join(player_lines) if player_lines else "*No players.*",
            inline=False,
        )
        embed.add_field(name="👥 Lobby Size", value=f"**{len(session.participants)}/{MAX_PLAYERS}**", inline=True)
        embed.add_field(name="⏳ Countdown", value=f"**{COUNTDOWN_DURATION_SECONDS}s**", inline=True)
        embed.set_image(url=COUNTDOWN_IMAGE_URL)
        embed.set_footer(text="No more joining or leaving.")
        return embed

    def build_question_embed(self, question: dict, question_number: int) -> discord.Embed:
        embed = discord.Embed(
            title=f"🧠 Duel Question {question_number}/{QUESTIONS_PER_DUEL}",
            description=question["question"],
            color=0x5865F2,
        )
        image_url = question.get("image_url")
        if image_url:
            embed.set_image(url=image_url)
        embed.set_footer(text=f"Question #{question['id']} • {QUESTION_DURATION_SECONDS}s to answer")
        return embed

    def build_round_win_embed(self, member: discord.Member, house_name: str) -> discord.Embed:
        embed = discord.Embed(
            title=f"✅ {member.display_name} got it first!",
            description=f"**+2 house points** for **{house_name}**.",
            color=HOUSE_COLORS.get(house_name, 0x57F287),
        )
        return embed

    def build_results_embed(
        self,
        guild: discord.Guild,
        session: DuelSession,
        rewards: dict[int, dict[str, int]],
        single_house_lobby: bool,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="🏆 Duel Results",
            description="The duel is over. Here are the final standings and rewards.",
            color=0x9B59B6,
        )

        sorted_players = sorted(
            session.participants,
            key=lambda user_id: (-session.scores.get(user_id, 0), user_id),
        )

        lines: list[str] = []
        previous_score: int | None = None
        display_rank = 0
        counted = 0

        for user_id in sorted_players:
            counted += 1
            score = session.scores.get(user_id, 0)
            if previous_score != score:
                display_rank = counted
                previous_score = score

            member = guild.get_member(user_id)
            display_name = member.display_name if member else f"User {user_id}"
            house_name = session.participant_houses.get(user_id, "Unknown")
            reward = rewards.get(user_id)

            medal = {
                1: "🥇",
                2: "🥈",
                3: "🥉",
            }.get(display_rank, "▫️")

            if reward:
                frog_word = "Chocolate Frog" if reward["frogs"] == 1 else "Chocolate Frogs"
                lines.append(
                    f"{medal} **{display_rank}.** {display_name} — **{score}** correct — {house_name}\n"
                    f"└ +{reward['house_points']} house points • +{reward['frogs']} {frog_word}"
                )
            else:
                lines.append(
                    f"{medal} **{display_rank}.** {display_name} — **{score}** correct — {house_name}"
                )

        if not lines:
            lines.append("*No duel results available.*")

        embed.add_field(name="Standings", value="\n".join(lines), inline=False)
        embed.set_footer(
            text="Single-house reward table used."
            if single_house_lobby
            else "Scaled multi-house reward table used."
        )
        return embed

    async def purge_channel_messages(self, channel: discord.TextChannel) -> None:
        try:
            await channel.purge(limit=None)
        except discord.HTTPException:
            messages = [message async for message in channel.history(limit=200)]
            for message in messages:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass

    async def post_start_embed(self, channel: discord.TextChannel) -> None:
        await channel.send(embed=self.get_start_embed(), view=StartDuelView(self))

    async def remove_duelling_role(
        self,
        guild: discord.Guild,
        participant_ids: list[int],
    ) -> None:
        role = guild.get_role(DUELLING_ROLE_ID)
        if role is None:
            return

        for user_id in participant_ids:
            member = guild.get_member(user_id)
            if member is None:
                continue
            try:
                await member.remove_roles(role, reason="Duel finished or cancelled")
            except discord.HTTPException:
                pass

    async def grant_duelling_role(
        self,
        guild: discord.Guild,
        participant_ids: list[int],
    ) -> None:
        role = guild.get_role(DUELLING_ROLE_ID)
        if role is None:
            return

        for user_id in participant_ids:
            member = guild.get_member(user_id)
            if member is None:
                continue
            try:
                await member.add_roles(role, reason="Joined duel")
            except discord.HTTPException:
                pass

    async def full_reset_channel(
        self,
        channel: discord.TextChannel,
        participant_ids: list[int] | None = None,
    ) -> None:
        if participant_ids:
            await self.remove_duelling_role(channel.guild, participant_ids)
        await self.purge_channel_messages(channel)
        await self.post_start_embed(channel)
        self.sessions.pop(channel.id, None)

    async def cancel_session(self, channel: discord.TextChannel) -> None:
        session = self.sessions.get(channel.id)
        if session is None:
            await self.full_reset_channel(channel)
            return

        session.cancelled = True
        if session.runner_task is not None:
            session.runner_task.cancel()
            try:
                await session.runner_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        participant_ids = list(session.participants)
        self.sessions.pop(channel.id, None)
        await self.full_reset_channel(channel, participant_ids)

    def choose_duel_questions(self) -> list[dict]:
        questions = list(self.quiz_repo.get_all())
        if not questions:
            raise ValueError("No duel questions are available.")

        count = min(QUESTIONS_PER_DUEL, len(questions))
        return random.sample(questions, count)

    def get_scaled_multi_house_points(self, player_count: int) -> dict[int, int]:
        scaled_points_by_player_count = {
            2: {1: 20, 2: 10, 3: 5},
            3: {1: 20, 2: 10, 3: 5},
            4: {1: 40, 2: 20, 3: 10},
            5: {1: 60, 2: 30, 3: 15},
            6: {1: 80, 2: 40, 3: 20},
            7: {1: 100, 2: 50, 3: 25},
        }
        return scaled_points_by_player_count.get(player_count, {1: 20, 2: 10, 3: 5})

    def calculate_rewards(self, session: DuelSession) -> tuple[dict[int, dict[str, int]], bool]:
        active_houses = {house for house in session.participant_houses.values() if house}
        single_house_lobby = len(active_houses) == 1

        player_count = len(session.participants)
        if single_house_lobby:
            points_by_rank = {1: 30, 2: 20, 3: 10}
        else:
            points_by_rank = self.get_scaled_multi_house_points(player_count)

        frogs_by_rank = {1: 3, 2: 2, 3: 1}

        score_groups: dict[int, list[int]] = {}
        for user_id in session.participants:
            score = session.scores.get(user_id, 0)
            score_groups.setdefault(score, []).append(user_id)

        rewards: dict[int, dict[str, int]] = {}
        rank = 1

        for score in sorted(score_groups.keys(), reverse=True):
            group = sorted(score_groups[score])
            if score <= 0:
                break
            if rank > 3:
                break

            if rank in points_by_rank:
                shared_points = points_by_rank[rank] // len(group)
                frogs = frogs_by_rank[rank]
                for user_id in group:
                    rewards[user_id] = {
                        "rank": rank,
                        "house_points": shared_points,
                        "frogs": frogs,
                    }

            rank += len(group)

        return rewards, single_house_lobby

    async def apply_rewards(
        self,
        guild: discord.Guild,
        session: DuelSession,
        rewards: dict[int, dict[str, int]],
    ) -> None:
        with self.database.connect() as conn:
            bot_state_repo = BotStateRepository(conn)
            contribution_repo = ContributionRepository(conn)
            inventory_repo = InventoryRepository(conn)
            user_repo = UserRepository(conn)
            house_points_service = HousePointsService(user_repo, contribution_repo)

            for user_id, reward in rewards.items():
                house_name = session.participant_houses.get(user_id)
                if not house_name:
                    continue
                user_repo.ensure_user(user_id)
                if reward["house_points"] > 0:
                    house_points_service.adjust_monthly_house_points(
                        user_id=user_id,
                        house_name=house_name,
                        points=reward["house_points"],
                    )
                if reward["frogs"] > 0:
                    inventory_repo.add_chocolate_frogs(user_id, reward["frogs"])

            board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
            await board_service.create_or_update_board(guild)

    async def ask_duel_questions(self, channel: discord.TextChannel, session: DuelSession) -> None:
        questions = self.choose_duel_questions()

        session.phase = "active"
        for index, question in enumerate(questions, start=1):
            if not self.is_session_current(session):
                return

            session.current_question = question
            session.current_question_number = index
            session.round_winner_id = None
            session.answer_locked = False
            session.round_event = asyncio.Event()

            await channel.send(embed=self.build_question_embed(question, index))

            try:
                await asyncio.wait_for(session.round_event.wait(), timeout=QUESTION_DURATION_SECONDS)
            except asyncio.TimeoutError:
                pass

            if not self.is_session_current(session):
                return

            session.current_question = None
            session.round_event = None
            session.answer_locked = True

            if session.round_winner_id is not None:
                await asyncio.sleep(CORRECT_ANSWER_DELAY_SECONDS)

        rewards, single_house_lobby = self.calculate_rewards(session)
        await self.apply_rewards(channel.guild, session, rewards)

        session.phase = "results"
        await channel.send(embed=self.build_results_embed(channel.guild, session, rewards, single_house_lobby))
        await asyncio.sleep(RESULTS_DURATION_SECONDS)

        if not self.is_session_current(session):
            return

        await self.full_reset_channel(channel, list(session.participants))

    async def run_lobby(self, channel: discord.TextChannel, session: DuelSession) -> None:
        try:
            try:
                await asyncio.wait_for(session.lobby_full_event.wait(), timeout=LOBBY_DURATION_SECONDS)
            except asyncio.TimeoutError:
                pass

            if not self.is_session_current(session):
                return

            if len(session.participants) < MIN_PLAYERS:
                await self.full_reset_channel(channel, list(session.participants))
                return

            session.phase = "countdown"
            await self.grant_duelling_role(channel.guild, list(session.participants))

            if session.lobby_message is not None:
                try:
                    await session.lobby_message.edit(
                        content=None,
                        embed=self.build_countdown_embed(channel, session),
                        view=None,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except discord.HTTPException:
                    pass

            await asyncio.sleep(COUNTDOWN_DURATION_SECONDS)
            if not self.is_session_current(session):
                return

            await self.purge_channel_messages(channel)
            await self.ask_duel_questions(channel, session)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.full_reset_channel(channel, list(session.participants))

    async def handle_start_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "This button can only be used inside a server text channel.",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        existing = self.sessions.get(channel.id)
        if existing is not None and existing.phase in {"lobby", "countdown", "active", "results"}:
            await interaction.response.send_message(
                "A duel is already running in this channel.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Only server members can start a duel.",
                ephemeral=True,
            )
            return

        role_ctx = resolve_member_roles(interaction.user)
        is_valid, error = validate_house_context(role_ctx)
        if not is_valid or not role_ctx.current_house:
            await interaction.response.send_message(
                error or "You need one valid house role to start a duel.",
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            embed=self.get_start_embed(),
            view=StartDuelView(self, disabled=True),
        )

        session = DuelSession(channel_id=channel.id)
        session.participants.append(interaction.user.id)
        session.participant_houses[interaction.user.id] = role_ctx.current_house
        session.scores[interaction.user.id] = 0
        self.sessions[channel.id] = session

        duel_role = interaction.guild.get_role(DUEL_PING_ROLE_ID)
        mention_text = duel_role.mention if duel_role else "A new duel lobby has opened!"

        lobby_message = await channel.send(
            content=mention_text if duel_role else None,
            embed=self.build_lobby_embed(channel, session),
            view=DuelLobbyView(self, channel.id),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        session.lobby_message = lobby_message
        session.runner_task = asyncio.create_task(self.run_lobby(channel, session))

    async def handle_join_button(self, interaction: discord.Interaction, channel_id: int) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button can only be used inside the server.",
                ephemeral=True,
            )
            return

        session = self.sessions.get(channel_id)
        if session is None or session.phase != "lobby":
            await interaction.response.send_message(
                "That lobby is no longer accepting players.",
                ephemeral=True,
            )
            return

        if interaction.user.id in session.participants:
            await interaction.response.send_message(
                "You already joined this duel.",
                ephemeral=True,
            )
            return

        if len(session.participants) >= MAX_PLAYERS:
            await interaction.response.send_message(
                "That duel lobby is already full.",
                ephemeral=True,
            )
            return

        role_ctx = resolve_member_roles(interaction.user)
        is_valid, error = validate_house_context(role_ctx)
        if not is_valid or not role_ctx.current_house:
            await interaction.response.send_message(
                error or "You need one valid house role.",
                ephemeral=True,
            )
            return

        session.participants.append(interaction.user.id)
        session.participant_houses[interaction.user.id] = role_ctx.current_house
        session.scores.setdefault(interaction.user.id, 0)

        if len(session.participants) >= MAX_PLAYERS:
            session.lobby_full_event.set()

        if session.lobby_message is not None:
            await interaction.response.edit_message(
                content=session.lobby_message.content,
                embed=self.build_lobby_embed(interaction.channel, session),
                view=DuelLobbyView(self, channel_id),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            session.lobby_message = await interaction.original_response()
        else:
            await interaction.response.send_message("Joined.", ephemeral=True)

    async def handle_leave_button(self, interaction: discord.Interaction, channel_id: int) -> None:
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button can only be used inside the server.",
                ephemeral=True,
            )
            return

        session = self.sessions.get(channel_id)
        if session is None or session.phase != "lobby":
            await interaction.response.send_message(
                "That lobby is no longer accepting changes.",
                ephemeral=True,
            )
            return

        if interaction.user.id not in session.participants:
            await interaction.response.send_message(
                "You are not in this duel lobby.",
                ephemeral=True,
            )
            return

        session.participants.remove(interaction.user.id)
        session.participant_houses.pop(interaction.user.id, None)
        session.scores.pop(interaction.user.id, None)

        if len(session.participants) < MAX_PLAYERS:
            session.lobby_full_event.clear()

        if session.lobby_message is not None:
            await interaction.response.edit_message(
                content=session.lobby_message.content,
                embed=self.build_lobby_embed(interaction.channel, session),
                view=DuelLobbyView(self, channel_id),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            session.lobby_message = await interaction.original_response()
        else:
            await interaction.response.send_message("Left.", ephemeral=True)

    @app_commands.command(
        name="setup_duel_channel",
        description="Admin: prepare a channel for dueling.",
    )
    @app_commands.describe(channel="The text channel to use for duels")
    async def setup_duel_channel(
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

        self.configured_channels.add(channel.id)
        await interaction.response.defer(ephemeral=True)
        await self.cancel_session(channel)
        await interaction.followup.send(
            f"Duel channel set up in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="stop_duel",
        description="Admin: stop the current duel or lobby and reset the channel.",
    )
    @app_commands.describe(channel="Optional duel channel to reset")
    async def stop_duel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
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

        target_channel = channel
        if target_channel is None:
            if not isinstance(interaction.channel, discord.TextChannel):
                await interaction.response.send_message(
                    "Please run this command inside a duel channel or specify one.",
                    ephemeral=True,
                )
                return
            target_channel = interaction.channel

        await interaction.response.defer(ephemeral=True)
        await self.cancel_session(target_channel)
        await interaction.followup.send(
            f"Duel stopped and reset in {target_channel.mention}.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        if not isinstance(message.author, discord.Member):
            return

        session = self.sessions.get(message.channel.id)
        if session is None or session.phase != "active":
            return

        if message.author.id not in session.participants:
            return

        if session.current_question is None or session.round_event is None:
            return

        if message.channel.id in self.processing_channels:
            return

        self.processing_channels.add(message.channel.id)
        try:
            if session.answer_locked:
                return

            is_correct = self.answer_service.is_correct_answer(
                session.current_question,
                message.content,
            )

            if not is_correct:
                try:
                    await message.add_reaction("❌")
                except discord.HTTPException:
                    pass
                return

            if session.answer_locked:
                return

            session.answer_locked = True
            session.round_winner_id = message.author.id
            session.scores[message.author.id] = session.scores.get(message.author.id, 0) + 1

            house_name = session.participant_houses.get(message.author.id)
            if house_name:
                with self.database.connect() as conn:
                    contribution_repo = ContributionRepository(conn)
                    user_repo = UserRepository(conn)
                    house_points_service = HousePointsService(user_repo, contribution_repo)
                    house_points_service.adjust_monthly_house_points(
                        user_id=message.author.id,
                        house_name=house_name,
                        points=2,
                    )

            try:
                await message.add_reaction("✅")
            except discord.HTTPException:
                pass

            if house_name:
                await message.channel.send(embed=self.build_round_win_embed(message.author, house_name))

            if session.round_event is not None:
                session.round_event.set()
        finally:
            self.processing_channels.discard(message.channel.id)