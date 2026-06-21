from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from supabase import create_client, Client
from google import genai
from google.genai import types
import random
import string
import json
import os
from dotenv import load_dotenv

load_dotenv()
gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL = "gemini-2.5-flash-lite"

app = FastAPI()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
app.mount("/static", StaticFiles(directory="static"), name="static")

def verify_host(x_admin_token: str = Header(...)):
    if x_admin_token != os.getenv("HOST_ADMIN_PASSWORD"):
        raise HTTPException(status_code=401, detail="Unauthorized")

def generate_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ── Static routes ─────────────────────────────────────────────────────────────

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
        "has_drunk, has_investigator, has_poisoner, has_paranoid"
    ).order("created_at", desc=True).execute()
    return {"templates": templates.data}


# ── Admin: Spawn from template (no AI call) ───────────────────────────────────

@app.post("/admin/create-from-template/{template_id}", dependencies=[Depends(verify_host)])
async def create_from_template(request: Request, template_id: str):
    template_res = supabase.table("game_templates").select("*").eq("id", template_id).execute()
    if not template_res.data:
        raise HTTPException(status_code=404, detail="Template not found")
    data = template_res.data[0]

    game_insert = supabase.table("games").insert({
        "theme": data["theme_title"], "theme_title": data["theme_title"],
        "short_description": data["short_description"],
        "master_story": json.dumps(data["master_story"])
    }).execute()
    game_id = game_insert.data[0]["id"]

    for char in data["characters"]:
        player_id = supabase.table("players").insert({
            "game_id": game_id, "access_key": generate_key(),
            "character_name": char["name"],
            "role_description": char["role_description"],
            "public_summary": char["public_summary"],
            "ghost_clue": char.get("ghost_clue") or "The spirits are silent... I took my secrets to the grave.",
            "is_killer":       char.get("is_killer", False),
            "is_accomplice":   char.get("is_accomplice", False),
            "is_investigator": char.get("is_investigator", False),
            "is_drunk":        char.get("is_drunk", False),
            "is_poisoner":     char.get("is_poisoner", False),
            "is_paranoid":     char.get("is_paranoid", False),
        }).execute().data[0]["id"]

        # Each clue has true_content + poisoned_content pre-baked
        clues_to_insert = [{
            "game_id": game_id,
            "player_id": player_id,
            "round_number": c["round"],
            "content": c.get("true_content") or c.get("content", ""),
            "poisoned_content": c.get("poisoned_content", ""),
            "is_poisoned": False,
            "is_released": False,
        } for c in char["clues"]]
        supabase.table("clues").insert(clues_to_insert).execute()

    return {
        "message": "Game spawned from template!",
        "game_id": game_id,
        "room_url": f"{request.base_url}room/{game_id}"
    }


# ── Admin: Generate new game (1 Gemini call) ──────────────────────────────────

