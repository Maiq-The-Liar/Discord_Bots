import asyncio
import time
from pathlib import Path
import discord

from repositories.bot_state_repository import BotStateRepository
from repositories.contribution_repository import ContributionRepository
from services.house_points_image_service import HousePointsImageService


class HouseCupBoardService:
    _recent_totals: dict[int, tuple[float, tuple[int, int, int, int]]] = {}
    _dirty_guild_ids: set[int] = set()

    @classmethod
    def mark_dirty(cls, guild_id: int) -> None:
        cls._dirty_guild_ids.add(int(guild_id))

    @classmethod
    def consume_dirty(cls, guild_id: int) -> bool:
        guild_id = int(guild_id)
        if guild_id not in cls._dirty_guild_ids:
            return False
        cls._dirty_guild_ids.discard(guild_id)
        return True

    @classmethod
    def is_dirty(cls, guild_id: int) -> bool:
        return int(guild_id) in cls._dirty_guild_ids

    CHANNEL_KEY = "house_board_channel_id"
    MESSAGE_KEY = "house_board_message_id"

    def __init__(
        self,
        bot_state_repo: BotStateRepository,
        contribution_repo: ContributionRepository,
    ):
        self.bot_state_repo = bot_state_repo
        self.contribution_repo = contribution_repo
        self.image_service = HousePointsImageService()

    def _get_totals(self) -> dict[str, int]:
        houses = ["Slytherin", "Ravenclaw", "Hufflepuff", "Gryffindor"]
        return self.contribution_repo.get_all_house_totals(houses)

    async def create_or_update_board(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel | None = None,
    ) -> tuple[bool, str]:
        if channel is None:
            stored_channel_id = self.bot_state_repo.get_value(self.CHANNEL_KEY)
            if stored_channel_id is None:
                return False, "House board channel is not configured."

            resolved_channel = guild.get_channel(int(stored_channel_id))
            if not isinstance(resolved_channel, discord.TextChannel):
                return False, "Configured house board channel could not be found."

            channel = resolved_channel
        else:
            self.bot_state_repo.set_value(self.CHANNEL_KEY, str(channel.id))

        totals = self._get_totals()
        totals_signature = (
            totals["Slytherin"],
            totals["Ravenclaw"],
            totals["Hufflepuff"],
            totals["Gryffindor"],
        )

        previous = self._recent_totals.get(guild.id)
        if previous is not None:
            previous_ts, previous_signature = previous
            if previous_signature == totals_signature and (time.monotonic() - previous_ts) < 10:
                return True, "House board already up to date."

        image_path = await asyncio.to_thread(
            self.image_service.generate_image,
            slytherin=totals["Slytherin"],
            ravenclaw=totals["Ravenclaw"],
            hufflepuff=totals["Hufflepuff"],
            gryffindor=totals["Gryffindor"],
        )

        embed = discord.Embed(
            title="House Cup Scoreboard",
            color=0xD4AF37,
        )
        embed.set_image(url="attachment://house_points_board.png")

        stored_message_id = self.bot_state_repo.get_value(self.MESSAGE_KEY)
        discord_file = discord.File(str(image_path), filename="house_points_board.png")

        if stored_message_id is not None:
            try:
                message = await channel.fetch_message(int(stored_message_id))
                await message.edit(embed=embed, attachments=[discord_file])
                self._recent_totals[guild.id] = (time.monotonic(), totals_signature)
                return True, "House board updated."
            except discord.NotFound:
                pass

        message = await channel.send(embed=embed, file=discord_file)
        self.bot_state_repo.set_value(self.MESSAGE_KEY, str(message.id))
        return True, "House board created."
