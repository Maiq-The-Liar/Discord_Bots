import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN was not found in the .env file.")

DISBOARD_BOT_ID = 302050872383242240
PING_ROLE_ID = 1494749646705262702

READY_CHANNEL_NAME = "🔔 BUMP-US 🔔"
COOLDOWN_CHANNEL_NAME = "bump-the-server"

BUMP_COOLDOWN_SECONDS = 2 * 60 * 60  # 2 hours

DATA_FILE = Path("bump_data.json")

# Optional:
# If you want faster slash-command registration while testing,
# put your server ID here and uncomment sync logic in setup_hook.
TEST_GUILD_ID = None  # example: 123456789012345678

# =========================
# Logging
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("bump-bot")

# =========================
# Intents
# =========================

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True  # needed to inspect DISBOARD's message/embed

# =========================
# Persistence helpers
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


def default_data() -> dict[str, Any]:
    return {"guilds": {}}


def load_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return default_data()

    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if "guilds" not in raw or not isinstance(raw["guilds"], dict):
            return default_data()
        return raw
    except Exception as e:
        log.exception("Failed to load data file: %s", e)
        return default_data()


def save_data(data: dict[str, Any]) -> None:
    tmp = DATA_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(DATA_FILE)


# =========================
# Bot
# =========================

class BumpBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)
        self.data: dict[str, Any] = load_data()
        self.reminder_tasks: dict[int, asyncio.Task] = {}

    async def setup_hook(self) -> None:
        # Register slash commands.
        if TEST_GUILD_ID:
            guild = discord.Object(id=TEST_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d test-guild command(s).", len(synced))
        else:
            synced = await self.tree.sync()
            log.info("Synced %d global command(s).", len(synced))

    def guild_config(self, guild_id: int) -> dict[str, Any]:
        gid = str(guild_id)
        guilds = self.data.setdefault("guilds", {})
        cfg = guilds.setdefault(
            gid,
            {
                "channel_id": None,
                "last_bump_at": None,
                "last_bumped_by": None,
                "last_disboard_message_id": None,
            },
        )
        return cfg

    def get_last_bump_dt(self, guild_id: int) -> datetime | None:
        cfg = self.guild_config(guild_id)
        return iso_to_dt(cfg.get("last_bump_at"))

    def set_last_bump_dt(self, guild_id: int, dt: datetime | None) -> None:
        cfg = self.guild_config(guild_id)
        cfg["last_bump_at"] = dt_to_iso(dt)
        save_data(self.data)

    def set_listen_channel(self, guild_id: int, channel_id: int) -> None:
        cfg = self.guild_config(guild_id)
        cfg["channel_id"] = channel_id
        save_data(self.data)

    def get_listen_channel_id(self, guild_id: int) -> int | None:
        cfg = self.guild_config(guild_id)
        value = cfg.get("channel_id")
        return int(value) if value else None

    def cancel_reminder_task(self, guild_id: int) -> None:
        task = self.reminder_tasks.pop(guild_id, None)
        if task and not task.done():
            task.cancel()

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info("Logged in as %s (%s)", self.user, self.user.id)

        # Rebuild timers after restart.
        for guild in self.guilds:
            await self.restore_guild_schedule(guild)

    async def restore_guild_schedule(self, guild: discord.Guild) -> None:
        channel_id = self.get_listen_channel_id(guild.id)
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            log.warning("Configured channel %s in guild %s is missing or not text.", channel_id, guild.id)
            return

        last_bump = self.get_last_bump_dt(guild.id)
        if not last_bump:
            return

        elapsed = (utc_now() - last_bump).total_seconds()

        if elapsed >= BUMP_COOLDOWN_SECONDS:
            await self.make_channel_ready(channel, send_ping=False)
        else:
            self.schedule_reminder(guild.id, channel, last_bump)

    def schedule_reminder(self, guild_id: int, channel: discord.TextChannel, last_bump: datetime) -> None:
        self.cancel_reminder_task(guild_id)
        self.reminder_tasks[guild_id] = asyncio.create_task(
            self._reminder_worker(guild_id, channel, last_bump)
        )

    async def _reminder_worker(self, guild_id: int, channel: discord.TextChannel, bump_time: datetime) -> None:
        try:
            target_time = bump_time + timedelta(seconds=BUMP_COOLDOWN_SECONDS)
            sleep_for = (target_time - utc_now()).total_seconds()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

            current_last_bump = self.get_last_bump_dt(guild_id)
            if current_last_bump is None:
                return

            # Ignore stale reminder tasks if a newer bump happened.
            if abs((current_last_bump - bump_time).total_seconds()) > 1:
                return

            await self.make_channel_ready(channel, send_ping=True)

        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Reminder worker failed for guild %s", guild_id)

    async def make_channel_ready(self, channel: discord.TextChannel, send_ping: bool) -> None:
        try:
            if channel.name != READY_CHANNEL_NAME:
                await channel.edit(name=READY_CHANNEL_NAME, reason="Bump cooldown finished")
        except discord.Forbidden:
            log.warning("Missing permission to rename channel %s", channel.id)
        except discord.HTTPException:
            log.exception("Failed to rename channel %s to ready state", channel.id)

        if send_ping:
            try:
                await channel.send(f"<@&{PING_ROLE_ID}> DISBOARD is ready to be bumped again!")
            except discord.Forbidden:
                log.warning("Missing permission to send message in channel %s", channel.id)
            except discord.HTTPException:
                log.exception("Failed to send ready ping in channel %s", channel.id)

    async def handle_successful_bump(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        disboard_message: discord.Message,
    ) -> None:
        cfg = self.guild_config(guild.id)

        now = utc_now()
        cfg["last_bump_at"] = dt_to_iso(now)
        cfg["last_disboard_message_id"] = disboard_message.id

        # Try to infer who used /bump from the message right before DISBOARD, if possible.
        last_bumped_by = None
        try:
            async for msg in channel.history(limit=5, before=disboard_message):
                if msg.author.bot:
                    continue
                if msg.interaction_metadata is not None:
                    # A slash command invocation often leaves a system message, but
                    # this is not guaranteed to be the source of the /bump.
                    pass
                last_bumped_by = msg.author.id
                break
        except Exception:
            pass

        cfg["last_bumped_by"] = last_bumped_by
        save_data(self.data)

        self.cancel_reminder_task(guild.id)

        try:
            if channel.name != COOLDOWN_CHANNEL_NAME:
                await channel.edit(name=COOLDOWN_CHANNEL_NAME, reason="Successful DISBOARD bump detected")
        except discord.Forbidden:
            log.warning("Missing permission to rename channel %s", channel.id)
        except discord.HTTPException:
            log.exception("Failed to rename channel %s to cooldown state", channel.id)

        self.schedule_reminder(guild.id, channel, now)

    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return

        if not isinstance(message.channel, discord.TextChannel):
            return

        listen_channel_id = self.get_listen_channel_id(message.guild.id)
        if not listen_channel_id or message.channel.id != listen_channel_id:
            return

        if message.author.id != DISBOARD_BOT_ID:
            return

        if self.is_successful_disboard_bump(message):
            log.info("Successful bump detected in guild=%s channel=%s", message.guild.id, message.channel.id)
            await self.handle_successful_bump(message.guild, message.channel, message)

    @staticmethod
    def is_successful_disboard_bump(message: discord.Message) -> bool:
        """
        DISBOARD usually sends an embed after /bump.
        We check common success phrases in title/description.
        """
        texts: list[str] = []

        if message.content:
            texts.append(message.content.lower())

        for embed in message.embeds:
            if embed.title:
                texts.append(embed.title.lower())
            if embed.description:
                texts.append(embed.description.lower())

            # Footer sometimes contains useful text.
            footer = getattr(embed, "footer", None)
            if footer and footer.text:
                texts.append(footer.text.lower())

        haystack = "\n".join(texts)

        success_markers = [
            "bump done",
            "server bumped",
            "bumped successfully",
            "successfully bumped",
            "please wait another 2 hours",
            "wait another 2 hours",
        ]

        return any(marker in haystack for marker in success_markers)


bot = BumpBot()

# =========================
# Checks
# =========================

def admin_only() -> app_commands.Check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.CheckFailure("This command can only be used in a server.")
        member = interaction.user
        if not isinstance(member, discord.Member):
            raise app_commands.CheckFailure("Could not verify your permissions.")
        if member.guild_permissions.administrator:
            return True
        raise app_commands.CheckFailure("You must be an administrator to use this command.")
    return app_commands.check(predicate)

# =========================
# Slash commands
# =========================


@bot.tree.command(name="bump_listen_here", description="Set this channel as the active DISBOARD listening channel.")
@admin_only()
@app_commands.guild_only()
async def bump_listen_here(interaction: discord.Interaction) -> None:
    assert interaction.guild is not None
    assert isinstance(interaction.channel, discord.TextChannel)

    bot.set_listen_channel(interaction.guild.id, interaction.channel.id)

    await interaction.response.send_message(
        f"Listening for successful DISBOARD bumps in {interaction.channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="bump_stats", description="Show the last successful bump time for this server.")
@app_commands.guild_only()
async def bump_stats(interaction: discord.Interaction) -> None:
    assert interaction.guild is not None

    cfg = bot.guild_config(interaction.guild.id)
    channel_id = cfg.get("channel_id")
    last_bump = bot.get_last_bump_dt(interaction.guild.id)
    last_bumped_by = cfg.get("last_bumped_by")

    if not channel_id:
        await interaction.response.send_message(
            "No listening channel is configured yet. Use `/bump_listen_here` in the bump channel first.",
            ephemeral=True,
        )
        return

    channel_mention = f"<#{channel_id}>"

    if last_bump is None:
        await interaction.response.send_message(
            f"Listening channel: {channel_mention}\nNo successful bump recorded yet.",
            ephemeral=False,
        )
        return

    unix = int(last_bump.timestamp())
    remaining = max(0, int(BUMP_COOLDOWN_SECONDS - (utc_now() - last_bump).total_seconds()))

    if remaining == 0:
        status = "Ready to bump again now."
    else:
        mins, secs = divmod(remaining, 60)
        hours, mins = divmod(mins, 60)
        status = f"Next bump in about {hours}h {mins}m {secs}s."

    bumped_by_text = f"<@{last_bumped_by}>" if last_bumped_by else "Unknown"

    embed = discord.Embed(title="Bump stats")
    embed.add_field(name="Listening channel", value=channel_mention, inline=False)
    embed.add_field(name="Last successful bump", value=f"<t:{unix}:F>\n(<t:{unix}:R>)", inline=False)
    embed.add_field(name="Last bumped by", value=bumped_by_text, inline=False)
    embed.add_field(name="Status", value=status, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=False)


# Optional admin helper
@bot.tree.command(name="bump_stop_listening", description="Disable bump listening for this server.")
@admin_only()
@app_commands.guild_only()
async def bump_stop_listening(interaction: discord.Interaction) -> None:
    assert interaction.guild is not None

    cfg = bot.guild_config(interaction.guild.id)
    cfg["channel_id"] = None
    save_data(bot.data)
    bot.cancel_reminder_task(interaction.guild.id)

    await interaction.response.send_message(
        "Stopped listening for DISBOARD bumps in this server.",
        ephemeral=True,
    )


# =========================
# Error handling
# =========================

@bump_listen_here.error
@bump_stop_listening.error
async def admin_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.CheckFailure):
        text = str(error)
    else:
        log.exception("Admin command error", exc_info=error)
        text = "Something went wrong while running that command."

    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


@bump_stats.error
async def bump_stats_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    log.exception("bump_stats error", exc_info=error)
    if interaction.response.is_done():
        await interaction.followup.send("Something went wrong while fetching bump stats.", ephemeral=True)
    else:
        await interaction.response.send_message("Something went wrong while fetching bump stats.", ephemeral=True)


# =========================
# Entry point
# =========================

if __name__ == "__main__":
    if TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("Edit bot.py and set TOKEN to your real bot token first.")

    bot.run(TOKEN)