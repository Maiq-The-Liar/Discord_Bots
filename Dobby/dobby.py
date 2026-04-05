import asyncio
import json
import logging
import os
import random
import sqlite3
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# =========================================================
# ENV / CONFIG
# =========================================================
load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID_RAW = os.getenv("GUILD_ID")

if not BOT_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set in the .env file.")

if not GUILD_ID_RAW:
    raise RuntimeError("GUILD_ID is not set in the .env file.")

try:
    GUILD_ID = int(GUILD_ID_RAW)
except ValueError as exc:
    raise RuntimeError("GUILD_ID in .env must be a valid integer.") from exc

DATA_DIR = Path(__file__).parent
DB_FILE = DATA_DIR / "bot_data.db"
FLAVORS_FILE = DATA_DIR / "flavors.json"

# =========================================================
# SETTINGS
# =========================================================
TEST_MODE = False

MAX_PARTICIPANTS = 5
EVENT_DURATION_SECONDS = 20 * 60  # 20 minutes

MIN_SPAWN_SECONDS = 5 * 60 * 60   # 5 hours
MAX_SPAWN_SECONDS = 7 * 60 * 60   # 7 hours

EVENT_TITLE = "\"Would Master kindly give Dobby another sock?\""
EVENT_DESCRIPTION = (
    "Dobby has appeared and is in desperate need of some socks.\n"
    "Each person may click exactly one button. Make sure you give him his favourite one...!"
)

EVENT_GIF_URLS = [
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Dobby_bed.gif?raw=true"
]

BEAN_IMAGE_URLS = [
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean1_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean2_cleanup.png?raw=true",
]

SOCK_EMOJI_POOL = [
    "<:Sock6:1485677804581421128>",
    "<:Sock10:1485676309253459988>",
    "<:Sock1:1485675915584344124>",
    "<:Sock2:1485675913499771061>",
    "<:Sock3:1485675911935168522>",
    "<:Sock4:148567591046424408>",
    "<:Sock5:1485675909582295171>",
    "<:Sock7:1485675907434811625>",
    "<:Sock8:1485675897389449287>",
    "<:Sock9:1485675896458444800>",
]

SOCKS_PER_EVENT = 5

REWARD_BY_RANK = {
    1: 10,
    2: 5,
    3: 3,
    4: 2,
    5: 1,
}

DOBBY_RESPONSE_BY_RANK = {
    1: "Dobby is amazed! Such a magnificent sock! Master earns **10 Bertie Bott’s Every Flavoured Beans**!",
    2: "Oho! Dobby likes this one quite a lot. Master earns **5 Bertie Bott’s Every Flavoured Beans**!",
    3: "This sock is respectable. Dobby nods politely. Master earns **3 Bertie Bott’s Every Flavoured Beans**.",
    4: "Hmm. Dobby has seen better socks, but this one will do. Master earns **2 Bertie Bott’s Every Flavoured Beans**.",
    5: "This sock is... a choice. Dobby supposes Master may have **1 Bertie Bott’s Every Flavoured Bean**.",
}

DOBBY_MISSED_DESCRIPTION = (
    "Dobby disappeared — and Master just missed him!\n"
    "But surely he’ll be back again soon with more socks to inspect..."
)

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("dobby_bot")

# =========================================================
# DISCORD SETUP
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
TEST_GUILD = discord.Object(id=GUILD_ID)

# =========================================================
# JSON HELPERS
# =========================================================
def read_json_file(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Required file is missing: {path.name}")

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{path.name} contains invalid JSON.") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not read {path.name}.") from exc


def get_flavors() -> list[str]:
    raw = read_json_file(FLAVORS_FILE)

    if not isinstance(raw, list):
        raise RuntimeError("flavors.json must contain a JSON list of flavour names.")

    flavors = [str(x).strip() for x in raw if str(x).strip()]
    unique_flavors = list(dict.fromkeys(flavors))

    if not unique_flavors:
        raise RuntimeError("flavors.json must contain at least one flavour.")

    return unique_flavors


def get_total_flavours() -> int:
    return len(get_flavors())

