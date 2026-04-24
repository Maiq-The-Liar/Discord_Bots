from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from db.database import Database
from domain.constants import HOUSE_EMOJIS
from domain.role_registry import (
    ROLE_KEY_QUIDDITCH_BEATER,
    ROLE_KEY_QUIDDITCH_CHASER,
    ROLE_KEY_QUIDDITCH_KEEPER,
    ROLE_KEY_QUIDDITCH_SEEKER,
)
from repositories.bot_state_repository import BotStateRepository
from repositories.contribution_repository import ContributionRepository
from repositories.guild_role_repository import GuildRoleRepository
from repositories.quidditch_progress_repository import QuidditchProgressRepository
from repositories.quidditch_repository import QuidditchRepository
from repositories.user_repository import UserRepository
from services.house_cup_board_service import HouseCupBoardService
from services.quidditch_image_service import QuidditchImageService
from services.quidditch_live_engine import QuidditchLiveEngine
from services.quidditch_service import QuidditchService
from services.role_service import RoleService


class CheerButton(discord.ui.Button):
    def __init__(
        self,
        *,
        cog: "QuidditchCog",
        match_scope: str,
        match_id: int,
        cheering_house: str,
        style: discord.ButtonStyle,
    ) -> None:
        super().__init__(
            label=f"Cheer for {cheering_house}",
            style=style,
            custom_id=f"quidditch_cheer:{match_scope}:{match_id}:{cheering_house}",
        )
        self.cog = cog
        self.match_scope = match_scope
        self.match_id = match_id
        self.cheering_house = cheering_house

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_cheer(
            interaction=interaction,
            match_scope=self.match_scope,
            match_id=self.match_id,
            cheering_house=self.cheering_house,
        )


class CheerView(discord.ui.View):
    def __init__(
        self,
        *,
        cog: "QuidditchCog",
        match_scope: str,
        match_id: int,
        home_house: str,
        away_house: str,
    ) -> None:
        super().__init__(timeout=None)
        self.add_item(
            CheerButton(
                cog=cog,
                match_scope=match_scope,
                match_id=match_id,
                cheering_house=home_house,
                style=discord.ButtonStyle.danger,
            )
        )
        self.add_item(
            CheerButton(
                cog=cog,
                match_scope=match_scope,
                match_id=match_id,
                cheering_house=away_house,
                style=discord.ButtonStyle.primary,
            )
        )




