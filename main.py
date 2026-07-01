"""
main.py — FastAPI route definitions only.
Business logic  → functions.py
Preset templates → presets.py
"""
from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from supabase import create_client, Client
from google import genai
import json
import logging
import os
from dotenv import load_dotenv

import functions as fn
import presets   as ps

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# ── Clients ───────────────────────────────────────────────────────────────────

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

fn.init_clients(supabase, gemini_client)
ps.init_preset_clients(supabase, fn.generate_key, fn.assign_bluff_roles)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

verify_host = fn.verify_host   # re-export for Depends()


# ── Static pages ──────────────────────────────────────────────────────────────

@app.get("/")
async def host_dashboard(): return FileResponse("static/index.html")

@app.get("/room/{game_id}")
async def lobby_view(game_id: str): return FileResponse("static/room.html")

@app.get("/play")
async def player_view(): return FileResponse("static/player.html")


# ── Admin: Templates ──────────────────────────────────────────────────────────

@app.get("/admin/templates", dependencies=[Depends(verify_host)])
async def get_templates():
    templates = supabase.table("game_templates").select(
        "id, theme, theme_title, short_description, player_count, accomplice_count, "
        "has_drunk, has_investigator, has_poisoner, has_paranoid, has_spy, has_fool, "
        "has_undertaker, has_recluse, has_alibi_cards"
    ).order("created_at", desc=True).execute()
    return {"templates": templates.data}


# ── Admin: Spawn from saved template ─────────────────────────────────────────

@app.post("/admin/create-from-template/{template_id}", dependencies=[Depends(verify_host)])
async def create_from_template(request: Request, template_id: str):
    from fastapi import HTTPException
    template_res = supabase.table("game_templates").select("*").eq("id", template_id).execute()
    if not template_res.data:
        raise HTTPException(status_code=404, detail="Template not found")
    data = template_res.data[0]

    game_id = supabase.table("games").insert({
        "theme":             data["theme_title"],
        "theme_title":       data["theme_title"],
        "short_description": data["short_description"],
        "master_story":      json.dumps(data["master_story"]),
    }).execute().data[0]["id"]

    fn.insert_players_and_clues(game_id, data["characters"])
    return {"message": "Game spawned from template!", "game_id": game_id,
            "room_url": f"{request.base_url}room/{game_id}"}


# ── Admin: Generate new game with AI ─────────────────────────────────────────

@app.post("/admin/create-game", dependencies=[Depends(verify_host)])
async def create_game(
    request: Request, theme: str, player_count: int,
    accomplice_count: int = 0, include_drunk: bool = False,
    include_investigator: bool = False, include_poisoner: bool = False,
    include_paranoid: bool = False, include_spy: bool = False, include_fool: bool = False,
    include_undertaker: bool = False, include_recluse: bool = False,
):
    game_data = fn.generate_game_with_ai_layered(
        theme, player_count, accomplice_count,
        include_drunk, include_investigator, include_poisoner,
        include_paranoid, include_spy, include_fool,
        include_undertaker, include_recluse,
    )

    supabase.table("game_templates").insert({
        "theme":             theme,
        "theme_title":       game_data.get("theme_title", f"Mystery: {theme}"),
        "short_description": game_data.get("short_description", "Trust no one."),
        "player_count":      player_count,
        "accomplice_count":  accomplice_count,
        "has_drunk":         include_drunk,
        "has_investigator":  include_investigator,
        "has_poisoner":      include_poisoner,
        "has_paranoid":      include_paranoid,
        "has_spy":           include_spy,
        "has_fool":          include_fool,
        "has_undertaker":    include_undertaker,
        "has_recluse":       include_recluse,
        "master_story":      game_data["master_story"],
        "characters":        game_data["characters"],
    }).execute()

    game_id = supabase.table("games").insert({
        "theme":             theme,
        "theme_title":       game_data.get("theme_title", f"Mystery: {theme}"),
        "short_description": game_data.get("short_description", "Trust no one."),
        "master_story":      json.dumps(game_data["master_story"]),
    }).execute().data[0]["id"]

    fn.insert_players_and_clues(game_id, game_data["characters"])
    return {"message": "Game generated!", "game_id": game_id,
            "room_url": f"{request.base_url}room/{game_id}"}


