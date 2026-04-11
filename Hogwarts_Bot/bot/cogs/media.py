import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta

from db.database import Database
from repositories.media_repository import MediaRepository
from repositories.user_repository import UserRepository
from repositories.contribution_repository import ContributionRepository
from repositories.bot_state_repository import BotStateRepository
from services.media_service import MediaService
from services.house_points_service import HousePointsService
from services.house_cup_board_service import HouseCupBoardService
from bot.cogs.profile import resolve_member_roles, validate_house_context


HEART_EMOJI = "❤️"


class MediaCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
        self.media_service = MediaService()
        self.media_channel_ids: set[int] = set()

    async def cog_load(self) -> None:
        with self.database.connect() as conn:
            media_repo = MediaRepository(conn)
            self.media_channel_ids = media_repo.list_media_channel_ids()

        if not self.media_close_loop.is_running():
            self.media_close_loop.start()

    async def cog_unload(self) -> None:
        if self.media_close_loop.is_running():
            self.media_close_loop.cancel()

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )

    @app_commands.command(
        name="setup_media_channel",
        description="Admin: enable media voting in a channel.",
    )
    @app_commands.describe(channel="The media channel to enable")
    async def setup_media_channel(
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
            media_repo = MediaRepository(conn)
            media_repo.add_media_channel(channel.id)

        self.media_channel_ids.add(channel.id)

        await interaction.response.send_message(
            f"Media voting has been enabled in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="remove_media_channel",
        description="Admin: disable media voting in a channel.",
    )
    @app_commands.describe(channel="The media channel to disable")
    async def remove_media_channel(
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
            media_repo = MediaRepository(conn)
            media_repo.remove_media_channel(channel.id)

        self.media_channel_ids.discard(channel.id)

        await interaction.response.send_message(
            f"Media voting has been disabled in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="media_reset",
        description="Admin: reset a user's active media post state.",
    )
    @app_commands.describe(member="The member whose media state should be reset")
    async def media_reset(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            media_repo = MediaRepository(conn)
            closed_count = media_repo.force_close_all_open_posts_for_user(member.id)

        await interaction.response.send_message(
            f"{member.mention}'s media state has been reset.\n"
            f"Closed active media posts: **{closed_count}**",
            ephemeral=True,
        )

    async def remove_user_reaction_if_possible(
        self,
        channel: discord.TextChannel,
        message_id: int,
        user_id: int,
    ) -> None:
        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            return

        member = channel.guild.get_member(user_id)
        if member is None:
            return

        try:
            await message.remove_reaction(HEART_EMOJI, member)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        if not isinstance(message.author, discord.Member):
            return

        if message.channel.id not in self.media_channel_ids:
            return

        if not message.attachments:
            return

        valid_attachment = None
        for attachment in message.attachments:
            if self.media_service.is_supported_media(attachment.filename, attachment.content_type):
                valid_attachment = attachment
                break

        if valid_attachment is None:
            return

        role_ctx = resolve_member_roles(message.author)
        is_valid, _ = validate_house_context(role_ctx)
        if not is_valid:
            return

        with self.database.connect() as conn:
            media_repo = MediaRepository(conn)
            existing_open_post = media_repo.get_open_post_for_user_in_channel(
                message.author.id,
                message.channel.id,
            )

            # Allow extra uploads, but only one active voteable image per user per channel.
            if existing_open_post is not None:
                return

            media_repo.create_media_post(
                message_id=message.id,
                channel_id=message.channel.id,
                author_user_id=message.author.id,
                closes_at=self.media_service.calculate_closes_at_iso(),
            )

        try:
            await message.add_reaction(HEART_EMOJI)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None:
            return

        if str(payload.emoji) != HEART_EMOJI:
            return

        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        channel = guild.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            return

        with self.database.connect() as conn:
            media_repo = MediaRepository(conn)
            media_post = media_repo.get_media_post(payload.message_id)

            if media_post is None:
                return

            media_service = MediaService()
            if media_service.is_post_closed(
                media_post["closes_at"],
                bool(media_post["is_closed"]),
            ):
                await self.remove_user_reaction_if_possible(channel, payload.message_id, payload.user_id)
                return

            author_user_id = int(media_post["author_user_id"])

            if payload.user_id == author_user_id:
                await self.remove_user_reaction_if_possible(channel, payload.message_id, payload.user_id)
                try:
                    await channel.send(
                        f"<@{payload.user_id}> you cannot support your own media post.",
                        delete_after=8,
                    )
                except discord.HTTPException:
                    pass
                return

            if media_repo.has_user_voted(payload.message_id, payload.user_id):
                return

            since_iso = media_service.calculate_vote_window_start_iso()
            recent_vote_count = media_repo.get_recent_vote_count(payload.user_id, since_iso)
            can_vote, _ = media_service.can_vote_in_window(recent_vote_count)

            if not can_vote:
                await self.remove_user_reaction_if_possible(channel, payload.message_id, payload.user_id)

                oldest_recent_vote_time = media_repo.get_oldest_recent_vote_time(payload.user_id, since_iso)
                minutes_left_text = "some time"

                if oldest_recent_vote_time:
                    oldest_dt = datetime.fromisoformat(oldest_recent_vote_time)
                    retry_dt = oldest_dt + timedelta(minutes=media_service.VOTE_WINDOW_MINUTES)
                    remaining = retry_dt - media_service.now()
                    remaining_minutes = max(1, int(remaining.total_seconds() // 60))
                    minutes_left_text = f"about **{remaining_minutes} minute(s)**"

                try:
                    await channel.send(
                        f"<@{payload.user_id}> you can only support **3** media posts per hour. "
                        f"Please wait {minutes_left_text} before supporting another post.",
                        delete_after=8,
                    )
                except discord.HTTPException:
                    pass
                return

            now_iso = media_service.now_iso()
            media_repo.add_vote(payload.message_id, payload.user_id, now_iso)

    @tasks.loop(minutes=1)
    async def media_close_loop(self) -> None:
        current_time_iso = self.media_service.now_iso()

        with self.database.connect() as conn:
            media_repo = MediaRepository(conn)
            expired_posts = media_repo.get_expired_open_posts(current_time_iso)

        for post in expired_posts:
            guild = None
            channel = self.bot.get_channel(int(post["channel_id"]))
            if isinstance(channel, discord.TextChannel):
                guild = channel.guild

            author_user_id = int(post["author_user_id"])
            vote_count = 0
            total_points = 0
            rewarded = False

            with self.database.connect() as conn:
                media_repo = MediaRepository(conn)
                vote_count = media_repo.get_vote_count(int(post["message_id"]))
                total_points = vote_count * int(post["reward_points_per_vote"])

                if guild is not None:
                    member = guild.get_member(author_user_id)
                else:
                    member = None

                if member is not None:
                    role_ctx = resolve_member_roles(member)
                    is_valid, _ = validate_house_context(role_ctx)

                    if is_valid and role_ctx.current_house and total_points > 0:
                        user_repo = UserRepository(conn)
                        contribution_repo = ContributionRepository(conn)
                        bot_state_repo = BotStateRepository(conn)

                        house_points_service = HousePointsService(user_repo, contribution_repo)
                        house_points_service.adjust_monthly_house_points(
                            user_id=author_user_id,
                            house_name=role_ctx.current_house,
                            points=total_points,
                        )

                        board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
                        await board_service.create_or_update_board(guild)
                        rewarded = True

                media_repo.close_media_post(
                    int(post["message_id"]),
                    total_points if rewarded else 0,
                )

            if isinstance(channel, discord.TextChannel):
                embed = discord.Embed(
                    title="Media Support Closed",
                    description=(
                        f"<@{author_user_id}> received **{vote_count}** support vote(s).\n"
                        f"House Points awarded: **{total_points if rewarded else 0}**"
                    ),
                    color=0xFF6B81,
                )
                await channel.send(embed=embed)

    @media_close_loop.before_loop
    async def before_media_close_loop(self) -> None:
        await self.bot.wait_until_ready()