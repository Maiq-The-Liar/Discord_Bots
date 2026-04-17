import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# =========================
# ENV
# =========================

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN was not found in the .env file.")

# =========================
# CONFIG
# =========================

DISBOARD_BOT_ID = 302050872383242240
PING_ROLE_ID = 1494749646705262702

READY_CHANNEL_NAME = "🔔 BUMP-US 🔔"
COOLDOWN_CHANNEL_NAME = "bump-the-server"

BUMP_COOLDOWN_SECONDS = 2 * 60 * 60  # 2 hours
DATA_FILE = Path("bump_data.json")

# Optional:
# Put your server ID here for instant slash command sync while testing.
# Leave as None for global commands.
TEST_GUILD_ID = None
# Example:
# TEST_GUILD_ID = 123456789012345678

# =========================
# LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("bump-bot")

# =========================
# INTENTS
# =========================

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

# =========================
# HELPERS
# =========================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def dt_to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"guilds": {}}

    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if "guilds" not in data:
            data["guilds"] = {}
        return data
    except Exception:
        log.exception("Failed to load data file.")
        return {"guilds": {}}


def save_data(data: dict) -> None:
    temp_file = DATA_FILE.with_suffix(".tmp")
    with temp_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    temp_file.replace(DATA_FILE)


# =========================
# BOT
# =========================

class BumpBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.data = load_data()
        self.reminder_tasks: dict[int, asyncio.Task] = {}

    async def setup_hook(self):
        if TEST_GUILD_ID:
            guild = discord.Object(id=TEST_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %s guild command(s).", len(synced))
        else:
            synced = await self.tree.sync()
            log.info("Synced %s global command(s).", len(synced))

    def guild_config(self, guild_id: int) -> dict:
        gid = str(guild_id)
        guilds = self.data.setdefault("guilds", {})
        if gid not in guilds:
            guilds[gid] = {
                "channel_id": None,
                "last_bump_at": None,
                "last_ready_ping_at": None
            }
        return guilds[gid]

    def get_listen_channel_id(self, guild_id: int) -> int | None:
        cfg = self.guild_config(guild_id)
        value = cfg.get("channel_id")
        return int(value) if value else None

    def set_listen_channel_id(self, guild_id: int, channel_id: int) -> None:
        cfg = self.guild_config(guild_id)
        cfg["channel_id"] = channel_id
        save_data(self.data)

    def get_last_bump_at(self, guild_id: int) -> datetime | None:
        cfg = self.guild_config(guild_id)
        return iso_to_dt(cfg.get("last_bump_at"))

    def set_last_bump_at(self, guild_id: int, dt: datetime) -> None:
        cfg = self.guild_config(guild_id)
        cfg["last_bump_at"] = dt_to_iso(dt)
        save_data(self.data)

    def cancel_reminder_task(self, guild_id: int) -> None:
        task = self.reminder_tasks.pop(guild_id, None)
        if task and not task.done():
            task.cancel()

    async def on_ready(self):
        assert self.user is not None
        log.info("Logged in as %s (%s)", self.user, self.user.id)

        for guild in self.guilds:
            await self.restore_schedule_for_guild(guild)

    async def restore_schedule_for_guild(self, guild: discord.Guild):
        channel_id = self.get_listen_channel_id(guild.id)
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            log.warning("Configured channel not found or not a text channel in guild %s", guild.id)
            return

        last_bump = self.get_last_bump_at(guild.id)
        if not last_bump:
            return

        elapsed = (utc_now() - last_bump).total_seconds()

        if elapsed >= BUMP_COOLDOWN_SECONDS:
            await self.make_channel_ready(channel, send_ping=False)
        else:
            self.schedule_reminder(guild.id, channel, last_bump)

    def schedule_reminder(self, guild_id: int, channel: discord.TextChannel, bump_time: datetime):
        self.cancel_reminder_task(guild_id)
        self.reminder_tasks[guild_id] = asyncio.create_task(
            self.reminder_worker(guild_id, channel, bump_time)
        )

    async def reminder_worker(self, guild_id: int, channel: discord.TextChannel, bump_time: datetime):
        try:
            target_time = bump_time + timedelta(seconds=BUMP_COOLDOWN_SECONDS)
            sleep_seconds = (target_time - utc_now()).total_seconds()

            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)

            latest_bump = self.get_last_bump_at(guild_id)
            if latest_bump is None:
                return

            # Prevent stale timer from firing if a newer bump happened
            if abs((latest_bump - bump_time).total_seconds()) > 1:
                return

            await self.make_channel_ready(channel, send_ping=True)

        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Reminder worker crashed for guild %s", guild_id)

    async def make_channel_ready(self, channel: discord.TextChannel, send_ping: bool):
        try:
            if channel.name != READY_CHANNEL_NAME:
                await channel.edit(name=READY_CHANNEL_NAME, reason="DISBOARD bump cooldown finished")
        except discord.Forbidden:
            log.warning("Missing permission to rename channel %s", channel.id)
        except discord.HTTPException:
            log.exception("Failed to rename channel %s", channel.id)

        if send_ping:
            try:
                await channel.send(f"<@&{PING_ROLE_ID}> DISBOARD is ready to be bumped again!")
            except discord.Forbidden:
                log.warning("Missing permission to send message in channel %s", channel.id)
            except discord.HTTPException:
                log.exception("Failed to send ready ping in channel %s", channel.id)

    async def handle_successful_bump(self, guild: discord.Guild, channel: discord.TextChannel):
        now = utc_now()
        self.set_last_bump_at(guild.id, now)

        self.cancel_reminder_task(guild.id)

        try:
            if channel.name != COOLDOWN_CHANNEL_NAME:
                await channel.edit(name=COOLDOWN_CHANNEL_NAME, reason="Successful DISBOARD bump detected")
        except discord.Forbidden:
            log.warning("Missing permission to rename channel %s", channel.id)
        except discord.HTTPException:
            log.exception("Failed to rename channel %s", channel.id)

        self.schedule_reminder(guild.id, channel, now)

    @staticmethod
    def is_successful_disboard_bump(message: discord.Message) -> bool:
        text_parts = []

        if message.content:
            text_parts.append(message.content.lower())

        for embed in message.embeds:
            if embed.title:
                text_parts.append(embed.title.lower())
            if embed.description:
                text_parts.append(embed.description.lower())
            if embed.footer and embed.footer.text:
                text_parts.append(embed.footer.text.lower())

        full_text = "\n".join(text_parts)

        success_markers = [
            "bump done",
            "server bumped",
            "successfully bumped",
            "bumped successfully",
            "please wait another 2 hours",
            "wait another 2 hours",
        ]

        return any(marker in full_text for marker in success_markers)

    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return

        if not isinstance(message.channel, discord.TextChannel):
            return

        listen_channel_id = self.get_listen_channel_id(message.guild.id)
        if not listen_channel_id:
            return

        if message.channel.id != listen_channel_id:
            return

        if message.author.id != DISBOARD_BOT_ID:
            return

        if self.is_successful_disboard_bump(message):
            log.info(
                "Successful DISBOARD bump detected in guild=%s channel=%s",
                message.guild.id,
                message.channel.id,
            )
            await self.handle_successful_bump(message.guild, message.channel)