# ── Admin: God-mode view ──────────────────────────────────────────────────────

@app.get("/admin/game/{game_id}", dependencies=[Depends(verify_host)])
async def get_game_state(game_id: str):
    game    = supabase.table("games").select("*").eq("id", game_id).execute()
    players = supabase.table("players").select("*").eq("game_id", game_id).execute()
    return {"game": game.data[0], "players": players.data}


# ── Admin: Release round ──────────────────────────────────────────────────────

@app.post("/admin/release-round/{game_id}/{round_num}", dependencies=[Depends(verify_host)])
async def release_clues(game_id: str, round_num: int):
    supabase.table("games").update({
        "current_round": round_num, "status": "started"
    }).eq("id", game_id).execute()

    if round_num > 1:
        fn.apply_poison_swap(game_id, round_num)
        if round_num == 2:
            fn.apply_undertaker_result(game_id)
            fn.apply_killer_awakening(game_id)
        supabase.table("clues").update({"is_released": True}).eq(
            "game_id", game_id).eq("round_number", round_num).execute()

    # Apply crisis extra kill when Round 3 begins
    if round_num == 3:
        killer = supabase.table("players").select("extra_kill_target").eq(
            "game_id", game_id).eq("is_killer", True).execute()
        if killer.data and killer.data[0].get("extra_kill_target"):
            extra_target = killer.data[0]["extra_kill_target"]
            supabase.table("players").update({
                "is_dead": True, "death_round": 3
            }).eq("game_id", game_id).eq("character_name", extra_target).execute()

    return {"message": f"Round {round_num} active!"}


# ── Admin: End game ───────────────────────────────────────────────────────────

@app.post("/admin/end-game/{game_id}", dependencies=[Depends(verify_host)])
async def end_game(game_id: str):
    recap_text = fn.build_recap(game_id)
    supabase.table("games").update({
        "status": "finished",
        "recap":  recap_text,
    }).eq("id", game_id).execute()
    return {"message": "Game ended! Results and story now visible on all player devices."}


# ── Admin: Spawn preset ───────────────────────────────────────────────────────

@app.post("/admin/spawn-preset/{preset_id}", dependencies=[Depends(verify_host)])
async def spawn_preset(request: Request, preset_id: str):
    return ps.spawn_preset_game(request, preset_id)


# ── Admin: Crisis dilemma ─────────────────────────────────────────────────────

@app.get("/admin/crisis-dilemma/{game_id}", dependencies=[Depends(verify_host)])
async def get_crisis_dilemma(game_id: str):
    from fastapi import HTTPException
    game = supabase.table("games").select(
        "theme_title, is_crisis_game, crisis_resolved, crisis_dangerous_won"
    ).eq("id", game_id).execute()
    if not game.data or not game.data[0].get("is_crisis_game"):
        raise HTTPException(status_code=400, detail="Not a crisis game.")
    g       = game.data[0]
    dilemma = fn.get_crisis_dilemma(g["theme_title"])
    votes   = supabase.table("crisis_votes").select("vote").eq("game_id", game_id).execute()
    tally   = {"safe": 0, "dangerous": 0}
    for v in votes.data: tally[v["vote"]] = tally.get(v["vote"], 0) + 1
    return {
        "dilemma":         dilemma,
        "tally":           tally,
        "crisis_resolved": g.get("crisis_resolved", False),
        "dangerous_won":   g.get("crisis_dangerous_won", False),
    }