class BetAmountModal(discord.ui.Modal):
    def __init__(self, *, cog: "QuidditchCog", fixture_id: int, picked_house: str) -> None:
        super().__init__(title=f"Bet on {picked_house}")
        self.cog = cog
        self.fixture_id = fixture_id
        self.picked_house = picked_house
        self.amount = discord.ui.TextInput(
            label="Stake in galleons",
            placeholder="Enter whole number",
            required=True,
            max_length=9,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_bet_submission(
            interaction=interaction,
            fixture_id=self.fixture_id,
            picked_house=self.picked_house,
            raw_amount=str(self.amount.value),
        )


class BetButton(discord.ui.Button):
    def __init__(self, *, cog: "QuidditchCog", fixture_id: int, picked_house: str, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(label=label, style=style, custom_id=f"quidditch_bet:{fixture_id}:{picked_house}")
        self.cog = cog
        self.fixture_id = fixture_id
        self.picked_house = picked_house

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            BetAmountModal(cog=self.cog, fixture_id=self.fixture_id, picked_house=self.picked_house)
        )


class BetView(discord.ui.View):
    def __init__(self, *, cog: "QuidditchCog", fixture_id: int, home_house: str, away_house: str) -> None:
        super().__init__(timeout=None)
        self.add_item(BetButton(cog=cog, fixture_id=fixture_id, picked_house=home_house, label=f"Bet on {home_house} winning", style=discord.ButtonStyle.danger))
        self.add_item(BetButton(cog=cog, fixture_id=fixture_id, picked_house=away_house, label=f"Bet on {away_house} winning", style=discord.ButtonStyle.primary))


class QuidditchCog(commands.Cog):
    TZ = ZoneInfo("Europe/Zurich")
    POSITION_ROLE_KEYS = {
        "keeper": ROLE_KEY_QUIDDITCH_KEEPER,
        "seeker": ROLE_KEY_QUIDDITCH_SEEKER,
        "beater": ROLE_KEY_QUIDDITCH_BEATER,
        "chaser": ROLE_KEY_QUIDDITCH_CHASER,
    }
    REQUIRED_COUNTS = {
        "keeper": 1,
        "seeker": 1,
        "beater": 2,
        "chaser": 3,
    }
    GIF_BASE_URL = "https://raw.githubusercontent.com/Maiq-The-Liar/01_Resource_Bot_Quidditch_Animations/main/gifs"
    HOUSE_GIF_INITIALS = {
        "Gryffindor": "G",
        "Hufflepuff": "H",
        "Ravenclaw": "R",
        "Slytherin": "S",
    }
    KNOCKOUT_GIF_CODES = {
        "keeper": "K",
        "seeker": "S",
        "chaser": "C",
        "beater": "B",
    }
    KNOCKOUT_GIF_ORDER = ("keeper", "seeker", "chaser", "beater")

    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
        self.image_service = QuidditchImageService()
        self.engine = QuidditchLiveEngine()
        self._startup_refresh_task: asyncio.Task | None = None

    async def cog_load(self) -> None:
        if not self.quidditch_loop.is_running():
            self.quidditch_loop.start()
        if self._startup_refresh_task is None or self._startup_refresh_task.done():
            self._startup_refresh_task = asyncio.create_task(self._restore_current_prompts_on_startup())

    async def cog_unload(self) -> None:
        if self.quidditch_loop.is_running():
            self.quidditch_loop.cancel()
        if self._startup_refresh_task is not None:
            self._startup_refresh_task.cancel()
            try:
                await self._startup_refresh_task
            except asyncio.CancelledError:
                pass

    async def _restore_current_prompts_on_startup(self) -> None:
        await self.bot.wait_until_ready()
        guild = self.bot.get_guild(getattr(self.bot, 'guild_id', None)) if hasattr(self.bot, 'guild_id') else None
        if guild is None:
            try:
                from config import load_settings
                settings = load_settings()
                guild = self.bot.get_guild(settings.guild_id)
            except Exception:
                guild = None
        if guild is None:
            return

        try:
            message = await self._refresh_current_quidditch_prompts(guild)
            if message.startswith("Refreshed the current"):
                logging.info("Quidditch startup refresh: %s", message)
        except Exception:
            logging.exception("Failed to refresh Quidditch prompts on startup.")

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )

    def _now(self) -> datetime:
        return datetime.now(self.TZ)

    def _trim_name(self, raw_name: str, limit: int = 18) -> str:
        name = raw_name.strip()
        return name if len(name) <= limit else f"{name[:limit - 1]}…"

    def _visible_log_lines(self, full_log: list[str]) -> list[str]:
        return full_log[-3:]

    def _format_log_block(self, full_log: list[str]) -> str:
        lines = self._visible_log_lines(full_log)
        if not lines:
            return "```text\n--:-- | No events yet.\n```"

        formatted: list[str] = []
        for line in lines:
            if " " in line:
                timestamp, rest = line.split(" ", 1)
                formatted.append(f"{timestamp} | {rest}")
            else:
                formatted.append(f"--:-- | {line}")

        separator = "\n" + ("-" * 34) + "\n"
        body = separator.join(formatted)
        return f"```text\n{body}\n```"

    def _roster_block_for_house(self, house_name: str, lineup: list[dict[str, Any]]) -> str:
        by_pos: dict[str, list[dict[str, Any]]] = {
            "seeker": [],
            "chaser": [],
            "beater": [],
            "keeper": [],
        }
        for player in lineup:
            pos = str(player.get("position", "")).lower()
            if pos in by_pos:
                by_pos[pos].append(player)

        def fmt_player(player: dict[str, Any]) -> str:
            name = str(
                player.get("display_name")
                or player.get("username")
                or player.get("name")
                or "Unknown"
            )
            return f"{name} lv. {int(player.get('level', 1))}"

        lines: list[str] = []
        lines.append(f"{HOUSE_EMOJIS.get(house_name, '🏰')} **{house_name}'s Roster**")
        lines.append("")
        lines.append("**Seeker**")
        for player in by_pos["seeker"][:1]:
            lines.append(fmt_player(player))
        lines.append("")
        lines.append("**Chaser**")
        for player in by_pos["chaser"][:3]:
            lines.append(fmt_player(player))
        lines.append("")
        lines.append("**Beater**")
        for player in by_pos["beater"][:2]:
            lines.append(fmt_player(player))
        lines.append("")
        lines.append("**Keeper**")
        for player in by_pos["keeper"][:1]:
            lines.append(fmt_player(player))

        return "\n".join(lines)

    def _betting_embed(
        self,
        *,
        fixture_id: int,
        home_house: str,
        away_house: str,
        home_lineup: list[dict[str, Any]],
        away_lineup: list[dict[str, Any]],
        odds_home: float,
        odds_away: float,
        betting_log_lines: list[str] | None = None,
    ) -> discord.Embed:
        left_house, right_house = self.image_service.get_display_order(home_house, away_house)
        if left_house == home_house:
            left_lineup, right_lineup = home_lineup, away_lineup
            left_odds, right_odds = odds_home, odds_away
        else:
            left_lineup, right_lineup = away_lineup, home_lineup
            left_odds, right_odds = odds_away, odds_home

        embed = discord.Embed(color=0x2F3136)
        embed.add_field(name="​", value=self._roster_block_for_house(left_house, left_lineup), inline=True)
        embed.add_field(name="​", value=self._roster_block_for_house(right_house, right_lineup), inline=True)
        embed.add_field(
            name="💰 Betting odds",
            value=(
                f"**{left_house}** — {left_odds:.2f}x\n"
                f"**{right_house}** — {right_odds:.2f}x\n\n"
                f"Example: a successful **100 galleon** bet on **{left_house}** pays out **{int(round(100 * left_odds))} galleons** total."
            ),
            inline=False,
        )
        embed.set_footer(text=f"Fixture #{fixture_id} betting closes 10 minutes before kickoff.")
        return embed

    def _final_score_embed(self) -> discord.Embed:
        return discord.Embed(title="Final Score", color=0xD4AF37)

    def _parse_preview_state(self, betting_state: Any) -> dict[str, Any]:
        if betting_state is None:
            return {}
        try:
            return json.loads(str(betting_state["preview_state_json"]))
        except Exception:
            return {}

    def _build_betting_log_lines(self, guild: discord.Guild, bets: list[Any]) -> list[str]:
        lines: list[str] = []
        for bet in bets:
            member = guild.get_member(int(bet["user_id"]))
            name = member.display_name if member else f"User {bet['user_id']}"
            lines.append(f"**{name}** bet **{int(bet['stake'])}** galleons on **{bet['picked_house']}**.")
        return lines

    async def _refresh_betting_embed_message(self, guild: discord.Guild, fixture_id: int) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            fixture = repo.get_fixture(fixture_id)
            betting_state = repo.get_betting_state(fixture_id)
            if fixture is None or betting_state is None or not betting_state["embed_message_id"]:
                return
            preview = self._parse_preview_state(betting_state)
            home_lineup = preview.get("home_lineup") or []
            away_lineup = preview.get("away_lineup") or []
            bets = repo.list_bets_for_fixture(fixture_id)
            odds_home = float(betting_state["odds_home"])
            odds_away = float(betting_state["odds_away"])
            channel = await self._fetch_configured_match_channel(guild, repo)
            if channel is None:
                return
        embed = self._betting_embed(
            fixture_id=fixture_id,
            home_house=str(fixture["home_house"]),
            away_house=str(fixture["away_house"]),
            home_lineup=home_lineup,
            away_lineup=away_lineup,
            odds_home=odds_home,
            odds_away=odds_away,
            betting_log_lines=self._build_betting_log_lines(guild, bets),
        )
        try:
            message = await channel.fetch_message(int(betting_state["embed_message_id"]))
            await message.edit(
                embed=embed,
                view=BetView(
                    cog=self,
                    fixture_id=fixture_id,
                    home_house=str(fixture["home_house"]),
                    away_house=str(fixture["away_house"]),
                ),
            )
        except discord.HTTPException:
            return

    def _sum_levels(self, lineup: list[dict[str, Any]], position: str) -> int:
        return sum(int(p.get("level", 1)) for p in lineup if str(p.get("position", "")).lower() == position)

    def _estimate_betting_odds(self, home_lineup: list[dict[str, Any]], away_lineup: list[dict[str, Any]]) -> tuple[float, float]:
        home_attack = (self._sum_levels(home_lineup, "chaser") / (120 * 3)) * 0.34 + (self._sum_levels(home_lineup, "beater") / (120 * 2)) * 0.08
        away_attack = (self._sum_levels(away_lineup, "chaser") / (120 * 3)) * 0.34 + (self._sum_levels(away_lineup, "beater") / (120 * 2)) * 0.08
        home_defense = (self._sum_levels(home_lineup, "keeper") / 120) * 0.26 + (self._sum_levels(home_lineup, "beater") / (120 * 2)) * 0.07
        away_defense = (self._sum_levels(away_lineup, "keeper") / 120) * 0.26 + (self._sum_levels(away_lineup, "beater") / (120 * 2)) * 0.07
        home_snitch = (self._sum_levels(home_lineup, "seeker") / 120) * 0.32
        away_snitch = (self._sum_levels(away_lineup, "seeker") / 120) * 0.32

        home_strength = home_attack * 1.0 + home_defense * 0.95 + home_snitch * 1.1
        away_strength = away_attack * 1.0 + away_defense * 0.95 + away_snitch * 1.1
        home_edge = home_strength - away_strength + (home_attack - away_defense) * 0.5 + (home_snitch - away_snitch) * 0.75
        home_prob = max(0.22, min(0.78, 0.5 + home_edge * 0.95))
        away_prob = 1.0 - home_prob

        def to_odds(prob: float) -> float:
            fair = 1.0 / max(0.08, prob)
            inflated = fair * 1.18
            return max(1.18, min(4.75, round(inflated, 2)))

        return to_odds(home_prob), to_odds(away_prob)

    async def _fetch_configured_match_channel(self, guild: discord.Guild, repo: QuidditchRepository) -> discord.TextChannel | None:
        config = repo.get_config(guild.id)
        if config is None or config["match_channel_id"] is None:
            return None
        channel = guild.get_channel(int(config["match_channel_id"]))
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _delete_message_if_exists(self, guild: discord.Guild, channel_id: int | None, message_id: int | None) -> None:
        if not channel_id or not message_id:
            return
        channel = guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(int(message_id))
            await message.delete()
        except discord.HTTPException:
            pass

    async def _cleanup_betting_messages(self, guild: discord.Guild, fixture_id: int) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            betting_state = repo.get_betting_state(fixture_id)
            live_state = repo.get_live_match_state(fixture_id)
        if betting_state is None:
            return
        channel_id = int(live_state["channel_id"]) if live_state is not None and live_state["channel_id"] else None
        if channel_id is None:
            with self.database.connect() as conn:
                repo = QuidditchRepository(conn)
                channel = await self._fetch_configured_match_channel(guild, repo)
                channel_id = channel.id if channel is not None else None
        await self._delete_message_if_exists(guild, channel_id, betting_state["image_message_id"])
        await self._delete_message_if_exists(guild, channel_id, betting_state["embed_message_id"])

    async def _announce_betting_for_fixture(self, guild: discord.Guild, fixture_id: int) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            fixture = repo.get_fixture(fixture_id)
            if fixture is None:
                return
            betting_state = repo.get_betting_state(fixture_id)
            if betting_state is None:
                return
            channel = await self._fetch_configured_match_channel(guild, repo)
            if channel is None:
                return
            preview = self._parse_preview_state(betting_state)
            home_lineup = preview.get("home_lineup") or []
            away_lineup = preview.get("away_lineup") or []
            odds_home = float(betting_state["odds_home"])
            odds_away = float(betting_state["odds_away"])

        image_path = self.image_service.get_upcoming_matchup_path(str(fixture["home_house"]), str(fixture["away_house"]))
        image_message = await channel.send(file=discord.File(str(image_path), filename="quidditch_upcoming.png"))
        embed = self._betting_embed(
            fixture_id=fixture_id,
            home_house=str(fixture["home_house"]),
            away_house=str(fixture["away_house"]),
            home_lineup=home_lineup,
            away_lineup=away_lineup,
            odds_home=odds_home,
            odds_away=odds_away,
            betting_log_lines=self._build_betting_log_lines(guild, []),
        )
        embed_message = await channel.send(
            embed=embed,
            view=BetView(
                cog=self,
                fixture_id=fixture_id,
                home_house=str(fixture["home_house"]),
                away_house=str(fixture["away_house"]),
            ),
        )

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            repo.mark_betting_announced(fixture_id, image_message_id=image_message.id, embed_message_id=embed_message.id)
            conn.commit()

    async def _schedule_betting_for_next_fixture(self, guild: discord.Guild, *, delay_minutes: int = 20, force_now: bool = False) -> str | None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            latest_season = repo.get_latest_season(guild.id)
            if latest_season is None:
                return None
            next_fixture = repo.get_next_scheduled_fixture(int(latest_season["id"]))
            if next_fixture is None or str(next_fixture["home_house"]) == "TBD" or str(next_fixture["away_house"]) == "TBD":
                return None
            betting_state = repo.get_betting_state(int(next_fixture["id"]))
            if betting_state is not None and str(betting_state["status"]) in {"pending", "announced", "closed", "settled"}:
                return f"Betting state already exists for **{next_fixture['home_house']} vs {next_fixture['away_house']}**."

            role_service = self._build_role_service(conn)
            progress_repo = QuidditchProgressRepository(conn)
            home_lineup, away_lineup = self._build_lineups(
                guild=guild,
                home_house=str(next_fixture["home_house"]),
                away_house=str(next_fixture["away_house"]),
                repo=repo,
                role_service=role_service,
                progress_repo=progress_repo,
            )
            odds_home, odds_away = self._estimate_betting_odds(home_lineup, away_lineup)
            now = self._now()
            starts_at = datetime.fromisoformat(str(next_fixture["starts_at"])).astimezone(self.TZ)
            announce_at = now if force_now else now + timedelta(minutes=delay_minutes)
            cleanup_at = starts_at - timedelta(minutes=10)
            if announce_at > cleanup_at:
                announce_at = now
            repo.upsert_betting_state(
                int(next_fixture["id"]),
                status="pending",
                announced_at=announce_at.isoformat(),
                cleanup_at=cleanup_at.isoformat(),
                preview_state={"home_lineup": home_lineup, "away_lineup": away_lineup},
                odds_home=odds_home,
                odds_away=odds_away,
            )
            conn.commit()
            return f"Betting scheduled for **{next_fixture['home_house']} vs {next_fixture['away_house']}**."

    async def handle_bet_submission(self, interaction: discord.Interaction, fixture_id: int, picked_house: str, raw_amount: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return
        try:
            amount = int(raw_amount.strip())
        except Exception:
            await interaction.response.send_message("Please enter a whole number of galleons.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("Bet amount must be greater than 0.", ephemeral=True)
            return

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            user_repo = UserRepository(conn)
            fixture = repo.get_fixture(fixture_id)
            betting_state = repo.get_betting_state(fixture_id)
            if fixture is None or betting_state is None:
                await interaction.response.send_message("Betting is not available for that match.", ephemeral=True)
                return
            if str(betting_state["status"]) != "announced":
                await interaction.response.send_message("Betting for that match is closed.", ephemeral=True)
                return
            existing = repo.get_bet_for_user(fixture_id, interaction.user.id)
            if existing is not None:
                await interaction.response.send_message("You already placed a bet on this match.", ephemeral=True)
                return
            user_repo.ensure_user(interaction.user.id)
            user_row = user_repo.get_user(interaction.user.id)
            balance = int(user_row["sickles_balance"])
            if amount > balance:
                await interaction.response.send_message(f"You only have {balance} galleons available.", ephemeral=True)
                return
            odds = float(betting_state["odds_home"]) if picked_house == str(fixture["home_house"]) else float(betting_state["odds_away"])
            if picked_house not in {str(fixture["home_house"]), str(fixture["away_house"])}:
                await interaction.response.send_message("That team is not playing in this fixture.", ephemeral=True)
                return
            if not user_repo.deduct_sickles(interaction.user.id, amount):
                await interaction.response.send_message("You do not have enough galleons for that bet.", ephemeral=True)
                return
            repo.create_bet(fixture_id, interaction.user.id, picked_house, amount, odds)
            conn.commit()

        await interaction.response.send_message(
            f"Bet placed: **{amount} galleons** on **{picked_house}** at **{odds:.2f}x**.\nPotential payout: **{int(round(amount * odds))} galleons** total.",
            ephemeral=True,
        )

    async def _post_betting_results(self, guild: discord.Guild, fixture_id: int, winner_house: str) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            user_repo = UserRepository(conn)
            fixture = repo.get_fixture(fixture_id)
            betting_state = repo.get_betting_state(fixture_id)
            if fixture is None or betting_state is None:
                return
            bets = repo.settle_bets_for_fixture(fixture_id, winner_house)
            channel = await self._fetch_configured_match_channel(guild, repo)
            if channel is None:
                return
            lines: list[str] = []
            for bet in bets:
                user_repo.ensure_user(int(bet["user_id"]))
                member = guild.get_member(int(bet["user_id"]))
                name = member.display_name if member else f"User {bet['user_id']}"
                if str(bet["result"]) == "won":
                    payout = int(bet["payout"])
                    user_repo.add_sickles(int(bet["user_id"]), payout)
                    profit = payout - int(bet["stake"])
                    lines.append(f"**{name}** won **{profit}** galleons net ({int(bet['stake'])} → {payout}).")
                else:
                    lines.append(f"**{name}** lost **{int(bet['stake'])}** galleons on {bet['picked_house']}.")
            if not lines:
                lines = ["No bets were placed on this match."]
            embed = discord.Embed(title="Betting Results", description="\n".join(lines[:20]), color=0x2ECC71)
            if betting_state["final_message_id"]:
                try:
                    final_message = await channel.fetch_message(int(betting_state["final_message_id"]))
                    result_message = await final_message.reply(embed=embed, mention_author=False)
                except discord.HTTPException:
                    result_message = await channel.send(embed=embed)
            else:
                result_message = await channel.send(embed=embed)
            repo.set_betting_results_message(fixture_id, result_message.id)
            repo.mark_betting_closed(fixture_id)
            conn.commit()

    def _build_live_embeds(
        self,
        *,
        home_house: str,
        away_house: str,
        home_lineup: list[dict[str, Any]],
        away_lineup: list[dict[str, Any]],
        full_log: list[str],
        footer_text: str,
        image_filename: str,
        is_test: bool,
        ended: bool,
        runtime_state: dict[str, Any],
    ) -> list[discord.Embed]:
        color = 0x5865F2 if is_test else 0xD4AF37

        left_house, right_house = self.image_service.get_display_order(home_house, away_house)

        if left_house == home_house:
            left_lineup = home_lineup
            right_lineup = away_lineup
        else:
            left_lineup = away_lineup
            right_lineup = home_lineup

        status_line = "Finished" if ended else "Live match"
        heading = f"## **{left_house} vs {right_house}**"

        roster_embed = discord.Embed(
            description=f"{heading}\n*{status_line}*",
            color=color,
        )
        roster_embed.add_field(
            name="\u200b",
            value=self._roster_block_for_house(left_house, left_lineup),
            inline=True,
        )
        roster_embed.add_field(
            name="\u200b",
            value=self._roster_block_for_house(right_house, right_lineup),
            inline=True,
        )
        roster_embed.add_field(
            name="📜 Match Log",
            value=self._format_log_block(full_log),
            inline=False,
        )
        roster_embed.set_footer(text=footer_text)

        gif_embed = discord.Embed(color=color)
        gif_embed.set_image(url=self._build_live_gif_url(
            home_house=home_house,
            away_house=away_house,
            home_lineup=home_lineup,
            away_lineup=away_lineup,
            runtime_state=runtime_state,
        ))

        scoreboard_embed = discord.Embed(color=color)
        scoreboard_embed.set_image(url=f"attachment://{image_filename}")

        return [roster_embed, gif_embed, scoreboard_embed]

    def _build_live_gif_url(
        self,
        *,
        home_house: str,
        away_house: str,
        home_lineup: list[dict[str, Any]],
        away_lineup: list[dict[str, Any]],
        runtime_state: dict[str, Any],
    ) -> str:
        left_house, right_house = self.image_service.get_display_order(home_house, away_house)
        left_initial = self.HOUSE_GIF_INITIALS[left_house]
        right_initial = self.HOUSE_GIF_INITIALS[right_house]

        possession_side = str(runtime_state.get("quaffle_possession_side") or "home")
        possession_house = home_house if possession_side == "home" else away_house
        if possession_house == left_house:
            possession_code = f"{left_initial}Qv{right_initial}"
        else:
            possession_code = f"{left_initial}v{right_initial}Q"

        if left_house == home_house:
            left_lineup = home_lineup
            right_lineup = away_lineup
        else:
            left_lineup = away_lineup
            right_lineup = home_lineup

        now = self._now()
        inactive_until = runtime_state.get("inactive_until", {})
        left_knockouts = self._encode_knockout_gif_side(left_lineup, inactive_until, now)
        right_knockouts = self._encode_knockout_gif_side(right_lineup, inactive_until, now)
        matchup_folder = f"{left_house.lower()}_{right_house.lower()}"
        filename = f"{possession_code}_{left_knockouts}v{right_knockouts}.gif"
        return f"{self.GIF_BASE_URL}/{matchup_folder}/{filename}"

    def _encode_knockout_gif_side(
        self,
        lineup: list[dict[str, Any]],
        inactive_until: dict[str, Any],
        now: datetime,
    ) -> str:
        inactive_positions: list[str] = []
        for player in lineup:
            token = str(player.get("token") or player.get("display_name") or player.get("username") or "unknown")
            until = inactive_until.get(token)
            if not until:
                continue
            try:
                if datetime.fromisoformat(str(until)) <= now:
                    continue
            except ValueError:
                continue
            position = str(player.get("position", "")).lower().strip()
            if position in self.KNOCKOUT_GIF_CODES:
                inactive_positions.append(position)

        if not inactive_positions:
            return "0"

        ordered_codes: list[str] = []
        for position in self.KNOCKOUT_GIF_ORDER:
            ordered_codes.extend(
                self.KNOCKOUT_GIF_CODES[position]
                for inactive_position in inactive_positions
                if inactive_position == position
            )
        return "".join(ordered_codes) or "0"

    async def _render_match_image(
        self,
        *,
        home_house: str,
        away_house: str,
        home_score: int,
        away_score: int,
        home_lineup: list[dict[str, Any]],
        away_lineup: list[dict[str, Any]],
    ) -> Path:
        return await asyncio.to_thread(
            self.image_service.render_match_image,
            home_house=home_house,
            away_house=away_house,
            home_score=home_score,
            away_score=away_score,
            home_lineup=home_lineup,
            away_lineup=away_lineup,
        )

    def _build_role_service(self, conn) -> RoleService:
        return RoleService(GuildRoleRepository(conn))

    def _member_house(
        self,
        role_service: RoleService,
        guild: discord.Guild,
        member: discord.Member,
    ) -> str | None:
        return role_service.get_member_house(guild, member)

    def _member_has_position(
        self,
        role_service: RoleService,
        guild: discord.Guild,
        member: discord.Member,
        position_key: str,
    ) -> bool:
        role = role_service.get_role(guild, self.POSITION_ROLE_KEYS[position_key])
        if role is None:
            return False
        return role in member.roles

    def _build_real_player(
        self,
        *,
        member: discord.Member,
        position_key: str,
        progress_repo: QuidditchProgressRepository,
    ) -> dict[str, Any]:
        progress_repo.ensure_user_positions(member.id)
        progress = progress_repo.get_progress(member.id, position_key)
        display_name = self._trim_name(member.display_name)
        return {
            "user_id": member.id,
            "username": member.display_name,
            "display_name": display_name,
            "position": position_key,
            "level": int(progress["level"]),
            "token": f"user:{member.id}",
            "is_npc": False,
            "house_name": None,
        }

    def _build_npc_player(
        self,
        *,
        house_name: str,
        position_key: str,
        target_level: int,
        used_names: set[str],
    ) -> dict[str, Any]:
        pool = self.engine.NPC_POOLS.get(house_name, {}).get(position_key, [])
        if not pool:
            pool = [f"{house_name} {position_key.title()} NPC"]

        choices = [name for name in pool if name not in used_names]
        npc_name = random.choice(choices or pool)
        used_names.add(npc_name)

        level = max(1, min(120, random.randint(max(1, target_level - 6), min(120, target_level + 6))))
        return {
            "user_id": None,
            "username": npc_name,
            "display_name": self._trim_name(npc_name),
            "position": position_key,
            "level": level,
            "token": f"npc:{house_name}:{position_key}:{npc_name}",
            "is_npc": True,
            "house_name": house_name,
        }

    def _normalize_rotation_queue(
        self,
        *,
        available_ids: list[int],
        stored_cycle: list[int],
    ) -> list[int]:
        available_set = set(available_ids)
        normalized = [user_id for user_id in stored_cycle if user_id in available_set]
        missing = [user_id for user_id in available_ids if user_id not in normalized]
        random.shuffle(missing)
        normalized.extend(missing)
        return normalized

    def _take_rotating_members(
        self,
        *,
        available_members: list[discord.Member],
        needed: int,
        repo: QuidditchRepository,
        guild_id: int,
        house_name: str,
        position_key: str,
    ) -> list[discord.Member]:
        if not available_members:
            repo.save_rotation_cycle(guild_id, house_name, position_key, [])
            return []

        member_by_id = {member.id: member for member in available_members}
        available_ids = list(member_by_id.keys())

        cycle = self._normalize_rotation_queue(
            available_ids=available_ids,
            stored_cycle=repo.get_rotation_cycle(guild_id, house_name, position_key),
        )

        selected_ids: list[int] = []
        queue = list(cycle)

        max_unique = min(needed, len(available_ids))
        while len(selected_ids) < max_unique:
            if not queue:
                queue = list(available_ids)
                random.shuffle(queue)

            next_id = queue.pop(0)
            if next_id in selected_ids:
                continue
            selected_ids.append(next_id)

        repo.save_rotation_cycle(guild_id, house_name, position_key, queue)
        return [member_by_id[user_id] for user_id in selected_ids]

    def _eligible_members_for_house_position(
        self,
        *,
        guild: discord.Guild,
        role_service: RoleService,
        house_name: str,
        position_key: str,
    ) -> list[discord.Member]:
        eligible: list[discord.Member] = []
        for member in guild.members:
            if member.bot:
                continue
            if self._member_house(role_service, guild, member) != house_name:
                continue
            if not self._member_has_position(role_service, guild, member, position_key):
                continue
            eligible.append(member)
        return eligible

    def _build_house_roster(
        self,
        *,
        guild: discord.Guild,
        house_name: str,
        repo: QuidditchRepository,
        role_service: RoleService,
        progress_repo: QuidditchProgressRepository,
        opponent_hint_levels: dict[str, int],
    ) -> list[dict[str, Any]]:
        roster: list[dict[str, Any]] = []
        used_npc_names: set[str] = set()

        for position_key, needed in self.REQUIRED_COUNTS.items():
            eligible_members = self._eligible_members_for_house_position(
                guild=guild,
                role_service=role_service,
                house_name=house_name,
                position_key=position_key,
            )

            selected_members = self._take_rotating_members(
                available_members=eligible_members,
                needed=needed,
                repo=repo,
                guild_id=guild.id,
                house_name=house_name,
                position_key=position_key,
            )

            for member in selected_members:
                roster.append(
                    self._build_real_player(
                        member=member,
                        position_key=position_key,
                        progress_repo=progress_repo,
                    )
                )

            missing = needed - len(selected_members)
            target_level = opponent_hint_levels.get(position_key, 18)
            for _ in range(missing):
                roster.append(
                    self._build_npc_player(
                        house_name=house_name,
                        position_key=position_key,
                        target_level=target_level,
                        used_names=used_npc_names,
                    )
                )

        return roster

    def _average_position_levels(
        self,
        roster: list[dict[str, Any]],
    ) -> dict[str, int]:
        result: dict[str, int] = {}
        for position_key in self.REQUIRED_COUNTS.keys():
            players = [p for p in roster if p["position"] == position_key]
            if not players:
                result[position_key] = 18
                continue
            result[position_key] = max(
                1,
                round(sum(int(p["level"]) for p in players) / len(players)),
            )
        return result

    def _build_lineups(
        self,
        *,
        guild: discord.Guild,
        home_house: str,
        away_house: str,
        repo: QuidditchRepository,
        role_service: RoleService,
        progress_repo: QuidditchProgressRepository,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        home_seed = self._build_house_roster(
            guild=guild,
            house_name=home_house,
            repo=repo,
            role_service=role_service,
            progress_repo=progress_repo,
            opponent_hint_levels={},
        )
        away_seed = self._build_house_roster(
            guild=guild,
            house_name=away_house,
            repo=repo,
            role_service=role_service,
            progress_repo=progress_repo,
            opponent_hint_levels=self._average_position_levels(home_seed),
        )

        home_avg = self._average_position_levels(away_seed)
        final_home = self._build_house_roster(
            guild=guild,
            house_name=home_house,
            repo=repo,
            role_service=role_service,
            progress_repo=progress_repo,
            opponent_hint_levels=home_avg,
        )
        return final_home, away_seed

    def _participant_user_ids(self, state: dict[str, Any]) -> set[int]:
        participant_ids: set[int] = set()
        for side_key in ("home_lineup", "away_lineup"):
            for player in state.get(side_key, []):
                user_id = player.get("user_id")
                if user_id is not None:
                    participant_ids.add(int(user_id))
        return participant_ids

    def _spectator_names(
        self,
        *,
        guild: discord.Guild,
        participant_ids: set[int],
    ) -> list[str]:
        return [
            self._trim_name(member.display_name)
            for member in guild.members
            if not member.bot and member.id not in participant_ids
        ]

    async def _update_scoreboard_message(
        self,
        *,
        guild: discord.Guild,
        repo: QuidditchRepository,
        service: QuidditchService,
        season_id: int,
    ) -> None:
        config = service.get_config(guild.id)
        if config is None or config["scoreboard_channel_id"] is None:
            return

        season = None
        latest = repo.get_latest_season(guild.id)
        if latest is not None and int(latest["id"]) == season_id:
            season = latest
        else:
            season = repo.conn.execute(
                "SELECT * FROM quidditch_seasons WHERE id = ?",
                (season_id,),
            ).fetchone()

        if season is None:
            return

        standings = repo.get_standings(season_id)
        title, description = service.build_scoreboard_embed(season, standings)
        channel = guild.get_channel(int(config["scoreboard_channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(title=title, description=description, color=0xD4AF37)
        scoreboard_message_id = config["scoreboard_message_id"]

        if scoreboard_message_id is not None:
            try:
                message = await channel.fetch_message(int(scoreboard_message_id))
                await message.edit(embed=embed)
                return
            except discord.HTTPException:
                pass

        message = await channel.send(embed=embed)
        service.set_scoreboard_message_id(guild.id, message.id)

    def _all_regular_fixtures_completed(self, fixtures: list[Any]) -> bool:
        regulars = [fixture for fixture in fixtures if str(fixture["stage"]) == "regular"]
        return bool(regulars) and all(str(fixture["status"]) == "completed" for fixture in regulars)

    def _placement_fixtures_need_fill(self, fixtures: list[Any]) -> bool:
        for fixture in fixtures:
            if str(fixture["stage"]) in {"third_place", "final"}:
                if str(fixture["home_house"]) == "TBD" or str(fixture["away_house"]) == "TBD":
                    return True
        return False

    def _prepare_placement_matchups(
        self,
        *,
        repo: QuidditchRepository,
        season_id: int,
    ) -> None:
        fixtures = repo.list_fixtures_for_season(season_id)
        if not self._all_regular_fixtures_completed(fixtures):
            return
        if not self._placement_fixtures_need_fill(fixtures):
            return

        standings = repo.get_standings(season_id)
        ranked = [str(row["house_name"]) for row in standings]
        if len(ranked) < 4:
            return

        third_place = next((f for f in fixtures if str(f["stage"]) == "third_place"), None)
        final = next((f for f in fixtures if str(f["stage"]) == "final"), None)

        if third_place is not None:
            repo.update_fixture_matchup(
                int(third_place["id"]),
                home_house=ranked[2],
                away_house=ranked[3],
            )
        if final is not None:
            repo.update_fixture_matchup(
                int(final["id"]),
                home_house=ranked[0],
                away_house=ranked[1],
            )

    async def _create_or_refresh_official_message(
        self,
        *,
        guild: discord.Guild,
        fixture,
        live_state,
        runtime_state: dict[str, Any],
        full_log: list[str],
        ended: bool,
        preserve_started_manually: bool,
    ) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            service = QuidditchService(repo)
            config = service.get_config(guild.id)
            if config is None or config["match_channel_id"] is None:
                return

            channel = guild.get_channel(int(config["match_channel_id"]))
            if not isinstance(channel, discord.TextChannel):
                return

            image_path = await self._render_match_image(
                home_house=str(fixture["home_house"]),
                away_house=str(fixture["away_house"]),
                home_score=int(runtime_state["home_score"]),
                away_score=int(runtime_state["away_score"]),
                home_lineup=runtime_state["home_lineup"],
                away_lineup=runtime_state["away_lineup"],
            )

            embeds = self._build_live_embeds(
                home_house=str(fixture["home_house"]),
                away_house=str(fixture["away_house"]),
                home_lineup=runtime_state["home_lineup"],
                away_lineup=runtime_state["away_lineup"],
                full_log=full_log,
                footer_text="Official Quidditch match",
                image_filename="quidditch_live_match.png",
                is_test=False,
                ended=ended,
                runtime_state=runtime_state,
            )

            view = None if ended else CheerView(
                cog=self,
                match_scope="official",
                match_id=int(fixture["id"]),
                home_house=str(fixture["home_house"]),
                away_house=str(fixture["away_house"]),
            )
            discord_file = discord.File(str(image_path), filename="quidditch_live_match.png")

            if live_state is not None and live_state["channel_id"] and live_state["message_id"]:
                try:
                    message = await channel.fetch_message(int(live_state["message_id"]))
                    await message.edit(embeds=embeds, attachments=[discord_file], view=view)
                    repo.upsert_live_match_state(
                        int(fixture["id"]),
                        channel_id=channel.id,
                        message_id=message.id,
                        image_path=str(image_path),
                        log_entries=full_log,
                        started_at=live_state["started_at"],
                        ends_at=live_state["ends_at"],
                        snitch_unlocked_at=live_state["snitch_unlocked_at"],
                        started_manually=preserve_started_manually,
                    )
                    conn.commit()
                    return
                except discord.HTTPException:
                    pass

            message = await channel.send(embeds=embeds, file=discord_file, view=view)
            started_at = live_state["started_at"] if live_state is not None else self._now().isoformat()
            ends_at = live_state["ends_at"] if live_state is not None else (self._now() + timedelta(hours=10)).isoformat()
            snitch_unlocked_at = (
                live_state["snitch_unlocked_at"]
                if live_state is not None
                else (self._now() + timedelta(hours=8)).isoformat()
            )
            repo.upsert_live_match_state(
                int(fixture["id"]),
                channel_id=channel.id,
                message_id=message.id,
                image_path=str(image_path),
                log_entries=full_log,
                started_at=started_at,
                ends_at=ends_at,
                snitch_unlocked_at=snitch_unlocked_at,
                started_manually=preserve_started_manually,
            )
            conn.commit()

    async def _create_or_refresh_test_message(
        self,
        *,
        guild: discord.Guild,
        test_match,
        runtime_state: dict[str, Any],
        full_log: list[str],
        ended: bool,
    ) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)

            channel = guild.get_channel(int(test_match["channel_id"])) if test_match["channel_id"] else None
            if not isinstance(channel, discord.TextChannel):
                config = repo.get_config(guild.id)
                if config is None or config["match_channel_id"] is None:
                    return
                channel = guild.get_channel(int(config["match_channel_id"]))
                if not isinstance(channel, discord.TextChannel):
                    return

            image_path = await self._render_match_image(
                home_house=str(test_match["home_house"]),
                away_house=str(test_match["away_house"]),
                home_score=int(runtime_state["home_score"]),
                away_score=int(runtime_state["away_score"]),
                home_lineup=runtime_state["home_lineup"],
                away_lineup=runtime_state["away_lineup"],
            )

            embeds = self._build_live_embeds(
                home_house=str(test_match["home_house"]),
                away_house=str(test_match["away_house"]),
                home_lineup=runtime_state["home_lineup"],
                away_lineup=runtime_state["away_lineup"],
                full_log=full_log,
                footer_text="Unofficial test match",
                image_filename="quidditch_test_match.png",
                is_test=True,
                ended=ended,
                runtime_state=runtime_state,
            )

            view = None if ended else CheerView(
                cog=self,
                match_scope="test",
                match_id=int(test_match["id"]),
                home_house=str(test_match["home_house"]),
                away_house=str(test_match["away_house"]),
            )
            discord_file = discord.File(str(image_path), filename="quidditch_test_match.png")

            if test_match["message_id"]:
                try:
                    message = await channel.fetch_message(int(test_match["message_id"]))
                    await message.edit(embeds=embeds, attachments=[discord_file], view=view)
                    repo.update_test_match_message(
                        int(test_match["id"]),
                        channel_id=channel.id,
                        message_id=message.id,
                    )
                    repo.set_test_match_image_path(int(test_match["id"]), str(image_path))
                    conn.commit()
                    return
                except discord.HTTPException:
                    pass

            message = await channel.send(embeds=embeds, file=discord_file, view=view)
            repo.update_test_match_message(
                int(test_match["id"]),
                channel_id=channel.id,
                message_id=message.id,
            )
            repo.set_test_match_image_path(int(test_match["id"]), str(image_path))
            conn.commit()

    def _get_current_official_prompt_target(self, guild_id: int) -> tuple[str | None, int | None, str | None]:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            latest_season = repo.get_latest_season(guild_id)
            if latest_season is None:
                return None, None, "No Quidditch season is currently available."

            active_fixture = repo.get_active_fixture(int(latest_season["id"]))
            if active_fixture is not None:
                matchup = f"{active_fixture['home_house']} vs {active_fixture['away_house']}"
                return "gameday", int(active_fixture["id"]), matchup

            next_fixture = repo.get_next_scheduled_fixture(int(latest_season["id"]))
            if next_fixture is None:
                return None, None, "There is no active game or upcoming betting prompt to refresh."

            betting_state = repo.get_betting_state(int(next_fixture["id"]))
            if betting_state is not None and str(betting_state["status"]) in {"pending", "announced"}:
                matchup = f"{next_fixture['home_house']} vs {next_fixture['away_house']}"
                return "betting", int(next_fixture["id"]), matchup

        return None, None, "There is no active game or betting prompt to refresh right now."

    async def _refresh_current_quidditch_prompts(self, guild: discord.Guild) -> str:
        stage, fixture_id, matchup = self._get_current_official_prompt_target(guild.id)
        if stage is None or fixture_id is None:
            return matchup or "There is no active Quidditch prompt to refresh right now."

        if stage == "betting":
            await self._cleanup_betting_messages(guild, fixture_id)
            await self._announce_betting_for_fixture(guild, fixture_id)
            return f"Refreshed the current betting prompt for **{matchup}**."

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            live_state = repo.get_live_match_state(fixture_id)
        if live_state is not None:
            await self._delete_message_if_exists(guild, live_state["channel_id"], live_state["message_id"])

        await self._ensure_official_match_initialized(
            guild=guild,
            fixture_id=fixture_id,
        )
        return f"Refreshed the current live match prompt for **{matchup}**."

    async def _ensure_official_match_initialized(
        self,
        *,
        guild: discord.Guild,
        fixture_id: int,
    ) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            fixture = repo.get_fixture(fixture_id)
            if fixture is None:
                return

            live_state = repo.get_live_match_state(fixture_id)
            runtime_state = repo.get_runtime_state("official", fixture_id)

            if runtime_state is None:
                betting_state = repo.get_betting_state(fixture_id)
                preview_state = self._parse_preview_state(betting_state)
                home_lineup = preview_state.get("home_lineup") or []
                away_lineup = preview_state.get("away_lineup") or []
                if not home_lineup or not away_lineup:
                    role_service = self._build_role_service(conn)
                    progress_repo = QuidditchProgressRepository(conn)
                    home_lineup, away_lineup = self._build_lineups(
                        guild=guild,
                        home_house=str(fixture["home_house"]),
                        away_house=str(fixture["away_house"]),
                        repo=repo,
                        role_service=role_service,
                        progress_repo=progress_repo,
                    )

                started_at_dt = (
                    datetime.fromisoformat(str(live_state["started_at"])).astimezone(self.TZ)
                    if live_state is not None and live_state["started_at"]
                    else self._now()
                )
                runtime_state = self.engine.build_initial_state(
                    home_house=str(fixture["home_house"]),
                    away_house=str(fixture["away_house"]),
                    home_lineup=home_lineup,
                    away_lineup=away_lineup,
                    now=started_at_dt,
                    is_test=False,
                )
                repo.upsert_runtime_state("official", fixture_id, runtime_state)

                left_house, right_house = self.image_service.get_display_order(
                    str(fixture["home_house"]),
                    str(fixture["away_house"]),
                )
                kickoff_log = [
                    f"{started_at_dt.strftime('%H:%M')} And the game is off! {left_house} vs {right_house} is underway.",
                    f"{started_at_dt.strftime('%H:%M')} Brooms kick skyward and the crowd erupts around the pitch.",
                ]
                repo.replace_live_match_log(fixture_id, kickoff_log)
                conn.commit()

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            fixture = repo.get_fixture(fixture_id)
            live_state = repo.get_live_match_state(fixture_id)
            runtime_state = repo.get_runtime_state("official", fixture_id)
            if fixture is None or runtime_state is None:
                return

            try:
                full_log = json.loads(str(live_state["log_json"])) if live_state is not None else []
            except Exception:
                full_log = []
            started_manually = bool(live_state["started_manually"]) if live_state is not None else False

        await self._create_or_refresh_official_message(
            guild=guild,
            fixture=fixture,
            live_state=live_state,
            runtime_state=runtime_state,
            full_log=full_log,
            ended=False,
            preserve_started_manually=started_manually,
        )

    async def _ensure_test_match_initialized(
        self,
        *,
        guild: discord.Guild,
        test_match_id: int,
    ) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            test_match = repo.get_test_match(test_match_id)
            if test_match is None:
                return

            runtime_state = repo.get_runtime_state("test", test_match_id)
            if runtime_state is None:
                role_service = self._build_role_service(conn)
                progress_repo = QuidditchProgressRepository(conn)
                home_lineup, away_lineup = self._build_lineups(
                    guild=guild,
                    home_house=str(test_match["home_house"]),
                    away_house=str(test_match["away_house"]),
                    repo=repo,
                    role_service=role_service,
                    progress_repo=progress_repo,
                )
                started_at_dt = datetime.fromisoformat(str(test_match["started_at"])).astimezone(self.TZ)
                runtime_state = self.engine.build_initial_state(
                    home_house=str(test_match["home_house"]),
                    away_house=str(test_match["away_house"]),
                    home_lineup=home_lineup,
                    away_lineup=away_lineup,
                    now=started_at_dt,
                    is_test=True,
                )
                repo.upsert_runtime_state("test", test_match_id, runtime_state)

                left_house, right_house = self.image_service.get_display_order(
                    str(test_match["home_house"]),
                    str(test_match["away_house"]),
                )
                full_log = [
                    f"{started_at_dt.strftime('%H:%M')} And the game is off! {left_house} vs {right_house} test match underway.",
                    f"{started_at_dt.strftime('%H:%M')} This one is unofficial and will not affect standings.",
                ]
                repo.replace_test_match_log(test_match_id, full_log)
                conn.commit()

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            test_match = repo.get_test_match(test_match_id)
            runtime_state = repo.get_runtime_state("test", test_match_id)
            if test_match is None or runtime_state is None:
                return
            try:
                full_log = json.loads(str(test_match["log_json"]))
            except Exception:
                full_log = []

        await self._create_or_refresh_test_message(
            guild=guild,
            test_match=test_match,
            runtime_state=runtime_state,
            full_log=full_log,
            ended=False,
        )

    async def _finalize_official_match(
        self,
        *,
        guild: discord.Guild,
        fixture_id: int,
        runtime_state: dict[str, Any],
    ) -> None:
        final_message_id: int | None = None
        final_channel_id: int | None = None
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            fixture = repo.get_fixture(fixture_id)
            live_state = repo.get_live_match_state(fixture_id)
            betting_state = repo.get_betting_state(fixture_id)
            if fixture is None or live_state is None:
                return

            winner_house = str(runtime_state["winner_house"])
            repo.apply_fixture_result(
                fixture_id,
                home_score=int(runtime_state["home_score"]),
                away_score=int(runtime_state["away_score"]),
                winner_house=winner_house,
            )
            repo.delete_runtime_state("official", fixture_id)
            repo.clear_match_cheers("official", fixture_id)

            contribution_repo = ContributionRepository(conn)
            contribution_repo.add_house_bonus_points(winner_house, 150)

            self._prepare_placement_matchups(repo=repo, season_id=int(fixture["season_id"]))
            conn.commit()

        channel = guild.get_channel(int(live_state["channel_id"])) if live_state["channel_id"] else None
        if isinstance(channel, discord.TextChannel) and live_state["message_id"]:
            try:
                message = await channel.fetch_message(int(live_state["message_id"]))
                await message.delete()
            except discord.HTTPException:
                pass

            image_path = await self._render_match_image(
                home_house=str(fixture["home_house"]),
                away_house=str(fixture["away_house"]),
                home_score=int(runtime_state["home_score"]),
                away_score=int(runtime_state["away_score"]),
                home_lineup=runtime_state["home_lineup"],
                away_lineup=runtime_state["away_lineup"],
            )
            final_message = await channel.send(
                embed=self._final_score_embed(),
                file=discord.File(str(image_path), filename="quidditch_final_score.png"),
            )
            final_message_id = final_message.id
            final_channel_id = channel.id

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            if final_message_id is not None:
                existing = repo.get_betting_state(fixture_id)
                preview = self._parse_preview_state(existing)
                odds_home = float(existing["odds_home"]) if existing is not None else 1.9
                odds_away = float(existing["odds_away"]) if existing is not None else 1.9
                repo.upsert_betting_state(
                    fixture_id,
                    status=(str(existing["status"]) if existing is not None else "closed"),
                    announced_at=(str(existing["announced_at"]) if existing is not None and existing["announced_at"] else None),
                    cleanup_at=(str(existing["cleanup_at"]) if existing is not None and existing["cleanup_at"] else None),
                    preview_state=preview,
                    odds_home=odds_home,
                    odds_away=odds_away,
                    final_message_id=final_message_id,
                )
            service = QuidditchService(repo)
            await self._update_scoreboard_message(
                guild=guild,
                repo=repo,
                service=service,
                season_id=int(fixture["season_id"]),
            )

            bot_state_repo = BotStateRepository(conn)
            contribution_repo = ContributionRepository(conn)
            board_service = HouseCupBoardService(bot_state_repo, contribution_repo)
            await board_service.create_or_update_board(guild)
            conn.commit()

        await self._post_betting_results(guild, fixture_id, str(runtime_state["winner_house"]))
        await self._schedule_betting_for_next_fixture(guild, delay_minutes=20, force_now=False)

    async def _finalize_test_match(
        self,
        *,
        guild: discord.Guild,
        test_match_id: int,
        runtime_state: dict[str, Any],
    ) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            test_match = repo.get_test_match(test_match_id)
            if test_match is None:
                return
            repo.complete_test_match(test_match_id)
            repo.delete_runtime_state("test", test_match_id)
            repo.clear_match_cheers("test", test_match_id)
            conn.commit()

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            test_match = repo.get_test_match(test_match_id)
            if test_match is None:
                return
            try:
                full_log = json.loads(str(test_match["log_json"]))
            except Exception:
                full_log = []

        await self._create_or_refresh_test_message(
            guild=guild,
            test_match=test_match,
            runtime_state=runtime_state,
            full_log=full_log,
            ended=True,
        )

    async def _tick_official_fixture(
        self,
        *,
        guild: discord.Guild,
        fixture_id: int,
    ) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            fixture = repo.get_fixture(fixture_id)
            live_state = repo.get_live_match_state(fixture_id)
            runtime_state = repo.get_runtime_state("official", fixture_id)
            if fixture is None or live_state is None or runtime_state is None:
                return

            try:
                full_log = json.loads(str(live_state["log_json"]))
            except Exception:
                full_log = []

            old_home = int(runtime_state["home_score"])
            old_away = int(runtime_state["away_score"])

            result = self.engine.tick(
                runtime_state,
                now=self._now(),
                spectator_names=self._spectator_names(
                    guild=guild,
                    participant_ids=self._participant_user_ids(runtime_state),
                ),
            )
            runtime_state = result.state
            repo.upsert_runtime_state("official", fixture_id, runtime_state)

            if result.new_logs:
                full_log.extend(result.new_logs)
                repo.replace_live_match_log(fixture_id, full_log)

            score_changed = result.score_changed or (
                int(runtime_state["home_score"]) != old_home
                or int(runtime_state["away_score"]) != old_away
            )

            conn.commit()

        if result.new_logs or score_changed or result.ended:
            with self.database.connect() as conn:
                repo = QuidditchRepository(conn)
                fixture = repo.get_fixture(fixture_id)
                live_state = repo.get_live_match_state(fixture_id)
                runtime_state = repo.get_runtime_state("official", fixture_id)
                if fixture is None or live_state is None or runtime_state is None:
                    return
                try:
                    full_log = json.loads(str(live_state["log_json"]))
                except Exception:
                    full_log = []

            await self._create_or_refresh_official_message(
                guild=guild,
                fixture=fixture,
                live_state=live_state,
                runtime_state=runtime_state,
                full_log=full_log,
                ended=result.ended,
                preserve_started_manually=bool(live_state["started_manually"]),
            )

        if result.ended:
            await self._finalize_official_match(
                guild=guild,
                fixture_id=fixture_id,
                runtime_state=runtime_state,
            )

    async def _tick_test_match(
        self,
        *,
        guild: discord.Guild,
        test_match_id: int,
    ) -> None:
        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            test_match = repo.get_test_match(test_match_id)
            runtime_state = repo.get_runtime_state("test", test_match_id)
            if test_match is None or runtime_state is None:
                return

            try:
                full_log = json.loads(str(test_match["log_json"]))
            except Exception:
                full_log = []

            old_home = int(runtime_state["home_score"])
            old_away = int(runtime_state["away_score"])

            result = self.engine.tick(
                runtime_state,
                now=self._now(),
                spectator_names=self._spectator_names(
                    guild=guild,
                    participant_ids=self._participant_user_ids(runtime_state),
                ),
            )
            runtime_state = result.state
            repo.upsert_runtime_state("test", test_match_id, runtime_state)

            if result.new_logs:
                full_log.extend(result.new_logs)
                repo.replace_test_match_log(test_match_id, full_log)

            score_changed = result.score_changed or (
                int(runtime_state["home_score"]) != old_home
                or int(runtime_state["away_score"]) != old_away
            )
            conn.commit()

        if result.new_logs or score_changed or result.ended:
            with self.database.connect() as conn:
                repo = QuidditchRepository(conn)
                test_match = repo.get_test_match(test_match_id)
                runtime_state = repo.get_runtime_state("test", test_match_id)
                if test_match is None or runtime_state is None:
                    return
                try:
                    full_log = json.loads(str(test_match["log_json"]))
                except Exception:
                    full_log = []

            await self._create_or_refresh_test_message(
                guild=guild,
                test_match=test_match,
                runtime_state=runtime_state,
                full_log=full_log,
                ended=result.ended,
            )

        if result.ended:
            await self._finalize_test_match(
                guild=guild,
                test_match_id=test_match_id,
                runtime_state=runtime_state,
            )

    async def handle_cheer(
        self,
        *,
        interaction: discord.Interaction,
        match_scope: str,
        match_id: int,
        cheering_house: str,
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This can only be used in the server.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            runtime_state = repo.get_runtime_state(match_scope, match_id)
            if runtime_state is None:
                await interaction.response.send_message(
                    "That match is no longer active.",
                    ephemeral=True,
                )
                return

            participant_ids = self._participant_user_ids(runtime_state)
            if interaction.user.id in participant_ids:
                await interaction.response.send_message(
                    "Players in the current match cannot cheer.",
                    ephemeral=True,
                )
                return

            now = self._now()
            if not repo.can_user_cheer_again(match_scope, match_id, interaction.user.id, now):
                await interaction.response.send_message(
                    "You can cheer only once every 20 minutes for this match.",
                    ephemeral=True,
                )
                return

            log_line = self.engine.apply_cheer(
                runtime_state,
                cheering_house=cheering_house,
                now=now,
            )
            repo.upsert_runtime_state(match_scope, match_id, runtime_state)
            repo.record_cheer(
                match_scope,
                match_id,
                interaction.user.id,
                cheering_house,
                now.isoformat(),
            )

            if match_scope == "official":
                live_state = repo.get_live_match_state(match_id)
                full_log = []
                if live_state is not None:
                    try:
                        full_log = json.loads(str(live_state["log_json"]))
                    except Exception:
                        full_log = []
                full_log.append(log_line)
                repo.replace_live_match_log(match_id, full_log)
                conn.commit()
            else:
                test_match = repo.get_test_match(match_id)
                full_log = []
                if test_match is not None:
                    try:
                        full_log = json.loads(str(test_match["log_json"]))
                    except Exception:
                        full_log = []
                full_log.append(log_line)
                repo.replace_test_match_log(match_id, full_log)
                conn.commit()

        if match_scope == "official":
            with self.database.connect() as conn:
                repo = QuidditchRepository(conn)
                fixture = repo.get_fixture(match_id)
                live_state = repo.get_live_match_state(match_id)
                runtime_state = repo.get_runtime_state("official", match_id)
                if fixture is None or live_state is None or runtime_state is None:
                    await interaction.response.send_message("Cheer recorded.", ephemeral=True)
                    return
                try:
                    full_log = json.loads(str(live_state["log_json"]))
                except Exception:
                    full_log = []

            await self._create_or_refresh_official_message(
                guild=interaction.guild,
                fixture=fixture,
                live_state=live_state,
                runtime_state=runtime_state,
                full_log=full_log,
                ended=False,
                preserve_started_manually=bool(live_state["started_manually"]),
            )
        else:
            with self.database.connect() as conn:
                repo = QuidditchRepository(conn)
                test_match = repo.get_test_match(match_id)
                runtime_state = repo.get_runtime_state("test", match_id)
                if test_match is None or runtime_state is None:
                    await interaction.response.send_message("Cheer recorded.", ephemeral=True)
                    return
                try:
                    full_log = json.loads(str(test_match["log_json"]))
                except Exception:
                    full_log = []

            await self._create_or_refresh_test_message(
                guild=interaction.guild,
                test_match=test_match,
                runtime_state=runtime_state,
                full_log=full_log,
                ended=False,
            )

        if interaction.response.is_done():
            await interaction.followup.send(f"You cheered for **{cheering_house}**!", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"You cheered for **{cheering_house}**!",
                ephemeral=True,
            )

    @tasks.loop(minutes=1)
    async def quidditch_loop(self) -> None:
        now = self._now()

        for guild in self.bot.guilds:
            try:
                with self.database.connect() as conn:
                    repo = QuidditchRepository(conn)
                    service = QuidditchService(repo)

                    latest_season = repo.get_latest_season(guild.id)
                    if latest_season is not None:
                        self._prepare_placement_matchups(
                            repo=repo,
                            season_id=int(latest_season["id"]),
                        )
                        conn.commit()

                        active_fixture = repo.get_active_fixture(int(latest_season["id"]))
                    else:
                        active_fixture = None

                    active_test = repo.get_active_test_match(guild.id)
                    pending_announcements = repo.list_pending_betting_announcements(now.isoformat())
                    betting_to_cleanup = repo.list_betting_to_cleanup(now.isoformat())

                    if active_fixture is None and active_test is None and latest_season is not None and service.is_loop_enabled(guild.id):
                        next_fixture = repo.get_next_scheduled_fixture(int(latest_season["id"]))
                        if next_fixture is not None:
                            starts_at = datetime.fromisoformat(str(next_fixture["starts_at"])).astimezone(self.TZ)
                            if (
                                starts_at <= now
                                and str(next_fixture["home_house"]) != "TBD"
                                and str(next_fixture["away_house"]) != "TBD"
                            ):
                                repo.set_fixture_active(int(next_fixture["id"]), starts_at=starts_at.isoformat())
                                repo.upsert_live_match_state(
                                    int(next_fixture["id"]),
                                    channel_id=None,
                                    message_id=None,
                                    image_path=None,
                                    log_entries=[],
                                    started_at=starts_at.isoformat(),
                                    ends_at=(starts_at + timedelta(hours=10)).isoformat(),
                                    snitch_unlocked_at=(starts_at + timedelta(hours=8)).isoformat(),
                                    started_manually=False,
                                )
                                conn.commit()

                with self.database.connect() as conn:
                    repo = QuidditchRepository(conn)
                    latest_season = repo.get_latest_season(guild.id)
                    active_fixture = repo.get_active_fixture(int(latest_season["id"])) if latest_season is not None else None
                    active_test = repo.get_active_test_match(guild.id)

                for betting_row in pending_announcements:
                    await self._announce_betting_for_fixture(guild, int(betting_row["fixture_id"]))

                for betting_row in betting_to_cleanup:
                    await self._cleanup_betting_messages(guild, int(betting_row["fixture_id"]))
                    with self.database.connect() as conn:
                        repo = QuidditchRepository(conn)
                        repo.mark_betting_closed(int(betting_row["fixture_id"]))
                        conn.commit()

                if active_fixture is not None:
                    await self._ensure_official_match_initialized(
                        guild=guild,
                        fixture_id=int(active_fixture["id"]),
                    )
                    await self._tick_official_fixture(
                        guild=guild,
                        fixture_id=int(active_fixture["id"]),
                    )

                if active_test is not None:
                    await self._ensure_test_match_initialized(
                        guild=guild,
                        test_match_id=int(active_test["id"]),
                    )
                    await self._tick_test_match(
                        guild=guild,
                        test_match_id=int(active_test["id"]),
                    )
            except Exception:
                continue

    @quidditch_loop.before_loop
    async def before_quidditch_loop(self) -> None:
        await self.bot.wait_until_ready()

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

        await self._ensure_official_match_initialized(
            guild=interaction.guild,
            fixture_id=int(result["fixture"]["id"]),
        )

        fixture = result["fixture"]
        await interaction.response.send_message(
            f"Manual Quidditch start activated.\n"
            f"**{fixture['home_house']} vs {fixture['away_house']}** has started now.",
            ephemeral=True,
        )

    @app_commands.command(
        name="quidditch_betting_now",
        description="Admin: immediately post the next official Quidditch betting preview.",
    )
    async def quidditch_betting_now(
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

        result = await self._schedule_betting_for_next_fixture(interaction.guild, delay_minutes=0, force_now=True)
        if result is None:
            await interaction.response.send_message(
                "No upcoming official fixture could be prepared for betting.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            repo = QuidditchRepository(conn)
            latest_season = repo.get_latest_season(interaction.guild.id)
            next_fixture = repo.get_next_scheduled_fixture(int(latest_season["id"])) if latest_season is not None else None
        if next_fixture is not None and "already exists" not in result.lower():
            await self._announce_betting_for_fixture(interaction.guild, int(next_fixture["id"]))
        await interaction.response.send_message(
            result,
            ephemeral=True,
        )

    @app_commands.command(
        name="update_quidditch_prompts",
        description="Admin: refresh the current official Quidditch betting or live-match prompt.",
    )
    async def update_quidditch_prompts(
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

        result = await self._refresh_current_quidditch_prompts(interaction.guild)
        await interaction.response.send_message(
            result,
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

            latest = repo.get_latest_season(interaction.guild.id)
            active_fixture = repo.get_active_fixture(int(latest["id"])) if latest is not None else None
            live_state = repo.get_live_match_state(int(active_fixture["id"])) if active_fixture is not None else None

            try:
                result = service.stop_manual_now(guild_id=interaction.guild.id)
                if active_fixture is not None:
                    repo.delete_runtime_state("official", int(active_fixture["id"]))
                    repo.clear_match_cheers("official", int(active_fixture["id"]))
                conn.commit()
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

        if live_state is not None and live_state["channel_id"] and live_state["message_id"]:
            channel = interaction.guild.get_channel(int(live_state["channel_id"]))
            if isinstance(channel, discord.TextChannel):
                try:
                    message = await channel.fetch_message(int(live_state["message_id"]))
                    await message.delete()
                except discord.HTTPException:
                    pass

        fixture = result["fixture"]
        await interaction.response.send_message(
            f"Manual Quidditch game stopped.\n"
            f"**{fixture['home_house']} vs {fixture['away_house']}** was reset to the normal scheduled start.",
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
            try:
                result = service.start_test_game(guild_id=interaction.guild.id)
                conn.commit()
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

        await self._ensure_test_match_initialized(
            guild=interaction.guild,
            test_match_id=int(result["test_match_id"]),
        )

        await interaction.response.send_message(
            "Unofficial Quidditch test game started.",
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

        home_house = "Gryffindor"
        away_house = "Ravenclaw"

        home_lineup = self.image_service.build_demo_lineup(home_house)
        away_lineup = self.image_service.build_demo_lineup(away_house)

        image_path = await self._render_match_image(
            home_house=home_house,
            away_house=away_house,
            home_score=score_team1,
            away_score=score_team2,
            home_lineup=home_lineup,
            away_lineup=away_lineup,
        )

        demo_runtime_state = {
            "home_house": home_house,
            "away_house": away_house,
            "home_score": score_team1,
            "away_score": score_team2,
            "home_lineup": home_lineup,
            "away_lineup": away_lineup,
            "inactive_until": {},
            "quaffle_possession_side": "home",
        }
        embeds = self._build_live_embeds(
            home_house=home_house,
            away_house=away_house,
            home_lineup=home_lineup,
            away_lineup=away_lineup,
            full_log=[
                "13:00 And the game is off! Gryffindor vs Ravenclaw is underway.",
                "13:01 A roar sweeps through the stands as both sides settle in.",
                "13:02 The commentator is already losing their mind in the best way.",
            ],
            footer_text="Pitch render test",
            image_filename="quidditch_test_pitch.png",
            is_test=True,
            ended=False,
            runtime_state=demo_runtime_state,
        )

        await interaction.response.send_message(
            embeds=embeds,
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
                repo.delete_runtime_state("test", int(active_test["id"]))
                repo.clear_match_cheers("test", int(active_test["id"]))
                conn.commit()
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

        test_match = result["test_match"]
        await interaction.response.send_message(
            f"Unofficial Quidditch test game stopped.\n"
            f"**{test_match['home_house']} vs {test_match['away_house']}** was cancelled.",
            ephemeral=True,
        )
