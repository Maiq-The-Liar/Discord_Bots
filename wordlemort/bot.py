import os
import io
import json
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# =========================================================
# CONFIG
# =========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

WORDS_FILE = Path("hp_words.json")
DB_FILE = Path("hp_wordle.db")

MAX_ROWS = 5
GAME_TIMEOUT_SECONDS = 900

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


# =========================================================
# DATABASE
# =========================================================

conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row

conn.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS daily_posts (
    day_key TEXT PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS game_results (
    day_key TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    solved INTEGER NOT NULL DEFAULT 0,
    tries INTEGER NOT NULL DEFAULT 0,
    guesses_json TEXT NOT NULL DEFAULT '[]',
    solved_at TEXT,
    PRIMARY KEY (day_key, user_id)
)
""")

conn.commit()


# =========================================================
# SETTINGS HELPERS
# =========================================================

def get_setting(key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn.execute("""
    INSERT INTO settings(key, value)
    VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()


def delete_setting(key: str):
    conn.execute("DELETE FROM settings WHERE key = ?", (key,))
    conn.commit()


# =========================================================
# WORDS
# =========================================================

def load_words():
    if not WORDS_FILE.exists():
        raise RuntimeError("hp_words.json not found")

    raw = json.loads(WORDS_FILE.read_text(encoding="utf-8"))
    words = []

    for word in raw:
        word = str(word).strip().lower()
        if word.isalpha() and 5 <= len(word) <= 10:
            words.append(word)

    words = sorted(set(words))

    if not words:
        raise RuntimeError("No valid 5-10 letter words found in hp_words.json")

    return words


WORDS = load_words()


def get_day_key(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def get_daily_word(day_key: str) -> str:
    digest = hashlib.sha256(day_key.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(WORDS)
    return WORDS[index]


# =========================================================
# GAME LOGIC
# =========================================================

def score_guess(guess: str, target: str):
    result = ["absent"] * len(target)
    remaining = list(target)

    # Greens first
    for i, ch in enumerate(guess):
        if ch == target[i]:
            result[i] = "correct"
            remaining[i] = None

    # Yellows second
    for i, ch in enumerate(guess):
        if result[i] == "correct":
            continue
        if ch in remaining:
            result[i] = "present"
            remaining[remaining.index(ch)] = None

    return result


# =========================================================
# PNG GENERATION
# =========================================================

def render_board_png(target: str, guesses: list[str]) -> bytes:
    cols = len(target)
    rows = MAX_ROWS

    cell_size = 70
    gap = 8
    padding = 24

    width = padding * 2 + cols * cell_size + (cols - 1) * gap
    height = padding * 2 + rows * cell_size + (rows - 1) * gap

    bg_color = (18, 18, 19)
    empty_border = (90, 90, 95)
    absent_color = (58, 58, 60)
    present_color = (181, 159, 59)
    correct_color = (83, 141, 78)
    text_color = (255, 255, 255)

    image = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    except Exception:
        font = ImageFont.load_default()

    for row in range(rows):
        y = padding + row * (cell_size + gap)

        if row < len(guesses):
            guess = guesses[row]
            states = score_guess(guess, target)
        else:
            guess = None
            states = None

        for col in range(cols):
            x = padding + col * (cell_size + gap)
            rect = [x, y, x + cell_size, y + cell_size]

            if guess:
                state = states[col]
                if state == "correct":
                    fill = correct_color
                elif state == "present":
                    fill = present_color
                else:
                    fill = absent_color

                draw.rounded_rectangle(rect, radius=8, fill=fill)

                letter = guess[col].upper()
                bbox = draw.textbbox((0, 0), letter, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                tx = x + (cell_size - tw) / 2
                ty = y + (cell_size - th) / 2 - 2
                draw.text((tx, ty), letter, fill=text_color, font=font)
            else:
                draw.rounded_rectangle(rect, radius=8, outline=empty_border, width=2)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read()


# =========================================================
# DATABASE HELPERS
# =========================================================

def get_daily_post(day_key: str):
    return conn.execute(
        "SELECT * FROM daily_posts WHERE day_key = ?",
        (day_key,)
    ).fetchone()


def save_daily_post(day_key: str, channel_id: int, message_id: int, word: str):
    conn.execute("""
    INSERT INTO daily_posts(day_key, channel_id, message_id, word, created_at)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(day_key) DO UPDATE SET
        channel_id = excluded.channel_id,
        message_id = excluded.message_id,
        word = excluded.word,
        created_at = excluded.created_at
    """, (
        day_key,
        channel_id,
        message_id,
        word,
        datetime.now(timezone.utc).isoformat()
    ))
    conn.commit()


def delete_daily_post(day_key: str):
    conn.execute("DELETE FROM daily_posts WHERE day_key = ?", (day_key,))
    conn.commit()


def delete_game_results(day_key: str):
    conn.execute("DELETE FROM game_results WHERE day_key = ?", (day_key,))
    conn.commit()


def get_result(day_key: str, user_id: int):
    return conn.execute(
        "SELECT * FROM game_results WHERE day_key = ? AND user_id = ?",
        (day_key, user_id)
    ).fetchone()


def upsert_result(day_key: str, user_id: int, username: str, solved: int, tries: int, guesses: list[str], solved_at: str | None):
    conn.execute("""
    INSERT INTO game_results(day_key, user_id, username, solved, tries, guesses_json, solved_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(day_key, user_id) DO UPDATE SET
        username = excluded.username,
        solved = excluded.solved,
        tries = excluded.tries,
        guesses_json = excluded.guesses_json,
        solved_at = excluded.solved_at
    """, (
        day_key,
        user_id,
        username,
        solved,
        tries,
        json.dumps(guesses),
        solved_at
    ))
    conn.commit()


def get_leaderboard(day_key: str, limit: int = 10):
    return conn.execute("""
    SELECT username, tries, solved_at
    FROM game_results
    WHERE day_key = ? AND solved = 1
    ORDER BY tries ASC, solved_at ASC
    LIMIT ?
    """, (day_key, limit)).fetchall()


# =========================================================
# EMBEDS
# =========================================================

def build_leaderboard_text(day_key: str) -> str:
    rows = get_leaderboard(day_key)

    if not rows:
        return "Nobody solved today's word yet."

    lines = []
    for i, row in enumerate(rows, start=1):
        lines.append(f"**{i}.** {row['username']} — {row['tries']} tries")
    return "\n".join(lines)


def make_daily_embed(day_key: str, word: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚡ Daily HP Wordle — {day_key}",
        description=(
            "Guess the Harry Potter word of the day.\n"
            f"Today's word has **{len(word)}** letters.\n"
            f"You get **{MAX_ROWS}** tries."
        ),
        color=discord.Color.blurple()
    )
    embed.add_field(name="Leaderboard", value=build_leaderboard_text(day_key), inline=False)
    embed.set_footer(text="Click the button below to start your private game.")
    return embed


def make_private_embed(day_key: str, target: str, guesses: list[str], solved: bool, lost: bool) -> discord.Embed:
    embed = discord.Embed(
        title=f"🪄 Your HP Wordle — {day_key}",
        description=f"Word length: **{len(target)}** | Tries: **{len(guesses)}/{MAX_ROWS}**",
        color=discord.Color.dark_teal()
    )

    if solved:
        embed.add_field(name="Status", value=f"✅ Solved in **{len(guesses)}** tries.", inline=False)
    elif lost:
        embed.add_field(name="Status", value=f"❌ Out of tries. The word was **{target.upper()}**.", inline=False)
    else:
        embed.add_field(name="Status", value="Press **Guess** to enter a word.", inline=False)

    return embed


# =========================================================
# UI
# =========================================================

class GuessModal(discord.ui.Modal, title="Enter your guess"):
    guess_input = discord.ui.TextInput(
        label="Guess",
        placeholder="Type your Harry Potter word",
        required=True,
        min_length=5,
        max_length=10,
    )

    def __init__(self, game_view: "PrivateGameView"):
        super().__init__()
        self.game_view = game_view

    async def on_submit(self, interaction: discord.Interaction):
        guess = str(self.guess_input.value).strip().lower()
        await self.game_view.handle_guess(interaction, guess)


class PrivateGameView(discord.ui.View):
    def __init__(self, user_id: int, day_key: str, target: str):
        super().__init__(timeout=GAME_TIMEOUT_SECONDS)
        self.user_id = user_id
        self.day_key = day_key
        self.target = target

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your game.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Guess", style=discord.ButtonStyle.primary)
    async def guess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = get_result(self.day_key, self.user_id)
        guesses = json.loads(row["guesses_json"]) if row else []
        solved = bool(row["solved"]) if row else False

        if solved or len(guesses) >= MAX_ROWS:
            await interaction.response.send_message("Your game is already finished for this challenge.", ephemeral=True)
            return

        await interaction.response.send_modal(GuessModal(self))

    async def handle_guess(self, interaction: discord.Interaction, guess: str):
        if len(guess) != len(self.target):
            await interaction.response.send_message(
                f"Your guess must be exactly **{len(self.target)}** letters.",
                ephemeral=True
            )
            return

        if not guess.isalpha():
            await interaction.response.send_message(
                "Your guess can only contain letters.",
                ephemeral=True
            )
            return

        row = get_result(self.day_key, self.user_id)
        guesses = json.loads(row["guesses_json"]) if row else []

        if len(guesses) >= MAX_ROWS:
            await interaction.response.send_message("You have no tries left for this challenge.", ephemeral=True)
            return

        guesses.append(guess)

        solved = int(guess == self.target)
        lost = len(guesses) >= MAX_ROWS and not solved
        solved_at = datetime.now(timezone.utc).isoformat() if solved else None

        upsert_result(
            self.day_key,
            self.user_id,
            interaction.user.display_name,
            solved,
            len(guesses),
            guesses,
            solved_at
        )

        png_bytes = render_board_png(self.target, guesses)
        file = discord.File(io.BytesIO(png_bytes), filename="board.png")
        embed = make_private_embed(self.day_key, self.target, guesses, bool(solved), bool(lost))

        new_view = None if (solved or lost) else PrivateGameView(self.user_id, self.day_key, self.target)

        await interaction.response.edit_message(
            embed=embed,
            attachments=[file],
            view=new_view
        )

        await refresh_daily_post(self.day_key)


class StartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Start Game", style=discord.ButtonStyle.success, custom_id="hpwordle:start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_day_key = get_current_active_day_key()
        target = get_daily_word(current_day_key)

        row = get_result(current_day_key, interaction.user.id)

        if row is None:
            upsert_result(
                day_key=current_day_key,
                user_id=interaction.user.id,
                username=interaction.user.display_name,
                solved=0,
                tries=0,
                guesses=[],
                solved_at=None
            )
            guesses = []
            solved = False
        else:
            guesses = json.loads(row["guesses_json"])
            solved = bool(row["solved"])

        lost = len(guesses) >= MAX_ROWS and not solved

        png_bytes = render_board_png(target, guesses)
        file = discord.File(io.BytesIO(png_bytes), filename="board.png")
        embed = make_private_embed(current_day_key, target, guesses, solved, lost)
        view = None if (solved or lost) else PrivateGameView(interaction.user.id, current_day_key, target)

        await interaction.response.send_message(
            embed=embed,
            file=file,
            view=view,
            ephemeral=True
        )


# =========================================================
# ACTIVE CHALLENGE CONTROL
# =========================================================

def get_current_active_day_key() -> str:
    forced_day_key = get_setting("active_day_key")
    if forced_day_key:
        return forced_day_key
    return get_day_key()


async def safe_delete_message(channel_id: int, message_id: int):
    try:
        channel = bot.get_channel(channel_id)
        if channel is None:
            channel = await bot.fetch_channel(channel_id)

        message = await channel.fetch_message(message_id)
        await message.delete()
    except Exception:
        pass


async def create_new_challenge(channel_id: int, day_key: str):
    word = get_daily_word(day_key)

    channel = bot.get_channel(channel_id)
    if channel is None:
        channel = await bot.fetch_channel(channel_id)

    embed = make_daily_embed(day_key, word)
    message = await channel.send(embed=embed, view=StartView())

    save_daily_post(day_key, channel.id, message.id, word)
    set_setting("wordle_channel_id", str(channel.id))
    set_setting("active_day_key", day_key)


async def reset_and_create_new_challenge(channel_id: int):
    old_day_key = get_setting("active_day_key")

    if old_day_key:
        old_post = get_daily_post(old_day_key)
        if old_post:
            await safe_delete_message(old_post["channel_id"], old_post["message_id"])
            delete_daily_post(old_day_key)

    new_day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
    delete_game_results(new_day_key)
    await create_new_challenge(channel_id, new_day_key)


async def refresh_daily_post(day_key: str):
    post = get_daily_post(day_key)
    if not post:
        return

    channel = bot.get_channel(post["channel_id"])
    if channel is None:
        channel = await bot.fetch_channel(post["channel_id"])

    try:
        message = await channel.fetch_message(post["message_id"])
    except discord.NotFound:
        return

    embed = make_daily_embed(day_key, post["word"])
    await message.edit(embed=embed, view=StartView())


async def rollover_if_needed():
    channel_id_raw = get_setting("wordle_channel_id")
    active_day_key = get_setting("active_day_key")

    if not channel_id_raw:
        return

    today_key = get_day_key()

    # If never set properly, create today's post
    if not active_day_key:
        await create_new_challenge(int(channel_id_raw), today_key)
        return

    # Manual test keys look like YYYY-MM-DD-HH-MM-SS
    # Daily rollover should only happen when the active key is not today's key.
    if active_day_key != today_key:
        old_post = get_daily_post(active_day_key)
        if old_post:
            await safe_delete_message(old_post["channel_id"], old_post["message_id"])
            delete_daily_post(active_day_key)

        await create_new_challenge(int(channel_id_raw), today_key)


@tasks.loop(minutes=1)
async def daily_rollover_loop():
    await rollover_if_needed()


# =========================================================
# SLASH COMMANDS
# =========================================================

@tree.command(name="setup_wordle", description="Set up or reset the Wordle challenge in a channel")
@app_commands.describe(channel="The channel where the public Wordle message should be posted")
@app_commands.default_permissions(administrator=True)
async def setup_wordle(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)

    await reset_and_create_new_challenge(channel.id)

    active_day_key = get_setting("active_day_key")
    await interaction.followup.send(
        f"Wordle set up in {channel.mention}.\n"
        f"New challenge key: `{active_day_key}`\n"
        f"Running `/setup_wordle` again will delete the old one and create a fresh test challenge.",
        ephemeral=True
    )


@tree.command(name="my_hp_wordle", description="Open your private HP Wordle game")
async def my_hp_wordle(interaction: discord.Interaction):
    current_day_key = get_current_active_day_key()
    target = get_daily_word(current_day_key)

    row = get_result(current_day_key, interaction.user.id)

    if row is None:
        upsert_result(
            day_key=current_day_key,
            user_id=interaction.user.id,
            username=interaction.user.display_name,
            solved=0,
            tries=0,
            guesses=[],
            solved_at=None
        )
        guesses = []
        solved = False
    else:
        guesses = json.loads(row["guesses_json"])
        solved = bool(row["solved"])

    lost = len(guesses) >= MAX_ROWS and not solved

    png_bytes = render_board_png(target, guesses)
    file = discord.File(io.BytesIO(png_bytes), filename="board.png")
    embed = make_private_embed(current_day_key, target, guesses, solved, lost)
    view = None if (solved or lost) else PrivateGameView(interaction.user.id, current_day_key, target)

    await interaction.response.send_message(
        embed=embed,
        file=file,
        view=view,
        ephemeral=True
    )


# =========================================================
# EVENTS
# =========================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

    bot.add_view(StartView())

    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
    else:
        await tree.sync()

    if not daily_rollover_loop.is_running():
        daily_rollover_loop.start()


# =========================================================
# START
# =========================================================

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing in .env")

bot.run(TOKEN)