@app.post("/admin/resolve-crisis/{game_id}", dependencies=[Depends(verify_host)])
async def resolve_crisis(game_id: str):
    import random
    votes = supabase.table("crisis_votes").select("vote, player_id").eq("game_id", game_id).execute()
    tally = {"safe": 0, "dangerous": 0}
    for v in votes.data: tally[v["vote"]] = tally.get(v["vote"], 0) + 1
    dangerous_won = tally["dangerous"] > tally["safe"]
    supabase.table("games").update({
        "crisis_resolved":      True,
        "crisis_dangerous_won": dangerous_won,
    }).eq("id", game_id).execute()

    if not dangerous_won:
        return {"message": "✅ Safe option won — no extra consequences.", "dangerous_won": False, "tally": tally}

    game     = supabase.table("games").select("theme_title, master_story").eq("id", game_id).execute()
    theme    = game.data[0]["theme_title"]
    alive    = supabase.table("players").select(
        "id, character_name, is_killer, is_accomplice"
    ).eq("game_id", game_id).eq("is_dead", False).execute()
    innocents = [p for p in alive.data if not p["is_killer"] and not p.get("is_accomplice")]

    # ── Penalty: Vote Suppression — Dead on Air ──────────────────────────────
    if "dead on air" in theme.lower():
        dangerous_ids = {v["player_id"] for v in votes.data if v["vote"] == "dangerous"}
        candidates    = [p for p in innocents if p["id"] in dangerous_ids] or innocents
        if candidates:
            target = random.choice(candidates)
            supabase.table("players").update({"is_quarantined": True}).eq(
                "id", target["id"]).execute()
            return {
                "message": f"⚠️ Dangerous option won — {target['character_name']} is quarantined and cannot cast a final vote. Announce this to the table.",
                "dangerous_won": True, "tally": tally,
                "quarantined_player": target["character_name"],
            }
        return {"message": "⚠️ Dangerous option won — quarantine penalty applied.", "dangerous_won": True, "tally": tally}

    # ── Penalty: Contaminated Broadcast — The Coastal Protocol ───────────────
    elif "coastal protocol" in theme.lower():
        if innocents:
            target      = random.choice(innocents)
            target_name = target["character_name"]
            fake_clue   = (
                f"⚠ STATION EMERGENCY LOG — Auto-archived 23:14: Movement sensor triggered in "
                f"Specimen Pool corridor at 22:58. Badge access confirmed: {target_name}. "
                f"Duration: 4 minutes. Alert was manually cleared without supervisor authorization. "
                f"— StationNet v2.4"
            )
            story = json.loads(game.data[0]["master_story"])
            story.setdefault("public_clues", []).append({"round": 2, "content": fake_clue})
            supabase.table("games").update({"master_story": json.dumps(story)}).eq(
                "id", game_id).execute()
            return {
                "message": f"⚠️ Dangerous option won — contaminated broadcast pushed to all player devices, implicating {target_name}. Players will see it on next sync.",
                "dangerous_won": True, "tally": tally,
            }
        return {"message": "⚠️ Dangerous option won — contaminated broadcast could not be generated.", "dangerous_won": True, "tally": tally}

    # ── Default Penalty: Extra Kill — all other crisis games ─────────────────
    else:
        supabase.table("players").update({"has_extra_kill": True}).eq(
            "game_id", game_id).eq("is_killer", True).execute()
        return {"message": "⚠️ Dangerous option won — killer granted an extra elimination before Round 3.",
                "dangerous_won": True, "tally": tally}


# ── Player: Ping (lightweight state check) ───────────────────────────────────

@app.get("/player/ping/{access_key}")
async def player_ping(access_key: str):
    from fastapi import HTTPException
    res = supabase.table("players").select("game_id, is_dead").eq(
        "access_key", access_key).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Invalid access key")
    p    = res.data[0]
    game = supabase.table("games").select("current_round, status").eq(
        "id", p["game_id"]).execute()
    g    = game.data[0]
    return {"round": g["current_round"], "status": g["status"], "is_dead": p["is_dead"]}


# ── Room: Public info (used by room.html before join) ─────────────────────────

