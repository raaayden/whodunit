"""
Murder Mystery Game Simulator — supports standard games AND experimental presets
Usage:
    # Standard game (existing room):
    python simulation.py <room_url_or_uuid> [--token=PASSWORD]

    # Spawn + simulate a preset:
    python simulation.py --preset=cursed_galleon   [--token=PASSWORD]
    python simulation.py --preset=operation_nusantara [--token=PASSWORD]
    python simulation.py --preset=the_last_carriage     [--token=PASSWORD]

    # Create new AI game from first template:
    python simulation.py
"""
import requests
import random
import time
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

script_dir = Path(__file__).parent.resolve()
load_dotenv(dotenv_path=script_dir / ".env")

BASE_URL = os.getenv("BASE_URL", "https://whodunit-4zqi.onrender.com")

# ── Utility ───────────────────────────────────────────────────────────────────

def pause(prompt: str = ""):
    msg = f"\n{'─'*55}\n  ▶  {prompt}\n     [Y + Enter] to continue  |  [Q + Enter] to quit\n{'─'*55}\n"
    while True:
        ans = input(msg).strip().upper()
        if ans in ("", "Y"): return
        if ans == "Q":
            print("\n🛑 Simulation aborted.")
            sys.exit(0)


def get_admin_password() -> str:
    pw = os.getenv("HOST_ADMIN_PASSWORD", "").strip()
    if pw: return pw
    for arg in sys.argv[1:]:
        if arg.startswith("--token="):
            return arg.split("=", 1)[1].strip()
    import getpass
    print("⚠️  HOST_ADMIN_PASSWORD not found in .env or --token= arg.")
    return getpass.getpass("   Enter admin password: ").strip()


def extract_game_id(s: str) -> str:
    return s.rstrip("/").split("/")[-1] if "/" in s else s.strip()


def req(method: str, path: str, headers: dict | None = None,
        params: dict | None = None) -> dict:
    res = getattr(requests, method)(
        f"{BASE_URL}{path}", headers=headers or {}, params=params
    )
    res.raise_for_status()
    return res.json()


def role_badge(p: dict) -> str:
    if p.get("is_killer"):       return "🔪 KILLER      "
    if p.get("is_poisoner"):     return "☠️  POISONER    "
    if p.get("is_accomplice"):   return "🤝 ACCOMPLICE  "
    if p.get("is_investigator"): return "🔎 INVESTIGATOR"
    if p.get("is_drunk"):        return "🍺 DRUNK       "
    if p.get("is_paranoid"):     return "🧠 PARANOID    "
    if p.get("is_spy"):          return "🕵️  SPY         "
    if p.get("is_fool"):         return "🃏 FOOL        "
    if p.get("is_jester"):       return "🎭 JESTER      "
    return                              "😇 innocent    "


