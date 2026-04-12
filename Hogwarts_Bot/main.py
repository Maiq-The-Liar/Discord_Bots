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
from bot.cogs.help import HelpCog
from bot.cogs.leveling import LevelingCog
from bot.cogs.media import MediaCog
from bot.cogs.duel import DuelCog
from repositories.guild_role_repository import GuildRoleRepository
from services.role_service import RoleService
from bot.cogs.reaction_roles import ReactionRolesCog
from bot.cogs.housing_quiz import HousingQuizCog
from bot.cogs.quidditch import QuidditchCog

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
        self._startup_role_sync_done = False

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
        await self.add_cog(HelpCog(self))
        await self.add_cog(LevelingCog(self, database))
        await self.add_cog(MediaCog(self, database))
        await self.add_cog(DuelCog(self, database))
        await self.add_cog(ReactionRolesCog(self, database))
        await self.add_cog(HousingQuizCog(self, database))
        await self.add_cog(QuidditchCog(self, database))

        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        logging.info("Synced %s command(s) to guild %s", len(synced), settings.guild_id)

    async def on_ready(self) -> None:
        logging.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "unknown")

        if self._startup_role_sync_done:
            return

        guild = self.get_guild(settings.guild_id)
        if guild is None:
            try:
                guild = await self.fetch_guild(settings.guild_id)
            except discord.HTTPException:
                logging.warning("Configured guild %s could not be fetched.", settings.guild_id)
                return

        try:
            with database.connect() as conn:
                role_repo = GuildRoleRepository(conn)
                role_service = RoleService(role_repo)
                result = await role_service.sync_all_managed_roles(guild)

            logging.info(
                "Role sync complete. created=%s updated=%s found=%s failed=%s",
                len(result["created"]),
                len(result["updated"]),
                len(result["found"]),
                len(result["failed"]),
            )
        except Exception:
            logging.exception("Startup role sync failed.")
            return

        self._startup_role_sync_done = True


bot = HogwartsBot()
bot.run(settings.discord_token)