@app.get("/api/room/{game_id}/info")
async def room_info(game_id: str):
    from fastapi import HTTPException
    game = supabase.table("games").select("theme_title, short_description, status").eq("id", game_id).execute()
    if not game.data:
        raise HTTPException(status_code=404, detail="Game not found.")
    g = game.data[0]
    if g["status"] == "finished":
        raise HTTPException(status_code=410, detail="This game has already ended.")
    return {"theme_title": g.get("theme_title", ""), "short_description": g.get("short_description", "")}


# ── Player: Join room ─────────────────────────────────────────────────────────

@app.post("/api/room/{game_id}/join")
async def join_room(game_id: str, player_name: str):
    from fastapi import HTTPException
    import random
    game = supabase.table("games").select("status").eq("id", game_id).execute()
    if not game.data:
        raise HTTPException(status_code=404, detail="Game not found.")
    if game.data[0]["status"] != "waiting":
        raise HTTPException(status_code=400, detail="Game has already started.")
    unclaimed = supabase.table("players").select("*").eq(
        "game_id", game_id).is_("claimed_by_user", "null").execute()
    if not unclaimed.data:
        raise HTTPException(status_code=400, detail="Room is full.")
    character = random.choice(unclaimed.data)
    supabase.table("players").update({"claimed_by_user": player_name}).eq(
        "id", character["id"]).execute()
    return {"access_key": character["access_key"], "character_name": character["character_name"]}


# ── Player: Dashboard ─────────────────────────────────────────────────────────

