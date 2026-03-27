import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks

from db.database import Database
from domain.constants import BIRTHDAY_ROLE_ID, ZODIAC_ROLE_IDS
from repositories.bot_state_repository import BotStateRepository
from repositories.birthday_repository import BirthdayRepository
from repositories.owned_item_repository import OwnedItemRepository
from repositories.user_repository import UserRepository
from services.birthday_service import BirthdayService


class BirthdayGiftView(discord.ui.View):
    def __init__(self, cog: "BirthdayCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Give Present",
        emoji="🎁",
        style=discord.ButtonStyle.primary,
        custom_id="birthday_gift_button",
    )
    async def give_present(
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
                "This birthday message is invalid.",
                ephemeral=True,
            )
            return

        with self.cog.database.connect() as conn:
            birthday_repo = BirthdayRepository(conn)
            owned_item_repo = OwnedItemRepository(conn)
            user_repo = UserRepository(conn)

            announcement = birthday_repo.get_announcement_by_message_id(interaction.message.id)
            if announcement is None:
                await interaction.response.send_message(
                    "This birthday gift message is no longer active.",
                    ephemeral=True,
                )
                return

            birthday_user_id = int(announcement["birthday_user_id"])

            if interaction.user.id == birthday_user_id:
                await interaction.response.send_message(
                    "You cannot give a birthday present to yourself.",
                    ephemeral=True,
                )
                return

            if birthday_repo.has_user_claimed_gift(interaction.message.id, interaction.user.id):
                await interaction.response.send_message(
                    "You already gave a present for this birthday message.",
                    ephemeral=True,
                )
                return

            user_repo.ensure_user(birthday_user_id)

            gift = self.cog.birthday_service.roll_birthday_gift()
            owned_item_repo.add_quantity(
                birthday_user_id,
                gift["item_key"],
                gift["quantity"],
            )
            birthday_repo.record_gift_claim(interaction.message.id, interaction.user.id)

        birthday_member = interaction.guild.get_member(birthday_user_id)
        birthday_mention = birthday_member.mention if birthday_member else f"<@{birthday_user_id}>"

        embed = discord.Embed(
            title="Birthday Present Delivered!",
            description=(
                f"{birthday_mention} received **{gift['label']}** "
                f"from {interaction.user.mention}."
            ),
            color=0xF1C40F,
        )

        await interaction.response.send_message(
            "Your birthday present has been delivered!",
            ephemeral=True,
        )
        await interaction.channel.send(embed=embed)


class BirthdayCog(commands.Cog):
    ANNOUNCEMENT_CHANNEL_KEY = "birthday_announcement_channel_id"

    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
        self.birthday_service = BirthdayService()

    async def cog_load(self) -> None:
        self.bot.add_view(BirthdayGiftView(self))
        if not self.birthday_loop.is_running():
            self.birthday_loop.start()

    async def cog_unload(self) -> None:
        if self.birthday_loop.is_running():
            self.birthday_loop.cancel()

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )

    def build_birthday_embed(self, member: discord.Member) -> discord.Embed:
        embed = discord.Embed(
            title="🎉 Birthday Celebration!",
            description=f"@everyone Today is **{member.mention}**'s birthday! 🎂",
            color=0xFF69B4,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="Celebrate",
            value="Click the button below to give a birthday present.",
            inline=False,
        )
        return embed

    async def sync_birthday_roles_and_announcements(self) -> None:
        today_day, today_month, today_str = self.birthday_service.today_parts()

        for guild in self.bot.guilds:
            with self.database.connect() as conn:
                user_repo = UserRepository(conn)
                bot_state_repo = BotStateRepository(conn)
                birthday_repo = BirthdayRepository(conn)

                birthday_user_ids = set(user_repo.get_users_with_birthday(today_day, today_month))
                announcement_channel_id = bot_state_repo.get_value(self.ANNOUNCEMENT_CHANNEL_KEY)

            birthday_role = guild.get_role(BIRTHDAY_ROLE_ID)
            if birthday_role is not None:
                for member in guild.members:
                    has_birthday_today = member.id in birthday_user_ids
                    has_role = birthday_role in member.roles

                    if has_birthday_today and not has_role:
                        try:
                            await member.add_roles(birthday_role, reason="Birthday role for today's birthday")
                        except discord.HTTPException:
                            pass
                    elif not has_birthday_today and has_role:
                        try:
                            await member.remove_roles(birthday_role, reason="Birthday role removed after birthday")
                        except discord.HTTPException:
                            pass

            if announcement_channel_id is None:
                continue

            channel = guild.get_channel(int(announcement_channel_id))
            if not isinstance(channel, discord.TextChannel):
                continue

            for user_id in birthday_user_ids:
                member = guild.get_member(user_id)
                if member is None:
                    continue

                with self.database.connect() as conn:
                    birthday_repo = BirthdayRepository(conn)
                    already_announced = birthday_repo.has_announcement_for_user_date(user_id, today_str)

                if already_announced:
                    continue

                embed = self.build_birthday_embed(member)
                view = BirthdayGiftView(self)
                message = await channel.send(
                    content="@everyone",
                    embed=embed,
                    view=view,
                )

                with self.database.connect() as conn:
                    birthday_repo = BirthdayRepository(conn)
                    birthday_repo.create_announcement(
                        message_id=message.id,
                        channel_id=channel.id,
                        birthday_user_id=user_id,
                        announcement_date=today_str,
                    )

    @tasks.loop(minutes=5)
    async def birthday_loop(self) -> None:
        await self.sync_birthday_roles_and_announcements()

    @birthday_loop.before_loop
    async def before_birthday_loop(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="setup_birthday_announcement",
        description="Admin: set the birthday announcement channel.",
    )
    @app_commands.describe(channel="The channel where birthday announcements should be posted")
    async def setup_birthday_announcement(
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
            bot_state_repo.set_value(self.ANNOUNCEMENT_CHANNEL_KEY, str(channel.id))

        await interaction.response.send_message(
            f"Birthday announcement channel set to {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="birthday_reset",
        description="Admin: reset a member's birthday so they can set it again.",
    )
    @app_commands.describe(member="The member whose birthday should be reset")
    async def birthday_reset(
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

        zodiac_role_ids = set(ZODIAC_ROLE_IDS.values())
        roles_to_remove = [role for role in member.roles if role.id in zodiac_role_ids or role.id == BIRTHDAY_ROLE_ID]

        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Birthday reset by admin")
            except discord.HTTPException:
                pass

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            user_repo.ensure_user(member.id)
            user_repo.clear_birthday(member.id)

        await interaction.response.send_message(
            f"{member.mention}'s birthday has been reset.",
            ephemeral=True,
        )