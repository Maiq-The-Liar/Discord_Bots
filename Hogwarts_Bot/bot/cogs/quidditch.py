from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from repositories.quidditch_repository import QuidditchRepository
from services.quidditch_image_service import QuidditchImageService
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

    @app_commands.command(
        name="quidditch_testgame",
        description="Admin: start an unofficial 10-hour Quidditch test game that does not affect standings.",
    )
    async def quidditch_testgame(
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

            config = service.get_config(interaction.guild.id)
            if config is None or config["match_channel_id"] is None:
                await interaction.response.send_message(
                    "Set up the Quidditch match channel first with `/setup_quidditch`.",
                    ephemeral=True,
                )
                return

            match_channel = interaction.guild.get_channel(int(config["match_channel_id"]))
            if not isinstance(match_channel, discord.TextChannel):
                await interaction.response.send_message(
                    "Configured Quidditch match channel could not be found.",
                    ephemeral=True,
                )
                return

            try:
                result = service.start_test_game(guild_id=interaction.guild.id)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

            embed = discord.Embed(
                title="🧪 Quidditch Test Game",
                description=(
                    f"**{result['home_house']} vs {result['away_house']}**\n\n"
                    f"This is an **unofficial** Quidditch test game.\n"
                    f"It lasts **10 hours** and does **not** affect:\n"
                    f"- season standings\n"
                    f"- Quidditch Cup ranking\n"
                    f"- House Cup points"
                ),
                color=0x5865F2,
            )
            embed.add_field(name=result["home_house"], value="0", inline=True)
            embed.add_field(name=result["away_house"], value="0", inline=True)
            embed.add_field(
                name="Match Log",
                value="No events yet.\nTest game initialized successfully.",
                inline=False,
            )
            embed.set_footer(text="Unofficial test match")

            message = await match_channel.send(embed=embed)
            repo.set_test_match_message(
                int(result["test_match_id"]),
                channel_id=match_channel.id,
                message_id=message.id,
            )
            conn.commit()

        await interaction.response.send_message(
            f"Unofficial Quidditch test game created in {match_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="quidditch_test_pitch",
        description="Admin: render a demo Quidditch pitch image with mock players and custom scores.",
    )
    async def quidditch_test_pitch(
        self,
        interaction: discord.Interaction,
        score_team1: app_commands.Range[int, 0, 9999],
        score_team2: app_commands.Range[int, 0, 9999],
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

        image_service = QuidditchImageService()
        home_house = "Gryffindor"
        away_house = "Ravenclaw"

        home_lineup = image_service.build_demo_lineup(home_house)
        away_lineup = image_service.build_demo_lineup(away_house)

        image_path = image_service.render_match_image(
            home_house=home_house,
            away_house=away_house,
            home_score=score_team1,
            away_score=score_team2,
            home_lineup=home_lineup,
            away_lineup=away_lineup,
        )

        embed = discord.Embed(
            title="🧪 Quidditch Pitch Render Test",
            description=(
                f"**{home_house} vs {away_house}**\n"
                f"Rendered with mock/demo lineups for layout tuning.\n"
                f"Score preview: **{score_team1:04d} – {score_team2:04d}**"
            ),
            color=0x5865F2,
        )
        embed.set_image(url="attachment://quidditch_test_pitch.png")

        await interaction.response.send_message(
            embed=embed,
            file=discord.File(str(image_path), filename="quidditch_test_pitch.png"),
            ephemeral=True,
        )

    @app_commands.command(
        name="quidditch_testgame_stop",
        description="Admin: stop the current unofficial Quidditch test game.",
    )
    async def quidditch_testgame_stop(
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

            active_test = repo.get_active_test_match(interaction.guild.id)
            if active_test is None:
                await interaction.response.send_message(
                    "There is no active Quidditch test game.",
                    ephemeral=True,
                )
                return

            channel_id = active_test["channel_id"]
            message_id = active_test["message_id"]

            try:
                result = service.stop_test_game(guild_id=interaction.guild.id)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

            if channel_id is not None and message_id is not None:
                channel = interaction.guild.get_channel(int(channel_id))
                if isinstance(channel, discord.TextChannel):
                    try:
                        message = await channel.fetch_message(int(message_id))
                        await message.delete()
                    except discord.HTTPException:
                        pass

            conn.commit()

        test_match = result["test_match"]
        await interaction.response.send_message(
            f"Unofficial Quidditch test game stopped.\n"
            f"**{test_match['home_house']} vs {test_match['away_house']}** was cancelled.",
            ephemeral=True,
        )