@app.get("/player/dashboard/{access_key}")
async def get_player_dashboard(access_key: str):
    from fastapi import HTTPException
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key")

    player  = player_res.data[0]
    game_id = player["game_id"]

    game_res = supabase.table("games").select(
        "current_round, status, master_story, theme_title, short_description, recap, "
        "is_crisis_game, crisis_resolved, crisis_dangerous_won"
    ).eq("id", game_id).execute()
    game_row      = game_res.data[0]
    current_round = game_row["current_round"]
    game_status   = game_row["status"]
    theme_title   = game_row.get("theme_title", "Secret Mission")
    short_desc    = game_row.get("short_description", "Trust no one.")
    recap         = game_row.get("recap", "")

    try:    master_story = json.loads(game_row["master_story"])
    except: master_story = {"background": "", "the_murder": "", "the_solution": "", "public_clues": []}

    is_currently_dead = player["is_dead"] and current_round >= player["death_round"]

    clues_res = supabase.table("clues").select(
        "round_number, content, is_poisoned"
    ).eq("player_id", player["id"]).eq("is_released", True).execute()

    all_players = supabase.table("players").select(
        "id, character_name, public_summary, claimed_by_user, is_dead, death_round, "
        "is_killer, is_accomplice, is_investigator, is_drunk, is_poisoner, is_paranoid, "
        "is_spy, is_fool, is_jester, is_undertaker, is_recluse, "
        "voted_for, poison_target, spy_used, spy_result, is_exiled, bluff_role"
    ).eq("game_id", game_id).execute()

    received_ghost_clues = supabase.table("players").select(
        "character_name, ghost_clue"
    ).eq("game_id", game_id).eq("ghost_clue_recipient", player["character_name"]).execute().data

    killers_count    = sum(1 for p in all_players.data if p["is_killer"])
    accomplice_count = sum(1 for p in all_players.data if p["is_accomplice"])

    known_killer = None
    if player.get("is_accomplice") or player.get("is_poisoner"):
        known_killer = next((p["character_name"] for p in all_players.data if p["is_killer"]), None)

    notes_dict = {n["target_character"]: n for n in supabase.table("player_notes").select(
        "*").eq("owner_player_id", player["id"]).execute().data}

    notebook = [
        {
            "character_name":   p["character_name"],
            "claimed_by":       p["claimed_by_user"],
            "public_summary":   p["public_summary"],
            "is_publicly_dead": p["is_dead"] and current_round >= p["death_round"],
            "my_note":          notes_dict.get(p["character_name"], {"status": "neutral", "note_text": ""}),
        }
        for p in all_players.data if p["id"] != player["id"]
    ]

    reveal_data = None
    if game_status == "finished":
        outcome      = fn.compute_outcome(all_players.data)
        killer_name  = outcome["killer_name"]
        jester_name  = outcome["jester_name"]
        votes        = []
        for p in all_players.data:
            if p["voted_for"]:
                votes.append({
                    "voter":       p["character_name"],
                    "player_name": p["claimed_by_user"],
                    "target":      p["voted_for"],
                    "is_correct":  p["voted_for"] == killer_name,
                })
        true_identities = [{
            "name":            p["character_name"],
            "player":          p["claimed_by_user"],
            "is_killer":       p["is_killer"],
            "is_accomplice":   p["is_accomplice"],
            "is_poisoner":     p.get("is_poisoner",     False),
            "is_investigator": p.get("is_investigator", False),
            "is_drunk":        p.get("is_drunk",        False),
            "is_paranoid":     p.get("is_paranoid",     False),
            "is_spy":          p.get("is_spy",          False),
            "is_fool":         p.get("is_fool",         False),
            "is_jester":       p.get("is_jester",       False),
            "is_undertaker":   p.get("is_undertaker",   False),
            "is_recluse":      p.get("is_recluse",      False),
            "is_dead":         p.get("is_dead",         False),
            "is_exiled":       p.get("is_exiled",       False),
            "bluff_role":      p.get("bluff_role",      None),
        } for p in all_players.data]
        reveal_data = {
            "master_story":    master_story,
            "true_identities": true_identities,
            "votes":           votes,
            "killer_caught":   outcome["killer_caught"],
            "jester_won":      outcome["jester_won"],
            "jester_name":     jester_name,
            "recap":           recap,
        }

    return {
        "game_status":          game_status,
        "game_id":              game_id,
        "current_round":        current_round,
        "character_name":       player["character_name"],
        "theme_title":          theme_title,
        "short_description":    short_desc,
        "active_story": {
            "background":        master_story.get("background", ""),
            "the_murder":        master_story.get("the_murder", ""),
            "public_clues":      master_story.get("public_clues", []),
        },
        "is_crisis_game":       game_row.get("is_crisis_game",       False),
        "crisis_resolved":      game_row.get("crisis_resolved",      False),
        "crisis_dangerous_won": game_row.get("crisis_dangerous_won", False),
        "role_description":     player["role_description"],
        "ghost_clue":           player["ghost_clue"],
        "ghost_clue_recipient": player["ghost_clue_recipient"],
        "received_ghost_clues": received_ghost_clues,
        "is_killer":            player["is_killer"],
        "is_accomplice":        player["is_accomplice"],
        "is_investigator":      player.get("is_investigator", False),
        "is_poisoner":          player.get("is_poisoner",     False),
        "is_spy":               player.get("is_spy",          False),
        "is_jester":            player.get("is_jester",       False),
        "is_undertaker":        player.get("is_undertaker",   False),
        "is_recluse":           player.get("is_recluse",      False),
        "undertaker_result":    player.get("undertaker_result", None),
        "alibi":                player.get("alibi",           None),
        "objective":            player.get("objective",       None),
        "bluff_role":           player.get("bluff_role",      None),
        "is_amnesia_game":      game_row.get("is_amnesia_game",  False),
        "is_awakened":          player.get("is_awakened",        False),
        "memory_fragments":     player.get("memory_fragments",   []) or [],
        "spy_used":             player.get("spy_used",        False),
        "spy_result":           player.get("spy_result",      ""),
        "poison_target":        player.get("poison_target"),
        "has_extra_kill":       player.get("has_extra_kill",  False),
        "extra_kill_target":    player.get("extra_kill_target"),
        "is_quarantined":       player.get("is_quarantined",  False),
        "known_killer":         known_killer,
        "is_exiled":            player.get("is_exiled",       False),
        "is_dead":              is_currently_dead,
        "voted_for":            player["voted_for"],
        "available_clues":      clues_res.data,
        "notebook":             notebook,
        "killers_count":        killers_count,
        "accomplice_count":     accomplice_count,
        "reveal_data":          reveal_data,
    }


