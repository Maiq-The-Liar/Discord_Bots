from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from repositories.quidditch_repository import QuidditchRepository
from services.quidditch_service import QuidditchService


class QuidditchCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )

    @app_commands.command(
        name="setup_quidditch",
        description="Admin: set the channel for live Quidditch match messages.",
    )
    async def setup_quidditch(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            service = QuidditchService(repo)
            service.set_match_channel(interaction.guild.id, channel.id)
            conn.commit()

        await interaction.response.send_message(
            f"Quidditch match channel set to {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="setup_quidditch_scoreboard",
        description="Admin: set the channel for the Quidditch scoreboard embed.",
    )
    async def setup_quidditch_scoreboard(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            service = QuidditchService(repo)
            service.set_scoreboard_channel(interaction.guild.id, channel.id)
            conn.commit()

        await interaction.response.send_message(
            f"Quidditch scoreboard channel set to {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="start_quidditch_loop",
        description="Admin: create this month's Quidditch schedule and scoreboard.",
    )
    async def start_quidditch_loop(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            service = QuidditchService(repo)

            config = service.get_config(interaction.guild.id)
            if config is None or config["scoreboard_channel_id"] is None:
                await interaction.followup.send(
                    "Set up the scoreboard channel first with `/setup_quidditch_scoreboard`.",
                    ephemeral=True,
                )
                return

            result = service.build_month_schedule(guild_id=interaction.guild.id)
            service.enable_loop(interaction.guild.id)

            season = repo.get_season_by_key(interaction.guild.id, result["season_key"])
            standings = repo.get_standings(int(season["id"]))
            title, description = service.build_scoreboard_embed(season, standings)

            channel = interaction.guild.get_channel(int(config["scoreboard_channel_id"]))
            if not isinstance(channel, discord.TextChannel):
                await interaction.followup.send(
                    "Configured Quidditch scoreboard channel could not be found.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title=title,
                description=description,
                color=0xD4AF37,
            )

            scoreboard_message_id = config["scoreboard_message_id"]
            if scoreboard_message_id is not None:
                try:
                    message = await channel.fetch_message(int(scoreboard_message_id))
                    await message.edit(embed=embed)
                except discord.HTTPException:
                    message = await channel.send(embed=embed)
                    service.set_scoreboard_message_id(interaction.guild.id, message.id)
            else:
                message = await channel.send(embed=embed)
                service.set_scoreboard_message_id(interaction.guild.id, message.id)

            conn.commit()

        fixture_count = len(result["fixtures"])
        season_kind = "reduced" if result["is_reduced"] else "full"

        await interaction.followup.send(
            f"Quidditch season `{result['season_key']}` started.\n"
            f"Format: **{season_kind}**\n"
            f"Fixtures created: **{fixture_count}**\n"
            f"Loop enabled: **yes**",
            ephemeral=True,
        )

    @app_commands.command(
        name="stop_loop",
        description="Admin: stop the automatic Quidditch loop.",
    )
    async def stop_loop(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            service = QuidditchService(repo)
            service.stop_loop(interaction.guild.id)
            conn.commit()

        await interaction.response.send_message(
            "Quidditch loop stopped. No scheduled games will auto-start until you enable it again with `/start_quidditch_loop`.",
            ephemeral=True,
        )

    @app_commands.command(
        name="quidditch_now",
        description="Admin: start today's scheduled Quidditch game immediately if it is still before 13:00 Swiss time.",
    )
    async def quidditch_now(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            service = QuidditchService(repo)

            try:
                result = service.start_manual_now(guild_id=interaction.guild.id)
                conn.commit()
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

        fixture = result["fixture"]
        await interaction.response.send_message(
            f"Manual Quidditch start activated.\n"
            f"**{fixture['home_house']} vs {fixture['away_house']}** has started now.\n"
            f"It will return to normal scheduled behavior tomorrow unless you stop it with `/quidditch_now_stop`.",
            ephemeral=True,
        )

    @app_commands.command(
        name="quidditch_now_stop",
        description="Admin: stop the current manually-started Quidditch game and restore the scheduled start.",
    )
    async def quidditch_now_stop(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            service = QuidditchService(repo)

            try:
                result = service.stop_manual_now(guild_id=interaction.guild.id)
                conn.commit()
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

        fixture = result["fixture"]
        await interaction.response.send_message(
            f"Manual Quidditch game stopped.\n"
            f"**{fixture['home_house']} vs {fixture['away_house']}** has been reset and will wait for the normal 13:00 Swiss start.",
            ephemeral=True,
        )