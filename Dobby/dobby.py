import asyncio
import json
import logging
import os
import random
import sqlite3
import time
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks
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

SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_DIR = SCRIPT_DIR.parent

DB_FILE = SCRIPT_DIR / "bot_data.db"
FLAVORS_FILE = SCRIPT_DIR / "flavors.json"


def resolve_beans_dir() -> Path:
    candidates = [
        SCRIPT_DIR / "Beans",
        PARENT_DIR / "Beans",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    raise RuntimeError(
        "Could not find a Beans folder. Expected either:\n"
        f"- {SCRIPT_DIR / 'Beans'}\n"
        f"- {PARENT_DIR / 'Beans'}"
    )


BEANS_DIR = resolve_beans_dir()

# =========================================================
# SETTINGS
# =========================================================
MAX_PARTICIPANTS = 5
EVENT_DURATION_SECONDS = 20 * 60

MIN_SPAWN_SECONDS = 2 * 60 * 60
MAX_SPAWN_SECONDS = 7 * 60 * 60
SPAWN_CHECK_INTERVAL_SECONDS = 60

EVENT_TITLE = "\"Would Master kindly give Dobby another sock?\""
EVENT_DESCRIPTION = (
    "Dobby has appeared and is in desperate need of some socks.\n"
    "Each person may click exactly one button. Make sure you give him his favourite one...!"
)

EVENT_GIF_URLS = [
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Dobby_bed.gif?raw=true"
]

SOCK_EMOJI_POOL = [
    "<:Sock6:1485677804581421128>",
    "<:Sock10:1485676309253459988>",
    "<:Sock1:1485675915584344124>",
    "<:Sock2:1485675913499771061>",
    "<:Sock3:1485675911935168522>",
    "<:Sock4:1485675910464244080>",
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
# BEAN IMAGE HELPERS
# =========================================================
last_bean_image_path: Path | None = None


def get_all_bean_image_paths() -> list[Path]:
    image_paths = sorted(
        [p for p in BEANS_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".png"]
    )

    if not image_paths:
        raise RuntimeError(f"No .png files found in Beans folder: {BEANS_DIR}")

    return image_paths


def get_random_bean_image_path() -> Path:
    global last_bean_image_path

    image_paths = get_all_bean_image_paths()

    if len(image_paths) == 1:
        chosen = image_paths[0]
        last_bean_image_path = chosen
        return chosen

    available = [p for p in image_paths if p != last_bean_image_path]
    chosen = random.choice(available)
    last_bean_image_path = chosen
    return chosen

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

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dobby_state (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                enabled INTEGER NOT NULL DEFAULT 0,
                clock_reset_ts INTEGER,
                last_spawn_ts INTEGER,
                last_spawn_channel_id TEXT
            )
            """
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO dobby_state (
                singleton,
                enabled,
                clock_reset_ts,
                last_spawn_ts,
                last_spawn_channel_id
            )
            VALUES (1, 0, NULL, NULL, NULL)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dobby_ping_subscriptions (
                channel_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                PRIMARY KEY (channel_id, user_id)
            )
            """
        )

        conn.commit()


init_db()
get_flavors()
get_all_bean_image_paths()

# =========================================================
# BEAN / INVENTORY HELPERS
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

# =========================================================
# DOBBY CHANNEL / STATE / PING HELPERS
# =========================================================
def get_allowed_channels() -> set[int]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT channel_id FROM allowed_channels").fetchall()
    return {int(row["channel_id"]) for row in rows}


def allow_channel(channel_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO allowed_channels (channel_id) VALUES (?)",
            (str(channel_id),),
        )
        conn.commit()


def disallow_channel(channel_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM allowed_channels WHERE channel_id = ?",
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


def get_dobby_state() -> dict[str, Any]:
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT enabled, clock_reset_ts, last_spawn_ts, last_spawn_channel_id
            FROM dobby_state
            WHERE singleton = 1
            """
        ).fetchone()

    if row is None:
        raise RuntimeError("dobby_state row missing.")

    return {
        "enabled": bool(row["enabled"]),
        "clock_reset_ts": int(row["clock_reset_ts"]) if row["clock_reset_ts"] is not None else None,
        "last_spawn_ts": int(row["last_spawn_ts"]) if row["last_spawn_ts"] is not None else None,
        "last_spawn_channel_id": int(row["last_spawn_channel_id"]) if row["last_spawn_channel_id"] is not None else None,
    }


def set_dobby_enabled(enabled: bool, reset_clock: bool = False) -> None:
    now = int(time.time())

    with get_db_connection() as conn:
        if reset_clock:
            conn.execute(
                """
                UPDATE dobby_state
                SET enabled = ?, clock_reset_ts = ?
                WHERE singleton = 1
                """,
                (1 if enabled else 0, now),
            )
        else:
            conn.execute(
                """
                UPDATE dobby_state
                SET enabled = ?
                WHERE singleton = 1
                """,
                (1 if enabled else 0,),
            )
        conn.commit()


def reset_dobby_clock() -> None:
    now = int(time.time())
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE dobby_state
            SET clock_reset_ts = ?
            WHERE singleton = 1
            """,
            (now,),
        )
        conn.commit()


def register_dobby_spawn(channel_id: int) -> None:
    now = int(time.time())
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE dobby_state
            SET clock_reset_ts = ?, last_spawn_ts = ?, last_spawn_channel_id = ?
            WHERE singleton = 1
            """,
            (now, now, str(channel_id)),
        )
        conn.commit()


def add_dobby_ping_subscription(channel_id: int, user_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO dobby_ping_subscriptions (channel_id, user_id)
            VALUES (?, ?)
            """,
            (str(channel_id), str(user_id)),
        )
        conn.commit()