# ── Player: Elimination ───────────────────────────────────────────────────────

@app.post("/player/eliminate/{killer_access_key}")
async def eliminate_player(killer_access_key: str, target_character: str):
    from fastapi import HTTPException
    killer = supabase.table("players").select("*").eq("access_key", killer_access_key).execute()
    if not killer.data or not killer.data[0]["is_killer"]:
        raise HTTPException(status_code=403, detail="Unauthorized.")
    game_id    = killer.data[0]["game_id"]
    next_round = supabase.table("games").select("current_round").eq(
        "id", game_id).execute().data[0]["current_round"] + 1
    supabase.table("players").update({"is_dead": False, "death_round": 99}).eq(
        "game_id", game_id).eq("death_round", next_round).execute()
    supabase.table("players").update({"is_dead": True, "death_round": next_round}).eq(
        "game_id", game_id).eq("character_name", target_character).execute()
    return {"message": f"Target locked: {target_character}. They drop dead at Round {next_round}."}


# ── Player: Extra kill (crisis bonus) ────────────────────────────────────────

@app.post("/player/extra-kill/{access_key}")
async def extra_kill(access_key: str, target_character: str):
    from fastapi import HTTPException
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key.")
    p = player_res.data[0]
    if not p["is_killer"]:
        raise HTTPException(status_code=403, detail="Only the killer can use the extra kill.")
    if p.get("is_dead"):
        raise HTTPException(status_code=403, detail="Eliminated players cannot use abilities.")
    if not p.get("has_extra_kill"):
        raise HTTPException(status_code=403, detail="No crisis bonus available.")
    target = supabase.table("players").select("id").eq(
        "game_id", p["game_id"]).eq("character_name", target_character).eq("is_dead", False).execute()
    if not target.data:
        raise HTTPException(status_code=404, detail="Target not found or already eliminated.")
    supabase.table("players").update({"extra_kill_target": target_character}).eq(
        "access_key", access_key).execute()
    return {"message": f"Extra target locked: {target_character}. They will be eliminated when Round 3 begins."}


# ── Player: Ghost clue ────────────────────────────────────────────────────────

@app.post("/player/send-ghost-clue/{access_key}")
async def send_ghost_clue(access_key: str, target_character: str):
    from fastapi import HTTPException
    player = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player.data[0]["is_dead"]:
        raise HTTPException(status_code=403, detail="Only eliminated players can send ghost clues.")
    supabase.table("players").update({"ghost_clue_recipient": target_character}).eq(
        "access_key", access_key).execute()
    return {"message": f"Ghost clue sent to {target_character}."}


# ── Player: Notes ─────────────────────────────────────────────────────────────

@app.post("/player/notes/{access_key}")
async def update_notes(access_key: str, target_character: str, status: str, note_text: str):
    player = supabase.table("players").select("id, game_id").eq("access_key", access_key).execute()
    supabase.table("player_notes").upsert({
        "game_id":          player.data[0]["game_id"],
        "owner_player_id":  player.data[0]["id"],
        "target_character": target_character,
        "status":           status,
        "note_text":        note_text,
    }, on_conflict="owner_player_id, target_character").execute()
    return {"message": "Note saved"}


# ── Player: Poison ────────────────────────────────────────────────────────────

@app.post("/player/poison/{access_key}")
async def poison_player(access_key: str, target_character: str):
    from fastapi import HTTPException
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key.")
    p = player_res.data[0]
    if not p.get("is_poisoner"):
        raise HTTPException(status_code=403, detail="Only the Poisoner can use this ability.")
    if p.get("is_dead"):
        raise HTTPException(status_code=403, detail="Eliminated players cannot use abilities.")
    target = supabase.table("players").select("id").eq(
        "game_id", p["game_id"]).eq("character_name", target_character).execute()
    if not target.data:
        raise HTTPException(status_code=404, detail="Target not found.")
    supabase.table("players").update({"poison_target": target_character}).eq(
        "access_key", access_key).execute()
    return {"message": f"Poison locked in. {target_character}'s next clue will be corrupted on round release."}