# =========================================================
# SQLITE HELPERS
# =========================================================
def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                user_id TEXT PRIMARY KEY,
                beans INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasted_flavours (
                user_id TEXT NOT NULL,
                flavour TEXT NOT NULL,
                PRIMARY KEY (user_id, flavour)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS allowed_channels (
                channel_id TEXT PRIMARY KEY
            )
            """
        )
        conn.commit()


init_db()
get_flavors()

# =========================================================
# DATA HELPERS
# =========================================================
def ensure_user_inventory(user_id: int) -> None:
    uid = str(user_id)
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO inventory (user_id, beans)
            VALUES (?, 0)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (uid,),
        )
        conn.commit()


def get_bean_count(user_id: int) -> int:
    uid = str(user_id)
    ensure_user_inventory(user_id)

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT beans FROM inventory WHERE user_id = ?",
            (uid,),
        ).fetchone()

    return int(row["beans"]) if row else 0


def add_beans(user_id: int, amount: int) -> int:
    if amount < 0:
        raise ValueError("amount must be >= 0")

    uid = str(user_id)
    ensure_user_inventory(user_id)

    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE inventory
            SET beans = beans + ?
            WHERE user_id = ?
            """,
            (amount, uid),
        )
        row = conn.execute(
            "SELECT beans FROM inventory WHERE user_id = ?",
            (uid,),
        ).fetchone()
        conn.commit()

    return int(row["beans"]) if row else 0


def remove_bean(user_id: int) -> bool:
    uid = str(user_id)
    ensure_user_inventory(user_id)

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT beans FROM inventory WHERE user_id = ?",
            (uid,),
        ).fetchone()

        current = int(row["beans"]) if row else 0
        if current <= 0:
            return False

        conn.execute(
            """
            UPDATE inventory
            SET beans = beans - 1
            WHERE user_id = ?
            """,
            (uid,),
        )
        conn.commit()

    return True


def get_user_tasted_flavours(user_id: int) -> set[str]:
    uid = str(user_id)

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT flavour
            FROM tasted_flavours
            WHERE user_id = ?
            """,
            (uid,),
        ).fetchall()

    return {str(row["flavour"]) for row in rows}


def add_tasted_flavour(user_id: int, flavour: str) -> tuple[bool, int]:
    uid = str(user_id)

    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO tasted_flavours (user_id, flavour)
            VALUES (?, ?)
            """,
            (uid, flavour),
        )
        is_new = cursor.rowcount > 0

        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM tasted_flavours
            WHERE user_id = ?
            """,
            (uid,),
        ).fetchone()
        conn.commit()

    discovered_count = int(row["count"]) if row else 0
    return is_new, discovered_count


def get_allowed_channels() -> set[int]:
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT channel_id
            FROM allowed_channels
            """
        ).fetchall()

    return {int(row["channel_id"]) for row in rows}


def allow_channel(channel_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO allowed_channels (channel_id)
            VALUES (?)
            """,
            (str(channel_id),),
        )
        conn.commit()


def disallow_channel(channel_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            DELETE FROM allowed_channels
            WHERE channel_id = ?
            """,
            (str(channel_id),),
        )
        conn.commit()


def clear_allowed_channels() -> int:
    with get_db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM allowed_channels").fetchone()
        removed_count = int(row["count"]) if row else 0

        conn.execute("DELETE FROM allowed_channels")
        conn.commit()

    return removed_count

# =========================================================
# EVENT STATE
# =========================================================
active_events: dict[int, "DobbyEvent"] = {}
spawn_loop_task: asyncio.Task | None = None

