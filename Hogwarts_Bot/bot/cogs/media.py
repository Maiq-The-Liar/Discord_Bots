import discord
from discord import app_commands
from discord.ext import commands, tasks

from db.database import Database
from repositories.media_repository import MediaRepository
from repositories.user_repository import UserRepository
from repositories.contribution_repository import ContributionRepository
from repositories.bot_state_repository import BotStateRepository
from services.media_service import MediaService
from services.house_points_service import HousePointsService
from services.house_cup_board_service import HouseCupBoardService
from domain.constants import HOUSE_COLORS
from bot.cogs.profile import resolve_member_roles, validate_house_context


class MediaVoteView(discord.ui.View):
    def __init__(self, cog: "MediaCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Give Support",
        emoji="❤️",
        style=discord.ButtonStyle.primary,
        custom_id="media_vote_button",
    )
    async def vote_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button can only be used inside the server.",
                ephemeral=True,
            )
            return

        if interaction.message is None:
            await interaction.response.send_message(
                "This media post is invalid.",
                ephemeral=True,
            )
            return

        with self.cog.database.connect() as conn:
            media_repo = MediaRepository(conn)
            media_service = MediaService()
            media_post = media_repo.get_media_post(interaction.message.id)

            if media_post is None:
                await interaction.response.send_message(
                    "This media post is not active.",
                    ephemeral=True,
                )
                return

            if media_service.is_post_closed(
                media_post["closes_at"],
                bool(media_post["is_closed"]),
            ):
                await interaction.response.send_message(
                    "This support window has already closed.",
                    ephemeral=True,
                )
                return

            author_user_id = int(media_post["author_user_id"])

            if interaction.user.id == author_user_id:
                await interaction.response.send_message(
                    "You cannot support your own media post.",
                    ephemeral=True,
                )
                return

            if media_repo.has_user_voted(interaction.message.id, interaction.user.id):
                await interaction.response.send_message(
                    "You already supported this media post.",
                    ephemeral=True,
                )
                return

            last_vote_at = media_repo.get_last_vote_time(interaction.user.id)
            can_vote, remaining_minutes = media_service.can_vote_again(last_vote_at)
            if not can_vote:
                await interaction.response.send_message(
                    f"You must wait about **{remaining_minutes} minute(s)** before supporting another post.",
                    ephemeral=True,
                )
                return

            now_iso = media_service.now_iso()
            media_repo.add_vote(interaction.message.id, interaction.user.id, now_iso)
            media_repo.set_vote_cooldown(interaction.user.id, now_iso)

            votes = media_repo.get_vote_count(interaction.message.id)

        await interaction.response.send_message(
            f"You supported this post. Current supports: **{votes}** ❤️",
            ephemeral=True,
        )


class MediaCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
        self.media_service = MediaService()

    async def cog_load(self) -> None:
        self.bot.add_view(MediaVoteView(self))
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

    def build_media_embed(
        self,
        member: discord.Member,
        attachment_filename: str,
        color: int,
        caption: str | None = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            description=caption or "",
            color=color,
        )
        embed.set_author(
            name=member.display_name,
            icon_url=member.display_avatar.url,
        )
        embed.set_image(url=f"attachment://{attachment_filename}")
        embed.set_footer(text="React with ❤️ below so this user can earn House Points.")
        return embed

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

        await interaction.response.send_message(
            f"Media voting has been disabled in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="media_reset",
        description="Admin: reset a user's media cooldown and active media post.",
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
            media_repo.clear_vote_cooldown(member.id)
            closed_message_id = media_repo.force_close_open_post_for_user(member.id)

        if closed_message_id is None:
            await interaction.response.send_message(
                f"{member.mention}'s media cooldown has been reset. They had no active media post.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"{member.mention}'s media cooldown has been reset and their active media post was closed.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        if not isinstance(message.author, discord.Member):
            return

        with self.database.connect() as conn:
            media_repo = MediaRepository(conn)
            if not media_repo.is_media_channel(message.channel.id):
                return

        if not message.attachments:
            return

        valid_attachment = None
        for attachment in message.attachments:
            if self.media_service.is_supported_image(attachment.filename, attachment.content_type):
                valid_attachment = attachment
                break

        # Ignore everything that is not png/jpg/jpeg
        if valid_attachment is None:
            return

        # Only now block if the user already has an active media post
        with self.database.connect() as conn:
            media_repo = MediaRepository(conn)
            existing_open_post = media_repo.get_open_post_for_user(message.author.id)
            if existing_open_post is not None:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass

                warning_embed = discord.Embed(
                    title="Media Post Already Active",
                    description=(
                        f"{message.author.mention}, you already have an active media post.\n"
                        f"Please wait until it closes before posting another one."
                    ),
                    color=0xE67E22,
                )
                await message.channel.send(embed=warning_embed, delete_after=10)
                return

        role_ctx = resolve_member_roles(message.author)
        is_valid, _ = validate_house_context(role_ctx)
        if not is_valid:
            return

        try:
            file = await valid_attachment.to_file()
        except discord.HTTPException:
            return

        color = HOUSE_COLORS.get(role_ctx.current_house or "", 0x2F3136)
        embed = self.build_media_embed(
            member=message.author,
            attachment_filename=file.filename,
            color=color,
            caption=message.content.strip() or None,
        )

        sent_message = await message.channel.send(
            embed=embed,
            file=file,
            view=MediaVoteView(self),
        )

        with self.database.connect() as conn:
            media_repo = MediaRepository(conn)
            media_repo.create_media_post(
                message_id=sent_message.id,
                channel_id=message.channel.id,
                author_user_id=message.author.id,
                closes_at=self.media_service.calculate_closes_at_iso(),
            )

        try:
            await message.delete()
        except discord.HTTPException:
            pass

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