import os
import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from repositories.user_repository import UserRepository
from repositories.owned_item_repository import OwnedItemRepository
from services.shop_service import ShopService
from domain.constants import (
    SHOP_ITEMS,
    GALLEONS_ICON,
    HOUSE_COLORS,
    ARROW_LEFT_EMOJI,
    ARROW_RIGHT_EMOJI,
    BUY_EMOJI,
    CLOSE_EMOJI,
)
from bot.cogs.profile import resolve_member_roles, validate_house_context


def cycle_index(current_index: int, step: int, total: int) -> int:
    return (current_index + step) % total


class ShopView(discord.ui.View):
    def __init__(
        self,
        database: Database,
        owner_id: int,
        house_color: int,
        start_index: int = 0,
    ):
        super().__init__(timeout=300)
        self.database = database
        self.owner_id = owner_id
        self.house_color = house_color
        self.current_index = start_index

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This shop session belongs to someone else.",
                ephemeral=True,
            )
            return False
        return True

    def build_embeds(self) -> list[discord.Embed]:
        item = SHOP_ITEMS[self.current_index]

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            owned_item_repo = OwnedItemRepository(conn)
            shop_service = ShopService(user_repo, owned_item_repo)
            state = shop_service.get_item_state(self.owner_id, item["key"])

        image_filename = os.path.basename(item["image_path"])

        image_embed = discord.Embed(color=self.house_color)
        image_embed.set_image(url=f"attachment://{image_filename}")

        details_embed = discord.Embed(
            title=item["display_name"],
            description=item["description"],
            color=self.house_color,
        )

        details_embed.add_field(
            name="Price",
            value=f"{GALLEONS_ICON} {item['price']}",
            inline=True,
        )
        details_embed.add_field(
            name="Owned",
            value=str(state["owned_quantity"]),
            inline=True,
        )
        details_embed.add_field(
            name="Type",
            value=item["type"].capitalize(),
            inline=True,
        )
        details_embed.add_field(
            name="Balance",
            value=f"{GALLEONS_ICON} {state['balance']}",
            inline=True,
        )

        status_text = "Available to purchase" if state["can_buy"] else (state["reason"] or "Unavailable")

        details_embed.add_field(
            name="Status",
            value=status_text,
            inline=True,
        )
        details_embed.add_field(
            name="Item",
            value=f"{self.current_index + 1} / {len(SHOP_ITEMS)}",
            inline=True,
        )

        return [image_embed, details_embed]

    def build_file(self) -> discord.File:
        item = SHOP_ITEMS[self.current_index]
        image_path = item["image_path"]
        image_filename = os.path.basename(image_path)
        return discord.File(image_path, filename=image_filename)

    async def refresh_message(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            embeds=self.build_embeds(),
            attachments=[self.build_file()],
            view=self,
        )

    @discord.ui.button(
        emoji=ARROW_LEFT_EMOJI,
        style=discord.ButtonStyle.secondary,
    )
    async def go_left(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.current_index = cycle_index(self.current_index, -1, len(SHOP_ITEMS))
        await self.refresh_message(interaction)

    @discord.ui.button(
        emoji=BUY_EMOJI,
        style=discord.ButtonStyle.success,
    )
    async def buy_current_item(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        item = SHOP_ITEMS[self.current_index]

        try:
            with self.database.connect() as conn:
                user_repo = UserRepository(conn)
                owned_item_repo = OwnedItemRepository(conn)
                shop_service = ShopService(user_repo, owned_item_repo)
                result = shop_service.buy_item(self.owner_id, item["key"])

            embeds = self.build_embeds()
            details_embed = embeds[1]

            details_embed.add_field(
                name="Purchase Successful",
                value=(
                    f"Bought **{result['display_name']}** for "
                    f"{GALLEONS_ICON} **{result['price']}**.\n"
                    f"You now own **{result['new_quantity']}**.\n"
                    f"New balance: {GALLEONS_ICON} **{result['new_balance']}**"
                ),
                inline=False,
            )

            await interaction.response.edit_message(
                embeds=embeds,
                attachments=[self.build_file()],
                view=self,
            )

        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)

    @discord.ui.button(
        emoji=ARROW_RIGHT_EMOJI,
        style=discord.ButtonStyle.secondary,
    )
    async def go_right(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.current_index = cycle_index(self.current_index, 1, len(SHOP_ITEMS))
        await self.refresh_message(interaction)

    @discord.ui.button(
        emoji=CLOSE_EMOJI,
        style=discord.ButtonStyle.danger,
    )
    async def close_shop(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="Shop closed.",
            embeds=[],
            attachments=[],
            view=self,
        )

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True


class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

    @app_commands.command(name="shop", description="Open the Hogwarts shop.")
    async def shop(self, interaction: discord.Interaction) -> None:
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

        house_color = HOUSE_COLORS.get(role_ctx.current_house or "", 0x2F3136)
        view = ShopView(
            database=self.database,
            owner_id=interaction.user.id,
            house_color=house_color,
            start_index=0,
        )

        await interaction.response.send_message(
            embeds=view.build_embeds(),
            file=view.build_file(),
            view=view,
            ephemeral=True,
        )