# ── Player: Exile vote ────────────────────────────────────────────────────────

@app.post("/player/exile-nominate/{access_key}")
async def exile_nominate(access_key: str, target_character: str):
    from fastapi import HTTPException
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key.")
    p = player_res.data[0]
    if p.get("is_dead"):
        raise HTTPException(status_code=403, detail="Eliminated players cannot nominate.")
    game = supabase.table("games").select("current_round").eq("id", p["game_id"]).execute().data[0]
    if game["current_round"] != 2:
        raise HTTPException(status_code=400, detail="Exile nominations are only allowed during Round 2.")
    supabase.table("exile_votes").upsert({
        "game_id":          p["game_id"],
        "voter_player_id":  p["id"],
        "target_character": target_character,
    }, on_conflict="game_id, voter_player_id").execute()
    all_alive   = supabase.table("players").select("id").eq("game_id", p["game_id"]).eq("is_dead", False).execute()
    exile_votes = supabase.table("exile_votes").select("target_character").eq(
        "game_id", p["game_id"]).eq("target_character", target_character).execute()
    needed = max(1, len(all_alive.data) / 2.0)
    exiled = len(exile_votes.data) >= needed
    if exiled:
        supabase.table("players").update({
            "is_dead": True, "death_round": game["current_round"], "is_exiled": True
        }).eq("game_id", p["game_id"]).eq("character_name", target_character).execute()
        return {"message": f"{target_character} has been exiled!", "exiled": True, "target": target_character}
    return {"message": f"Vote cast. {len(exile_votes.data)}/{int(needed)+1} needed.", "exiled": False}


@app.get("/player/exile-status/{game_id}")
async def exile_status(game_id: str):
    votes = supabase.table("exile_votes").select("target_character").eq("game_id", game_id).execute()
    tally: dict = {}
    for v in votes.data: tally[v["target_character"]] = tally.get(v["target_character"], 0) + 1
    alive_count = supabase.table("players").select("id", count="exact").eq(
        "game_id", game_id).eq("is_dead", False).execute().count or 1
    return {"tally": tally, "alive_count": alive_count, "needed": max(1, alive_count / 2.0)}


# ── Player: Spy ───────────────────────────────────────────────────────────────

@app.post("/player/send-memory/{access_key}")
async def send_memory_fragment(access_key: str, fragment: str):
    from fastapi import HTTPException
    player_res = supabase.table("players").select("game_id, is_accomplice, is_poisoner").eq(
        "access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key.")
    p = player_res.data[0]
    if not p.get("is_accomplice") and not p.get("is_poisoner"):
        raise HTTPException(status_code=403, detail="Only accomplices can send memory fragments.")
    game = supabase.table("games").select("current_round, is_amnesia_game").eq(
        "id", p["game_id"]).execute().data[0]
    if not game.get("is_amnesia_game"):
        raise HTTPException(status_code=400, detail="Not an amnesia game.")
    if game["current_round"] != 1:
        raise HTTPException(status_code=400, detail="Memory fragments can only be sent during Round 1.")
    killer = supabase.table("players").select("id, memory_fragments").eq(
        "game_id", p["game_id"]).eq("is_killer", True).execute()
    if not killer.data:
        raise HTTPException(status_code=404, detail="Killer not found.")
    current = killer.data[0].get("memory_fragments") or []
    if len(current) >= 3:
        raise HTTPException(status_code=400, detail="Maximum 3 memory fragments already sent.")
    updated = current + [fragment]
    supabase.table("players").update({"memory_fragments": updated}).eq(
        "id", killer.data[0]["id"]).execute()
    return {"message": f"Memory fragment delivered. {len(updated)}/3 sent."}