# =========================================================
# EVENT CLASS
# =========================================================
class DobbyEvent:
    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        self.channel_id = channel.id
        self.guild_id = channel.guild.id

        self.active = True
        self.gif_url = random.choice(EVENT_GIF_URLS)
        self.socks = random.sample(SOCK_EMOJI_POOL, SOCKS_PER_EVENT)
        self.assignment = self._create_assignment()

        self.participants: dict[int, dict[str, str]] = {}
        self.message: discord.Message | None = None
        self.view: "DobbyView | None" = None
        self.end_task: asyncio.Task | None = None

    def _create_assignment(self) -> dict[str, int]:
        ranks = [1, 2, 3, 4, 5]
        random.shuffle(ranks)
        return dict(zip(self.socks, ranks))

    def participant_count(self) -> int:
        return len(self.participants)

    def has_participated(self, user_id: int) -> bool:
        return user_id in self.participants

    def add_participant(
        self,
        member: discord.Member | discord.User,
        sock_emoji: str,
    ) -> tuple[int, int]:
        rank = self.assignment[sock_emoji]
        reward = REWARD_BY_RANK[rank]

        display_name = getattr(member, "display_name", member.name)
        self.participants[member.id] = {
            "name": display_name,
            "sock": sock_emoji,
        }

        add_beans(member.id, reward)
        log.info(
            "Participant added: user=%s sock=%s rank=%s reward=%s channel=%s",
            member.id, sock_emoji, rank, reward, self.channel_id,
        )
        return rank, reward

    def build_embed(self) -> discord.Embed:
        if self.participants:
            names = "\n".join(f"• {info['name']}" for info in self.participants.values())
        else:
            names = "Nobody yet."

        embed = discord.Embed(
            title=EVENT_TITLE,
            description=(
                f"{EVENT_DESCRIPTION}\n\n"
                f"**Participants:** {self.participant_count()}/{MAX_PARTICIPANTS}\n"
                f"**People who already interacted:**\n{names}"
            ),
            color=discord.Color.green(),
        )
        embed.set_image(url=self.gif_url)
        embed.set_footer(
            text=f"Event ends after {EVENT_DURATION_SECONDS // 60} minutes or when {MAX_PARTICIPANTS} unique users have interacted."
        )
        return embed

    async def send(self) -> None:
        self.view = DobbyView(self)
        self.message = await self.channel.send(embed=self.build_embed(), view=self.view)
        log.info(
            "Dobby event sent: guild=%s channel=%s message=%s",
            self.guild_id, self.channel_id, self.message.id,
        )
        self.end_task = asyncio.create_task(self._auto_end())

    async def refresh_message(self) -> None:
        if self.message and self.view and self.active:
            try:
                await self.message.edit(embed=self.build_embed(), view=self.view)
            except discord.HTTPException:
                log.exception("Failed to refresh Dobby message in channel=%s", self.channel_id)

    async def _auto_end(self) -> None:
        try:
            await asyncio.sleep(EVENT_DURATION_SECONDS)
            if self.active:
                await self.end(reason="timer")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Unexpected error in _auto_end for channel=%s", self.channel_id)

    async def end(self, reason: str = "unknown") -> None:
        if not self.active:
            return

        log.info(
            "Ending Dobby event: channel=%s message=%s reason=%s participants=%s",
            self.channel_id,
            self.message.id if self.message else "unknown",
            reason,
            self.participant_count(),
        )

        self.active = False

        if self.view:
            for child in self.view.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True

        if self.end_task and not self.end_task.done():
            self.end_task.cancel()

        active_events.pop(self.channel_id, None)

        if self.message:
            try:
                missed_embed = discord.Embed(
                    title=EVENT_TITLE,
                    description=DOBBY_MISSED_DESCRIPTION,
                    color=discord.Color.dark_grey(),
                )
                missed_embed.set_footer(text="Dobby has already left.")
                await self.message.edit(embed=missed_embed, view=self.view)
            except discord.HTTPException:
                log.exception("Failed to edit finished Dobby message in channel=%s", self.channel_id)

# =========================================================
# BUTTON VIEW
# =========================================================
class SockButton(discord.ui.Button["DobbyView"]):
    def __init__(self, sock_emoji: str, index: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=discord.PartialEmoji.from_str(sock_emoji),
            custom_id=f"dobby_button_sock_{index}",
        )
        self.sock_emoji = sock_emoji

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            await interaction.response.send_message(
                "This button is not available right now.",
                ephemeral=True,
            )
            return

        await self.view.handle_press(interaction, self.sock_emoji)


