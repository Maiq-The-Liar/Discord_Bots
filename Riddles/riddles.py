import json
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

# =========================================================
# CONFIG
# =========================================================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1079764344688095312
CONFIG_FILE = Path("milestones.json")

# =========================================================
# DISCORD SETUP
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================================================
# JSON HELPERS
# =========================================================
def load_config() -> dict:
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(data: dict) -> None:
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


milestones = load_config()


def normalize_text(text: str) -> str:
    return text.strip().lower()


def admin_only():
    return app_commands.checks.has_permissions(administrator=True)

# =========================================================
# READY
# =========================================================
@bot.event
async def on_ready() -> None:
    guild = discord.Object(id=GUILD_ID)

    # Sync only to your server so commands appear quickly while testing
    synced = await bot.tree.sync(guild=guild)

    print(f"Logged in as {bot.user}")
    print(f"Synced {len(synced)} guild slash command(s) to guild {GUILD_ID}")

# =========================================================
# SLASH COMMANDS
# =========================================================
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@bot.tree.command(
    name="setmilestone",
    description="Set the required word and reward role for this channel.",
)
@app_commands.describe(
    word="The exact word/string users must send",
    role="The role to give when they send the correct word",
)
@admin_only()
async def set_milestone(
    interaction: discord.Interaction,
    word: str,
    role: discord.Role,
) -> None:
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command can only be used in a server channel.",
            ephemeral=True,
        )
        return

    channel_id = str(interaction.channel.id)
    milestones[channel_id] = {
        "word": word,
        "role_id": role.id,
    }
    save_config(milestones)

    await interaction.response.send_message(
        f"Milestone set for {interaction.channel.mention}.\n"
        f"Required word: `{word}`\n"
        f"Reward role: {role.mention}",
        ephemeral=True,
    )


@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@bot.tree.command(
    name="clearmilestone",
    description="Remove the milestone restriction from this channel.",
)
@admin_only()
async def clear_milestone(interaction: discord.Interaction) -> None:
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command can only be used in a server channel.",
            ephemeral=True,
        )
        return

    channel_id = str(interaction.channel.id)

    if channel_id in milestones:
        del milestones[channel_id]
        save_config(milestones)
        await interaction.response.send_message(
            f"Milestone cleared for {interaction.channel.mention}.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "There is no milestone set for this channel.",
            ephemeral=True,
        )

# =========================================================
# ERROR HANDLER
# =========================================================
@set_milestone.error
@clear_milestone.error
async def admin_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.errors.MissingPermissions):
        msg = "Only admins can use this command."
    else:
        msg = f"Error: {error}"

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)

# =========================================================
# MESSAGE HANDLER
# =========================================================
@bot.event
async def on_message(message: discord.Message) -> None:
    await bot.process_commands(message)

    if message.author.bot or message.guild is None:
        return

    channel_id = str(message.channel.id)
    config = milestones.get(channel_id)

    if not config:
        return

    required_word = config["word"]
    role_id = config["role_id"]

    if not message.content:
        return

    # Always delete immediately
    try:
        await message.delete()
    except discord.Forbidden:
        pass
    except discord.HTTPException:
        pass

    # Correct answer
    role = message.guild.get_role(role_id)
    if role is None:
        try:
            await message.author.send("Role is missing. Contact an admin.")
        except discord.Forbidden:
            pass
        return

    member = message.author

    if role not in member.roles:
        try:
            await member.add_roles(role, reason="Milestone completed")
        except discord.Forbidden:
            try:
                await message.author.send("I can't assign the role.")
            except discord.Forbidden:
                pass
            return

    try:
        await message.channel.send(
            f"{member.mention} well done...",
            delete_after=5,
        )
    except discord.HTTPException:
        pass

# =========================================================
# MAIN
# =========================================================
def main() -> None:
    if not TOKEN:
        raise RuntimeError(
            'DISCORD_TOKEN is not set. Run:\nexport DISCORD_TOKEN="your_token_here"'
        )

    bot.run(TOKEN)


if __name__ == "__main__":
    main()