def sep(title: str = ""):
    line = "═" * 55
    if title:
        pad = max(0, (53 - len(title)) // 2)
        print(f"\n╔{line}╗")
        print(f"║{' '*pad} {title} {' '*(53 - pad - len(title))}║")
        print(f"╚{line}╝")
    else:
        print(f"\n{'─'*55}")


# ── Player perspective printer ────────────────────────────────────────────────

def print_player_perspective(bot_name: str, access_key: str):
    try:
        d = req("get", f"/player/dashboard/{access_key}")
    except Exception as e:
        print(f"     ⚠️  Could not fetch dashboard: {e}")
        return

    char  = d.get("character_name", "?")
    dead  = " [DEAD 💀]" if d.get("is_dead") else ""
    exiled = " [EXILED ⚖️]" if d.get("is_exiled") else ""
    round_ = d.get("current_round", "?")

    print(f"\n  ┌─ 👤 {bot_name}  (Round {round_})")
    print(f"  │  Character : {char}{dead}{exiled}")
    print(f"  │  Role      : {role_badge(d)}")

    if (d.get("is_accomplice") or d.get("is_poisoner")) and d.get("known_killer"):
        print(f"  │  Knows killer: {d['known_killer']}")
    if d.get("is_poisoner"):
        pt = d.get("poison_target")
        print(f"  │  Poison target: {pt if pt else '(none set)'}")
    if d.get("is_spy"):
        if d.get("spy_used"):
            print(f"  │  Spy result: {d.get('spy_result','')}")
        else:
            print(f"  │  Spy ability: not yet used")
    if d.get("is_jester"):
        print(f"  │  🎭 Goal: trick the majority into voting for me")

    # Role sheet
    desc = d.get("role_description", "").strip()
    if desc:
        print(f"  │")
        print(f"  │  📋 Role Sheet:")
        for line in desc.split("\n"):
            if line.strip():
                print(f"  │     {line.strip()}")

    # Public clues (Round 3 only)
    public_clues = d.get("active_story", {}).get("public_clues", [])
    active_public = [c for c in public_clues if c.get("round", 99) <= round_]
    if active_public:
        print(f"  │")
        print(f"  │  📢 Public announcement:")
        for c in active_public:
            print(f"  │     [R{c['round']}] {c['content'].strip()}")

    # Private clues
    clues = d.get("available_clues", [])
    if clues:
        print(f"  │")
        print(f"  │  🔍 Private clues ({len(clues)}):")
        for c in clues:
            print(f"  │     [R{c.get('round_number','?')}] {c.get('content','').strip()}")

    # Ghost clues received
    ghost_clues = d.get("received_ghost_clues", [])
    if ghost_clues:
        print(f"  │")
        print(f"  │  👻 Ghost clues received:")
        for g in ghost_clues:
            print(f"  │     From {g.get('character_name','?')}: {g.get('ghost_clue','').strip()}")

    # Dead — ghost clue status
    if d.get("is_dead"):
        print(f"  │")
        print(f"  │  💀 Ghost clue: {d.get('ghost_clue','').strip()}")
        recipient = d.get("ghost_clue_recipient")
        print(f"  │     → {'Sent to: ' + recipient if recipient else 'Not sent yet'}")

    # Notebook
    notebook = d.get("notebook", [])
    if notebook:
        print(f"  │")
        print(f"  │  📓 Notebook:")
        for entry in notebook:
            status = entry.get("my_note", {}).get("status", "neutral")
            icon = {"sus": "🔴", "alright fam": "🟢", "neutral": "⚪"}.get(status, "⚪")
            dead_tag = " [dead]" if entry.get("is_publicly_dead") else ""
            print(f"  │     {icon} {entry['character_name']:<30} ← {entry.get('claimed_by') or '—'}{dead_tag}")

    if d.get("voted_for"):
        print(f"  │")
        print(f"  │  🗳️  Voted for: {d['voted_for']}")

    print(f"  └{'─'*52}")


# ── Main simulation ───────────────────────────────────────────────────────────

def run_simulation(game_id: str | None = None, preset: str | None = None):
    sep("MURDER MYSTERY SIMULATOR 🕵️")

    admin_pass = get_admin_password()
    headers    = {"x-admin-token": admin_pass}

    # Auth check
    print("\n[auth] Verifying admin token...")
    test = requests.get(f"{BASE_URL}/admin/templates", headers=headers)
    if test.status_code == 401:
        raise RuntimeError("Admin token rejected (401). Check HOST_ADMIN_PASSWORD.")
    test.raise_for_status()
    print("       ✅ Token accepted.")

    # ── Resolve game ──────────────────────────────────────────────────────────
    if preset:
        print(f"\n[game] Spawning preset: {preset}...")
        data    = req("post", f"/admin/spawn-preset/{preset}", headers=headers)
        game_id = data["game_id"]
        is_crisis = data.get("is_crisis", False) or preset in ("operation_nusantara", "the_last_carriage")
        print(f"       ✅ {data['message']}")
        print(f"       Room: {data['room_url']}")
    elif game_id:
        game_id   = extract_game_id(game_id)
        is_crisis = False
        print(f"\n[game] Using existing room: {game_id}")
    else:
        print("\n[game] Creating new game from first template...")
        templates = req("get", "/admin/templates", headers=headers).get("templates", [])
        if not templates:
            raise RuntimeError("No templates found. Create one in the dashboard first.")
        t = templates[0]
        print(f"       Template: {t['theme_title']}")
        result  = req("post", f"/admin/create-from-template/{t['id']}", headers=headers)
        game_id = result["game_id"]
        is_crisis = False
        print(f"       Created: {game_id}")

    print(f"       Room URL: {BASE_URL}/room/{game_id}")

    # ── Fetch state & join bots ───────────────────────────────────────────────
    god = req("get", f"/admin/game/{game_id}", headers=headers)
    players = god["players"]
    print(f"\n[game] {len(players)} character slot(s)")

    sep("STEP 1 — JOINING PLAYERS")
    access_keys: dict[str, str] = {}   # bot_name → access_key

    for i, p in enumerate(players):
        if p.get("claimed_by_user"):
            print(f"  ⏭️  Slot {i+1} already claimed by '{p['claimed_by_user']}'")
            continue
        bot_name = f"SimBot_{i+1}"
        res = requests.post(
            f"{BASE_URL}/api/room/{game_id}/join",
            params={"player_name": bot_name}
        )
        res.raise_for_status()
        data = res.json()
        access_keys[bot_name] = data["access_key"]
        print(f"  🤖 {bot_name:<12} joined as '{data['character_name']}'")

    # ── Roster ────────────────────────────────────────────────────────────────
    sep("ROSTER — SECRET IDENTITIES (GOD VIEW)")
    god2 = req("get", f"/admin/game/{game_id}", headers=headers)

    for p in god2["players"]:
        owner  = p.get("claimed_by_user") or "—"
        extras = []
        if p.get("is_poisoner"):       extras.append("corrupts clues each round")
        elif p.get("is_paranoid"):     extras.append("convinced wrong person is guilty")
        elif p.get("is_drunk"):        extras.append("all clues are false")
        elif p.get("is_investigator"): extras.append("gets 50/50 ping at R3")
        elif p.get("is_spy"):          extras.append("can learn one player's role")
        elif p.get("is_fool"):         extras.append("thinks they're killer — they're not")
        elif p.get("is_jester"):       extras.append("wins if majority votes for them")
        suffix = f"  ({extras[0]})" if extras else ""
        print(f"  {role_badge(p)}  {p['character_name']:<32} ← {owner}{suffix}")

    # ── ROUNDS ────────────────────────────────────────────────────────────────
    TOTAL_ROUNDS = 3

    for round_num in range(1, TOTAL_ROUNDS + 1):
        sep(f"ROUND {round_num} of {TOTAL_ROUNDS}")
        pause(f"Release Round {round_num}?")

        print(f"\n[R{round_num}] Releasing round {round_num}...")
        req("post", f"/admin/release-round/{game_id}/{round_num}", headers=headers)
        time.sleep(0.8)

        state = req("get", f"/admin/game/{game_id}", headers=headers)

        # ── Round 1 actions ───────────────────────────────────────────────────
        if round_num == 1:
            # Killer picks target
            print(f"\n[R{round_num}] Killer selects elimination target...")
            killer_key     = None
            innocent_names = []
            for p in state["players"]:
                owner = p.get("claimed_by_user", "")
                key   = access_keys.get(owner)
                if p["is_killer"]:
                    killer_key = key
                    if not key: print(f"       ⚠️  Killer ({owner}) is human — skipping.")
                elif not p.get("is_jester"):  # killer won't target jester (no value)
                    innocent_names.append(p["character_name"])

            if killer_key and innocent_names:
                target = random.choice(innocent_names)
                req("post", f"/player/eliminate/{killer_key}",
                    params={"target_character": target})
                print(f"       🔪 Killer locked in: {target}")

            # Poisoner picks Round 2 target
            poisoner = next(
                (p for p in state["players"] if p.get("is_poisoner") and not p.get("is_dead")), None
            )
            if poisoner:
                owner = poisoner.get("claimed_by_user", "")
                pkey  = access_keys.get(owner)
                if pkey:
                    candidates = [
                        p["character_name"] for p in state["players"]
                        if not p.get("is_killer") and not p.get("is_accomplice")
                        and not p.get("is_poisoner") and p["character_name"] != poisoner["character_name"]
                    ]
                    if candidates:
                        ptarget = random.choice(candidates)
                        try:
                            req("post", f"/player/poison/{pkey}",
                                params={"target_character": ptarget})
                            print(f"       ☠️  Poisoner locked in: {ptarget} (corrupted on R2 release)")
                        except Exception as e:
                            print(f"       ⚠️  Poison failed: {e}")

        # ── Round 2 actions ───────────────────────────────────────────────────
        elif round_num == 2:
            # Ghost clues from dead bots
            print(f"\n[R{round_num}] Dead bots sending ghost clues...")
            alive_chars = [p["character_name"] for p in state["players"] if not p.get("is_dead")]

            for p in state["players"]:
                if not p.get("is_dead"): continue
                owner = p.get("claimed_by_user", "")
                key   = access_keys.get(owner)
                if not key or p.get("ghost_clue_recipient"): continue
                candidates = [c for c in alive_chars if c != p["character_name"]]
                if not candidates: continue
                recipient = random.choice(candidates)
                try:
                    req("post", f"/player/send-ghost-clue/{key}",
                        params={"target_character": recipient})
                    print(f"       👻 {p['character_name']} haunted → {recipient}")
                except Exception as e:
                    print(f"       ⚠️  Ghost clue failed: {e}")

            # Spy uses ability
            spy = next(
                (p for p in state["players"] if p.get("is_spy") and not p.get("is_dead")), None
            )
            if spy:
                owner = spy.get("claimed_by_user", "")
                skey  = access_keys.get(owner)
                if skey:
                    dash = req("get", f"/player/dashboard/{skey}")
                    if not dash.get("spy_used"):
                        candidates = [
                            p["character_name"] for p in state["players"]
                            if p["character_name"] != spy["character_name"] and not p.get("is_dead")
                        ]
                        if candidates:
                            peek = random.choice(candidates)
                            try:
                                result = req("post", f"/player/spy/{skey}",
                                             params={"target_character": peek})
                                print(f"       🕵️  {spy['character_name']} investigated {peek} → {result.get('role','?')}")
                            except Exception as e:
                                print(f"       ⚠️  Spy failed: {e}")

            # Exile vote (30% chance per bot)
            print(f"\n[R{round_num}] Simulating exile nominations...")
            alive_bots = [
                p for p in state["players"]
                if not p.get("is_dead") and access_keys.get(p.get("claimed_by_user", ""))
            ]
            exile_targets = [p["character_name"] for p in state["players"] if not p.get("is_dead")]
            exiled_this_round = False
            for p in alive_bots:
                if random.random() > 0.3: continue
                if exiled_this_round: break
                owner = p.get("claimed_by_user", "")
                key   = access_keys.get(owner)
                if not key or not exile_targets: continue
                nominee = random.choice(exile_targets)
                try:
                    result = req("post", f"/player/exile-nominate/{key}",
                                 params={"target_character": nominee})
                    exiled = result.get("exiled", False)
                    print(f"       ⚖️  {owner} nominated {nominee}{' → EXILED!' if exiled else ''}")
                    if exiled:
                        exiled_this_round = True
                except Exception as e:
                    print(f"       ⚠️  Exile failed: {e}")

            # Crisis dilemma (crisis games only)
            if is_crisis:
                print(f"\n[R{round_num}] 🚨 Crisis Dilemma — bots casting votes...")
                alive_voters = [
                    p for p in state["players"]
                    if not p.get("is_dead") and access_keys.get(p.get("claimed_by_user", ""))
                ]
                for p in alive_voters:
                    owner = p.get("claimed_by_user", "")
                    key   = access_keys.get(owner)
                    if not key: continue
                    # Evil bots vote dangerous, innocents split
                    if p.get("is_killer") or p.get("is_accomplice") or p.get("is_poisoner"):
                        vote = "dangerous"
                    else:
                        vote = random.choice(["safe", "dangerous"])
                    try:
                        result = req("post", f"/player/crisis-vote/{key}",
                                     params={"vote": vote})
                        print(f"       ⚡ {owner} ({p['character_name']}) voted: {vote}")
                    except Exception as e:
                        print(f"       ⚠️  Crisis vote failed: {e}")

                # Resolve crisis
                print(f"\n[R{round_num}] Resolving crisis dilemma...")
                time.sleep(0.5)
                result = req("post", f"/admin/resolve-crisis/{game_id}", headers=headers)
                print(f"       {'⚠️' if result.get('dangerous_won') else '✅'} {result['message']}")

                # If dangerous won, killer picks extra elimination target
                if result.get("dangerous_won"):
                    print(f"\n[R{round_num}] ⚡ Killer selecting extra elimination target...")
                    state2 = req("get", f"/admin/game/{game_id}", headers=headers)
                    killer_key2 = None
                    alive_names = []
                    for p in state2["players"]:
                        owner = p.get("claimed_by_user", "")
                        key   = access_keys.get(owner)
                        if p["is_killer"] and not p.get("is_dead"):
                            killer_key2 = key
                        elif not p.get("is_dead") and not p.get("is_jester"):
                            alive_names.append(p["character_name"])
                    if killer_key2 and alive_names:
                        extra_target = random.choice(alive_names)
                        try:
                            req("post", f"/player/eliminate/{killer_key2}",
                                params={"target_character": extra_target})
                            print(f"       🔪 Extra kill locked: {extra_target}")
                        except Exception as e:
                            print(f"       ⚠️  Extra kill failed: {e}")

            # Poisoner picks Round 3 target (if still alive)
            poisoner = next(
                (p for p in state["players"] if p.get("is_poisoner") and not p.get("is_dead")), None
            )
            if poisoner:
                owner = poisoner.get("claimed_by_user", "")
                pkey  = access_keys.get(owner)
                if pkey:
                    candidates = [
                        p["character_name"] for p in state["players"]
                        if not p.get("is_dead") and not p.get("is_killer")
                        and not p.get("is_accomplice") and not p.get("is_poisoner")
                    ]
                    if candidates:
                        ptarget = random.choice(candidates)
                        try:
                            req("post", f"/player/poison/{pkey}",
                                params={"target_character": ptarget})
                            print(f"       ☠️  Poisoner re-locked: {ptarget} (corrupted on R3 release)")
                        except Exception as e:
                            print(f"       ⚠️  Poison R3 failed: {e}")

        # ── Round 3: Final votes ──────────────────────────────────────────────
        elif round_num == TOTAL_ROUNDS:
            print(f"\n[R{round_num}] Final votes...")
            living = [p["character_name"] for p in state["players"] if not p.get("is_dead")]
            alive  = [p for p in state["players"] if not p.get("is_dead")]

            # Find jester name for strategic voting
            jester_name = next(
                (p["character_name"] for p in state["players"] if p.get("is_jester")), None
            )

            for p in alive:
                owner = p.get("claimed_by_user", "")
                key   = access_keys.get(owner)
                if not key: continue

                # Voting logic:
                # - Killer/accomplice: vote for jester (to frame them) or random innocent
                # - Jester: votes for themselves (that's the whole point)
                # - Paranoid: votes for whoever their clue points to (random innocent simulation)
                # - Everyone else: random from living
                if p.get("is_killer") or p.get("is_accomplice") or p.get("is_poisoner"):
                    # Evil team prefers to vote for jester if present (deflects onto them)
                    vote = jester_name if jester_name and jester_name in living else random.choice(living)
                elif p.get("is_jester"):
                    # Jester votes for themselves
                    vote = p["character_name"] if p["character_name"] in living else random.choice(living)
                else:
                    vote = random.choice(living)

                try:
                    req("post", f"/player/vote/{key}", params={"suspect": vote})
                    role = role_badge(p).strip()
                    print(f"       🗳️  {owner} [{role}] → {vote}")
                except Exception as e:
                    print(f"       ⚠️  Vote failed: {e}")

        # ── Print perspectives ────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  📱 BOT PERSPECTIVES")
        print(f"{'─'*55}")
        for bot_name, access_key in access_keys.items():
            print_player_perspective(bot_name, access_key)
            time.sleep(0.15)

    # ── End game ──────────────────────────────────────────────────────────────
    sep("END GAME")
    pause("End the game and generate recap?")

    print("[end] Ending game (Gemini writing recap)...")
    req("post", f"/admin/end-game/{game_id}", headers=headers)
    time.sleep(2.5)

    # Final reveal
    first_key = next(iter(access_keys.values()), None)
    if first_key:
        d      = req("get", f"/player/dashboard/{first_key}")
        reveal = d.get("reveal_data", {})

        if reveal:
            sep("FINAL REVEAL 🎭")

            # Recap (skipped for preset games)
            recap = reveal.get("recap", "")
            if recap:
                print("\n📖 Story Recap:")
                print(f"{'─'*55}")
                for para in recap.split("\n"):
                    if para.strip():
                        # Word-wrap at 80 chars
                        words = para.strip().split()
                        line  = "  "
                        for word in words:
                            if len(line) + len(word) > 80:
                                print(line)
                                line = "  " + word + " "
                            else:
                                line += word + " "
                        if line.strip():
                            print(line)
                        print()
                print(f"{'─'*55}")

            # Outcome
            jester_won = reveal.get("jester_won", False)
            caught     = reveal.get("killer_caught", False)
            if jester_won:
                jname = reveal.get("jester_name", "The Jester")
                print(f"\n🎭 JESTER WINS — {jname} tricked everyone!")
            elif caught:
                print(f"\n🎉 INNOCENTS WIN — killer was caught!")
            else:
                print(f"\n💀 KILLER WINS — got away with murder!")

            # Solution
            story = reveal.get("master_story", {})
            if story.get("the_solution"):
                print("\n🔍 The Solution:")
                for line in story["the_solution"].split("\n"):
                    if line.strip(): print(f"   {line.strip()}")

            # True identities
            print("\n🎭 True Identities:")
            for ident in reveal.get("true_identities", []):
                badge  = role_badge(ident)
                extras = []
                if ident.get("is_exiled"):  extras.append("EXILED")
                if ident.get("is_dead"):    extras.append("dead")
                suffix = f"  [{', '.join(extras)}]" if extras else ""
                print(f"   {badge}  {ident['name']:<32} ← {ident.get('player','—')}{suffix}")

            # Votes
            print("\n🗳️  Final Votes:")
            for v in reveal.get("votes", []):
                tick = "✅" if v.get("is_correct") else (
                    "🎭" if v.get("target") == reveal.get("jester_name") else "❌"
                )
                print(f"   {tick} {v.get('voter','?'):<32} accused {v.get('target','?')}")

    print(f"\n✅ Simulation complete!")
    print(f"   Results: {BASE_URL}/room/{game_id}\n")


if __name__ == "__main__":
    # Parse args
    preset_arg  = next((a.split("=",1)[1] for a in sys.argv[1:] if a.startswith("--preset=")), None)
    room_arg    = next((a for a in sys.argv[1:] if not a.startswith("--")), None)

    try:
        run_simulation(game_id=room_arg, preset=preset_arg)
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted.")
    except Exception as e:
        print(f"\n❌ Simulation failed: {e}")
        raise
