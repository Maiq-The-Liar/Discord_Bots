import logging
import discord
from discord.ext import commands

from config import load_settings
from db.database import Database
from bot.cogs.profile import ProfileCog
from bot.cogs.admin import AdminCog
from bot.cogs.shop import ShopCog
from bot.cogs.patronus import PatronusCog
from bot.cogs.house_cup import HouseCupCog
from bot.cogs.chocolate_frogs import ChocolateFrogCog
from bot.cogs.casual_quiz import CasualQuizCog
from bot.cogs.birthday import BirthdayCog

logging.basicConfig(level=logging.INFO)

settings = load_settings()
database = Database(settings.database_path)
database.initialize()


class HogwartsBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self) -> None:
        guild = discord.Object(id=settings.guild_id)

        await self.add_cog(ProfileCog(self, database))
        await self.add_cog(AdminCog(self, database))
        await self.add_cog(ShopCog(self, database))
        await self.add_cog(PatronusCog(self, database))
        await self.add_cog(HouseCupCog(self, database))
        await self.add_cog(ChocolateFrogCog(self, database))
        await self.add_cog(CasualQuizCog(self, database))
        await self.add_cog(BirthdayCog(self, database))

        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        logging.info("Synced %s command(s) to guild %s", len(synced), settings.guild_id)

    async def on_ready(self) -> None:
        logging.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "unknown")


bot = HogwartsBot()
bot.run(settings.discord_token)