class DobbyView(discord.ui.View):
    def __init__(self, event: DobbyEvent):
        super().__init__(timeout=None)
        self.event = event

        for index, sock_emoji in enumerate(event.socks, start=1):
            self.add_item(SockButton(sock_emoji, index))

    async def handle_press(self, interaction: discord.Interaction, sock_emoji: str) -> None:
        if not self.event.active:
            await interaction.response.send_message(
                "Too late — Dobby has already left.",
                ephemeral=True,
            )
            return

        if self.event.has_participated(interaction.user.id):
            await interaction.response.send_message(
                "You already interacted with this Dobby event.",
                ephemeral=True,
            )
            return

        rank, reward = self.event.add_participant(interaction.user, sock_emoji)
        total = get_bean_count(interaction.user.id)
        bean_word = "Bean" if reward == 1 else "Beans"

        await self.event.refresh_message()

        await interaction.response.send_message(
            f"{DOBBY_RESPONSE_BY_RANK[rank]}\n\n"
            f"You received **{reward} Bertie Bott’s Every Flavoured {bean_word}**.\n"
            f"You now have **{total} Bertie Bott’s Every Flavoured Beans**.",
            ephemeral=True,
        )

        if self.event.participant_count() >= MAX_PARTICIPANTS:
            await self.event.end(reason="max_participants")

# =========================================================
# EVENT HELPERS
# =========================================================
async def start_dobby_event(channel: discord.TextChannel) -> tuple[bool, str]:
    if channel.id in active_events:
        return False, "A Dobby event is already active in this channel."

    event = DobbyEvent(channel)
    active_events[channel.id] = event
    await event.send()
    return True, "Dobby has appeared."


def get_valid_allowed_channels() -> list[discord.TextChannel]:
    channels: list[discord.TextChannel] = []

    for channel_id in get_allowed_channels():
        channel = bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            continue
        if channel.id in active_events:
            continue
        channels.append(channel)

    return channels


def choose_spawn_channel() -> discord.TextChannel | None:
    channels = get_valid_allowed_channels()
    if not channels:
        return None
    return random.choice(channels)

# =========================================================
# RANDOM SPAWN LOOP
# =========================================================
async def random_spawn_loop() -> None:
    await bot.wait_until_ready()

    try:
        while not bot.is_closed():
            delay = random.randint(MIN_SPAWN_SECONDS, MAX_SPAWN_SECONDS)
            log.info("Next Dobby spawn check in %s seconds.", delay)
            await asyncio.sleep(delay)

            channel = choose_spawn_channel()
            if channel is None:
                log.info("No allowed channel available for Dobby spawn.")
                continue

            try:
                _, message = await start_dobby_event(channel)
                log.info("Spawn attempt in #%s: %s", channel.name, message)
            except Exception:
                log.exception("Failed to start Dobby event.")
    except asyncio.CancelledError:
        log.info("Random Dobby spawn loop cancelled.")
        raise

# =========================================================
# PERMISSION HELPERS
# =========================================================
def admin_only() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.CheckFailure("This command can only be used in a server.")
        if not interaction.user.guild_permissions.administrator:
            raise app_commands.CheckFailure("You must be an administrator to use this command.")
        return True

    return app_commands.check(predicate)


ADMIN_COMMAND_PERMS = app_commands.default_permissions(administrator=True)
GUILD_ONLY = app_commands.guild_only()

# =========================================================
# PUBLIC COMMANDS
# =========================================================
@bot.tree.command(
    guild=TEST_GUILD,
    name="eat_bean",
    description="Eat one Bertie Bott's Every Flavoured Bean.",
)
@app_commands.guild_only()
async def eat_bean(interaction: discord.Interaction) -> None:
    if not remove_bean(interaction.user.id):
        await interaction.response.send_message(
            "You do not have any Bertie Bott’s Every Flavoured Beans to eat.",
            ephemeral=True,
        )
        return

    flavors = get_flavors()
    flavor = random.choice(flavors)
    remaining = get_bean_count(interaction.user.id)

    is_new_flavour, discovered_count = add_tasted_flavour(interaction.user.id, flavor)
    total_flavours = get_total_flavours()
    bean_image_url = random.choice(BEAN_IMAGE_URLS)

    status = "unfamiliar tasting" if is_new_flavour else "familiar tasting"
    bean_word = "bean" if remaining == 1 else "beans"

    embed = discord.Embed(
        description=(
            f"**{interaction.user.display_name} ate a {status} bean…**\n\n"
            f"🍬 **{flavor.upper()}** 🍬\n\n"
            f"`{discovered_count}/{total_flavours} discovered • {remaining} {bean_word} left`"
        ),
        color=discord.Color.green(),
    )
    embed.set_thumbnail(url=bean_image_url)

    await interaction.response.send_message(embed=embed)