@app.post("/player/spy/{access_key}")
async def spy_peek(access_key: str, target_character: str):
    from fastapi import HTTPException
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key.")
    p = player_res.data[0]
    if not p.get("is_spy"):    raise HTTPException(status_code=403, detail="Only the Spy can use this ability.")
    if p.get("spy_used"):      raise HTTPException(status_code=400, detail="Spy ability already used.")
    if p.get("is_dead"):       raise HTTPException(status_code=403, detail="Eliminated players cannot use abilities.")
    t = supabase.table("players").select(
        "character_name, is_killer, is_accomplice, is_poisoner, is_investigator, "
        "is_drunk, is_paranoid, is_fool, is_jester, is_recluse"
    ).eq("game_id", p["game_id"]).eq("character_name", target_character).execute()
    if not t.data: raise HTTPException(status_code=404, detail="Target not found.")
    td = t.data[0]
    if   td["is_killer"]:              role = "Killer"
    elif td.get("is_recluse"):         role = "Killer"          # Recluse registers as Killer to Spy
    elif td.get("is_poisoner"):        role = "Poisoner (Accomplice)"
    elif td["is_accomplice"]:          role = "Accomplice"
    elif td.get("is_investigator"):    role = "Investigator"
    elif td.get("is_drunk"):           role = "Drunk"
    elif td.get("is_paranoid"):        role = "Paranoid"
    elif td.get("is_fool"):            role = "Fool (Innocent)"
    elif td.get("is_jester"):          role = "Jester"
    else:                              role = "Innocent"
    supabase.table("players").update({
        "spy_used":   True,
        "spy_result": f"{target_character} is: {role}"
    }).eq("access_key", access_key).execute()
    return {"message": "Intelligence gathered.", "target": target_character, "role": role}


# ── Player: Crisis vote ───────────────────────────────────────────────────────

@app.post("/player/crisis-vote/{access_key}")
async def crisis_vote(access_key: str, vote: str):
    from fastapi import HTTPException
    if vote not in ("safe", "dangerous"):
        raise HTTPException(status_code=400, detail="Vote must be 'safe' or 'dangerous'.")
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key.")
    p = player_res.data[0]
    if p.get("is_dead"):
        raise HTTPException(status_code=403, detail="Eliminated players cannot vote on the dilemma.")
    supabase.table("crisis_votes").upsert({
        "game_id":   p["game_id"],
        "player_id": p["id"],
        "vote":      vote,
    }, on_conflict="game_id, player_id").execute()
    all_votes = supabase.table("crisis_votes").select("vote").eq("game_id", p["game_id"]).execute()
    tally     = {"safe": 0, "dangerous": 0}
    for v in all_votes.data: tally[v["vote"]] = tally.get(v["vote"], 0) + 1
    alive = supabase.table("players").select("id", count="exact").eq(
        "game_id", p["game_id"]).eq("is_dead", False).execute().count or 1
    return {"message": f"Vote cast: {vote}", "tally": tally,
            "total_alive": alive, "total_voted": sum(tally.values())}


# ── Player: Final vote ────────────────────────────────────────────────────────

@app.post("/player/vote/{access_key}")
async def cast_vote(access_key: str, suspect: str):
    from fastapi import HTTPException
    player = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if player.data[0]["is_dead"]:
        raise HTTPException(status_code=403, detail="Eliminated players cannot vote.")
    if player.data[0].get("is_quarantined"):
        raise HTTPException(status_code=403, detail="You are quarantined and cannot cast a vote.")
    game_id = player.data[0]["game_id"]
    target  = supabase.table("players").select("is_dead").eq(
        "game_id", game_id).eq("character_name", suspect).execute()
    if target.data and target.data[0]["is_dead"]:
        raise HTTPException(status_code=400, detail="Cannot vote for an eliminated player.")
    supabase.table("players").update({"voted_for": suspect}).eq("access_key", access_key).execute()
    return {"message": "Vote locked in!"}
