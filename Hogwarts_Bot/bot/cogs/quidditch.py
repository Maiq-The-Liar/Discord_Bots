from __future__ import annotations

from datetime import datetime

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
            f"Fixtures created: **{fixture_count}**",
            ephemeral=True,
        )