@app.post("/admin/create-game", dependencies=[Depends(verify_host)])
async def create_game(
    request: Request, theme: str, player_count: int,
    accomplice_count: int = 0, include_drunk: bool = False,
    include_investigator: bool = False, include_poisoner: bool = False,
    include_paranoid: bool = False
):
    accomplice_instruction = f"EXACTLY {accomplice_count} character(s) MUST have 'is_accomplice': true."
    drunk_instruction      = (
        "EXACTLY ONE innocent character MUST have 'is_drunk': true. "
        "ALL of their clues (both true_content and poisoned_content) must be completely FALSE."
    ) if include_drunk else "NO characters may have 'is_drunk': true."
    investigator_instruction = (
        "EXACTLY ONE innocent character MUST have 'is_investigator': true. "
        "Their Round 2 true_content MUST say 'Either [Killer Name] or [Innocent Name] is guilty.'"
    ) if include_investigator else "NO characters may have 'is_investigator': true."
    poisoner_instruction = (
        "ONE accomplice MUST have 'is_poisoner': true. "
        "In their role_description add: '• Poisoner Ability: Each round you may secretly corrupt one player\\'s evidence.'"
    ) if include_poisoner and accomplice_count > 0 else "NO characters may have 'is_poisoner': true."
    paranoid_instruction = (
        "EXACTLY ONE innocent character MUST have 'is_paranoid': true. "
        "ALL their clues must point suspiciously at a specific OTHER innocent player, never the killer. "
        "In their role_description add: '• Paranoid Instinct: Your gut screams that [name a specific innocent] is the killer.'"
    ) if include_paranoid else "NO characters may have 'is_paranoid': true."

    prompt = f"""
    Create a highly interactive social deduction murder mystery for {player_count} players. Theme: {theme}.

    --- STRICT RULES ---
    1. NO PLACEHOLDERS. Fill every detail. Never write "[Name]", "[Killer]", "[Motive]" etc.
    2. TOTAL CHARACTERS: You MUST generate EXACTLY {player_count} characters — no more, no fewer.
       Special roles (drunk, investigator, paranoid, poisoner) are assigned TO existing characters
       within the {player_count} total. They do NOT add extra characters.
    3. ROLE COUNTS:
       - EXACTLY 1 character must have "is_killer": true.
       - {accomplice_instruction}
       - {drunk_instruction}
       - {investigator_instruction}
       - {poisoner_instruction}
       - {paranoid_instruction}
    3. CLUE RULES — every innocent character needs TWO versions of each clue:
       - "true_content": a genuine observation about ANOTHER player (incriminating toward the real killer).
       - "poisoned_content": a plausible-sounding BUT FALSE version that redirects suspicion toward an INNOCENT player instead.
       Killer/Accomplice clues: both true_content and poisoned_content are disinformation (fake alibis / framing innocents).

    Return ONLY a JSON object with this exact structure:
    {{
        "theme_title": "A catchy 2-4 word title",
        "short_description": "A dark atmospheric 2-sentence description of the setting and tension.",
        "master_story": {{
            "background": "• Point 1\\n• Point 2",
            "the_murder": "• Point 1\\n• Point 2",
            "the_solution": "• Point 1\\n• Point 2",
            "public_clues": [
                {{"round": 2, "content": "A public piece of evidence revealed to ALL players at Round 2."}},
                {{"round": 3, "content": "A final public piece of evidence revealed to ALL players at Round 3."}}
            ]
        }},
        "characters": [
            {{
                "name": "Character Name",
                "public_summary": "1-sentence summary of what everyone knows about this person.",
                "role_description": "• Personality: (how to act)\\n• Connection: (to the victim)\\n• Dark Secret: (something they hide)",
                "is_killer": false, "is_accomplice": false, "is_investigator": false,
                "is_drunk": false, "is_poisoner": false, "is_paranoid": false,
                "ghost_clue": "A revealing clue only unlocked after this character is murdered.",
                "clues": [
                    {{
                        "round": 2,
                        "true_content": "• The real clue — genuine observation pointing toward the killer.",
                        "poisoned_content": "• The corrupted version — plausible but false, points at an innocent."
                    }},
                    {{
                        "round": 3,
                        "true_content": "• Hard physical evidence about the killer.",
                        "poisoned_content": "• Fabricated physical evidence framing a different innocent."
                    }}
                ]
            }}
        ]
    }}
    """

    response  = gemini.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    game_data = json.loads(response.text)

    # 1. Save template
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
        "master_story":      game_data["master_story"],
        "characters":        game_data["characters"],
    }).execute()

    # 2. Launch active game
    game_insert = supabase.table("games").insert({
        "theme":             theme,
        "theme_title":       game_data.get("theme_title", f"Mystery: {theme}"),
        "short_description": game_data.get("short_description", "Trust no one."),
        "master_story":      json.dumps(game_data["master_story"]),
    }).execute()
    game_id = game_insert.data[0]["id"]

    for char in game_data["characters"]:
        player_id = supabase.table("players").insert({
            "game_id":         game_id,
            "access_key":      generate_key(),
            "character_name":  char["name"],
            "role_description": char["role_description"],
            "public_summary":  char["public_summary"],
            "ghost_clue":      char.get("ghost_clue") or "The spirits are silent... I took my secrets to the grave.",
            "is_killer":       char.get("is_killer", False),
            "is_accomplice":   char.get("is_accomplice", False),
            "is_investigator": char.get("is_investigator", False),
            "is_drunk":        char.get("is_drunk", False),
            "is_poisoner":     char.get("is_poisoner", False),
            "is_paranoid":     char.get("is_paranoid", False),
        }).execute().data[0]["id"]

        clues_to_insert = [{
            "game_id":          game_id,
            "player_id":        player_id,
            "round_number":     c["round"],
            "content":          c["true_content"],
            "poisoned_content": c.get("poisoned_content", ""),
            "is_poisoned":      False,
            "is_released":      False,
        } for c in char["clues"]]
        supabase.table("clues").insert(clues_to_insert).execute()

    return {
        "message":  "Game generated!",
        "game_id":  game_id,
        "room_url": f"{request.base_url}room/{game_id}"
    }


# ── Admin: Game state (god view) ──────────────────────────────────────────────

