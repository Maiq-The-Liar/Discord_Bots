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
    KNOCKABLE_POSITIONS = {"seeker", "beater", "chaser", "keeper"}
    SCENARIOS = (
        "balanced",
        "comeback",
        "grindy",
        "chaotic",
        "tense_finish",
        "swingy",
        "tactical",
        "open",
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
        "{time} — {player} tears through the last line and buries it for {house}.",
        "{time} — {player} snaps the move to life and rifles the Quaffle home for {house}.",
        "{time} — {player} ghosts past the keeper and drives in ten more for {house}.",
        "{time} — {player} finishes the attack with ruthless precision. Goal for {house}.",
        "{time} — {player} opens the shoulders, sees the gap, and hammers the Quaffle through for {house}.",
        "{time} — {player} wins the race to the hoop and punches in another ten for {house}.",
        "{time} — {player} sells the feint, freezes the keeper, and scores for {house}.",
        "{time} — {player} hits the opening at full tilt and {house} cash in again.",
    ]

    SAVE_TEMPLATES = [
        "{time} — {keeper} flings themselves across the hoops and denies {attacker} brilliantly.",
        "{time} — {keeper} reads it early and smothers the finish from {attacker}.",
        "{time} — {keeper} gets both hands to it and turns {attacker} away.",
        "{time} — {keeper} stands tall at the hoop and slams the door on {attacker}.",
        "{time} — {keeper} claws the Quaffle out of danger. No goal.",
        "{time} — {keeper} reacts in a flash and keeps {attacker} out.",
    ]

    KNOCKOUT_TEMPLATES = [
        "{time} — {beater} drives a savage bludger into {target} and they tumble badly away from the play.",
        "{time} — {beater} catches {target} flush. That is a brutal hit and medics are already moving.",
        "{time} — {beater} absolutely buries {target} with a bludger. The whole stand recoils.",
        "{time} — {target} is blasted off line by {beater}. That's a vicious one.",
        "{time} — {beater} picks out {target} and detonates the bludger into them.",
        "{time} — {target} folds over the broom after a monstrous hit from {beater}.",
    ]

    KNOCKOUT_MISS_TEMPLATES = [
        "{time} — {beater} lets the bludger fly at {target}, but it howls past them harmlessly.",
        "{time} — {beater} lines up {target} and misses by a breath.",
        "{time} — {beater} goes hunting for {target}, but the shot does not land.",
    ]

    FOUL_TEMPLATES = [
        "{time} — The whistle cuts through the noise and {house} come away with the better of it.",
        "{time} — A heavy collision leaves both sides roaring at the referee before {house} settle first.",
        "{time} — Tempers flare in mid-air and the referee waves play on with {house} favoured by the break.",
        "{time} — A late body check sends the crowd into uproar and gives {house} a small edge.",
        "{time} — The referee intervenes before the whole thing turns ugly. {house} benefit.",
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

    SNITCH_SPOTTED_TEMPLATES = [
        "{time} — {seeker} has spotted the Snitch and tears after it for {house}!",
        "{time} — A flash of gold — {seeker} sees it first and launches into pursuit for {house}.",
        "{time} — {seeker} spots the Snitch and bolts after it for {house}!",
        "{time} — {seeker} points, dives, and gives chase — the Snitch is in sight for {house}!",
    ]

    SNITCH_LOST_TEMPLATES = [
        "{time} — {seeker} loses sight of the Snitch in the chaos and the chase breaks apart.",
        "{time} — {seeker} had it for a moment, then the golden blur vanishes again.",
        "{time} — {seeker} reaches empty air; the Snitch is gone and the chase resets.",
    ]

    SNITCH_STOLEN_TEMPLATES = [
        "{time} — {thief} swoops in from nowhere and steals the Snitch chase away from {other_seeker}!",
        "{time} — {thief} reads it perfectly and snatches the advantage away from {other_seeker}.",
        "{time} — {other_seeker} was closing fast, but {thief} cuts across and takes over the Snitch chase!",
    ]

    SNITCH_INTERFERENCE_TEMPLATES = [
        "{time} — {beater} hammers a bludger straight across {seeker}'s pursuit line and the Snitch chase is broken instantly.",
        "{time} — {beater} picks out {seeker} in full pursuit and drives them off the Snitch.",
        "{time} — {beater} times the bludger to perfection; {seeker} is smashed off the chase and the golden trail is gone.",
    ]

    SNITCH_CONTINUE_TEMPLATES = [
        "{time} — {seeker} is still after it — the chase carries on into the next minute.",
        "{time} — {seeker} stays locked on the Snitch and the pursuit continues.",
        "{time} — {seeker} refuses to give up the line; the Snitch chase lives on.",
    ]

    ATTACK_MISS_TEMPLATES = [
        "{time} — {attacker} gets free for {house}, but drags the finish wide.",
        "{time} — {attacker} has the lane for {house} and cannot keep the shot on line.",
        "{time} — {attacker} flies straight at the hoops, only to send it skimming away from goal.",
        "{time} — {attacker} breaks through for {house} and misses the target.",
    ]

    EMERGENCY_BLOCK_TEMPLATES = [
        "{time} — With the keeper beaten, {defender} dives back and hacks the Quaffle clear.",
        "{time} — {defender} throws everything at the line and somehow rescues the defence.",
        "{time} — {defender} arrives in desperation and knocks the Quaffle away from the hoop.",
    ]

    CHEER_TEMPLATES = [
        "{time} — The {house} end erupts and the noise rolls straight onto the pitch.",
        "{time} — A fresh roar rises for {house}, and the players seem to feed off it.",
        "{time} — The {house} supporters are in full cry now and the tempo lifts with them.",
        "{time} — The stands shake with noise behind {house}.",
    ]

    EASTER_EGG_TEMPLATES = [
        "{time} — {spectator} has somehow ended up far too close to the boundary rope before being hauled away.",
        "{time} — An owl slices straight through the formation and both teams hate every second of it.",
        "{time} — A bewitched banner whips loose in the stands and causes a brief panic.",
        "{time} — For one alarming moment, a bludger appears to be chasing entirely the wrong target.",
        "{time} — The crowd lose themselves in a fresh surge of noise after chaos in the upper rows.",
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
        kickoff_side = random.choice(["home", "away"])
        comeback_burden_side = random.choice(["home", "away"])
        swing_start_side = random.choice(["home", "away"])
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
            "snitch_chase_active": False,
            "snitch_chase_side": None,
            "snitch_chase_seeker_token": None,
            "snitch_chase_ticks": 0,
            "snitch_chase_started_minute": None,
            "quaffle_possession_side": kickoff_side,
            "failed_shots_this_possession": 0,
            "possession_started_minute": 0,
            "current_attack_flow": "structured",
            "counter_window_ticks": 0,
            "kickoff_logged": False,
            "comeback_burden_side": comeback_burden_side,
            "swing_phase_side": swing_start_side,
            "swing_phase_until_minute": random.randint(75, 130),
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
        self._update_swing_window(state)
        logs.extend(self._collect_recovery_logs(state, now))
        self._expire_pressure_effects(state, now)
        state["counter_window_ticks"] = max(0, int(state.get("counter_window_ticks", 0)) - 1)

        if not state.get("kickoff_logged"):
            house = state["home_house"] if state.get("quaffle_possession_side") == "home" else state["away_house"]
            logs.append(f"{now.strftime('%H:%M')} — The Quaffle is released and {house} immediately take possession.")
            state["kickoff_logged"] = True

        if state.get("snitch_caught"):
            return MatchTickResult(state=state, new_logs=logs, score_changed=False, ended=True, winner_house=state.get("winner_house"))

        if state.get("snitch_chase_active"):
            chase_logs, chase_scored = self._resolve_snitch_chase(state, now)
            logs.extend(chase_logs)
            score_changed = chase_scored
            state["last_event_at"] = now.isoformat() if logs else state.get("last_event_at")
            state["full_log_count"] = int(state.get("full_log_count", 0)) + len(logs)
            return MatchTickResult(state=state, new_logs=logs, score_changed=score_changed, ended=bool(state.get("snitch_caught")), winner_house=state.get("winner_house"))

        spot_log = self._maybe_start_snitch_chase(state, now)
        if spot_log:
            logs.append(spot_log)
            state["last_event_at"] = now.isoformat()
            state["full_log_count"] = int(state.get("full_log_count", 0)) + len(logs)
            return MatchTickResult(state=state, new_logs=logs, score_changed=False, ended=False, winner_house=None)

        tick_logs, score_changed = self._run_quaffle_tick(state, now, spectator_names)
        logs.extend(tick_logs)
        state["last_event_at"] = now.isoformat() if logs else state.get("last_event_at")
        state["full_log_count"] = int(state.get("full_log_count", 0)) + len(logs)
        return MatchTickResult(state=state, new_logs=logs, score_changed=score_changed, ended=bool(state.get("snitch_caught")), winner_house=state.get("winner_house"))

    def _event_probability(self, state: dict[str, Any]) -> float:
        scenario = str(state.get("scenario", "balanced"))
        base = 0.30
        if scenario == "grindy":
            base = 0.24
        elif scenario == "chaotic":
            base = 0.43
        elif scenario == "open":
            base = 0.34
        elif scenario == "tactical":
            base = 0.28
        elif scenario == "swingy":
            base = 0.31
        elif scenario == "tense_finish":
            base = 0.29
        elif scenario == "comeback":
            base = 0.30
        if int(state.get("minute", 0)) >= 480:
            base += 0.04
        return self._clamp_probability(base, low=0.14, high=0.56)

    def _pick_event_type(self, state: dict[str, Any], now: datetime) -> str:
        scenario = str(state.get("scenario", "balanced"))
        weights = {"foul": 7, "easter_egg": 3}
        if scenario == "chaotic":
            weights["foul"] = 6
            weights["easter_egg"] = 4
        elif scenario == "grindy":
            weights["foul"] = 9
        elif scenario == "tactical":
            weights["foul"] = 8
            weights["easter_egg"] = 2
        options = list(weights.keys())
        return random.choices(options, weights=[weights[k] for k in options], k=1)[0]

    def _beater_event_probability(self, state: dict[str, Any]) -> float:
        scenario = str(state.get("scenario", "balanced"))
        base = 0.022
        if scenario == "chaotic":
            base = 0.052
        elif scenario == "grindy":
            base = 0.016
        elif scenario == "open":
            base = 0.025
        elif scenario == "tactical":
            base = 0.019
        elif scenario == "swingy":
            base = 0.027
        elif scenario == "tense_finish":
            base = 0.024
        elif scenario == "comeback":
            base = 0.023
        if int(state.get("minute", 0)) >= 480:
            base += 0.003
        return self._clamp_probability(base, low=0.012, high=0.060)

    def _ambient_flavor_probability(self, state: dict[str, Any]) -> float:
        scenario = str(state.get("scenario", "balanced"))
        base = 0.012
        if scenario == "chaotic":
            base = 0.016
        elif scenario == "grindy":
            base = 0.013
        elif scenario == "tactical":
            base = 0.011
        return self._clamp_probability(base, low=0.008, high=0.022)

    def _run_quaffle_tick(self, state: dict[str, Any], now: datetime, spectator_names: list[str]) -> tuple[list[str], bool]:
        event_probability = self._event_probability(state)
        side = str(state.get("quaffle_possession_side") or "home")
        if side not in {"home", "away"}:
            side = random.choice(["home", "away"])
            state["quaffle_possession_side"] = side
        steal_prob = self._steal_attempt_probability(state, side, now)
        shot_prob = self._attack_attempt_probability(state, side, now)
        beater_prob = self._beater_event_probability(state)
        flavor_prob = self._ambient_flavor_probability(state) if random.random() < event_probability else 0.0
        roll = random.random()
        if roll < steal_prob:
            return [self._resolve_steal_event(state, now)], False
        roll -= steal_prob
        if roll < shot_prob:
            return self._resolve_attack_event(state, now)
        roll -= shot_prob
        if roll < beater_prob:
            log = self._knockout_event(state, now)
            return ([log] if log else []), False
        roll -= beater_prob
        if roll < flavor_prob:
            event_type = self._pick_event_type(state, now)
            if event_type == "foul":
                log = random.choice(self.FOUL_TEMPLATES).format(time=now.strftime("%H:%M"), house=random.choice([state["home_house"], state["away_house"]]))
            else:
                log = self._easter_egg_event(state, now, spectator_names)
            return ([log] if log else []), False
        if random.random() < 0.35:
            return [self._retention_log(state, now)], False
        return [], False

    def _goal_event(self, state: dict[str, Any], now: datetime) -> tuple[list[str], str | None]:
        logs, scored = self._resolve_attack_event(state, now)
        scorer_house = None
        if scored:
            scorer_house = state["away_house"] if state.get("quaffle_possession_side") == "home" else state["home_house"]
        return logs, scorer_house

    def _knockout_event(self, state: dict[str, Any], now: datetime) -> str | None:
        striking_side = random.choice(["home", "away"])
        target_side = "away" if striking_side == "home" else "home"
        beater = self._random_active_player(state, striking_side, {"beater"}, now)
        if beater is None:
            return None
        target_role = self._choose_knockout_target_role(state, now, target_side)
        if target_role is None:
            return None
        target = self._random_active_player(state, target_side, {target_role}, now)
        if target is None:
            return None
        beater_level = max(1, int(beater.get("level", 1)))
        hit_prob = self._clamp_probability(0.48 + (beater_level / 120.0) * 0.22, low=0.40, high=0.80)
        if random.random() > hit_prob:
            return random.choice(self.KNOCKOUT_MISS_TEMPLATES).format(time=now.strftime("%H:%M"), beater=beater["display_name"], target=target["display_name"])
        role = str(target.get("position", "player")).lower()
        if role == "chaser":
            knocked_minutes = self._biased_knockout_minutes(10, 25, beater_level)
        elif role == "keeper":
            knocked_minutes = self._biased_knockout_minutes(10, 20, beater_level)
        else:
            knocked_minutes = self._biased_knockout_minutes(8, 18, beater_level)
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
            "target_role": role,
        })
        self._apply_knockout_momentum_swing(state, target_side, role, target)
        base_log = random.choice(self.KNOCKOUT_TEMPLATES).format(time=now.strftime("%H:%M"), beater=beater["display_name"], target=target["display_name"])
        turnover_log = self._maybe_apply_beater_turnover(state, now, striking_side, target_side, beater, target)
        effect_log = self._knockout_effect_log(state, striking_side, target, impact, now, knocked_minutes)
        extra = [entry for entry in (turnover_log, effect_log) if entry]
        return "\n".join([base_log] + extra)

    def _turnover_event(self, state: dict[str, Any], now: datetime) -> str | None:
        return self._resolve_steal_event(state, now)

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


    def _side_house(self, state: dict[str, Any], side: str) -> str:
        return state["home_house"] if side == "home" else state["away_house"]

    def _switch_possession(self, state: dict[str, Any], new_side: str, now: datetime, *, flow: str = "structured") -> None:
        state["quaffle_possession_side"] = new_side
        state["failed_shots_this_possession"] = 0
        state["possession_started_minute"] = int(state.get("minute", 0))
        state["current_attack_flow"] = flow

    def _active_chaser_count(self, state: dict[str, Any], side: str, now: datetime) -> int:
        return len(self._players_for_side(state, side, {"chaser"}, now))

    def _scenario_bias(self, state: dict[str, Any], side: str) -> dict[str, float]:
        scenario = str(state.get("scenario", "balanced"))
        minute = int(state.get("minute", 0))
        bias = {"retention": 0.0, "danger": 0.0, "steal_for": 0.0, "keeper": 0.0, "beater": 0.0, "counter": 0.0}
        if scenario == "grindy":
            bias["retention"] += 0.05
            bias["danger"] -= 0.03
            bias["steal_for"] -= 0.03
            bias["keeper"] += 0.03
            bias["beater"] -= 0.03
        elif scenario == "chaotic":
            bias["retention"] -= 0.06
            bias["steal_for"] += 0.05
            bias["beater"] += 0.08
            bias["counter"] += 0.04
        elif scenario == "open":
            bias["danger"] += 0.06
            bias["keeper"] -= 0.03
            bias["steal_for"] -= 0.02
        elif scenario == "tactical":
            bias["retention"] += 0.03
            bias["steal_for"] += 0.03
            bias["danger"] -= 0.01
            bias["beater"] -= 0.02
        elif scenario == "swingy":
            phase_side = state.get("swing_phase_side")
            if phase_side == side:
                bias["retention"] += 0.05
                bias["danger"] += 0.03
            else:
                bias["steal_for"] += 0.05
        elif scenario == "tense_finish" and minute >= 420:
            trail = self._trailing_side(state)
            if trail == side:
                bias["steal_for"] += 0.03
                bias["counter"] += 0.04
                bias["danger"] += 0.02
            elif trail is not None:
                bias["retention"] -= 0.02
        elif scenario == "comeback":
            burden = state.get("comeback_burden_side")
            if burden in {"home", "away"}:
                phase = 0 if minute < 180 else 1 if minute < 360 else 2
                if phase == 0:
                    if side == burden:
                        bias["retention"] -= 0.05
                        bias["danger"] -= 0.03
                    else:
                        bias["steal_for"] += 0.03
                elif phase == 2:
                    if side == burden:
                        bias["retention"] += 0.04
                        bias["counter"] += 0.04
                        bias["danger"] += 0.02
                    else:
                        bias["steal_for"] -= 0.02
        return bias

    def _trailing_side(self, state: dict[str, Any]) -> str | None:
        if int(state["home_score"]) < int(state["away_score"]):
            return "home"
        if int(state["away_score"]) < int(state["home_score"]):
            return "away"
        return None

    def _update_swing_window(self, state: dict[str, Any]) -> None:
        if str(state.get("scenario")) != "swingy":
            return
        minute = int(state.get("minute", 0))
        if minute >= int(state.get("swing_phase_until_minute", 9999)):
            state["swing_phase_side"] = "away" if state.get("swing_phase_side") == "home" else "home"
            state["swing_phase_until_minute"] = minute + random.randint(65, 120)

    def _steal_attempt_probability(self, state: dict[str, Any], possession_side: str, now: datetime) -> float:
        defending_side = "away" if possession_side == "home" else "home"
        attack = self._team_attack_strength(state, possession_side, now)
        defence = self._team_defence_strength(state, defending_side, now)
        active_diff = self._active_chaser_count(state, defending_side, now) - self._active_chaser_count(state, possession_side, now)
        poss_bias = self._scenario_bias(state, possession_side)
        def_bias = self._scenario_bias(state, defending_side)
        raw = 0.10 + (defence - attack) * 0.16 + active_diff * 0.028 + float(state.get(f"{defending_side}_momentum", 0.0)) * 0.10 - float(state.get(f"{possession_side}_momentum", 0.0)) * 0.07 + def_bias["steal_for"] - poss_bias["retention"] * 0.45 + float(state.get(f"cheer_boost_{defending_side}", 0.0)) * 0.35
        return self._clamp_probability(raw, low=0.04, high=0.24)

    def _attack_attempt_probability(self, state: dict[str, Any], possession_side: str, now: datetime) -> float:
        bias = self._scenario_bias(state, possession_side)
        failed = int(state.get("failed_shots_this_possession", 0))
        flow = str(state.get("current_attack_flow", "structured"))
        raw = 0.22 + max(0, failed - 1) * 0.03 + bias["danger"] * 0.12
        if flow == "fast_break":
            raw += 0.10 + bias["counter"] * 0.2
        elif flow == "scramble":
            raw += 0.04
        return self._clamp_probability(raw, low=0.16, high=0.42)

    def _resolve_steal_event(self, state: dict[str, Any], now: datetime) -> str:
        possession_side = str(state.get("quaffle_possession_side") or "home")
        defending_side = "away" if possession_side == "home" else "home"
        defender = self._random_active_player(state, defending_side, {"chaser"}, now) or self._random_active_player(state, defending_side, {"beater", "chaser"}, now)
        carrier = self._random_active_player(state, possession_side, {"chaser"}, now) or self._random_active_player(state, possession_side, {"chaser", "beater"}, now)
        if defender is None or carrier is None:
            return self._retention_log(state, now)
        attack = self._team_attack_strength(state, possession_side, now)
        defence = self._team_attack_strength(state, defending_side, now) * 0.65 + self._team_defence_strength(state, defending_side, now) * 0.35
        poss_bias = self._scenario_bias(state, possession_side)
        def_bias = self._scenario_bias(state, defending_side)
        active_diff = self._active_chaser_count(state, defending_side, now) - self._active_chaser_count(state, possession_side, now)
        success = self._clamp_probability(0.41 + (defence - attack) * 0.38 + active_diff * 0.05 + def_bias["steal_for"] - poss_bias["retention"] + float(state.get(f"{defending_side}_momentum", 0.0)) * 0.28 + float(state.get(f"cheer_boost_{defending_side}", 0.0)) * 0.30, low=0.18, high=0.72)
        if random.random() < success:
            turnover_type = random.choices(["interception", "tackle", "strip"], weights=[36, 41, 23], k=1)[0]
            flow = "fast_break" if turnover_type == "interception" and random.random() < 0.72 else "scramble" if turnover_type == "strip" else "structured"
            self._switch_possession(state, defending_side, now, flow=flow)
            state["counter_window_ticks"] = 2 if flow == "fast_break" else max(0, int(state.get("counter_window_ticks", 0)))
            if turnover_type == "interception":
                return f"{now.strftime('%H:%M')} — {defender['display_name']} reads the pass, cuts it out cleanly, and {self._side_house(state, defending_side)} break the other way at speed."
            if turnover_type == "tackle":
                return f"{now.strftime('%H:%M')} — {defender['display_name']} leans into {carrier['display_name']}, jars the Quaffle free, and {self._side_house(state, defending_side)} come away with it."
            return f"{now.strftime('%H:%M')} — {defender['display_name']} claws at the Quaffle in traffic; it spills loose, and {self._side_house(state, defending_side)} recover it first."
        return f"{now.strftime('%H:%M')} — {defender['display_name']} lunges for the steal, but {carrier['display_name']} shields the Quaffle and {self._side_house(state, possession_side)} keep moving."

    def _resolve_attack_event(self, state: dict[str, Any], now: datetime) -> tuple[list[str], bool]:
        attacking_side = str(state.get("quaffle_possession_side") or "home")
        defending_side = "away" if attacking_side == "home" else "home"
        attacker = self._random_active_player(state, attacking_side, {"chaser"}, now) or self._random_active_player(state, attacking_side, {"chaser", "beater", "seeker"}, now)
        if attacker is None:
            return [], False
        keeper = self._random_active_player(state, defending_side, {"keeper"}, now)
        flow = str(state.get("current_attack_flow", "structured"))
        logs: list[str] = []
        attack_edge = self._team_attack_strength(state, attacking_side, now) - self._team_defence_strength(state, defending_side, now)
        attack_edge += float(state.get(f"{attacking_side}_momentum", 0.0)) - float(state.get(f"{defending_side}_momentum", 0.0)) * 0.55
        attack_edge += float(state.get(f"cheer_boost_{attacking_side}", 0.0)) * 0.6
        attack_edge += self._pressure_modifier(state, attacking_side, now)
        attack_edge -= self._pressure_modifier(state, defending_side, now) * 0.55
        attack_edge += self._scenario_bias(state, attacking_side)["danger"]
        if int(state.get("counter_window_ticks", 0)) > 0 and flow == "fast_break":
            attack_edge += 0.06 + self._scenario_bias(state, attacking_side)["counter"]
        if flow == "scramble":
            attack_edge += 0.02
        attacker_level = max(1, int(attacker.get("level", 1)))
        shot_on_target_prob = self._clamp_probability(0.57 + (attacker_level / 120.0) * 0.09 + attack_edge * 0.20, low=0.40, high=0.86)
        if random.random() > shot_on_target_prob:
            state["failed_shots_this_possession"] = int(state.get("failed_shots_this_possession", 0)) + 1
            logs.append(self._attack_intro_log(state, now, attacker["display_name"], flow, miss=True))
            logs.append(random.choice(self.ATTACK_MISS_TEMPLATES).format(time=now.strftime("%H:%M"), attacker=attacker["display_name"], house=self._side_house(state, attacking_side)))
            stall_log = self._post_failed_shot_events(state, now, attacking_side, defending_side, keeper, attacker)
            if stall_log:
                logs.append(stall_log)
            return logs, False
        if keeper is not None:
            keeper_level = max(1, int(keeper.get("level", 1)))
            keeper_save_prob = self._clamp_probability(0.30 + (keeper_level / 120.0) * 0.18 - (attacker_level / 120.0) * 0.05 - attack_edge * 0.15 + self._scenario_bias(state, defending_side)["keeper"] - self._scenario_bias(state, attacking_side)["danger"] * 0.25, low=0.12, high=0.70)
            if flow == "fast_break":
                keeper_save_prob = max(0.08, keeper_save_prob - 0.05)
            if random.random() < keeper_save_prob:
                state["failed_shots_this_possession"] = int(state.get("failed_shots_this_possession", 0)) + 1
                logs.append(self._attack_intro_log(state, now, attacker["display_name"], flow, miss=False))
                logs.append(random.choice(self.SAVE_TEMPLATES).format(time=now.strftime("%H:%M"), keeper=keeper["display_name"], attacker=attacker["display_name"]))
                keeper_turnover = self._keeper_catch_turnover(state, now, attacking_side, defending_side, keeper)
                if keeper_turnover:
                    logs.append(keeper_turnover)
                else:
                    stall_log = self._post_failed_shot_events(state, now, attacking_side, defending_side, keeper, attacker, already_saved=True)
                    if stall_log:
                        logs.append(stall_log)
                return logs, False
        score_key = "home_score" if attacking_side == "home" else "away_score"
        state[score_key] = int(state[score_key]) + 10
        house = self._side_house(state, attacking_side)
        logs.append(self._attack_intro_log(state, now, attacker["display_name"], flow, miss=False, scored=True))
        logs.append(random.choice(self.GOAL_TEMPLATES).format(time=now.strftime("%H:%M"), player=attacker["display_name"], house=house))
        self._switch_possession(state, defending_side, now, flow="structured")
        state["counter_window_ticks"] = 0
        self._swing_momentum(state, house, 0.06 if flow != "fast_break" else 0.07)
        gap = abs(int(state["home_score"]) - int(state["away_score"]))
        if gap == 0:
            logs.append(f"{now.strftime('%H:%M')} — They are level again and the noise around the ground surges at once.")
        elif gap == 10:
            logs.append(f"{now.strftime('%H:%M')} — There is almost nothing between them now.")
        elif gap >= 40 and random.random() < 0.42:
            leader = self._side_house(state, "home" if int(state["home_score"]) > int(state["away_score"]) else "away")
            logs.append(f"{now.strftime('%H:%M')} — {leader} are beginning to squeeze the life out of the contest.")
        return logs, True

    def _attack_intro_log(self, state: dict[str, Any], now: datetime, attacker_name: str, flow: str, *, miss: bool, scored: bool=False) -> str:
        house = self._side_house(state, str(state.get("quaffle_possession_side") or "home"))
        if flow == "fast_break":
            return f"{now.strftime('%H:%M')} — {house} spring forward off the turnover; {attacker_name} tears onto the Quaffle in open space."
        if flow == "scramble":
            return f"{now.strftime('%H:%M')} — The play breaks apart in front of the hoops and {attacker_name} pounces for {house}."
        if miss and int(state.get("failed_shots_this_possession", 0)) >= 2:
            return f"{now.strftime('%H:%M')} — {house} keep the pressure on and work the Quaffle back to {attacker_name}."
        return f"{now.strftime('%H:%M')} — {house} build patiently before {attacker_name} attacks the middle."

    def _keeper_catch_turnover(self, state: dict[str, Any], now: datetime, attacking_side: str, defending_side: str, keeper: dict[str, Any] | None) -> str | None:
        if keeper is None:
            return None
        keeper_level = max(1, int(keeper.get("level", 1)))
        scenario_shift = self._scenario_bias(state, defending_side)["keeper"] - self._scenario_bias(state, attacking_side)["danger"] * 0.15
        prob = self._clamp_probability(0.25 + (keeper_level - 60) / 240.0 + scenario_shift, low=0.12, high=0.44)
        if random.random() >= prob:
            return None
        self._switch_possession(state, defending_side, now, flow="structured")
        state["counter_window_ticks"] = 1 if random.random() < 0.35 else 0
        return f"{now.strftime('%H:%M')} — {keeper['display_name']} holds it cleanly this time and immediately turns play back the other way for {self._side_house(state, defending_side)}."

    def _post_failed_shot_events(self, state: dict[str, Any], now: datetime, attacking_side: str, defending_side: str, keeper: dict[str, Any] | None, attacker: dict[str, Any], already_saved: bool=False) -> str | None:
        failed = int(state.get("failed_shots_this_possession", 0))
        if failed >= 3:
            log = self._stall_breaker_beater_event(state, now, attacking_side, defending_side)
            if log:
                return log
        if already_saved:
            return f"{now.strftime('%H:%M')} — {self._side_house(state, attacking_side)} recover the rebound and keep the possession alive."
        return f"{now.strftime('%H:%M')} — The Quaffle stays with {self._side_house(state, attacking_side)} and they recycle the attack."

    def _stall_breaker_beater_event(self, state: dict[str, Any], now: datetime, attacking_side: str, defending_side: str) -> str | None:
        beater = self._random_active_player(state, defending_side, {"beater"}, now)
        target = self._random_active_player(state, attacking_side, {"chaser"}, now)
        if beater is None or target is None:
            return None
        beater_level = max(1, int(beater.get("level", 1)))
        disruption = self._clamp_probability(0.34 + (beater_level / 120.0) * 0.18 + self._scenario_bias(state, defending_side)["beater"], low=0.18, high=0.64)
        if random.random() > disruption:
            return f"{now.strftime('%H:%M')} — {beater['display_name']} hammers a bludger at the Quaffle-side chaser, but {self._side_house(state, attacking_side)} somehow keep control."
        on_ball_prob = self._clamp_probability(0.33 + (beater_level / 120.0) * 0.10, low=0.23, high=0.52)
        if random.random() < on_ball_prob:
            if random.random() < 0.90:
                self._switch_possession(state, defending_side, now, flow="scramble")
                state["counter_window_ticks"] = 1
                return f"{now.strftime('%H:%M')} — {beater['display_name']} smashes the bludger into the Quaffle-side chaser. The ball spills loose and {self._side_house(state, defending_side)} snatch up the turnover at once."
            return f"{now.strftime('%H:%M')} — {beater['display_name']} crushes the Quaffle-side chaser, but {self._side_house(state, attacking_side)} dive on the loose ball and somehow retain possession."
        return f"{now.strftime('%H:%M')} — {beater['display_name']} batters an off-ball chaser and forces {self._side_house(state, attacking_side)} to reset the whole attack."

    def _maybe_apply_beater_turnover(self, state: dict[str, Any], now: datetime, striking_side: str, target_side: str, beater: dict[str, Any], target: dict[str, Any], target_context: str | None = None) -> str | None:
        if str(target.get("position", "")).lower() != "chaser":
            return None
        possession_side = state.get("quaffle_possession_side")
        if possession_side != target_side:
            return None
        beater_level = max(1, int(beater.get("level", 1)))
        failed = int(state.get("failed_shots_this_possession", 0))
        on_ball_prob = 0.33 + (beater_level / 120.0) * 0.08 + (0.14 if failed >= 3 else 0.0) + self._scenario_bias(state, striking_side)["beater"] * 0.35
        if target_context != "quaffle_chaser" and random.random() >= self._clamp_probability(on_ball_prob, low=0.20, high=0.72):
            return None
        if random.random() < 0.90:
            self._switch_possession(state, striking_side, now, flow="scramble")
            state["counter_window_ticks"] = 1
            return f"{now.strftime('%H:%M')} — {target['display_name']} had the Quaffle when the bludger landed. It breaks loose on contact, and {self._side_house(state, striking_side)} recover the turnover in the same violent scramble."
        return f"{now.strftime('%H:%M')} — {target['display_name']} is smashed while carrying the Quaffle, but {self._side_house(state, target_side)} fling themselves onto the loose ball and keep possession alive."

    def _beater_target_context(self, state: dict[str, Any], now: datetime, striking_side: str, target_side: str, beater: dict[str, Any], target: dict[str, Any]) -> str:
        role = str(target.get("position", "player")).lower()
        if role == "seeker":
            return "seeker_general"
        if role == "keeper":
            return "keeper"
        if role != "chaser":
            return "generic"
        possession_side = str(state.get("quaffle_possession_side") or "home")
        beater_level = max(1, int(beater.get("level", 1)))
        failed = int(state.get("failed_shots_this_possession", 0))
        if possession_side == target_side:
            on_ball_prob = 0.33 + (beater_level / 120.0) * 0.08 + (0.14 if failed >= 3 else 0.0) + self._scenario_bias(state, striking_side)["beater"] * 0.35
            if random.random() < self._clamp_probability(on_ball_prob, low=0.20, high=0.72):
                return "quaffle_chaser"
            return "support_chaser"
        return "defensive_chaser"

    def _beater_miss_log(self, now: datetime, beater: dict[str, Any], target: dict[str, Any], target_context: str) -> str:
        time = now.strftime('%H:%M')
        if target_context == "quaffle_chaser":
            options = [
                f"{time} — {beater['display_name']} tears after {target['display_name']}, who has the Quaffle, but the bludger whistles wide.",
                f"{time} — {beater['display_name']} lines up the Quaffle-carrier {target['display_name']} and just misses them.",
            ]
        elif target_context == "support_chaser":
            options = [
                f"{time} — {beater['display_name']} goes after {target['display_name']} away from the Quaffle, but cannot land the shot.",
                f"{time} — {beater['display_name']} tries to flatten the supporting chaser {target['display_name']}, and the bludger misses by a breath.",
            ]
        elif target_context == "defensive_chaser":
            options = [
                f"{time} — {beater['display_name']} drives a bludger toward the recovering chaser {target['display_name']}, but it screams harmlessly past.",
                f"{time} — {beater['display_name']} hunts {target['display_name']} in retreat and cannot make the bludger stick.",
            ]
        elif target_context == "keeper":
            options = [
                f"{time} — {beater['display_name']} tries to rattle the keeper {target['display_name']} in front of the hoops, but misses completely.",
                f"{time} — {beater['display_name']} sends a bludger at keeper {target['display_name']}, and it flashes wide of the cage.",
            ]
        elif target_context == "seeker_general":
            options = [
                f"{time} — {beater['display_name']} takes aim at seeker {target['display_name']} away from the Snitch chase, but the bludger does not connect.",
                f"{time} — {beater['display_name']} tries to knock seeker {target['display_name']} off balance, and misses them cleanly.",
            ]
        else:
            options = [random.choice(self.KNOCKOUT_MISS_TEMPLATES).format(time=time, beater=beater['display_name'], target=target['display_name'])]
        return random.choice(options)

    def _beater_hit_log(self, now: datetime, state: dict[str, Any], beater: dict[str, Any], target: dict[str, Any], target_context: str) -> str:
        time = now.strftime('%H:%M')
        if target_context == "quaffle_chaser":
            options = [
                f"{time} — {beater['display_name']} drives a bludger straight into {target['display_name']} while they carry the Quaffle. That is a savage hit on the ball-side chaser.",
                f"{time} — {beater['display_name']} picks off {target['display_name']} with the Quaffle in hand and nearly tears the whole attack apart.",
            ]
        elif target_context == "support_chaser":
            options = [
                f"{time} — {beater['display_name']} buries an off-ball bludger into supporting chaser {target['display_name']} and the formation blows apart around them.",
                f"{time} — {beater['display_name']} catches {target['display_name']} away from the Quaffle with a brutal bludger and the attack shudders.",
            ]
        elif target_context == "defensive_chaser":
            options = [
                f"{time} — {beater['display_name']} wipes out defending chaser {target['display_name']} with a bludger as the play turns.",
                f"{time} — {beater['display_name']} hammers {target['display_name']} off the recovery line with a vicious bludger.",
            ]
        elif target_context == "keeper":
            options = [
                f"{time} — {beater['display_name']} drills the bludger into keeper {target['display_name']} right in front of the hoops. The goalmouth is chaos for a moment.",
                f"{time} — {beater['display_name']} smashes keeper {target['display_name']} in the shadow of the hoops with a brutal bludger.",
            ]
        elif target_context == "seeker_general":
            options = [
                f"{time} — {beater['display_name']} catches seeker {target['display_name']} away from any live Snitch chase and sends them reeling across the pitch.",
                f"{time} — {beater['display_name']} buries a bludger into seeker {target['display_name']} well away from the Snitch and the whole crowd groans.",
            ]
        else:
            options = [random.choice(self.KNOCKOUT_TEMPLATES).format(time=time, beater=beater['display_name'], target=target['display_name'])]
        return random.choice(options)

    def _retention_log(self, state: dict[str, Any], now: datetime) -> str:
        house = self._side_house(state, str(state.get("quaffle_possession_side") or "home"))
        options = [
            f"{now.strftime('%H:%M')} — {house} circle the hoops, probing for a cleaner opening.",
            f"{now.strftime('%H:%M')} — {house} keep the Quaffle moving from hand to hand and refuse to rush it.",
            f"{now.strftime('%H:%M')} — {house} settle the play and make the defence work all over again.",
        ]
        return random.choice(options)

    def _elapsed_minutes(self, state: dict[str, Any], now: datetime) -> int:
        started_at = datetime.fromisoformat(state["started_at"])
        return max(0, int((now - started_at).total_seconds() // 60))

    def _clamp_probability(self, raw: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, raw))

    def _team_level_sum(self, state: dict[str, Any], side: str, positions: set[str], now: datetime) -> int:
        return sum(
            max(1, int(player.get("level", 1)))
            for player in self._players_for_side(state, side, positions, now)
        )

    def _active_seeker(self, state: dict[str, Any], side: str, now: datetime) -> dict[str, Any] | None:
        return self._random_active_player(state, side, {"seeker"}, now)

    def _seeker_power(self, state: dict[str, Any], side: str, now: datetime) -> float:
        seeker = self._active_seeker(state, side, now)
        seeker_level = max(1, int(seeker.get("level", 1))) if seeker else 1
        level_term = seeker_level / 120.0
        momentum_term = float(state["home_momentum"] if side == "home" else state["away_momentum"]) * 0.45
        cheer_term = float(state["cheer_boost_home"] if side == "home" else state["cheer_boost_away"]) * 0.85
        pressure_term = self._pressure_modifier(state, side, now, mode="seek")
        return level_term + momentum_term + cheer_term + pressure_term

    def _global_snitch_spotting_probability(self, state: dict[str, Any], now: datetime) -> float:
        h = self._elapsed_minutes(state, now) / 60.0

        if h < 4.5:
            base = 0.00010
        elif h < 5.5:
            progress = h - 4.5
            base = 0.00010 + progress * 0.0015
        elif h < 6.5:
            progress = h - 5.5
            base = 0.0016 + progress * 0.0034
        elif h < 7.5:
            progress = h - 6.5
            base = 0.0050 + progress * 0.0080
        elif h < 8.5:
            progress = h - 7.5
            base = 0.016 + progress * 0.020
        elif h < 9.5:
            progress = h - 8.5
            base = 0.040 + progress * 0.045
        else:
            progress = min(2.5, h - 9.5)
            base = 0.085 + progress * 0.070

        return self._clamp_probability(base, low=0.00004, high=0.42)

    def _choose_snitch_spotting_side(self, state: dict[str, Any], now: datetime) -> str | None:
        home_seeker = self._active_seeker(state, "home", now)
        away_seeker = self._active_seeker(state, "away", now)
        if home_seeker is None and away_seeker is None:
            return None
        if home_seeker is None:
            return "away"
        if away_seeker is None:
            return "home"

        home_power = self._seeker_power(state, "home", now)
        away_power = self._seeker_power(state, "away", now)
        home_prob = self._clamp_probability(0.5 + (home_power - away_power) * 0.22, low=0.24, high=0.76)
        return "home" if random.random() < home_prob else "away"

    def _maybe_start_snitch_chase(self, state: dict[str, Any], now: datetime) -> str | None:
        if state.get("snitch_chase_active") or state.get("snitch_caught"):
            return None

        safeguard_hours = self._elapsed_minutes(state, now) / 60.0
        if safeguard_hours >= 12.0:
            force_start = True
        else:
            force_start = False

        if not force_start and random.random() > self._global_snitch_spotting_probability(state, now):
            return None

        side = self._choose_snitch_spotting_side(state, now)
        if side is None:
            return None

        seeker = self._active_seeker(state, side, now)
        if seeker is None:
            return None

        state["snitch_chase_active"] = True
        state["snitch_chase_side"] = side
        state["snitch_chase_seeker_token"] = seeker["token"]
        state["snitch_chase_ticks"] = 0
        state["snitch_chase_started_minute"] = int(state["minute"])

        house = state["home_house"] if side == "home" else state["away_house"]
        return random.choice(self.SNITCH_SPOTTED_TEMPLATES).format(
            time=now.strftime("%H:%M"),
            seeker=seeker["display_name"],
            house=house,
        )

    def _clear_snitch_chase(self, state: dict[str, Any]) -> None:
        state["snitch_chase_active"] = False
        state["snitch_chase_side"] = None
        state["snitch_chase_seeker_token"] = None
        state["snitch_chase_ticks"] = 0
        state["snitch_chase_started_minute"] = None

    def _active_chasing_seeker(self, state: dict[str, Any], now: datetime) -> dict[str, Any] | None:
        side = state.get("snitch_chase_side")
        token = state.get("snitch_chase_seeker_token")
        if side not in {"home", "away"} or not token:
            return None

        lineup_key = "home_lineup" if side == "home" else "away_lineup"
        for player in state.get(lineup_key, []):
            player_token = str(player.get("token") or player.get("display_name") or player.get("username") or "unknown")
            if player_token != token:
                continue
            if not self._is_player_active(state, player_token, now):
                return None

            player_copy = dict(player)
            player_copy["token"] = player_token
            player_copy["display_name"] = str(
                player.get("display_name") or player.get("username") or player.get("name") or "Unknown Player"
            )
            return player_copy
        return None

    def _defending_beater_for_snitch(self, state: dict[str, Any], chasing_side: str, now: datetime) -> dict[str, Any] | None:
        defending_side = "away" if chasing_side == "home" else "home"
        return self._random_active_player(state, defending_side, {"beater"}, now)

    def _resolve_snitch_chase(self, state: dict[str, Any], now: datetime) -> tuple[list[str], bool]:
        chasing_side = state.get("snitch_chase_side")
        if chasing_side not in {"home", "away"}:
            self._clear_snitch_chase(state)
            return [], False

        chasing_seeker = self._active_chasing_seeker(state, now)
        if chasing_seeker is None:
            self._clear_snitch_chase(state)
            return [], False

        other_side = "away" if chasing_side == "home" else "home"
        other_seeker = self._active_seeker(state, other_side, now)

        state["snitch_chase_ticks"] = int(state.get("snitch_chase_ticks", 0)) + 1
        chase_ticks = int(state["snitch_chase_ticks"])

        elapsed_hours = self._elapsed_minutes(state, now) / 60.0
        chase_time_bonus = min(0.18, chase_ticks * 0.035)

        primary_power = self._seeker_power(state, chasing_side, now)
        other_power = self._seeker_power(state, other_side, now) if other_seeker else 0.15

        if elapsed_hours < 5.5:
            base_catch = 0.008
        elif elapsed_hours < 6.5:
            base_catch = 0.015
        elif elapsed_hours < 7.5:
            base_catch = 0.024
        elif elapsed_hours < 8.5:
            base_catch = 0.050
        elif elapsed_hours < 9.5:
            base_catch = 0.120
        else:
            base_catch = 0.35 + min(0.25, (elapsed_hours - 9.5) * 0.12)

        if elapsed_hours >= 12.5:
            base_catch = max(base_catch, 0.85)

        catch_prob = self._clamp_probability(
            base_catch + (primary_power - other_power) * 0.10 + chase_time_bonus,
            low=0.02,
            high=0.92,
        )

        steal_prob = 0.0
        if other_seeker is not None:
            steal_prob = self._clamp_probability(
                0.07 + (other_power - primary_power) * 0.08 + max(0.0, elapsed_hours - 7.5) * 0.012,
                low=0.03,
                high=0.16,
            )

        defending_beater = self._defending_beater_for_snitch(state, chasing_side, now)
        interference_prob = 0.0
        if defending_beater is not None:
            beater_level = max(1, int(defending_beater.get("level", 1)))
            early_break_bonus = 0.0
            if elapsed_hours < 7.5:
                early_break_bonus = 0.12
            elif elapsed_hours < 8.5:
                early_break_bonus = 0.08
            elif elapsed_hours < 9.5:
                early_break_bonus = 0.04
            interference_prob = self._clamp_probability(
                0.08 + (beater_level / 120.0) * 0.12 + early_break_bonus + max(0.0, elapsed_hours - 8.5) * 0.01,
                low=0.08,
                high=0.32,
            )

        lose_prob = self._clamp_probability(
            0.42 - (primary_power * 0.12) - max(0.0, elapsed_hours - 7.0) * 0.03 - chase_ticks * 0.025,
            low=0.08,
            high=0.45,
        )

        continue_prob = max(0.03, 1.0 - (catch_prob + steal_prob + interference_prob + lose_prob))

        total = catch_prob + steal_prob + interference_prob + lose_prob + continue_prob
        catch_prob /= total
        steal_prob /= total
        interference_prob /= total
        lose_prob /= total
        continue_prob /= total

        roll = random.random()

        if roll < catch_prob:
            house = state["home_house"] if chasing_side == "home" else state["away_house"]
            score_key = "home_score" if chasing_side == "home" else "away_score"
            state[score_key] = int(state[score_key]) + 150
            state["snitch_caught"] = True
            state["winner_house"] = house
            self._clear_snitch_chase(state)
            return [random.choice(self.SNITCH_CATCH_TEMPLATES).format(
                time=now.strftime("%H:%M"),
                seeker=chasing_seeker["display_name"],
                house=house,
            )], True

        roll -= catch_prob
        if roll < steal_prob and other_seeker is not None:
            house = state["home_house"] if other_side == "home" else state["away_house"]
            score_key = "home_score" if other_side == "home" else "away_score"
            state[score_key] = int(state[score_key]) + 150
            state["snitch_caught"] = True
            state["winner_house"] = house
            self._clear_snitch_chase(state)
            return [random.choice(self.SNITCH_STOLEN_TEMPLATES).format(
                time=now.strftime("%H:%M"),
                thief=other_seeker["display_name"],
                other_seeker=chasing_seeker["display_name"],
            ) + f" {other_seeker['display_name']} closes their hand around the Snitch for {house}!"], True

        roll -= steal_prob
        if roll < interference_prob and defending_beater is not None:
            self._clear_snitch_chase(state)
            return [random.choice(self.SNITCH_INTERFERENCE_TEMPLATES).format(
                time=now.strftime("%H:%M"),
                beater=defending_beater["display_name"],
                seeker=chasing_seeker["display_name"],
            )], False

        roll -= interference_prob
        if roll < lose_prob:
            self._clear_snitch_chase(state)
            return [random.choice(self.SNITCH_LOST_TEMPLATES).format(
                time=now.strftime("%H:%M"),
                seeker=chasing_seeker["display_name"],
            )], False

        return [random.choice(self.SNITCH_CONTINUE_TEMPLATES).format(
            time=now.strftime("%H:%M"),
            seeker=chasing_seeker["display_name"],
        )], False

    def _choose_knockout_target_role(self, state: dict[str, Any], now: datetime, target_side: str) -> str | None:
        elapsed_hours = self._elapsed_minutes(state, now) / 60.0

        if elapsed_hours < 7.5:
            weighted_roles = [("chaser", 72), ("keeper", 23), ("seeker", 5)]
        else:
            weighted_roles = [("seeker", 56), ("chaser", 29), ("keeper", 15)]

        available_roles: list[str] = []
        available_weights: list[int] = []
        for role, weight in weighted_roles:
            if self._players_for_side(state, target_side, {role}, now):
                available_roles.append(role)
                available_weights.append(weight)

        if not available_roles:
            return None
        return random.choices(available_roles, weights=available_weights, k=1)[0]

    def _biased_knockout_minutes(self, low: int, high: int, beater_level: int) -> int:
        span = high - low
        bias = beater_level / 120.0
        roll = (random.random() + random.random() + bias) / 3.0
        return low + int(round(span * roll))

    def _apply_knockout_momentum_swing(
        self,
        state: dict[str, Any],
        target_side: str,
        role: str,
        target: dict[str, Any],
    ) -> None:
        target_level = max(1, int(target.get("level", 1)))
        level_factor = target_level / 120.0

        if role == "chaser":
            penalty = 0.016 + 0.020 * level_factor
        elif role == "keeper":
            penalty = 0.012 + 0.012 * level_factor
        elif role == "seeker":
            penalty = 0.008 + 0.010 * level_factor
        else:
            penalty = 0.010

        if target_side == "home":
            state["home_momentum"] = max(-0.16, float(state["home_momentum"]) - penalty)
            state["away_momentum"] = min(0.16, float(state["away_momentum"]) + penalty * 0.55)
        else:
            state["away_momentum"] = max(-0.16, float(state["away_momentum"]) - penalty)
            state["home_momentum"] = min(0.16, float(state["home_momentum"]) + penalty * 0.55)

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

        beater_factor = 0.70 + 0.30 * (beater_level / 120.0)
        target_factor = 0.55 + 0.45 * (target_level / 120.0)
        late_phase = self._elapsed_minutes(state, now) >= int(7.5 * 60)

        attack = 0.0
        defence = 0.0
        seek = 0.0

        if target_role == "chaser":
            attack = 0.014 + 0.028 * beater_factor * target_factor
        elif target_role == "keeper":
            attack = 0.028 + 0.020 * beater_factor * target_factor
            defence = 0.005 + 0.008 * beater_factor
        elif target_role == "beater":
            attack = 0.008 + 0.010 * beater_factor * target_factor
            defence = 0.006 + 0.008 * beater_factor * target_factor
        elif target_role == "seeker":
            seek = 0.010 + 0.020 * beater_factor * target_factor
            if late_phase:
                seek += 0.015

        return {
            "attack": min(0.060, attack),
            "defence": min(0.025, defence),
            "seek": min(0.060, seek),
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
            return f"{now.strftime('%H:%M')} — {striking_house} have blown a hole in the opposing attacking shape, and that player will be out for at least several minutes."
        if target_role == "keeper":
            return f"{now.strftime('%H:%M')} — The medics are attending to the keeper, and the hoops suddenly look far more vulnerable."
        if target_role == "beater":
            return f"{now.strftime('%H:%M')} — {striking_house} may control the physical side of this match for a while now."
        if target_role == "seeker":
            return f"{now.strftime('%H:%M')} — That could echo through the Snitch chase later on."
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