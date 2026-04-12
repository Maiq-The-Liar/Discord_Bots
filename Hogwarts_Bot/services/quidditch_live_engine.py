from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(slots=True)
class MatchTickResult:
    state: dict[str, Any]
    new_logs: list[str]
    score_changed: bool
    ended: bool
    winner_house: str | None


class QuidditchLiveEngine:
    POSITIONS = ("keeper", "seeker", "beater", "chaser")
    KNOCKABLE_POSITIONS = {"seeker", "beater", "chaser"}
    SCENARIOS = (
        "balanced",
        "comeback",
        "grindy",
        "chaotic",
        "dominant_then_stable",
        "tense_finish",
    )

    NPC_POOLS: dict[str, dict[str, list[str]]] = {
        "Gryffindor": {
            "keeper": ["Oliver Wood", "Katie Bell"],
            "seeker": ["Harry Potter", "Ginny Weasley"],
            "beater": ["Fred Weasley", "George Weasley", "Jimmy Peakes"],
            "chaser": ["Angelina Johnson", "Alicia Spinnet", "Demelza Robins", "Dean Thomas"],
        },
        "Hufflepuff": {
            "keeper": ["Herbert Fleet", "Summerby"],
            "seeker": ["Cedric Diggory", "Tamsin Applebee"],
            "beater": ["Maxine O'Flaherty", "Silas Diggory", "Beatrice Haywood"],
            "chaser": ["Zacharias Smith", "Nia Goldspring", "Megan Jones", "Rory Fairbairn"],
        },
        "Ravenclaw": {
            "keeper": ["Grant Page", "Randolph Burrow"],
            "seeker": ["Cho Chang", "Luna Lovegood"],
            "beater": ["Duncan Inglebee", "Jeremy Stretton", "Nadia Vale"],
            "chaser": ["Roger Davies", "Marietta Edgecombe", "Eddie Carmichael", "Padma Patil"],
        },
        "Slytherin": {
            "keeper": ["Miles Bletchley", "Cassius Warrington"],
            "seeker": ["Draco Malfoy", "Voldemort"],
            "beater": ["Vincent Crabbe", "Gregory Goyle", "Peregrine Derrick", "Lucian Bole"],
            "chaser": ["Marcus Flint", "Adrian Pucey", "Graham Montague", "Pansy Parkinson"],
        },
    }

    GOAL_TEMPLATES = [
        "{time} — {player} slams a fabulous goal through the hoops for {house}!",
        "{time} — {player} darts past the defence and scores for {house}.",
        "{time} — {player} threads the Quaffle with outrageous precision. {house} score!",
        "{time} — {player} rockets forward and buries another ten points for {house}.",
        "{time} — {player} makes the crowd erupt with a brilliant finish for {house}.",
        "{time} — {player} turns on the speed and flicks in a classy goal for {house}.",
        "{time} — {player} spins away from pressure and tucks home ten for {house}.",
        "{time} — {player} punishes the defence with a clinical strike for {house}.",
    ]

    SAVE_TEMPLATES = [
        "{time} — {keeper} heroically dives and denies {attacker} a certain goal.",
        "{time} — {keeper} gets both hands to the Quaffle and shuts the door.",
        "{time} — {keeper} reads the angle perfectly and stones {attacker}.",
        "{time} — {keeper} throws out a spectacular save to protect the hoops.",
        "{time} — {keeper} snatches the shot out of the air. No goal this time.",
    ]

    KNOCKOUT_TEMPLATES = [
        "{time} — {beater} smacks a vicious bludger into {target}; they look dazed and drop out for a while.",
        "{time} — {beater} catches {target} cleanly with a bludger. They'll need a few minutes to recover.",
        "{time} — {beater} sends {target} spinning off line with a brutal bludger hit.",
        "{time} — {beater} absolutely hammers a bludger at {target}. Mediwizards are taking notes.",
        "{time} — {target} is knocked half senseless by {beater}'s bludger. That's trouble.",
    ]

    FOUL_TEMPLATES = [
        "{time} — A clumsy foul hands momentum to {house}.",
        "{time} — The referee whistles sharply as {house} get away with a suspicious challenge.",
        "{time} — Tempers flare and the pace breaks up for a moment.",
        "{time} — A messy collision leaves both sides shouting at the referee.",
        "{time} — The crowd boos loudly after a rather questionable bit of contact.",
    ]

    TURNOVER_TEMPLATES = [
        "{time} — {player} fumbles the Quaffle under pressure. A wasted chance for {house}.",
        "{time} — {player} misreads the pass and gifts possession away.",
        "{time} — {player} tries something far too fancy and the move collapses.",
        "{time} — {player} loses control mid-flight and the attack fizzles out.",
        "{time} — {player} forces the play and turns it over cheaply.",
    ]

    SNITCH_HUNT_TEMPLATES = [
        "{time} — {seeker} spots the first golden glint of the Snitch and gives chase.",
        "{time} — {seeker} dives sharply after a flash of gold. The stands roar.",
        "{time} — {seeker} thinks they've seen the Snitch near the upper stands.",
        "{time} — Both seekers accelerate violently as a golden blur streaks away.",
        "{time} — {seeker} lunges after the Snitch, but it vanishes again.",
    ]

    SNITCH_CATCH_TEMPLATES = [
        "{time} — {seeker} closes their fist around the Golden Snitch for {house}! The match is over!",
        "{time} — {seeker} makes a breathtaking dive and catches the Snitch! {house} win it!",
        "{time} — {seeker} snatches the Golden Snitch out of thin air. Curtains for this one.",
        "{time} — {seeker} wins the chase, catches the Snitch, and sends {house} into celebration!",
    ]

    CHEER_TEMPLATES = [
        "{time} — The {house} crowd erupts as supporters pour in behind their side.",
        "{time} — Fresh cheers ring out for {house}, giving them a small lift.",
        "{time} — The stands shake with noise as spectators rally for {house}.",
        "{time} — The roar for {house} grows louder and the players seem to feel it.",
    ]

    EASTER_EGG_TEMPLATES = [
        "{time} — {spectator} has stormed the pitch naked. We have a runner. We most definitely have a runner.",
        "{time} — An owl swoops straight through the formation and everyone forgets the Quaffle for a moment.",
        "{time} — Someone in the stands spills butterbeer on half a row. The outrage is immediate.",
        "{time} — A bewitched banner wraps itself around a railing and three prefects panic at once.",
        "{time} — The commentator completely loses the thread and starts yelling about broom aerodynamics.",
        "{time} — {spectator} leans too far over the barrier and is hauled back by very tired staff.",
        "{time} — A bludger chases the wrong target for several deeply concerning seconds.",
    ]

    def build_initial_state(
        self,
        *,
        home_house: str,
        away_house: str,
        home_lineup: list[dict[str, Any]],
        away_lineup: list[dict[str, Any]],
        now: datetime,
        is_test: bool,
    ) -> dict[str, Any]:
        return {
            "home_house": home_house,
            "away_house": away_house,
            "home_score": 0,
            "away_score": 0,
            "scenario": random.choice(self.SCENARIOS),
            "minute": 0,
            "started_at": now.isoformat(),
            "is_test": is_test,
            "snitch_caught": False,
            "winner_house": None,
            "home_momentum": 0.0,
            "away_momentum": 0.0,
            "cheer_boost_home": 0.0,
            "cheer_boost_away": 0.0,
            "home_lineup": deepcopy(home_lineup),
            "away_lineup": deepcopy(away_lineup),
            "inactive_until": {},
            "last_event_at": None,
            "full_log_count": 0,
        }

    def apply_cheer(
        self,
        state: dict[str, Any],
        *,
        cheering_house: str,
        now: datetime,
    ) -> str:
        if cheering_house == state["home_house"]:
            state["cheer_boost_home"] = min(0.12, float(state["cheer_boost_home"]) + 0.0125)
            return random.choice(self.CHEER_TEMPLATES).format(
                time=now.strftime("%H:%M"),
                house=state["home_house"],
            )

        state["cheer_boost_away"] = min(0.12, float(state["cheer_boost_away"]) + 0.0125)
        return random.choice(self.CHEER_TEMPLATES).format(
            time=now.strftime("%H:%M"),
            house=state["away_house"],
        )

    def tick(
        self,
        state: dict[str, Any],
        *,
        now: datetime,
        spectator_names: list[str] | None = None,
    ) -> MatchTickResult:
        spectator_names = spectator_names or []
        state = deepcopy(state)
        logs: list[str] = []
        score_changed = False

        state["minute"] = int(state.get("minute", 0)) + 1
        self._decay_momentum(state)

        if state.get("snitch_caught"):
            return MatchTickResult(
                state=state,
                new_logs=[],
                score_changed=False,
                ended=True,
                winner_house=state.get("winner_house"),
            )

        event_probability = self._event_probability(state)
        if random.random() > event_probability:
            return MatchTickResult(
                state=state,
                new_logs=[],
                score_changed=False,
                ended=False,
                winner_house=None,
            )

        event_type = self._pick_event_type(state, now)

        if event_type == "goal":
            log, scorer_house = self._goal_event(state, now)
            logs.append(log)
            score_changed = True
            self._swing_momentum(state, scorer_house, 0.06)

        elif event_type == "save":
            log = self._save_event(state, now)
            if log:
                logs.append(log)

        elif event_type == "knockout":
            log = self._knockout_event(state, now)
            if log:
                logs.append(log)

        elif event_type == "foul":
            logs.append(random.choice(self.FOUL_TEMPLATES).format(
                time=now.strftime("%H:%M"),
                house=random.choice([state["home_house"], state["away_house"]]),
            ))

        elif event_type == "turnover":
            log = self._turnover_event(state, now)
            if log:
                logs.append(log)

        elif event_type == "snitch_hunt":
            log = self._snitch_hunt_event(state, now)
            if log:
                logs.append(log)

        elif event_type == "snitch_catch":
            log = self._snitch_catch_event(state, now)
            logs.append(log)
            score_changed = True

        elif event_type == "easter_egg":
            logs.append(self._easter_egg_event(state, now, spectator_names))

        state["last_event_at"] = now.isoformat() if logs else state.get("last_event_at")
        state["full_log_count"] = int(state.get("full_log_count", 0)) + len(logs)

        ended = bool(state.get("snitch_caught")) or now >= datetime.fromisoformat(state["started_at"]) + timedelta(hours=10)
        winner_house = None
        if ended:
            winner_house = self._resolve_winner(state, now, logs)

        return MatchTickResult(
            state=state,
            new_logs=logs,
            score_changed=score_changed,
            ended=ended,
            winner_house=winner_house,
        )

    def _event_probability(self, state: dict[str, Any]) -> float:
        scenario = str(state.get("scenario", "balanced"))
        minute = int(state.get("minute", 0))

        base = 0.34
        if scenario == "grindy":
            base = 0.20
        elif scenario == "chaotic":
            base = 0.48
        elif scenario == "tense_finish":
            base = 0.28
        elif scenario == "dominant_then_stable":
            base = 0.38
        elif scenario == "comeback":
            base = 0.33

        if minute >= 480:
            base += 0.06

        return max(0.12, min(0.62, base))

    def _pick_event_type(self, state: dict[str, Any], now: datetime) -> str:
        weights = {
            "goal": 36,
            "save": 16,
            "knockout": 11,
            "foul": 10,
            "turnover": 11,
            "snitch_hunt": 8,
            "snitch_catch": 0,
            "easter_egg": 4,
        }

        elapsed = now - datetime.fromisoformat(state["started_at"])
        if elapsed >= timedelta(hours=8):
            minutes_after = max(0, int((elapsed - timedelta(hours=8)).total_seconds() // 60))
            weights["snitch_catch"] = min(26, 1 + (minutes_after // 18))

        options = list(weights.keys())
        values = [weights[key] for key in options]
        return random.choices(options, weights=values, k=1)[0]

    def _goal_event(self, state: dict[str, Any], now: datetime) -> tuple[str, str]:
        home_attack = self._team_attack_strength(state, "home")
        away_attack = self._team_attack_strength(state, "away")
        home_def = self._team_defence_strength(state, "home")
        away_def = self._team_defence_strength(state, "away")

        scenario = str(state.get("scenario", "balanced"))
        home_edge = home_attack - away_def + float(state["home_momentum"]) + float(state["cheer_boost_home"])
        away_edge = away_attack - home_def + float(state["away_momentum"]) + float(state["cheer_boost_away"])

        if scenario == "dominant_then_stable" and int(state["minute"]) < 180:
            home_edge += 0.04 if random.random() < 0.5 else -0.04
        elif scenario == "comeback" and int(state["minute"]) > 300:
            leader = self._leader_side(state)
            if leader == "home":
                away_edge += 0.08
            elif leader == "away":
                home_edge += 0.08
        elif scenario == "tense_finish" and int(state["minute"]) > 420:
            if abs(int(state["home_score"]) - int(state["away_score"])) <= 30:
                home_edge += 0.03
                away_edge += 0.03

        home_goal_prob = self._clamp_winlike_probability(0.5 + (home_edge - away_edge))
        scoring_side = "home" if random.random() < home_goal_prob else "away"

        scorer = self._random_active_player(state, scoring_side, {"chaser"})
        if scorer is None:
            scorer = self._random_active_player(state, scoring_side, {"beater", "seeker", "chaser"})

        if scoring_side == "home":
            state["home_score"] = int(state["home_score"]) + 10
            house = state["home_house"]
        else:
            state["away_score"] = int(state["away_score"]) + 10
            house = state["away_house"]

        player_name = scorer["display_name"] if scorer else "A wild substitute"
        return (
            random.choice(self.GOAL_TEMPLATES).format(
                time=now.strftime("%H:%M"),
                player=player_name,
                house=house,
            ),
            house,
        )

    def _save_event(self, state: dict[str, Any], now: datetime) -> str | None:
        attacking_side = random.choice(["home", "away"])
        defending_side = "away" if attacking_side == "home" else "home"

        attacker = self._random_active_player(state, attacking_side, {"chaser"})
        keeper = self._random_active_player(state, defending_side, {"keeper"})
        if attacker is None or keeper is None:
            return None

        return random.choice(self.SAVE_TEMPLATES).format(
            time=now.strftime("%H:%M"),
            keeper=keeper["display_name"],
            attacker=attacker["display_name"],
        )

    def _knockout_event(self, state: dict[str, Any], now: datetime) -> str | None:
        striking_side = random.choice(["home", "away"])
        target_side = "away" if striking_side == "home" else "home"

        beater = self._random_active_player(state, striking_side, {"beater"})
        target = self._random_active_player(state, target_side, self.KNOCKABLE_POSITIONS)
        if beater is None or target is None:
            return None

        knocked_minutes = random.randint(8, 26)
        inactive_until = now + timedelta(minutes=knocked_minutes)
        state["inactive_until"][target["token"]] = inactive_until.isoformat()

        return random.choice(self.KNOCKOUT_TEMPLATES).format(
            time=now.strftime("%H:%M"),
            beater=beater["display_name"],
            target=target["display_name"],
        )

    def _turnover_event(self, state: dict[str, Any], now: datetime) -> str | None:
        side = random.choice(["home", "away"])
        player = self._random_active_player(state, side, {"chaser", "beater", "seeker"})
        if player is None:
            return None

        house = state["home_house"] if side == "home" else state["away_house"]
        return random.choice(self.TURNOVER_TEMPLATES).format(
            time=now.strftime("%H:%M"),
            player=player["display_name"],
            house=house,
        )

    def _snitch_hunt_event(self, state: dict[str, Any], now: datetime) -> str | None:
        elapsed = now - datetime.fromisoformat(state["started_at"])
        if elapsed < timedelta(hours=8):
            return None

        side = random.choice(["home", "away"])
        seeker = self._random_active_player(state, side, {"seeker"})
        if seeker is None:
            return None

        return random.choice(self.SNITCH_HUNT_TEMPLATES).format(
            time=now.strftime("%H:%M"),
            seeker=seeker["display_name"],
        )

    def _snitch_catch_event(self, state: dict[str, Any], now: datetime) -> str:
        elapsed = now - datetime.fromisoformat(state["started_at"])
        if elapsed < timedelta(hours=8):
            raise RuntimeError("Snitch catch attempted before unlock window.")

        home_seek = self._team_seek_strength(state, "home") + float(state["home_momentum"]) + float(state["cheer_boost_home"])
        away_seek = self._team_seek_strength(state, "away") + float(state["away_momentum"]) + float(state["cheer_boost_away"])

        home_prob = self._clamp_winlike_probability(0.5 + (home_seek - away_seek))
        side = "home" if random.random() < home_prob else "away"

        seeker = self._random_active_player(state, side, {"seeker"})
        house = state["home_house"] if side == "home" else state["away_house"]

        if side == "home":
            state["home_score"] = int(state["home_score"]) + 150
        else:
            state["away_score"] = int(state["away_score"]) + 150

        state["snitch_caught"] = True
        state["winner_house"] = house

        return random.choice(self.SNITCH_CATCH_TEMPLATES).format(
            time=now.strftime("%H:%M"),
            seeker=seeker["display_name"] if seeker else "The seeker",
            house=house,
        )

    def _easter_egg_event(
        self,
        state: dict[str, Any],
        now: datetime,
        spectator_names: list[str],
    ) -> str:
        spectator = random.choice(spectator_names) if spectator_names else "A random fan"
        return random.choice(self.EASTER_EGG_TEMPLATES).format(
            time=now.strftime("%H:%M"),
            spectator=spectator,
        )

    def _resolve_winner(
        self,
        state: dict[str, Any],
        now: datetime,
        logs: list[str],
    ) -> str:
        if int(state["home_score"]) == int(state["away_score"]):
            side = "home" if random.random() < 0.5 else "away"
            if side == "home":
                state["home_score"] = int(state["home_score"]) + 10
                winner = state["home_house"]
            else:
                state["away_score"] = int(state["away_score"]) + 10
                winner = state["away_house"]

            logs.append(
                f"{now.strftime('%H:%M')} — One last frantic surge breaks the deadlock. No ties in Quidditch today."
            )
            state["winner_house"] = winner
            return winner

        winner = state["home_house"] if int(state["home_score"]) > int(state["away_score"]) else state["away_house"]
        state["winner_house"] = winner
        return winner

    def _random_active_player(
        self,
        state: dict[str, Any],
        side: str,
        allowed_positions: set[str],
    ) -> dict[str, Any] | None:
        lineup_key = "home_lineup" if side == "home" else "away_lineup"
        players = state.get(lineup_key, [])
        active_players: list[dict[str, Any]] = []

        for player in players:
            position = str(player.get("position", "")).lower()
            if position not in allowed_positions:
                continue

            token = str(player.get("token") or player.get("display_name") or player.get("username") or "unknown")
            inactive_until = state.get("inactive_until", {}).get(token)
            if inactive_until and datetime.fromisoformat(inactive_until) > datetime.now(datetime.now().astimezone().tzinfo):
                continue

            player_copy = dict(player)
            player_copy["token"] = token
            player_copy["display_name"] = str(
                player.get("display_name")
                or player.get("username")
                or player.get("name")
                or "Unknown Player"
            )
            active_players.append(player_copy)

        if not active_players:
            return None

        weighted: list[tuple[dict[str, Any], float]] = []
        for player in active_players:
            lvl = max(1, int(player.get("level", 1)))
            weight = 1.0 + min(1.8, lvl / 80.0)
            weighted.append((player, weight))

        population = [entry[0] for entry in weighted]
        weights = [entry[1] for entry in weighted]
        return random.choices(population, weights=weights, k=1)[0]

    def _team_attack_strength(self, state: dict[str, Any], side: str) -> float:
        chasers = self._players_for_side(state, side, {"chaser"})
        beaters = self._players_for_side(state, side, {"beater"})
        chaser_avg = self._avg_level(chasers)
        beater_avg = self._avg_level(beaters)
        return (chaser_avg / 120.0) * 0.34 + (beater_avg / 120.0) * 0.08

    def _team_defence_strength(self, state: dict[str, Any], side: str) -> float:
        keepers = self._players_for_side(state, side, {"keeper"})
        beaters = self._players_for_side(state, side, {"beater"})
        return (self._avg_level(keepers) / 120.0) * 0.26 + (self._avg_level(beaters) / 120.0) * 0.07

    def _team_seek_strength(self, state: dict[str, Any], side: str) -> float:
        seekers = self._players_for_side(state, side, {"seeker"})
        return (self._avg_level(seekers) / 120.0) * 0.32

    def _players_for_side(
        self,
        state: dict[str, Any],
        side: str,
        allowed_positions: set[str],
    ) -> list[dict[str, Any]]:
        lineup_key = "home_lineup" if side == "home" else "away_lineup"
        lineup = state.get(lineup_key, [])
        players: list[dict[str, Any]] = []

        for player in lineup:
            position = str(player.get("position", "")).lower()
            if position not in allowed_positions:
                continue

            token = str(player.get("token") or player.get("display_name") or player.get("username") or "unknown")
            inactive_until = state.get("inactive_until", {}).get(token)
            if inactive_until:
                try:
                    if datetime.fromisoformat(inactive_until) > datetime.now(datetime.now().astimezone().tzinfo):
                        continue
                except ValueError:
                    pass

            players.append(player)

        return players

    def _avg_level(self, players: list[dict[str, Any]]) -> float:
        if not players:
            return 1.0
        return sum(max(1, int(player.get("level", 1))) for player in players) / len(players)

    def _leader_side(self, state: dict[str, Any]) -> str | None:
        if int(state["home_score"]) > int(state["away_score"]):
            return "home"
        if int(state["away_score"]) > int(state["home_score"]):
            return "away"
        return None

    def _decay_momentum(self, state: dict[str, Any]) -> None:
        state["home_momentum"] = max(-0.16, min(0.16, float(state.get("home_momentum", 0.0)) * 0.93))
        state["away_momentum"] = max(-0.16, min(0.16, float(state.get("away_momentum", 0.0)) * 0.93))
        state["cheer_boost_home"] = max(0.0, float(state.get("cheer_boost_home", 0.0)) * 0.985)
        state["cheer_boost_away"] = max(0.0, float(state.get("cheer_boost_away", 0.0)) * 0.985)

    def _swing_momentum(self, state: dict[str, Any], scoring_house: str, amount: float) -> None:
        if scoring_house == state["home_house"]:
            state["home_momentum"] = min(0.16, float(state["home_momentum"]) + amount)
            state["away_momentum"] = max(-0.16, float(state["away_momentum"]) - amount * 0.7)
        else:
            state["away_momentum"] = min(0.16, float(state["away_momentum"]) + amount)
            state["home_momentum"] = max(-0.16, float(state["home_momentum"]) - amount * 0.7)

    def _clamp_winlike_probability(self, raw: float) -> float:
        return max(0.20, min(0.80, raw))