@app.get("/admin/game/{game_id}", dependencies=[Depends(verify_host)])
async def get_game_state(game_id: str):
    game    = supabase.table("games").select("*").eq("id", game_id).execute()
    players = supabase.table("players").select("*").eq("game_id", game_id).execute()
    return {"game": game.data[0], "players": players.data}


# ── Admin: Release round — applies poison swap, no Gemini call ────────────────

@app.post("/admin/release-round/{game_id}/{round_num}", dependencies=[Depends(verify_host)])
async def release_clues(game_id: str, round_num: int):
    supabase.table("games").update({
        "current_round": round_num, "status": "started"
    }).eq("id", game_id).execute()

    if round_num > 1:
        # Check if poisoner has a target locked for this round
        poisoner_res = supabase.table("players").select("poison_target").eq(
            "game_id", game_id).eq("is_poisoner", True).execute()

        if poisoner_res.data and poisoner_res.data[0].get("poison_target"):
            target_name = poisoner_res.data[0]["poison_target"]
            target_res  = supabase.table("players").select("id").eq(
                "game_id", game_id).eq("character_name", target_name).execute()

            if target_res.data:
                target_id = target_res.data[0]["id"]
                # Fetch this round's clue for the target
                clue_res = supabase.table("clues").select("id, poisoned_content").eq(
                    "player_id", target_id).eq("round_number", round_num).execute()

                if clue_res.data and clue_res.data[0].get("poisoned_content"):
                    clue = clue_res.data[0]
                    # Swap content → poisoned_content, flag as poisoned
                    supabase.table("clues").update({
                        "content":    clue["poisoned_content"],
                        "is_poisoned": True,
                    }).eq("id", clue["id"]).execute()

            # Reset poison_target — poisoner must re-select each round
            supabase.table("players").update({"poison_target": None}).eq(
                "game_id", game_id).eq("is_poisoner", True).execute()

        # Release all clues for this round
        supabase.table("clues").update({"is_released": True}).eq(
            "game_id", game_id).eq("round_number", round_num).execute()

    return {"message": f"Round {round_num} active!"}


# ── Player: Poison target selection ──────────────────────────────────────────

@app.post("/player/poison/{access_key}")
async def poison_player(access_key: str, target_character: str):
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
    return {"message": f"Poison locked in. {target_character}'s next clue will be corrupted when the round releases."}


# ── Admin: End game — 1 Gemini call for recap ─────────────────────────────────

@app.post("/admin/end-game/{game_id}", dependencies=[Depends(verify_host)])
async def end_game(game_id: str):
    game_res    = supabase.table("games").select("theme_title, master_story").eq("id", game_id).execute()
    all_players = supabase.table("players").select("*").eq("game_id", game_id).execute()

    game_row    = game_res.data[0]
    theme_title = game_row.get("theme_title", "the manor")
    try:    master_story = json.loads(game_row["master_story"])
    except: master_story = {}

    killer     = next((p for p in all_players.data if p["is_killer"]), None)
    accomplices = [p for p in all_players.data if p.get("is_accomplice") and not p["is_killer"]]
    dead        = [p for p in all_players.data if p.get("is_dead")]
    poisoner    = next((p for p in all_players.data if p.get("is_poisoner")), None)
    paranoid    = next((p for p in all_players.data if p.get("is_paranoid")), None)

    killer_name   = killer["character_name"] if killer else "Unknown"
    killer_player = killer["claimed_by_user"] if killer else "?"

    # Compute outcome
    alive_innocents = [p for p in all_players.data if not p["is_killer"] and not p.get("is_accomplice") and not p.get("is_dead")]
    correct_votes   = [p for p in alive_innocents if p.get("voted_for") == killer_name]
    killer_caught   = len(correct_votes) >= max(1, len(alive_innocents) / 2.0)

    # Build rich context for recap
    deaths_text     = ", ".join(f"{p['character_name']}" for p in dead) or "nobody"
    accomplice_text = ", ".join(f"{p['character_name']}" for p in accomplices) or "none"
    poisoner_text   = f"{poisoner['character_name']} secretly corrupted evidence each round" if poisoner else "no poisoner in this game"
    paranoid_text   = f"{paranoid['character_name']} was convinced the wrong person was guilty" if paranoid else "no paranoid in this game"
    outcome_text    = "The killer was caught and justice was served" if killer_caught else f"{killer_name} got away with murder"

    recap_prompt = f"""
    Write a short noir-style post-game story recap for a murder mystery called "{theme_title}".
    Write exactly 1 paragraph. Be atmospheric and dramatic. Use character names only with player names in parentheses.
    Do not use markdown, headers, or bullet points. Plain prose only.

    Facts to weave in naturally:
    - The killer was {killer_name}
    - Accomplices: {accomplice_text}
    - {poisoner_text}
    - {paranoid_text}
    - Characters who died during the game: {deaths_text}
    - Outcome: {outcome_text}
    - The true story: {master_story.get("the_solution", "")}

    Write it as the closing narration of a noir film. Make it feel complete and satisfying.
    """

    recap_text = ""
    try:
        recap_resp = gemini.models.generate_content(
            model=GEMINI_MODEL,
            contents=recap_prompt,
        )
        recap_text = recap_resp.text.strip()
    except Exception:
        recap_text = (
            f"The night of secrets finally came to an end at {theme_title}. "
            f"{killer_name} had woven an intricate web of lies — and "
            f"{'justice caught up with them at last' if killer_caught else 'walked free into the darkness, leaving only questions behind'}."
        )

    supabase.table("games").update({
        "status": "finished",
        "recap":  recap_text,
    }).eq("id", game_id).execute()

    return {"message": "Game ended! Results and story now visible on all player devices."}


