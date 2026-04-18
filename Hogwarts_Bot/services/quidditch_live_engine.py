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
            "keeper": ["Oliver W.", "Katie B."],
            "seeker": ["Harry P.", "Ginny W."],
            "beater": ["Fred W.", "George W.", "Jimmy P."],
            "chaser": ["Angelina J.", "Alicia S.", "Demelza R.", "Dean T."],
        },
        "Hufflepuff": {
            "keeper": ["Herbert F.", "Summerby"],
            "seeker": ["Cedric D.", "Tamsin A."],
            "beater": ["Maxine O.", "Silas D.", "Beatrice H."],
            "chaser": ["Zacharias S.", "Nia G.", "Megan J.", "Rory F."],
        },
        "Ravenclaw": {
            "keeper": ["Grant P.", "Randolph B."],
            "seeker": ["Cho C.", "Luna L."],
            "beater": ["Duncan I.", "Jeremy S.", "Nadia V."],
            "chaser": ["Roger D.", "Marietta E.", "Eddie C.", "Padma P."],
        },
        "Slytherin": {
            "keeper": ["Miles B.", "Cassius W."],
            "seeker": ["Draco M.", "Voldemort"],
            "beater": ["Vincent C.", "Gregory G.", "Peregrine D.", "Lucian B."],
            "chaser": ["Marcus F.", "Adrian P.", "Graham M.", "Pansy P."],
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
        "{time} — {player} slices between two defenders and whips the Quaffle in for {house}.",
        "{time} — {player} hangs in the air for one absurd second and rifles home for {house}.",
        "{time} — {player} sells a shameless fake, leaves the keeper guessing, and scores for {house}.",
        "{time} — {player} absolutely ruins a defender's afternoon and adds ten for {house}.",
        "{time} — {player} arrives like a thunderbolt, hammers the Quaffle through, and {house} cash in again.",
    ]

    SAVE_TEMPLATES = [
        "{time} — {keeper} heroically dives and denies {attacker} a certain goal.",
        "{time} — {keeper} gets both hands to the Quaffle and shuts the door.",
        "{time} — {keeper} reads the angle perfectly and stones {attacker}.",
        "{time} — {keeper} throws out a spectacular save to protect the hoops.",
        "{time} — {keeper} snatches the shot out of the air. No goal this time.",
        "{time} — {keeper} gets a fingertip to it and the Quaffle dies against the rim.",
        "{time} — {keeper} swats the shot away with the expression of someone deeply insulted by the attempt.",
        "{time} — {keeper} sprawls across the hoops and somehow keeps {attacker} out.",
        "{time} — {keeper} reacts impossibly late and still claws the Quaffle clear.",
        "{time} — {keeper} blocks it with reckless elegance and the crowd completely lose their minds.",
    ]

    KNOCKOUT_TEMPLATES = [
        "{time} — {beater} smacks a vicious bludger into {target}; they look dazed and drop out for a while.",
        "{time} — {beater} catches {target} cleanly with a bludger. They'll need a few minutes to recover.",
        "{time} — {beater} sends {target} spinning off line with a brutal bludger hit.",
        "{time} — {beater} absolutely hammers a bludger at {target}. Mediwizards are taking notes.",
        "{time} — {target} is knocked half senseless by {beater}'s bludger. That's trouble.",
        "{time} — {beater} drives a bludger straight through {target}'s plans and very nearly through their ribs.",
        "{time} — {target} takes a savage bludger from {beater} and folds over their broom with a noise nobody enjoys.",
        "{time} — {beater} picks the moment perfectly and detonates a bludger into {target}. The whole stand winces.",
        "{time} — {beater} sends {target} pinwheeling away in complete disarray. That's a nasty one.",
        "{time} — {target} is drilled by {beater}'s bludger and needs a moment, several stars, and possibly a new spine.",
    ]

    FOUL_TEMPLATES = [
        "{time} — A clumsy foul hands momentum to {house}.",
        "{time} — The referee whistles sharply as {house} get away with a suspicious challenge.",
        "{time} — Tempers flare and the pace breaks up for a moment.",
        "{time} — A messy collision leaves both sides shouting at the referee.",
        "{time} — The crowd boos loudly after a rather questionable bit of contact.",
        "{time} — A broom clips where it absolutely should not and the referee goes pale before signalling advantage to {house}.",
        "{time} — Someone has committed a foul with so little subtlety that even the commentator stops laughing for a second.",
        "{time} — The whistle shrieks again; there are six different accusations in the air and all of them sound plausible.",
        "{time} — A late body check sends tempers boiling and gives {house} a precious edge.",
        "{time} — The referee intervenes before this turns into a mid-air divorce court. {house} come out better from it.",
    ]

    TURNOVER_TEMPLATES = [
        "{time} — {player} fumbles the Quaffle under pressure. A wasted chance for {house}.",
        "{time} — {player} misreads the pass and gifts possession away.",
        "{time} — {player} tries something far too fancy and the move collapses.",
        "{time} — {player} loses control mid-flight and the attack fizzles out.",
        "{time} — {player} forces the play and turns it over cheaply.",
        "{time} — {player} drops the Quaffle like it has offended them personally. {house} waste the attack.",
        "{time} — {player} sees a pass that simply does not exist and the whole move dies on the spot.",
        "{time} — {player} gets tangled under pressure and leaves the Quaffle behind in embarrassing fashion.",
        "{time} — {player} overcooks the feed, and possession disappears into the grateful hands of the opposition.",
        "{time} — {player} tries to be a hero, forgets the basics, and gives it away for {house}.",
    ]

    SNITCH_HUNT_TEMPLATES = [
        "{time} — {seeker} spots the first golden glint of the Snitch and gives chase.",
        "{time} — {seeker} dives sharply after a flash of gold. The stands roar.",
        "{time} — {seeker} thinks they've seen the Snitch near the upper stands.",
        "{time} — Both seekers accelerate violently as a golden blur streaks away.",
        "{time} — {seeker} lunges after the Snitch, but it vanishes again.",
        "{time} — {seeker} screams past the commentary box after a flicker of gold that may or may not have been real.",
        "{time} — Both seekers dive toward the lower stands and pull out at the last possible second. Chaos follows.",
        "{time} — {seeker} chases a golden sparkle into traffic and emerges furious, empty-handed, and still accelerating.",
        "{time} — A glint near the hoops sends {seeker} into a reckless plunge after the Snitch.",
        "{time} — The Snitch zips across the pitch like a bad idea and {seeker} tears off after it.",
    ]

    SNITCH_CATCH_TEMPLATES = [
        "{time} — {seeker} closes their fist around the Golden Snitch for {house}! The match is over!",
        "{time} — {seeker} makes a breathtaking dive and catches the Snitch! {house} win it!",
        "{time} — {seeker} snatches the Golden Snitch out of thin air. Curtains for this one.",
        "{time} — {seeker} wins the chase, catches the Snitch, and sends {house} into celebration!",
        "{time} — {seeker} plucks the Snitch from the air with ridiculous composure. {house} have ended it.",
        "{time} — {seeker} vanishes into the glare, reappears with the Snitch in hand, and {house} erupt.",
        "{time} — {seeker} risks life, bone, and basic reason to seize the Snitch for {house}!",
        "{time} — {seeker} gets there first, closes the hand, and rips the heart out of this match for {house}.",
        "{time} — {seeker} wins the ugliest, fastest chase of the day and catches the Snitch for {house}!",
    ]

    CHEER_TEMPLATES = [
        "{time} — The {house} crowd erupts as supporters pour in behind their side.",
        "{time} — Fresh cheers ring out for {house}, giving them a small lift.",
        "{time} — The stands shake with noise as spectators rally for {house}.",
        "{time} — The roar for {house} grows louder and the players seem to feel it.",
        "{time} — A wall of noise crashes down from the {house} section and the tempo lifts immediately.",
        "{time} — Someone starts a chant in the {house} stands and suddenly half the arena is shouting it.",
        "{time} — The {house} supporters are in full voice now, loud enough to rattle broomsticks.",
        "{time} — A thunder of applause sweeps through the {house} end and gives the players fresh legs.",
        "{time} — The {house} faithful decide subtlety is overrated and scream their lungs empty.",
    ]

    EASTER_EGG_TEMPLATES = [
        "{time} — {spectator} has stormed the pitch naked. We have a runner. We most definitely have a runner.",
        "{time} — An owl swoops straight through the formation and everyone forgets the Quaffle for a moment.",
        "{time} — Someone in the stands spills butterbeer on half a row. The outrage is immediate.",
        "{time} — A bewitched banner wraps itself around a railing and three prefects panic at once.",
        "{time} — The commentator completely loses the thread and starts yelling about broom aerodynamics.",
        "{time} — {spectator} leans too far over the barrier and is hauled back by very tired staff.",
        "{time} — A bludger chases the wrong target for several deeply concerning seconds.",
        "{time} — A seat somewhere in the upper stands collapses theatrically and at least four people pretend they saw it coming.",
        "{time} — Two mascots begin fighting near the tunnel and nobody in authority seems eager to intervene.",
        "{time} — A charmed programme bursts into song at exactly the wrong moment and cannot be silenced.",
        "{time} — {spectator} appears to be arguing with a seagull over a meat pie, and somehow the seagull is winning.",
        "{time} — For one cursed moment, every broom on the pitch drifts left at once and the crowd makes a very interesting noise.",
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
            "pressure_effects": [],
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
        logs.extend(self._collect_recovery_logs(state, now))
        self._expire_pressure_effects(state, now)

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
            event_logs, scorer_house = self._goal_event(state, now)
            logs.extend(event_logs)
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

    def _goal_event(self, state: dict[str, Any], now: datetime) -> tuple[list[str], str]:
        home_attack = self._team_attack_strength(state, "home", now)
        away_attack = self._team_attack_strength(state, "away", now)
        home_def = self._team_defence_strength(state, "home", now)
        away_def = self._team_defence_strength(state, "away", now)

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

        home_pressure = self._pressure_modifier(state, "home", now)
        away_pressure = self._pressure_modifier(state, "away", now)
        home_goal_prob = self._clamp_winlike_probability(0.5 + (home_edge + home_pressure - away_edge - away_pressure))
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
        logs = [
            random.choice(self.GOAL_TEMPLATES).format(
                time=now.strftime("%H:%M"),
                player=player_name,
                house=house,
            )
        ]

        score_gap = abs(int(state["home_score"]) - int(state["away_score"]))
        if score_gap == 0:
            logs.append(f"{now.strftime('%H:%M')} — The scores are level again and the tempo spikes immediately.")
        elif score_gap == 10:
            logs.append(f"{now.strftime('%H:%M')} — Barely anything separates them now; every possession feels dangerous.")
        elif score_gap >= 40 and random.random() < 0.45:
            leader = state['home_house'] if int(state['home_score']) > int(state['away_score']) else state['away_house']
            logs.append(f"{now.strftime('%H:%M')} — {leader} are starting to squeeze the match by the throat.")

        return logs, house

    def _save_event(self, state: dict[str, Any], now: datetime) -> str | None:
        attacking_side = random.choice(["home", "away"])
        defending_side = "away" if attacking_side == "home" else "home"

        attacker = self._random_active_player(state, attacking_side, {"chaser"}, now)
        keeper = self._random_active_player(state, defending_side, {"keeper"}, now)
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

        beater = self._random_active_player(state, striking_side, {"beater"}, now)
        target = self._random_active_player(state, target_side, self.KNOCKABLE_POSITIONS, now)
        if beater is None or target is None:
            return None

        knocked_minutes = random.randint(8, 26)
        inactive_until = now + timedelta(minutes=knocked_minutes)
        state["inactive_until"][target["token"]] = inactive_until.isoformat()
        impact = self._knockout_impact(beater, target, now, state)
        state.setdefault("pressure_effects", []).append({
            "team": striking_side,
            "attack": impact["attack"],
            "defence": impact["defence"],
            "seek": impact["seek"],
            "expires_at": inactive_until.isoformat(),
            "target_name": target["display_name"],
            "target_role": str(target.get("position", "player")).lower(),
        })

        base_log = random.choice(self.KNOCKOUT_TEMPLATES).format(
            time=now.strftime("%H:%M"),
            beater=beater["display_name"],
            target=target["display_name"],
        )
        effect_log = self._knockout_effect_log(state, striking_side, target, impact, now, knocked_minutes)
        return f"{base_log}\n{effect_log}" if effect_log else base_log

    def _turnover_event(self, state: dict[str, Any], now: datetime) -> str | None:
        side = random.choice(["home", "away"])
        player = self._random_active_player(state, side, {"chaser", "beater", "seeker"}, now)
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
        seeker = self._random_active_player(state, side, {"seeker"}, now)
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

        home_seek = self._team_seek_strength(state, "home", now) + float(state["home_momentum"]) + float(state["cheer_boost_home"]) + self._pressure_modifier(state, "home", now, mode="seek")
        away_seek = self._team_seek_strength(state, "away", now) + float(state["away_momentum"]) + float(state["cheer_boost_away"]) + self._pressure_modifier(state, "away", now, mode="seek")

        home_prob = self._clamp_winlike_probability(0.5 + (home_seek - away_seek))
        side = "home" if random.random() < home_prob else "away"

        seeker = self._random_active_player(state, side, {"seeker"}, now)
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
        now: datetime,
    ) -> dict[str, Any] | None:
        lineup_key = "home_lineup" if side == "home" else "away_lineup"
        players = state.get(lineup_key, [])
        active_players: list[dict[str, Any]] = []

        for player in players:
            position = str(player.get("position", "")).lower()
            if position not in allowed_positions:
                continue

            token = str(player.get("token") or player.get("display_name") or player.get("username") or "unknown")
            if not self._is_player_active(state, token, now):
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

    def _team_attack_strength(self, state: dict[str, Any], side: str, now: datetime) -> float:
        chasers = self._players_for_side(state, side, {"chaser"}, now)
        beaters = self._players_for_side(state, side, {"beater"}, now)
        chaser_strength = self._slot_weighted_strength(chasers, expected_slots=3)
        beater_strength = self._slot_weighted_strength(beaters, expected_slots=2)
        return chaser_strength * 0.34 + beater_strength * 0.08

    def _team_defence_strength(self, state: dict[str, Any], side: str, now: datetime) -> float:
        keepers = self._players_for_side(state, side, {"keeper"}, now)
        beaters = self._players_for_side(state, side, {"beater"}, now)
        keeper_strength = self._slot_weighted_strength(keepers, expected_slots=1)
        beater_strength = self._slot_weighted_strength(beaters, expected_slots=2)
        return keeper_strength * 0.26 + beater_strength * 0.07

    def _team_seek_strength(self, state: dict[str, Any], side: str, now: datetime) -> float:
        seekers = self._players_for_side(state, side, {"seeker"}, now)
        return self._slot_weighted_strength(seekers, expected_slots=1) * 0.32

    def _players_for_side(
        self,
        state: dict[str, Any],
        side: str,
        allowed_positions: set[str],
        now: datetime,
    ) -> list[dict[str, Any]]:
        lineup_key = "home_lineup" if side == "home" else "away_lineup"
        lineup = state.get(lineup_key, [])
        players: list[dict[str, Any]] = []

        for player in lineup:
            position = str(player.get("position", "")).lower()
            if position not in allowed_positions:
                continue

            token = str(player.get("token") or player.get("display_name") or player.get("username") or "unknown")
            if not self._is_player_active(state, token, now):
                continue

            players.append(player)

        return players

    def _slot_weighted_strength(self, players: list[dict[str, Any]], *, expected_slots: int) -> float:
        if expected_slots <= 0 or not players:
            return 0.0
        total = sum(max(1, int(player.get("level", 1))) for player in players)
        return total / (120.0 * expected_slots)

    def _is_player_active(self, state: dict[str, Any], token: str, now: datetime) -> bool:
        inactive_until = state.get("inactive_until", {}).get(token)
        if not inactive_until:
            return True
        try:
            return datetime.fromisoformat(inactive_until) <= now
        except ValueError:
            return True

    def _leader_side(self, state: dict[str, Any]) -> str | None:
        if int(state["home_score"]) > int(state["away_score"]):
            return "home"
        if int(state["away_score"]) > int(state["home_score"]):
            return "away"
        return None

    def _collect_recovery_logs(self, state: dict[str, Any], now: datetime) -> list[str]:
        logs: list[str] = []
        inactive = state.get("inactive_until", {})
        if not inactive:
            return logs

        active_tokens = {
            str(player.get("token") or player.get("display_name") or player.get("username") or "unknown")
            for player in state.get("home_lineup", []) + state.get("away_lineup", [])
        }
        token_to_name = {
            str(player.get("token") or player.get("display_name") or player.get("username") or "unknown"): str(
                player.get("display_name") or player.get("username") or player.get("name") or "Unknown Player"
            )
            for player in state.get("home_lineup", []) + state.get("away_lineup", [])
        }

        recovered: list[str] = []
        for token, until in list(inactive.items()):
            try:
                if datetime.fromisoformat(until) <= now:
                    recovered.append(token)
            except ValueError:
                recovered.append(token)

        for token in recovered:
            inactive.pop(token, None)
            if token in active_tokens and random.random() < 0.65:
                logs.append(f"{now.strftime('%H:%M')} — {token_to_name.get(token, 'A player')} steadies themselves and rejoins the flow of play.")

        return logs

    def _expire_pressure_effects(self, state: dict[str, Any], now: datetime) -> None:
        effects = state.get("pressure_effects", [])
        if not effects:
            return
        state["pressure_effects"] = [
            effect for effect in effects
            if self._effect_is_active(effect, now)
        ]

    def _effect_is_active(self, effect: dict[str, Any], now: datetime) -> bool:
        expires_at = effect.get("expires_at")
        if not expires_at:
            return False
        try:
            return datetime.fromisoformat(str(expires_at)) > now
        except ValueError:
            return False

    def _pressure_modifier(self, state: dict[str, Any], side: str, now: datetime, *, mode: str = "goal") -> float:
        total = 0.0
        for effect in state.get("pressure_effects", []):
            if effect.get("team") != side or not self._effect_is_active(effect, now):
                continue
            if mode == "seek":
                total += float(effect.get("seek", 0.0))
            else:
                total += float(effect.get("attack", 0.0)) + float(effect.get("defence", 0.0))
        return min(0.09 if mode == "goal" else 0.08, total)

    def _knockout_impact(
        self,
        beater: dict[str, Any],
        target: dict[str, Any],
        now: datetime,
        state: dict[str, Any],
    ) -> dict[str, float]:
        beater_level = max(1, int(beater.get("level", 1)))
        target_level = max(1, int(target.get("level", 1)))
        target_role = str(target.get("position", "player")).lower()
        beater_factor = 0.75 + 0.25 * (beater_level / 120.0)
        target_factor = 0.55 + 0.45 * (target_level / 120.0)

        attack = 0.0
        defence = 0.0
        seek = 0.0
        if target_role == "chaser":
            attack = 0.010 + 0.020 * beater_factor * target_factor
        elif target_role == "keeper":
            attack = 0.014 + 0.018 * beater_factor * target_factor
            defence = 0.004 + 0.006 * beater_factor
        elif target_role == "beater":
            attack = 0.006 + 0.010 * beater_factor * target_factor
            defence = 0.005 + 0.008 * beater_factor * target_factor
        elif target_role == "seeker":
            seek = 0.006 + 0.010 * beater_factor * target_factor
            if now - datetime.fromisoformat(state["started_at"]) >= timedelta(hours=8):
                seek += 0.012 * target_factor
            else:
                attack = 0.004 + 0.006 * beater_factor

        return {
            "attack": min(0.045, attack),
            "defence": min(0.022, defence),
            "seek": min(0.05, seek),
        }

    def _knockout_effect_log(
        self,
        state: dict[str, Any],
        striking_side: str,
        target: dict[str, Any],
        impact: dict[str, float],
        now: datetime,
        knocked_minutes: int,
    ) -> str | None:
        target_role = str(target.get("position", "player")).lower()
        striking_house = state["home_house"] if striking_side == "home" else state["away_house"]
        if target_role == "chaser":
            return f"{now.strftime('%H:%M')} — {striking_house} smell blood now; that hit could blunt the opposing attack for about {knocked_minutes} minutes."
        if target_role == "keeper":
            return f"{now.strftime('%H:%M')} — The hoops suddenly look a little more exposed for {knocked_minutes} minutes."
        if target_role == "beater":
            return f"{now.strftime('%H:%M')} — {striking_house} have won a nasty little battle in the air and may control the physical side of the match for a spell."
        if target_role == "seeker" and impact.get("seek", 0.0) > 0.0:
            return f"{now.strftime('%H:%M')} — That could matter enormously in the Snitch chase if the match goes long."
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