def remove_dobby_ping_subscription(channel_id: int, user_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            DELETE FROM dobby_ping_subscriptions
            WHERE channel_id = ? AND user_id = ?
            """,
            (str(channel_id), str(user_id)),
        )
        conn.commit()


def get_dobby_ping_user_ids(channel_id: int) -> list[int]:
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT user_id
            FROM dobby_ping_subscriptions
            WHERE channel_id = ?
            """,
            (str(channel_id),),
        ).fetchall()

    return [int(row["user_id"]) for row in rows]

# =========================================================
# GENERAL HELPERS
# =========================================================
def utc_now_ts() -> int:
    return int(time.time())


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "n/a"

    if seconds < 0:
        seconds = 0

    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)

    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or hours:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)


def format_discord_timestamp(ts: int | None) -> str:
    if ts is None:
        return "Never"
    return f"<t:{ts}:F> (<t:{ts}:R>)"


def compute_spawn_probability(elapsed_seconds: int | None) -> float:
    if elapsed_seconds is None:
        return 0.0
    if elapsed_seconds < MIN_SPAWN_SECONDS:
        return 0.0
    if elapsed_seconds >= MAX_SPAWN_SECONDS:
        return 1.0

    window = MAX_SPAWN_SECONDS - MIN_SPAWN_SECONDS
    progressed = elapsed_seconds - MIN_SPAWN_SECONDS
    return progressed / window


def safe_partial_or_fallback(
    bot: commands.Bot,
    emoji_str: str,
) -> discord.PartialEmoji | str:
    parsed = discord.PartialEmoji.from_str(emoji_str)

    if parsed.id is None:
        return emoji_str

    real_emoji = bot.get_emoji(parsed.id)
    if real_emoji is not None:
        return real_emoji

    return "🧦"

