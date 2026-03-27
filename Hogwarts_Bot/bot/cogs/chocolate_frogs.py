from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from repositories.user_repository import UserRepository
from repositories.owned_item_repository import OwnedItemRepository
from repositories.frog_collection_repository import FrogCollectionRepository
from repositories.chocolate_frog_repository import ChocolateFrogRepository
from services.chocolate_frog_service import ChocolateFrogService
from domain.constants import HOUSE_COLORS, ARROW_LEFT_EMOJI, ARROW_RIGHT_EMOJI, CLOSE_EMOJI
from bot.cogs.profile import resolve_member_roles, validate_house_context


class FrogAlbumView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        entries: list[dict],
        color: int,
        member: discord.Member,
    ):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.entries = entries
        self.color = color
        self.member = member
        self.index = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This album belongs to someone else.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(self) -> discord.Embed:
        entry = self.entries[self.index]
        total_cards = len(self.entries)

        embed = discord.Embed(
            title=f"#{entry['id']} — {entry['name']}",
            description=entry["description"],
            color=self.color,
        )

        embed.set_author(
            name=f"{self.member.display_name}'s Chocolate Frog Album"
        )

        embed.set_image(url=entry["url"])

        progress = f"{self.index + 1}/{total_cards}"

        embed.add_field(
            name="Collection Progress",
            value=progress,
            inline=True,
        )

        embed.add_field(
            name="Copies Owned",
            value=str(entry["quantity"]),
            inline=True,
        )

        embed.add_field(
            name="Card ID",
            value=f"#{entry['id']}",
            inline=True,
        )

        embed.set_footer(
            text="Use buttons to browse your collection"
        )

        return embed

    async def refresh(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self,
        )

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str(ARROW_LEFT_EMOJI),
        style=discord.ButtonStyle.secondary,
    )
    async def prev(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.index = (self.index - 1) % len(self.entries)
        await self.refresh(interaction)

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str(ARROW_RIGHT_EMOJI),
        style=discord.ButtonStyle.secondary,
    )
    async def next(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.index = (self.index + 1) % len(self.entries)
        await self.refresh(interaction)

    @discord.ui.button(
        emoji=CLOSE_EMOJI,
        style=discord.ButtonStyle.danger,
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="Album closed.",
            embeds=[],
            view=self,
        )


class ChocolateFrogCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

        base_dir = Path(__file__).resolve().parents[2]
        self.frog_repo = ChocolateFrogRepository(
            str(base_dir / "resources" / "chocolate_frogs.json")
        )

    def build_card_embed(
        self,
        member: discord.Member,
        card: dict,
        color: int,
        title_prefix: str = "",
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"{title_prefix}{card['name']}",
            description=card["description"],
            color=color,
        )
        embed.set_author(name=f"{member.display_name}'s Chocolate Frog Card")
        embed.set_image(url=card["url"])
        return embed

    @app_commands.command(
        name="open_chocolate_frog",
        description="Open one Chocolate Frog and discover a card.",
    )
    async def open_chocolate_frog(
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
            frog_collection_repo = FrogCollectionRepository(conn)
            service = ChocolateFrogService(
                user_repo=user_repo,
                owned_item_repo=owned_item_repo,
                frog_collection_repo=frog_collection_repo,
                frog_repo=self.frog_repo,
            )

            try:
                result = service.open_frog(interaction.user.id)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

        color = HOUSE_COLORS.get(role_ctx.current_house or "", 0x2F3136)
        title_prefix = "✨ New Card Discovered: " if result["is_new"] else "Duplicate Card: "
        embed = self.build_card_embed(
            interaction.user,
            result["card"],
            color,
            title_prefix=title_prefix,
        )
        embed.add_field(
            name="Result",
            value="New card!" if result["is_new"] else "You already had this card.",
            inline=True,
        )
        embed.add_field(
            name="Copies Owned",
            value=str(result["new_card_quantity"]),
            inline=True,
        )
        embed.add_field(
            name="Chocolate Frogs Remaining",
            value=str(result["remaining_frogs"]),
            inline=True,
        )
        embed.add_field(
            name="Album Progress",
            value=f"{result['unique_cards']} / {result['total_cards']}",
            inline=True,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="frog_album",
        description="Browse a Chocolate Frog collection.",
    )
    @app_commands.describe(member="The member whose album you want to view")
    async def frog_album(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        target = member or interaction.user

        if not isinstance(target, discord.Member):
            await interaction.response.send_message(
                "Invalid user.",
                ephemeral=True,
            )
            return

        role_ctx = resolve_member_roles(target)
        is_valid, error = validate_house_context(role_ctx)
        if not is_valid:
            await interaction.response.send_message(error, ephemeral=True)
            return

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            owned_item_repo = OwnedItemRepository(conn)
            frog_collection_repo = FrogCollectionRepository(conn)

            service = ChocolateFrogService(
                user_repo=user_repo,
                owned_item_repo=owned_item_repo,
                frog_collection_repo=frog_collection_repo,
                frog_repo=self.frog_repo,
            )

            album = service.get_album_page(target.id, page=1, page_size=999)

        if not album["entries"]:
            await interaction.response.send_message(
                "No cards collected yet.",
                ephemeral=True,
            )
            return

        color = HOUSE_COLORS.get(role_ctx.current_house or "", 0x2F3136)

        view = FrogAlbumView(
            owner_id=interaction.user.id,
            entries=album["entries"],
            color=color,
            member=target,
        )

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
        )

    @app_commands.command(
        name="give_card",
        description="Give one owned Chocolate Frog card to another user.",
    )
    @app_commands.describe(
        member="The member who should receive the card",
        card_id="The ID of the Chocolate Frog card to give",
    )
    async def give_card(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        card_id: int,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "You cannot give a card to yourself.",
                ephemeral=True,
            )
            return

        giver_role_ctx = resolve_member_roles(interaction.user)
        giver_valid, giver_error = validate_house_context(giver_role_ctx)
        if not giver_valid:
            await interaction.response.send_message(giver_error, ephemeral=True)
            return

        receiver_role_ctx = resolve_member_roles(member)
        receiver_valid, receiver_error = validate_house_context(receiver_role_ctx)
        if not receiver_valid:
            await interaction.response.send_message(
                f"Cannot give card: {receiver_error}",
                ephemeral=True,
            )
            return

        card = self.frog_repo.get_by_id(card_id)
        if card is None:
            await interaction.response.send_message(
                f"Invalid card ID: **{card_id}**.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            frog_collection_repo = FrogCollectionRepository(conn)

            user_repo.ensure_user(interaction.user.id)
            user_repo.ensure_user(member.id)

            giver_before = frog_collection_repo.get_card_quantity(interaction.user.id, card_id)
            if giver_before <= 0:
                await interaction.response.send_message(
                    "You do not own this card.",
                    ephemeral=True,
                )
                return

            receiver_before = frog_collection_repo.get_card_quantity(member.id, card_id)

            removed = frog_collection_repo.remove_card(interaction.user.id, card_id, 1)
            if not removed:
                await interaction.response.send_message(
                    "You do not own this card.",
                    ephemeral=True,
                )
                return

            frog_collection_repo.add_card(member.id, card_id, 1)

            giver_after = frog_collection_repo.get_card_quantity(interaction.user.id, card_id)
            receiver_after = frog_collection_repo.get_card_quantity(member.id, card_id)

            giver_unique = frog_collection_repo.get_unique_count(interaction.user.id)
            receiver_unique = frog_collection_repo.get_unique_count(member.id)
            total_cards = self.frog_repo.get_total_count()

        color = HOUSE_COLORS.get(giver_role_ctx.current_house or "", 0x2F3136)
        embed = discord.Embed(
            title="Chocolate Frog Card Gifted",
            description=(
                f"{interaction.user.mention} gave **#{card_id} — {card['name']}** to {member.mention}."
            ),
            color=color,
        )
        embed.set_image(url=card["url"])
        embed.add_field(
            name="Your Copies Left",
            value=str(giver_after),
            inline=True,
        )
        embed.add_field(
            name=f"{member.display_name}'s Copies",
            value=str(receiver_after),
            inline=True,
        )
        embed.add_field(
            name="Card ID",
            value=f"#{card_id}",
            inline=True,
        )
        embed.add_field(
            name="Your Album Progress",
            value=f"{giver_unique} / {total_cards}",
            inline=True,
        )
        embed.add_field(
            name=f"{member.display_name}'s Album Progress",
            value=f"{receiver_unique} / {total_cards}",
            inline=True,
        )

        await interaction.response.send_message(embed=embed)