# ── Player: Join room ─────────────────────────────────────────────────────────

@app.post("/api/room/{game_id}/join")
async def join_room(game_id: str, player_name: str):
    game = supabase.table("games").select("status").eq("id", game_id).execute()
    if not game.data:
        raise HTTPException(status_code=404, detail="Game not found.")
    if game.data[0]["status"] != "waiting":
        raise HTTPException(status_code=400, detail="Game has already started.")

    unclaimed = supabase.table("players").select("*").eq("game_id", game_id).is_("claimed_by_user", "null").execute()
    if not unclaimed.data:
        raise HTTPException(status_code=400, detail="Room is full.")

    character = random.choice(unclaimed.data)
    supabase.table("players").update({"claimed_by_user": player_name}).eq("id", character["id"]).execute()
    return {"access_key": character["access_key"], "character_name": character["character_name"]}


# ── Player: Dashboard ─────────────────────────────────────────────────────────

@app.get("/player/dashboard/{access_key}")
async def get_player_dashboard(access_key: str):
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key")

    player  = player_res.data[0]
    game_id = player["game_id"]

    game_res = supabase.table("games").select(
        "current_round, status, master_story, theme_title, short_description, recap"
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

    # Only serve non-poisoned released clues to the player
    # (poisoned clues have had their content already swapped in release-round,
    #  so the player just sees "content" — they never know it was tampered with)
    clues_res = supabase.table("clues").select(
        "round_number, content, is_poisoned"
    ).eq("player_id", player["id"]).eq("is_released", True).execute()

    all_players = supabase.table("players").select(
        "id, character_name, public_summary, claimed_by_user, is_dead, death_round, "
        "is_killer, is_accomplice, is_investigator, is_drunk, is_poisoner, is_paranoid, voted_for, poison_target"
    ).eq("game_id", game_id).execute()

    received_ghost_req = supabase.table("players").select(
        "character_name, ghost_clue"
    ).eq("game_id", game_id).eq("ghost_clue_recipient", player["character_name"]).execute()
    received_ghost_clues = received_ghost_req.data

    killers_count   = sum(1 for p in all_players.data if p["is_killer"])
    accomplice_count = sum(1 for p in all_players.data if p["is_accomplice"])

    # Accomplice and poisoner both know the killer
    known_killer = None
    if player.get("is_accomplice") or player.get("is_poisoner"):
        known_killer = next((p["character_name"] for p in all_players.data if p["is_killer"]), None)

    my_notes   = supabase.table("player_notes").select("*").eq("owner_player_id", player["id"]).execute()
    notes_dict = {n["target_character"]: n for n in my_notes.data}

    notebook = []
    for p in all_players.data:
        if p["id"] != player["id"]:
            notebook.append({
                "character_name":   p["character_name"],
                "claimed_by":       p["claimed_by_user"],
                "public_summary":   p["public_summary"],
                "is_publicly_dead": p["is_dead"] and current_round >= p["death_round"],
                "my_note":          notes_dict.get(p["character_name"], {"status": "neutral", "note_text": ""}),
            })

    reveal_data = None
    if game_status == "finished":
        killer_name     = next((p["character_name"] for p in all_players.data if p["is_killer"]), "Unknown")
        votes           = []
        correct_votes   = 0
        alive_innocents = 0

        for p in all_players.data:
            is_innocent = not p["is_killer"] and not p["is_accomplice"]
            if is_innocent and not p["is_dead"]: alive_innocents += 1
            if p["voted_for"]:
                is_correct = (p["voted_for"] == killer_name)
                if is_correct and is_innocent and not p["is_dead"]: correct_votes += 1
                votes.append({
                    "voter":       p["character_name"],
                    "player_name": p["claimed_by_user"],
                    "target":      p["voted_for"],
                    "is_correct":  is_correct,
                })

        killer_caught  = correct_votes >= max(1, alive_innocents / 2.0)
        true_identities = [{
            "name":          p["character_name"],
            "player":        p["claimed_by_user"],
            "is_killer":     p["is_killer"],
            "is_accomplice": p["is_accomplice"],
            "is_poisoner":   p.get("is_poisoner", False),
            "is_investigator": p.get("is_investigator", False),
            "is_drunk":      p.get("is_drunk", False),
            "is_paranoid":   p.get("is_paranoid", False),
        } for p in all_players.data]

        reveal_data = {
            "master_story":    master_story,
            "true_identities": true_identities,
            "votes":           votes,
            "killer_caught":   killer_caught,
            "recap":           recap,
        }

    return {
        "game_status":      game_status,
        "current_round":    current_round,
        "character_name":   player["character_name"],
        "theme_title":      theme_title,
        "short_description": short_desc,
        "active_story": {
            "background":   master_story.get("background", ""),
            "the_murder":   master_story.get("the_murder", ""),
            "public_clues": master_story.get("public_clues", []),
        },
        "role_description":    player["role_description"],
        "ghost_clue":          player["ghost_clue"],
        "ghost_clue_recipient": player["ghost_clue_recipient"],
        "received_ghost_clues": received_ghost_clues,
        "is_killer":       player["is_killer"],
        "is_accomplice":   player["is_accomplice"],
        "is_investigator": player.get("is_investigator", False),
        "is_drunk":        player.get("is_drunk", False),
        "is_poisoner":     player.get("is_poisoner", False),
        "is_paranoid":     player.get("is_paranoid", False),
        "poison_target":   player.get("poison_target"),
        "known_killer":    known_killer,
        "is_dead":         is_currently_dead,
        "voted_for":       player["voted_for"],
        "available_clues": clues_res.data,
        "notebook":        notebook,
        "killers_count":   killers_count,
        "accomplice_count": accomplice_count,
        "reveal_data":     reveal_data,
    }


# ── Player: Elimination ───────────────────────────────────────────────────────

@app.post("/player/eliminate/{killer_access_key}")
async def eliminate_player(killer_access_key: str, target_character: str):
    killer = supabase.table("players").select("*").eq("access_key", killer_access_key).execute()
    if not killer.data or not killer.data[0]["is_killer"]:
        raise HTTPException(status_code=403, detail="Unauthorized.")

    game_id    = killer.data[0]["game_id"]
    game       = supabase.table("games").select("current_round").eq("id", game_id).execute()
    next_round = game.data[0]["current_round"] + 1

    supabase.table("players").update({"is_dead": False, "death_round": 99}).eq(
        "game_id", game_id).eq("death_round", next_round).execute()
    supabase.table("players").update({"is_dead": True, "death_round": next_round}).eq(
        "game_id", game_id).eq("character_name", target_character).execute()
    return {"message": f"Target locked: {target_character}. They will drop dead at the start of Round {next_round}."}


# ── Player: Ghost clue ────────────────────────────────────────────────────────

@app.post("/player/send-ghost-clue/{access_key}")
async def send_ghost_clue(access_key: str, target_character: str):
    player = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player.data[0]["is_dead"]:
        raise HTTPException(status_code=403, detail="Only eliminated players can send ghost clues.")
    supabase.table("players").update({"ghost_clue_recipient": target_character}).eq(
        "access_key", access_key).execute()
    return {"message": f"Message sent to {target_character} from the beyond."}


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


# ── Player: Vote ──────────────────────────────────────────────────────────────

@app.post("/player/vote/{access_key}")
async def cast_vote(access_key: str, suspect: str):
    player = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if player.data[0]["is_dead"]:
        raise HTTPException(status_code=403, detail="Eliminated players cannot vote.")

    game_id = player.data[0]["game_id"]
    target  = supabase.table("players").select("is_dead").eq(
        "game_id", game_id).eq("character_name", suspect).execute()
    if target.data and target.data[0]["is_dead"]:
        raise HTTPException(status_code=400, detail="Cannot vote for an eliminated player.")

    supabase.table("players").update({"voted_for": suspect}).eq("access_key", access_key).execute()
    return {"message": "Vote locked in!"}