# =========================================================
# EVENT STATE
# =========================================================
active_events: dict[int, "DobbyEvent"] = {}
spawn_lock = asyncio.Lock()

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
        self._event_lock = asyncio.Lock()

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
            member.id,
            sock_emoji,
            rank,
            reward,
            self.channel_id,
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

        ping_user_ids = get_dobby_ping_user_ids(self.channel_id)
        if ping_user_ids:
            mention_text = " ".join(f"<@{uid}>" for uid in ping_user_ids)
            try:
                await self.channel.send(
                    f"{mention_text} Dobby has appeared in {self.channel.mention}!",
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            except discord.HTTPException:
                log.exception("Failed to send Dobby ping message in channel=%s", self.channel_id)

        log.info(
            "Dobby event sent: guild=%s channel=%s message=%s",
            self.guild_id,
            self.channel_id,
            self.message.id,
        )

        self.end_task = asyncio.create_task(self._auto_end())

    async def refresh_message(self) -> None:
        if not self.active or self.message is None or self.view is None:
            return

        try:
            await self.message.edit(embed=self.build_embed(), view=self.view)
        except discord.NotFound:
            log.warning("Dobby message vanished in channel=%s. Ending event.", self.channel_id)
            await self.end(reason="message_deleted")
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
        async with self._event_lock:
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
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    log.exception("Failed to edit finished Dobby message in channel=%s", self.channel_id)

# =========================================================
# BUTTON VIEW
# =========================================================
class SockButton(discord.ui.Button["DobbyView"]):
    def __init__(self, sock_emoji: str, index: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=safe_partial_or_fallback(bot, sock_emoji),
            custom_id=f"dobby_button_sock_{index}",
        )
        self.sock_emoji = sock_emoji

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            if interaction.response.is_done():
                await interaction.followup.send("This button is not available right now.", ephemeral=True)
            else:
                await interaction.response.send_message("This button is not available right now.", ephemeral=True)
            return

        await self.view.handle_press(interaction, self.sock_emoji)


class DobbyView(discord.ui.View):
    def __init__(self, event: DobbyEvent):
        super().__init__(timeout=None)
        self.event = event
        self._press_lock = asyncio.Lock()

        for index, sock_emoji in enumerate(event.socks, start=1):
            self.add_item(SockButton(sock_emoji, index))

    async def handle_press(self, interaction: discord.Interaction, sock_emoji: str) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        async with self._press_lock:
            if not self.event.active:
                await interaction.followup.send(
                    "Too late — Dobby has already left.",
                    ephemeral=True,
                )
                return

            if self.event.has_participated(interaction.user.id):
                await interaction.followup.send(
                    "You already interacted with this Dobby event.",
                    ephemeral=True,
                )
                return

            rank, reward = self.event.add_participant(interaction.user, sock_emoji)
            total = get_bean_count(interaction.user.id)
            bean_word = "Bean" if reward == 1 else "Beans"

            await self.event.refresh_message()

            await interaction.followup.send(
                f"{DOBBY_RESPONSE_BY_RANK[rank]}\n\n"
                f"You received **{reward} Bertie Bott’s Every Flavoured {bean_word}**.\n"
                f"You now have **{total} Bertie Bott’s Every Flavoured Beans**.",
                ephemeral=True,
            )

            if self.event.participant_count() >= MAX_PARTICIPANTS:
                await self.event.end(reason="max_participants")

# =========================================================
# BOT CLASS
# =========================================================
class DobbyBot(commands.Bot):
    async def setup_hook(self) -> None:
        if not dobby_supervisor.is_running():
            dobby_supervisor.start()

        synced = await self.tree.sync(guild=TEST_GUILD)
        log.info("Synced %s guild slash commands to guild %s.", len(synced), GUILD_ID)


bot = DobbyBot(command_prefix="!", intents=intents)

# =========================================================
# EVENT HELPERS
# =========================================================
def get_single_guild() -> discord.Guild | None:
    return bot.get_guild(GUILD_ID)


def validate_sock_emoji_pool() -> None:
    unavailable: list[str] = []

    for emoji_str in SOCK_EMOJI_POOL:
        parsed = discord.PartialEmoji.from_str(emoji_str)
        if parsed.id is not None and bot.get_emoji(parsed.id) is None:
            unavailable.append(emoji_str)

    if unavailable:
        log.warning(
            "Some sock emojis are not available to the bot and will fall back to 🧦: %s",
            unavailable,
        )


def prune_stale_active_events() -> None:
    stale_channel_ids: list[int] = []

    for channel_id, event in active_events.items():
        if not event.active:
            stale_channel_ids.append(channel_id)
            continue

        if event.message is None:
            stale_channel_ids.append(channel_id)
            continue

    for channel_id in stale_channel_ids:
        active_events.pop(channel_id, None)

    if stale_channel_ids:
        log.warning("Pruned stale active events: %s", stale_channel_ids)


def get_valid_allowed_channels() -> list[discord.TextChannel]:
    guild = get_single_guild()
    if guild is None:
        return []

    me = guild.me
    if me is None:
        return []

    channels: list[discord.TextChannel] = []

    for channel_id in get_allowed_channels():
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            continue
        if channel.id in active_events:
            continue

        perms = channel.permissions_for(me)
        if not perms.view_channel or not perms.send_messages:
            continue

        channels.append(channel)

    return channels


async def start_dobby_event(channel: discord.TextChannel) -> tuple[bool, str]:
    async with spawn_lock:
        state = get_dobby_state()

        if not state["enabled"]:
            return False, "Dobby is currently not started."

        if channel.id not in get_allowed_channels():
            return False, "This channel is not allowed for Dobby."

        prune_stale_active_events()

        if active_events:
            return False, "Another Dobby event is already active."

        event = DobbyEvent(channel)
        active_events[channel.id] = event

        try:
            await event.send()
            register_dobby_spawn(channel.id)
            return True, "Dobby has appeared."
        except Exception:
            active_events.pop(channel.id, None)
            log.exception("Failed to send Dobby event in channel=%s", channel.id)
            return False, "Dobby failed to appear because the event message could not be sent."


async def end_all_active_events(reason: str) -> int:
    events = list(active_events.values())
    for event in events:
        await event.end(reason=reason)
    return len(events)

# =========================================================
# RANDOM SUPERVISOR LOOP
# =========================================================
@tasks.loop(seconds=SPAWN_CHECK_INTERVAL_SECONDS)
async def dobby_supervisor() -> None:
    await bot.wait_until_ready()

    try:
        async with spawn_lock:
            state = get_dobby_state()

            if not state["enabled"]:
                return

            prune_stale_active_events()

            if active_events:
                return

            valid_channels = get_valid_allowed_channels()
            if not valid_channels:
                return

            now = utc_now_ts()
            clock_reset_ts = state["clock_reset_ts"]

            if clock_reset_ts is None:
                reset_dobby_clock()
                return

            elapsed = now - clock_reset_ts
            probability = compute_spawn_probability(elapsed)

            log.info(
                "Dobby supervisor tick | enabled=%s | allowed=%s | elapsed=%s | probability=%.4f",
                state["enabled"],
                len(valid_channels),
                elapsed,
                probability,
            )

            if probability <= 0.0:
                return

            should_spawn = probability >= 1.0 or (random.random() <= probability)
            if not should_spawn:
                return

            channel = random.choice(valid_channels)

        ok, message = await start_dobby_event(channel)
        log.info("Spawn attempt in #%s: %s", channel.name, message)

    except Exception:
        log.exception("Unexpected error in dobby_supervisor.")


@dobby_supervisor.before_loop
async def before_dobby_supervisor() -> None:
    await bot.wait_until_ready()

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

    bean_image_path = get_random_bean_image_path()
    bean_file = discord.File(bean_image_path, filename=bean_image_path.name)

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
    embed.set_thumbnail(url=f"attachment://{bean_image_path.name}")

    await interaction.response.send_message(embed=embed, file=bean_file)

# =========================================================
# ADMIN COMMANDS
# =========================================================
@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_start",
    description="Start Dobby activity and reset his timer to zero.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
async def dobby_start(interaction: discord.Interaction) -> None:
    set_dobby_enabled(True, reset_clock=True)

    await interaction.response.send_message(
        "Dobby has been **started**.\n"
        "His timer has been reset to zero and he may begin appearing again in allowed channels.",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_stop",
    description="Stop Dobby activity and end all active Dobby events. Allowed channels stay.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
async def dobby_stop(interaction: discord.Interaction) -> None:
    ended = await end_all_active_events(reason="stopped")
    set_dobby_enabled(False, reset_clock=True)

    await interaction.response.send_message(
        f"Dobby has been **stopped**.\n"
        f"Ended **{ended}** active event(s).\n"
        f"Allowed channels were kept.",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_reset",
    description="Stop Dobby, end all events, and remove all allowed channels.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
async def dobby_reset(interaction: discord.Interaction) -> None:
    ended = await end_all_active_events(reason="reset")
    removed_channels = clear_allowed_channels()
    set_dobby_enabled(False, reset_clock=True)

    await interaction.response.send_message(
        f"Dobby has been **fully reset**.\n"
        f"Ended **{ended}** active event(s).\n"
        f"Removed **{removed_channels}** allowed channel(s).",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_allow",
    description="Allow Dobby to appear in a selected channel.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
@app_commands.describe(channel="The channel to allow for Dobby")
async def dobby_allow(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    allow_channel(channel.id)

    await interaction.response.send_message(
        f"Dobby is now allowed to appear in {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_disallow",
    description="Disallow Dobby from appearing in a selected channel.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
@app_commands.describe(channel="The channel to remove from Dobby spawns")
async def dobby_disallow(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    disallow_channel(channel.id)

    was_active = channel.id in active_events
    if was_active:
        await active_events[channel.id].end(reason="disallowed")

    await interaction.response.send_message(
        f"Dobby will no longer appear in {channel.mention}."
        + (" An active event there was also ended." if was_active else ""),
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_test",
    description="Trigger Dobby immediately in this channel if allowed and started.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
async def dobby_test(interaction: discord.Interaction) -> None:
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("Use this in a text channel.", ephemeral=True)
        return

    state = get_dobby_state()
    if not state["enabled"]:
        await interaction.response.send_message(
            "Dobby is not started. Use `/dobby_start` first.",
            ephemeral=True,
        )
        return

    if channel.id not in get_allowed_channels():
        await interaction.response.send_message(
            "This channel is not allowed for Dobby. Use `/dobby_allow` first.",
            ephemeral=True,
        )
        return

    ok, message = await start_dobby_event(channel)
    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_pingme",
    description="Set a user to be pinged when Dobby appears in a specific channel.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
@app_commands.describe(
    channel="The allowed channel to watch for Dobby",
    user="The user to ping when Dobby appears there",
)
async def dobby_pingme(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    user: discord.Member,
) -> None:
    if channel.id not in get_allowed_channels():
        await interaction.response.send_message(
            f"{channel.mention} is not currently an allowed Dobby channel.",
            ephemeral=True,
        )
        return

    add_dobby_ping_subscription(channel.id, user.id)

    await interaction.response.send_message(
        f"{user.mention} will now be pinged when Dobby appears in {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_unpingme",
    description="Remove a Dobby ping subscription for a user in a specific channel.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
@app_commands.describe(
    channel="The channel to stop watching",
    user="The user to stop pinging",
)
async def dobby_unpingme(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    user: discord.Member,
) -> None:
    remove_dobby_ping_subscription(channel.id, user.id)

    await interaction.response.send_message(
        f"{user.mention} will no longer be pinged when Dobby appears in {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(
    guild=TEST_GUILD,
    name="dobby_stats",
    description="Show Dobby state, allowed channels, last appearance and current probability.",
)
@ADMIN_COMMAND_PERMS
@GUILD_ONLY
@admin_only()
async def dobby_stats(interaction: discord.Interaction) -> None:
    prune_stale_active_events()

    state = get_dobby_state()
    allowed_ids = sorted(get_allowed_channels())
    guild = interaction.guild

    now = utc_now_ts()
    elapsed = None
    probability = 0.0

    if state["clock_reset_ts"] is not None:
        elapsed = now - state["clock_reset_ts"]
        probability = compute_spawn_probability(elapsed)

    allowed_mentions: list[str] = []
    for cid in allowed_ids:
        ch = guild.get_channel(cid) if guild else None
        allowed_mentions.append(ch.mention if isinstance(ch, discord.TextChannel) else f"`{cid}`")

    last_channel_text = "Never"
    if state["last_spawn_channel_id"] is not None and guild is not None:
        ch = guild.get_channel(state["last_spawn_channel_id"])
        last_channel_text = ch.mention if isinstance(ch, discord.TextChannel) else f"`{state['last_spawn_channel_id']}`"

    current_active_channels: list[str] = []
    for cid in active_events:
        ch = guild.get_channel(cid) if guild else None
        current_active_channels.append(ch.mention if isinstance(ch, discord.TextChannel) else f"`{cid}`")

    ping_lines: list[str] = []
    for cid in allowed_ids:
        user_ids = get_dobby_ping_user_ids(cid)
        if not user_ids:
            continue

        ch = guild.get_channel(cid) if guild else None
        ch_name = ch.mention if isinstance(ch, discord.TextChannel) else f"`{cid}`"
        mentions = " ".join(f"<@{uid}>" for uid in user_ids)
        ping_lines.append(f"{ch_name}: {mentions}")

    embed = discord.Embed(
        title="Dobby Stats",
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="Active",
        value="Yes" if state["enabled"] else "No",
        inline=True,
    )
    embed.add_field(
        name="Allowed channels",
        value="\n".join(allowed_mentions) if allowed_mentions else "None",
        inline=False,
    )
    embed.add_field(
        name="Current active event channels",
        value="\n".join(current_active_channels) if current_active_channels else "None",
        inline=False,
    )
    embed.add_field(
        name="Last appearance time",
        value=format_discord_timestamp(state["last_spawn_ts"]),
        inline=False,
    )
    embed.add_field(
        name="Last appearance channel",
        value=last_channel_text,
        inline=False,
    )
    embed.add_field(
        name="Elapsed since last trigger reset",
        value=format_duration(elapsed),
        inline=True,
    )
    embed.add_field(
        name="Current spawn probability",
        value=f"{probability * 100:.2f}%",
        inline=True,
    )
    embed.add_field(
        name="Ping subscriptions",
        value="\n".join(ping_lines) if ping_lines else "None",
        inline=False,
    )
    embed.add_field(
        name="Spawn model",
        value=(
            f"0% before **{MIN_SPAWN_SECONDS // 3600}h**, "
            f"then ramps up linearly to **100% by {MAX_SPAWN_SECONDS // 3600}h**.\n"
            f"Checked every **{SPAWN_CHECK_INTERVAL_SECONDS} seconds**."
        ),
        inline=False,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


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
    log.info("Logged in as %s (%s)", bot.user, bot.user.id if bot.user else "unknown")
    log.info("Dobby supervisor running: %s", dobby_supervisor.is_running())
    log.info("Beans folder resolved to: %s", BEANS_DIR)
    validate_sock_emoji_pool()
    prune_stale_active_events()

# =========================================================
# MAIN
# =========================================================
def main() -> None:
    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()