# =========================================================
# ADMIN COMMANDS
# =========================================================
@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_test",
    description="Spawn Dobby in the current channel for testing.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
async def dobby_test(interaction: discord.Interaction) -> None:
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("Use this in a text channel.", ephemeral=True)
        return

    _, message = await start_dobby_event(channel)
    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_start",
    description="Start Dobby's random spawn loop.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
async def dobby_start(interaction: discord.Interaction) -> None:
    global spawn_loop_task

    if spawn_loop_task is not None and not spawn_loop_task.done():
        await interaction.response.send_message(
            "Dobby's random spawn loop is already running.",
            ephemeral=True,
        )
        return

    spawn_loop_task = asyncio.create_task(random_spawn_loop())
    await interaction.response.send_message(
        "Dobby's random spawn loop has started.",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_stop",
    description="Stop Dobby's random spawn loop.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
async def dobby_stop(interaction: discord.Interaction) -> None:
    global spawn_loop_task

    if spawn_loop_task is None or spawn_loop_task.done():
        await interaction.response.send_message(
            "Dobby's random spawn loop is not currently running.",
            ephemeral=True,
        )
        return

    spawn_loop_task.cancel()
    spawn_loop_task = None

    await interaction.response.send_message(
        "Dobby's random spawn loop has stopped.",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_cleanup",
    description="Clear all channels where Dobby is allowed to randomly appear.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
async def dobby_cleanup(interaction: discord.Interaction) -> None:
    removed_count = clear_allowed_channels()

    await interaction.response.send_message(
        f"Removed **{removed_count}** allowed channel(s). Dobby now has nowhere to randomly appear.",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_allow",
    description="Allow Dobby to randomly appear in a selected channel.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
@app_commands.describe(channel="The channel to allow for random Dobby spawns")
async def dobby_allow(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    allow_channel(channel.id)
    await interaction.response.send_message(
        f"Dobby is now allowed to appear in {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_disallow",
    description="Stop Dobby from randomly appearing in a selected channel.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
@app_commands.describe(channel="The channel to remove from random Dobby spawns")
async def dobby_disallow(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    disallow_channel(channel.id)
    await interaction.response.send_message(
        f"Dobby will no longer randomly appear in {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="give_beans",
    description="Give a user beans.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
@app_commands.describe(user="The user to receive beans", amount="How many beans to give")
async def give_beans(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: app_commands.Range[int, 1, 100000],
) -> None:
    new_total = add_beans(user.id, amount)
    bean_word = "Bean" if amount == 1 else "Beans"
    total_word = "Bean" if new_total == 1 else "Beans"

    await interaction.response.send_message(
        f"Gave **{amount} Bertie Bott’s Every Flavoured {bean_word}** to {user.mention}. "
        f"They now have **{new_total} Bertie Bott’s Every Flavoured {total_word}**."
    )

# =========================================================
# ERROR HANDLER
# =========================================================
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.CheckFailure):
        if interaction.response.is_done():
            await interaction.followup.send(str(error), ephemeral=True)
        else:
            await interaction.response.send_message(str(error), ephemeral=True)
        return

    if isinstance(error, app_commands.CommandNotFound):
        log.warning("Ignored stale command interaction: %s", error)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "That command is outdated. Please refresh Discord and try again.",
                ephemeral=True,
            )
        return

    log.exception("Unhandled app command error", exc_info=error)

    if interaction.response.is_done():
        await interaction.followup.send(
            "Something went wrong while running that command.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "Something went wrong while running that command.",
            ephemeral=True,
        )

# =========================================================
# READY
# =========================================================
@bot.event
async def on_ready() -> None:
    synced = await bot.tree.sync(guild=TEST_GUILD)

    log.info("Logged in as %s (%s)", bot.user, bot.user.id if bot.user else "unknown")
    log.info("Synced %s guild slash commands to guild %s.", len(synced), GUILD_ID)
    log.info("TEST_MODE=%s EVENT_DURATION_SECONDS=%s", TEST_MODE, EVENT_DURATION_SECONDS)
    log.info("Random Dobby spawn loop is controlled via /dobby_start and /dobby_stop.")

# =========================================================
# MAIN
# =========================================================
def main() -> None:
    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()