bot = BumpBot()

# =========================
# COMMANDS
# =========================

@bot.tree.command(name="bump_listen_here", description="Set this channel as the active DISBOARD listening channel.")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def bump_listen_here(interaction: discord.Interaction):
    if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This command can only be used in a server text channel.", ephemeral=True)
        return

    member = interaction.user
    if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    bot.set_listen_channel_id(interaction.guild.id, interaction.channel.id)

    await interaction.response.send_message(
        f"This channel is now the active bump listening channel: {interaction.channel.mention}",
        ephemeral=True
    )


@bot.tree.command(name="bump_stats", description="Show the last successful bump time for this server.")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def bump_stats(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    member = interaction.user
    if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    cfg = bot.guild_config(interaction.guild.id)
    channel_id = cfg.get("channel_id")
    last_bump = bot.get_last_bump_at(interaction.guild.id)

    if not channel_id:
        await interaction.response.send_message(
            "No listening channel is configured yet. Use `/bump_listen_here` in the bump channel first.",
            ephemeral=True
        )
        return

    if last_bump is None:
        await interaction.response.send_message(
            f"Listening channel: <#{channel_id}>\nNo successful bump recorded yet.",
            ephemeral=True
        )
        return

    unix_ts = int(last_bump.timestamp())
    remaining = max(0, int(BUMP_COOLDOWN_SECONDS - (utc_now() - last_bump).total_seconds()))

    if remaining == 0:
        status_text = "Ready to bump again now."
    else:
        hours, remainder = divmod(remaining, 3600)
        minutes, seconds = divmod(remainder, 60)
        status_text = f"Next bump in about {hours}h {minutes}m {seconds}s."

    embed = discord.Embed(title="Bump stats")
    embed.add_field(name="Listening channel", value=f"<#{channel_id}>", inline=False)
    embed.add_field(name="Last successful bump", value=f"<t:{unix_ts}:F>\n(<t:{unix_ts}:R>)", inline=False)
    embed.add_field(name="Status", value=status_text, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# Optional extra admin command
@bot.tree.command(name="bump_stop_listening", description="Disable bump listening in this server.")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def bump_stop_listening(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    member = interaction.user
    if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    cfg = bot.guild_config(interaction.guild.id)
    cfg["channel_id"] = None
    save_data(bot.data)
    bot.cancel_reminder_task(interaction.guild.id)

    await interaction.response.send_message("Stopped listening for DISBOARD bumps in this server.", ephemeral=True)


# =========================
# ERROR HANDLING
# =========================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.exception("Slash command error", exc_info=error)

    message = "Something went wrong while running that command."

    if isinstance(error, app_commands.CheckFailure):
        message = str(error)

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    bot.run(TOKEN)