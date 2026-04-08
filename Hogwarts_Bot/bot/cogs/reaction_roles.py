import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from repositories.guild_role_repository import GuildRoleRepository
from repositories.reaction_role_repository import ReactionRoleRepository
from services.reaction_role_service import ReactionRoleService


class ReactionRolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )

    @app_commands.command(
        name="setup_roles",
        description="Admin: clear a channel and print all reaction role menus there.",
    )
    @app_commands.describe(channel="The channel where the reaction role menus should live")
    async def setup_roles(
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

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            with self.database.connect() as conn:
                guild_role_repo = GuildRoleRepository(conn)
                reaction_repo = ReactionRoleRepository(conn)
                service = ReactionRoleService(self.bot, reaction_repo, guild_role_repo)
                result = await service.setup_channel(interaction.guild, channel)
        except discord.Forbidden:
            await interaction.followup.send(
                "I could not set up the role channel. Make sure I can manage roles, read the channel, manage messages, attach files, and add reactions.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as exc:
            await interaction.followup.send(
                f"Setup failed: {exc}",
                ephemeral=True,
            )
            return
        except FileNotFoundError as exc:
            await interaction.followup.send(
                f"Banner image missing: {exc}",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"Reaction role channel set to {channel.mention}.\n"
            f"Deleted messages: **{result['deleted_messages']}**\n"
            f"Posted menus: **{result['posted_messages']}**",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None:
            return

        with self.database.connect() as conn:
            guild_role_repo = GuildRoleRepository(conn)
            reaction_repo = ReactionRoleRepository(conn)
            service = ReactionRoleService(self.bot, reaction_repo, guild_role_repo)
            await service.handle_reaction_add(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None:
            return

        with self.database.connect() as conn:
            guild_role_repo = GuildRoleRepository(conn)
            reaction_repo = ReactionRoleRepository(conn)
            service = ReactionRoleService(self.bot, reaction_repo, guild_role_repo)
            await service.handle_reaction_remove(payload)