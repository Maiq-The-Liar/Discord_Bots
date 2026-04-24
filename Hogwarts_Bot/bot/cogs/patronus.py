from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from repositories.user_repository import UserRepository
from repositories.owned_item_repository import OwnedItemRepository
from repositories.patronus_repository import PatronusRepository
from services.patronus_service import PatronusService
from domain.constants import HOUSE_COLORS
from bot.cogs.profile import resolve_member_roles, validate_house_context
from bot.permissions import is_admin_or_head_student


class PatronusCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

        base_dir = Path(__file__).resolve().parents[2]
        self.patronus_repo = PatronusRepository(
            str(base_dir / "resources" / "patronus.json")
        )

    def build_patronus_embed(
        self,
        member: discord.Member,
        patronus: dict,
        color: int,
        title_prefix: str = "",
    ) -> discord.Embed:
        title = f"{title_prefix}{member.display_name}'s Patronus"
        embed = discord.Embed(
            title=title,
            description=(
                f"**Name:** {patronus['name']}\n"
                f"**Rarity:** {patronus['rarity'].capitalize()}"
            ),
            color=color,
        )
        embed.set_image(url=patronus["gif_url"])
        return embed

    @app_commands.command(name="patronus", description="Show your Patronus.")
    async def patronus(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        role_ctx = resolve_member_roles(interaction.user)
        is_valid, error = validate_house_context(role_ctx)
        if not is_valid:
            await interaction.response.send_message(error, ephemeral=True)
            return

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            owned_item_repo = OwnedItemRepository(conn)
            service = PatronusService(user_repo, owned_item_repo, self.patronus_repo)
            patronus = service.get_user_patronus(interaction.user.id)

        if patronus is None:
            await interaction.response.send_message(
                "You do not yet have a Patronus.",
                ephemeral=True,
            )
            return

        color = HOUSE_COLORS.get(role_ctx.current_house or "", 0x2F3136)
        embed = self.build_patronus_embed(interaction.user, patronus, color)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="discoverpatronus",
        description="Use a Patronus Spell Book to discover or change your Patronus.",
    )
    async def discoverpatronus(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        role_ctx = resolve_member_roles(interaction.user)
        is_valid, error = validate_house_context(role_ctx)
        if not is_valid:
            await interaction.response.send_message(error, ephemeral=True)
            return

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            owned_item_repo = OwnedItemRepository(conn)
            service = PatronusService(user_repo, owned_item_repo, self.patronus_repo)

            try:
                patronus = service.discover_patronus(interaction.user.id)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

            remaining_books = owned_item_repo.get_quantity(
                interaction.user.id,
                "patronus_spell_book",
            )

        color = HOUSE_COLORS.get(role_ctx.current_house or "", 0x2F3136)
        embed = self.build_patronus_embed(
            interaction.user,
            patronus,
            color,
            title_prefix="Discovered: ",
        )
        embed.add_field(
            name="Patronus Spell Books Remaining",
            value=str(remaining_books),
            inline=True,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
    name="assign_patronus",
    description="Admin/Head Student: Assign a specific Patronus to a user by ID.",
    )
    
    @app_commands.describe(
        member="The member to assign the Patronus to",
        patronus_id="The Patronus ID from the JSON file",
    )
    async def assign_patronus(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        patronus_id: int,
    ) -> None:
        # 🔒 Admin or Head Student check
        if not is_admin_or_head_student(interaction.user):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        # Validate Patronus ID
        patronus = self.patronus_repo.get_by_id(patronus_id)
        if patronus is None:
            await interaction.response.send_message(
                f"Invalid Patronus ID: `{patronus_id}`",
                ephemeral=True,
            )
            return

        # Validate house context
        role_ctx = resolve_member_roles(member)
        is_valid, error = validate_house_context(role_ctx)

        if not is_valid:
            await interaction.response.send_message(
                f"Cannot assign Patronus: {error}",
                ephemeral=True,
            )
            return

        # Assign Patronus
        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            user_repo.ensure_user(member.id)
            user_repo.set_patronus_id(member.id, patronus_id)

        color = HOUSE_COLORS.get(role_ctx.current_house or "", 0x2F3136)

        embed = self.build_patronus_embed(
            member,
            patronus,
            color,
            title_prefix="Assigned: ",
        )

        embed.add_field(
            name="Admin Action",
            value=f"Assigned by {interaction.user.mention}",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)