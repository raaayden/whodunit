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
        "has_drunk, has_investigator, has_poisoner, has_paranoid, has_spy, has_fool"
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
    include_paranoid: bool = False, include_spy: bool = False, include_fool: bool = False
):
    accomplice_instruction   = f"EXACTLY {accomplice_count} character(s) MUST have 'is_accomplice': true."
    drunk_instruction        = (
        "EXACTLY ONE innocent character MUST have 'is_drunk': true. "
        "ALL of their clues (both true_content and poisoned_content) must be completely FALSE."
    ) if include_drunk else "NO characters may have 'is_drunk': true."
    investigator_instruction = (
        "EXACTLY ONE innocent character MUST have 'is_investigator': true. "
        "Their Round 3 true_content MUST name two specific suspects: "
        "'Either [Killer Name] or [Innocent Name] is guilty.' Delivered at the final round."
    ) if include_investigator else "NO characters may have 'is_investigator': true."
    poisoner_instruction     = (
        f"One of the {accomplice_count} accomplice character(s) MUST have both 'is_accomplice': true AND "
        "'is_poisoner': true simultaneously on the SAME character object. "
        "This is not a new character — it is an existing accomplice who also has the poisoner role. "
        "In their role_description add: '• Poisoner Ability: Each round you may secretly corrupt one player\\'s evidence on your device.'"
    ) if include_poisoner and accomplice_count > 0 else "NO characters may have 'is_poisoner': true."
    paranoid_instruction     = (
        "EXACTLY ONE innocent character MUST have 'is_paranoid': true. "
        "ALL their clues must point suspiciously at a specific OTHER innocent player, never the killer. "
        "In their role_description add: '• Paranoid Instinct: Your gut tells you that [name a specific innocent] is the killer — and it never lies.'"
    ) if include_paranoid else "NO characters may have 'is_paranoid': true."
    spy_instruction          = (
        "EXACTLY ONE innocent character MUST have 'is_spy': true. "
        "In their role_description add: '• Spy Ability: Once per game you may secretly learn the true role of one other player. Use it wisely.'"
    ) if include_spy else "NO characters may have 'is_spy': true."
    fool_instruction         = (
        "EXACTLY ONE innocent character MUST have 'is_fool': true. "
        "Write their role_description exactly like a killer — believable motive and a plan — "
        "but set 'is_killer': false and 'is_fool': true. Their clues are normal innocent clues. "
        "Only valid for 10+ player games."
    ) if include_fool and player_count >= 10 else "NO characters may have 'is_fool': true."

    prompt = f"""
    Create a highly interactive social deduction murder mystery for {player_count} players. Theme: {theme}.

    --- STRICT RULES ---
    1. NO PLACEHOLDERS. Fill every detail. Never write "[Name]", "[Killer]", "[Motive]" etc.
    2. TOTAL CHARACTERS: The "characters" array MUST contain EXACTLY {player_count} objects.
       Count them before returning. {player_count} characters. Not {player_count + 1}. Not {player_count + 2}. Exactly {player_count}.
       Special roles (drunk, investigator, paranoid, poisoner, spy, fool) are LABELS applied to
       characters that already exist in the list. They are NOT new characters. Do not add extras.
    3. ROLE COUNTS:
       - EXACTLY 1 character must have "is_killer": true.
       - {accomplice_instruction}
       - {drunk_instruction}
       - {investigator_instruction}
       - {poisoner_instruction}
       - {paranoid_instruction}
       - {spy_instruction}
       - {fool_instruction}
    4. CLUE RULES — read every word carefully:
       a) ALL clues must be written as first-person observations about a THIRD PARTY — never about oneself.
       b) INNOCENT clues (true_content): subtle and indirect. Do NOT say "implicates the killer" or name the
          killer directly. Instead describe a suspicious behaviour, overheard conversation, or physical detail
          about another character that a smart player could piece together over multiple rounds.
          Round 2 clues = something seen or heard. Round 3 clues = something physical found.
       c) INNOCENT clues (poisoned_content): equally indirect, equally plausible, but pointing at a DIFFERENT
          innocent character. Should read identically in tone to the true_content — just about someone else.
       d) KILLER and ACCOMPLICE clues: write a convincing false alibi or an observation that subtly frames
          an innocent person. Should sound exactly like an innocent's clue in tone and style.
       e) NEVER use the words "killer", "accomplice", "murderer", "guilty", or "evidence" inside a clue.
          Clues are observations and discoveries, not conclusions.
       f) POISONER: if is_poisoner is true on an accomplice, that character MUST be marked with both
          "is_accomplice": true AND "is_poisoner": true. Do not create a separate character for the poisoner.
    5. PUBLIC CLUE: Only ONE public clue at Round 3 (the final round only). No Round 2 public clue.
       Make it dramatic — physical evidence or a witnessed event that narrows down the killer.

    Return ONLY a JSON object with this exact structure:
    {{
        "theme_title": "A catchy 2-4 word title",
        "short_description": "A dark atmospheric 2-sentence description of the setting and tension.",
        "master_story": {{
            "background": "• Point 1\n• Point 2",
            "the_murder": "• Point 1\n• Point 2",
            "the_solution": "• Point 1\n• Point 2",
            "public_clues": [
                {{"round": 3, "content": "A single dramatic public clue revealed to ALL players at Round 3."}}
            ]
        }},
        "characters": [
            {{
                "name": "Character Name",
                "public_summary": "1-sentence summary of what everyone knows about this person.",
                "role_description": "• Personality: (how to act)\n• Connection: (to the victim)\n• Dark Secret: (something they hide)",
                "is_killer": false, "is_accomplice": false, "is_investigator": false,
                "is_drunk": false, "is_poisoner": false, "is_paranoid": false,
                "is_spy": false, "is_fool": false,
                "ghost_clue": "A revealing clue about the killer or accomplice, only unlocked after this character is murdered.",
                "clues": [
                    {{
                        "round": 2,
                        "true_content": "You noticed that [specific other character name] [concrete observable action pointing toward killer].",
                        "poisoned_content": "You noticed that [different innocent name] [false but plausible observable detail]."
                    }},
                    {{
                        "round": 3,
                        "true_content": "You found [specific physical evidence] that directly implicates [killer or accomplice name].",
                        "poisoned_content": "You found [fabricated evidence] that appears to implicate [innocent character name]."
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
        "has_spy":           include_spy,
        "has_fool":          include_fool,
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
            "is_spy":          char.get("is_spy", False),
            "is_fool":         char.get("is_fool", False),
            "is_jester":       char.get("is_jester", False),
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
    jester     = next((p for p in all_players.data if p.get("is_jester")), None)
    accomplices = [p for p in all_players.data if p.get("is_accomplice") and not p["is_killer"]]
    dead        = [p for p in all_players.data if p.get("is_dead")]
    poisoner    = next((p for p in all_players.data if p.get("is_poisoner")), None)
    paranoid    = next((p for p in all_players.data if p.get("is_paranoid")), None)
    spy         = next((p for p in all_players.data if p.get("is_spy")), None)
    fool        = next((p for p in all_players.data if p.get("is_fool")), None)

    # Jester wins if they received majority innocent votes
    jester_name    = jester["character_name"] if jester else None
    jester_votes   = sum(1 for p in all_players.data if p.get("voted_for") == jester_name) if jester_name else 0
    jester_won     = jester_name and jester_votes >= max(1, len([p for p in all_players.data if not p.get("is_dead")]) / 2.0)

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
    spy_text        = f"{spy['character_name']} was secretly gathering intelligence on other players" if spy else "no spy in this game"
    fool_text       = f"{fool['character_name']} believed themselves to be the killer but was completely innocent" if fool else "no fool in this game"
    jester_text     = f"{jester_name} was the Jester — they tricked everyone into voting for them!" if jester_won else ("no jester in this game" if not jester_name else f"{jester_name} was the Jester but failed to get voted out")
    outcome_text    = ("The Jester won — everyone voted for the wrong person!" if jester_won else ("The killer was caught and justice was served" if killer_caught else f"{killer_name} got away with murder"))

    recap_prompt = f"""
    Write a noir-style post-game story recap for a murder mystery called "{theme_title}".
    Write exactly 5 paragraphs of rich, atmospheric prose. Each paragraph should be 4-6 sentences.
    Use character names only, never player names. No markdown, headers, or bullet points.

    Structure it like this:
    - Paragraph 1: Set the scene. Describe the setting, the mood of the evening, and the discovery of the murder.
    - Paragraph 2: The web of suspicion. Who suspected whom, what red herrings confused the group, how the paranoid/drunk/fool (if present) stirred the pot.
    - Paragraph 3: Behind the scenes. What the killer and accomplices were really doing — their plan, their lies, how they almost got away with it.
    - Paragraph 4: The turning point. What evidence or moment shifted the tide — the ghost clue, the investigator's ping, the public announcement, or the exile vote.
    - Paragraph 5: The verdict. How the final vote went, whether justice was served or the killer escaped, and a closing line that feels like the last frame of a film.

    Facts to weave in naturally:
    - The killer was {killer_name}
    - Accomplices: {accomplice_text}
    - {poisoner_text}
    - {paranoid_text}
    - {spy_text}
    - {fool_text}
    - Characters who died during the game: {deaths_text}
    - Outcome: {outcome_text}
    - The true story: {master_story.get("the_solution", "")}

    Write it as the closing narration of a classic noir film. Be cinematic and specific — name characters, describe moments, make it feel like this particular game.
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
        "current_round, status, master_story, theme_title, short_description, recap, is_crisis_game, crisis_resolved, crisis_dangerous_won"
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
        "is_killer, is_accomplice, is_investigator, is_drunk, is_poisoner, is_paranoid, is_spy, is_fool, is_jester, voted_for, poison_target, spy_used, spy_result, is_exiled"
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
            "is_spy":        p.get("is_spy", False),
            "is_fool":       p.get("is_fool", False),
            "is_jester":     p.get("is_jester", False),
        } for p in all_players.data]

        # Jester win: majority voted for jester
        jester_char    = next((p["character_name"] for p in all_players.data if p.get("is_jester")), None)
        j_votes        = sum(1 for p in all_players.data if p.get("voted_for") == jester_char) if jester_char else 0
        jester_won_rv  = jester_char and j_votes >= max(1, alive_innocents / 2.0)
        reveal_data = {
            "master_story":    master_story,
            "true_identities": true_identities,
            "votes":           votes,
            "killer_caught":   killer_caught,
            "jester_won":      bool(jester_won_rv),
            "jester_name":     jester_char,
            "recap":           recap,
        }

    return {
        "game_status":      game_status,
        "current_round":    current_round,
        "character_name":   player["character_name"],
        "theme_title":      theme_title,
        "short_description": short_desc,
        "active_story": {
            "background":        master_story.get("background", ""),
            "the_murder":        master_story.get("the_murder", ""),
            "public_clues":      master_story.get("public_clues", []),
        },
        "is_crisis_game":      game_row.get("is_crisis_game", False),
        "crisis_resolved":     game_row.get("crisis_resolved", False),
        "crisis_dangerous_won": game_row.get("crisis_dangerous_won", False),
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
        "is_spy":          player.get("is_spy", False),
        "is_fool":         player.get("is_fool", False),
        "is_jester":       player.get("is_jester", False),
        "spy_used":        player.get("spy_used", False),
        "spy_result":      player.get("spy_result", ""),
        "poison_target":   player.get("poison_target"),
        "known_killer":    known_killer,
        "is_exiled":       player.get("is_exiled", False),
        "has_extra_kill":  player.get("has_extra_kill", False),
        "is_crisis_game":  game_row.get("is_crisis_game", False),
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



# ── Player: Exile vote ────────────────────────────────────────────────────────
# Players can propose and vote to exile someone mid-game (Round 2 only).
# If majority of alive players agree, target is exiled (publicly known, not a murder).

@app.post("/player/exile-nominate/{access_key}")
async def exile_nominate(access_key: str, target_character: str):
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key.")
    p = player_res.data[0]
    if p.get("is_dead"):
        raise HTTPException(status_code=403, detail="Eliminated players cannot nominate.")
    game_res = supabase.table("games").select("current_round, status").eq("id", p["game_id"]).execute()
    game     = game_res.data[0]
    if game["current_round"] != 2:
        raise HTTPException(status_code=400, detail="Exile nominations are only allowed during Round 2.")
    # Store nomination — one per player, overwritable
    supabase.table("exile_votes").upsert({
        "game_id":        p["game_id"],
        "voter_player_id": p["id"],
        "target_character": target_character,
    }, on_conflict="game_id, voter_player_id").execute()
    # Check if majority reached
    all_alive = supabase.table("players").select("id").eq("game_id", p["game_id"]).eq("is_dead", False).execute()
    exile_votes = supabase.table("exile_votes").select("target_character").eq("game_id", p["game_id"]).eq("target_character", target_character).execute()
    needed  = max(1, len(all_alive.data) / 2.0)
    exiled  = len(exile_votes.data) >= needed
    if exiled:
        # Mark target as exiled (dead, but via exile not murder)
        supabase.table("players").update({"is_dead": True, "death_round": game["current_round"], "is_exiled": True}).eq(
            "game_id", p["game_id"]).eq("character_name", target_character).execute()
        return {"message": f"{target_character} has been exiled by popular vote!", "exiled": True, "target": target_character}
    return {"message": f"Exile vote cast for {target_character}. {len(exile_votes.data)}/{int(needed)+1} votes needed.", "exiled": False}


@app.get("/player/exile-status/{game_id}")
async def exile_status(game_id: str):
    votes = supabase.table("exile_votes").select("target_character, voter_player_id").eq("game_id", game_id).execute()
    tally: dict = {}
    for v in votes.data:
        t = v["target_character"]
        tally[t] = tally.get(t, 0) + 1
    alive_count = supabase.table("players").select("id", count="exact").eq("game_id", game_id).eq("is_dead", False).execute().count or 1
    return {"tally": tally, "alive_count": alive_count, "needed": max(1, alive_count / 2.0)}


# ── Player: Spy — learn one player's role ────────────────────────────────────

@app.post("/player/spy/{access_key}")
async def spy_peek(access_key: str, target_character: str):
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key.")
    p = player_res.data[0]
    if not p.get("is_spy"):
        raise HTTPException(status_code=403, detail="Only the Spy can use this ability.")
    if p.get("spy_used"):
        raise HTTPException(status_code=400, detail="You have already used your Spy ability.")
    if p.get("is_dead"):
        raise HTTPException(status_code=403, detail="Eliminated players cannot use abilities.")
    target_res = supabase.table("players").select(
        "character_name, is_killer, is_accomplice, is_poisoner, is_investigator, is_drunk, is_paranoid, is_fool"
    ).eq("game_id", p["game_id"]).eq("character_name", target_character).execute()
    if not target_res.data:
        raise HTTPException(status_code=404, detail="Target not found.")
    t = target_res.data[0]
    # Determine role label
    if t["is_killer"]:         role = "Killer"
    elif t.get("is_poisoner"): role = "Poisoner (Accomplice)"
    elif t["is_accomplice"]:   role = "Accomplice"
    elif t.get("is_investigator"): role = "Investigator"
    elif t.get("is_drunk"):    role = "Drunk"
    elif t.get("is_paranoid"): role = "Paranoid"
    elif t.get("is_fool"):     role = "Fool (Innocent)"
    else:                      role = "Innocent"
    # Mark spy ability as used and store result
    supabase.table("players").update({
        "spy_used": True,
        "spy_result": f"{target_character} is: {role}"
    }).eq("access_key", access_key).execute()
    return {"message": f"Intelligence gathered.", "target": target_character, "role": role}



# ── Experimental: Hardcoded preset spawner ───────────────────────────────────

CURSED_GALLEON_TEMPLATE = {
    "theme_title": "The Cursed Galleon",
    "short_description": "A body has been found on the deck of the Serpent's Fury at dawn. The crew is restless, the seas are rough, and someone among you fed a shipmate to the deep.",
    "master_story": {
        "background": "• The Serpent's Fury is three days from port, carrying stolen treasure from the governor's vault.\n• Tensions have been rising — the crew suspects the treasure is cursed, and rations are running low.\n• Last night, First Mate Diego Torres was seen arguing violently with someone below deck.",
        "the_murder": "• Diego Torres was found face-down at the bow, a weighted anchor chain wrapped around his ankles.\n• The ship's surgeon confirmed he was dead before hitting the water — killed by a blow to the back of the head.\n• The killer used the chaos of the midnight storm to cover their tracks.",
        "the_solution": "• Captain Rourke O'Malley killed Diego to prevent him from exposing the truth: Rourke had been skimming gold from the haul to pay off a debt to a rival pirate lord.\n• Scarlett Vane, the ship's navigator, knew and helped cover it up in exchange for a greater share.\n• The blow was delivered with a belaying pin, which was thrown overboard before dawn.",
        "public_clues": [
            {"round": 3, "content": "The ship's cook found a bloodstained belaying pin hidden inside the flour barrel near the galley — someone had tried to wash it but the wood grain held the stain."}
        ]
    },
    "characters": [
        {
            "name": "Captain Rourke O'Malley",
            "public_summary": "The commanding and feared captain of the Serpent's Fury, known for his iron discipline and rumoured debts.",
            "role_description": "• Personality: Authoritative, deflects blame onto others, quick to remind people of your rank
• Connection: Diego was your first mate and the only one who knew about the stolen gold
• Dark Secret: You have been siphoning treasure to pay Blackthorn the pirate lord — Diego found out",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "The night Diego died, he slipped a note under my cabin door. It read: 'I know what you took from the chest. Meet me at the bow at midnight or I go to the crew.' I burned it at dawn.",
            "clues": [
                {"round": 2, "true_content": "You heard the surgeon muttering that the wound on Diego's head was consistent with a belaying pin — and you made sure to act surprised.", "poisoned_content": "You saw the cook scrubbing something off the galley floor the morning after the storm."},
                {"round": 3, "true_content": "You told the crew Diego slipped during the storm, but three sailors saw the body and noticed the bruising pattern did not match a fall.", "poisoned_content": "You overheard Mad Meg whispering to the gunner about something she had seen below deck the night before."}
            ]
        },
        {
            "name": "Scarlett Vane",
            "public_summary": "The ship's sharp-eyed navigator, trusted by the captain and respected by the crew for getting them out of dangerous waters.",
            "role_description": "• Personality: Calm and calculating, always seem to have an angle, never volunteer information
• Connection: The captain cut you in on the stolen gold — you have as much to lose as he does
• Dark Secret: You helped the captain dispose of evidence after the murder",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Scarlett Vane helped the captain throw something overboard before sunrise. I saw her from the crow's nest but said nothing — I was afraid.",
            "clues": [
                {"round": 2, "true_content": "You helped the captain adjust the ship's log to show Diego was on watch duty during the storm — a lie, but a useful one.", "poisoned_content": "You noticed the gunpowder master acting strangely nervous during the morning headcount."},
                {"round": 3, "true_content": "You told the crew you were charting the course all night, but the helmsman knows you left your post for nearly an hour around midnight.", "poisoned_content": "You saw the ship's surgeon pocket something small and metallic when he finished examining the body."}
            ]
        },
        {
            "name": "Blind Pete the Bosun",
            "public_summary": "The half-blind but sharp-eared bosun who has sailed with the crew for twenty years and misses nothing despite his poor eyesight.",
            "role_description": "• Personality: Gruff, nostalgic, uses humour to deflect — but deeply loyal to the crew
• Connection: Diego was like a son to you; you taught him everything he knew about the sea
• Dark Secret: You have been smuggling personal rum rations to sell at port — Diego knew and protected you",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": True, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Old Pete was the last one I trusted. His clue is false — the rum has clouded everything he thinks he saw.",
            "clues": [
                {"round": 2, "true_content": "You swear you heard the surgeon and the gunpowder master arguing near the hold the night Diego died, but the rum makes everything blurry.", "poisoned_content": "You are certain you saw Mad Meg climbing back from the bow just before the storm peaked, soaking wet and out of breath."},
                {"round": 3, "true_content": "You remember seeing two figures near the bow just before midnight, but the details keep shifting — it might have been the captain and the navigator, or it might have been the moonlight playing tricks.", "poisoned_content": "You found a torn piece of cloth near the anchor chain that looks like it came from the cook's apron."}
            ]
        },
        {
            "name": "Mad Meg the Gunpowder Master",
            "public_summary": "The volatile and unpredictable keeper of the ship's cannons, feared for her temper and respected for her accuracy.",
            "role_description": "• Personality: Loud, confrontational, always the first to accuse — and secretly terrified of being accused yourself
• Connection: Diego caught you stealing powder to sell at port and threatened to report you
• Dark Secret: You had a powerful motive to silence Diego, but you did not kill him — you just wished you had",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": True, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Meg had nothing to do with my death. But she knows something she is not saying about who visited the captain's cabin the night I died.",
            "clues": [
                {"round": 2, "true_content": "You are absolutely convinced the ship's surgeon did it — the way he examined the body was too calm, too practiced, like he had seen it before.", "poisoned_content": "You are certain the cook is behind it — the man had Diego's blood on his boots the morning after, you are sure of it."},
                {"round": 3, "true_content": "You know in your gut it was the surgeon — you just cannot explain why yet, but your instincts have never been wrong on open water.", "poisoned_content": "The cook avoided eye contact at breakfast and that proves everything you already suspected."}
            ]
        },
        {
            "name": "Dr. Silas Crowe",
            "public_summary": "The ship's soft-spoken surgeon, recruited in Tortuga under mysterious circumstances, who keeps detailed journals no one is allowed to read.",
            "role_description": "• Personality: Precise, quiet, answers every question with another question
• Connection: You treated Diego for a chest wound six months ago and he confided secrets to you
• Dark Secret: You are actually a spy for the governor, documenting the stolen treasure for a future seizure",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": True, "is_fool": False, "is_jester": False,
            "ghost_clue": "Dr. Crowe examined my body with surgical precision. He noted the angle of the blow — something that only someone trained in anatomy would understand the significance of.",
            "clues": [
                {"round": 2, "true_content": "During your examination of Diego's body, you noticed a faint smudge of tar on his collar that matches the belaying pin storage rack near the captain's cabin.", "poisoned_content": "You noticed that the navigator's logbook had a page torn out — the entry for the night of the murder is missing."},
                {"round": 3, "true_content": "You documented in your journal that the force and angle of the blow to Diego's head could only have been delivered by someone taller than average and standing directly behind him — consistent with the captain.", "poisoned_content": "Your journal notes suggest the cook had access to the galley belaying pin and no alibi for the early morning hours."}
            ]
        },
        {
            "name": "Copper Jenny the Cook",
            "public_summary": "The resourceful ship's cook who keeps the crew fed and the gossip flowing, knowing everyone's business before they know it themselves.",
            "role_description": "• Personality: Warm and chatty on the surface, but quietly collecting information about everyone
• Connection: Diego used to eat alone with you every evening and shared things about the captain
• Dark Secret: You are planning to leave the crew at the next port with a small bag of stolen coins you have been hoarding",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": True,
            "ghost_clue": "Jenny always laughed too easily. But she heard everything that happened near the galley that night — more than she has admitted.",
            "clues": [
                {"round": 2, "true_content": "You noticed the captain came down to the galley around midnight during the storm — unusual, as he never leaves the helm during bad weather — and helped himself to a cloth and bucket of water.", "poisoned_content": "You saw the surgeon slipping out of Diego's quarters very early in the morning with something tucked under his coat."},
                {"round": 3, "true_content": "You found the flour barrel had been disturbed — someone had hidden something inside it — and when you looked closer you found traces of dark staining on the wood interior.", "poisoned_content": "You are certain you saw Blind Pete near the anchor chain storage before dawn, moving carefully in the dark."}
            ]
        },
        {
            "name": "Finnegan Ash the Helmsman",
            "public_summary": "The steady-handed helmsman who keeps the ship on course and prides himself on noticing everything from the wheel.",
            "role_description": "• Personality: Methodical and observant, speaks slowly and chooses words carefully
• Connection: You respected Diego but always felt he was hiding something about the captain
• Dark Secret: You saw the navigator leave her post for an hour but stayed quiet because you feared the captain",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Finnegan saw two people near the bow that night. He stayed quiet to protect himself. His silence cost me my life.",
            "clues": [
                {"round": 2, "true_content": "You noticed the navigator was absent from her post for nearly an hour around midnight — you covered for her because you were afraid of what she might do if you told the captain.", "poisoned_content": "You saw the cook carrying something heavy wrapped in canvas towards the stern during the height of the storm."},
                {"round": 3, "true_content": "Your Round 3 instincts tell you that either Captain Rourke O'Malley or Copper Jenny the Cook committed the murder — one of them was near the bow when Diego died.", "poisoned_content": "You found scratch marks near the railing consistent with a struggle — and they lead toward the galley, not the captain's cabin."}
            ]
        },
        {
            "name": "Luca Bones the Deckhand",
            "public_summary": "The youngest crew member, barely eighteen, who joined the ship in desperation and has been trying to prove himself ever since.",
            "role_description": "• Personality: Nervous and eager to please, talks too much when scared
• Connection: Diego was your mentor and the only person who made you feel welcome on the ship
• Dark Secret: You stole a small gold coin from the treasure chest and Diego promised to stay quiet",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Luca was the last person to see me alive. He was crying. He knew something was wrong that night but did not say anything until it was too late.",
            "clues": [
                {"round": 2, "true_content": "You saw the captain pacing near the bow very late during the storm — alone, which was strange because the captain always has someone with him in bad weather.", "poisoned_content": "You overheard Mad Meg muttering to herself about making someone pay, right before the storm started."},
                {"round": 3, "true_content": "You found a monogrammed handkerchief near where Diego's body was discovered — it has the initials R.O. pressed into the corner in black thread.", "poisoned_content": "You found a powder burn near the railing that suggests someone may have used a signal flare to distract the night watch — and only the gunpowder master has access to those."}
            ]
        }
    ]
}

OPERATION_NUSANTARA_TEMPLATE = {
    "theme_title": "Operation Nusantara",
    "short_description": "During a classified trilateral intelligence summit in Kuala Lumpur, a senior double agent has been found dead in a sealed conference room. Everyone in this building had clearance. Someone used it.",
    "master_story": {
        "background": "• The summit brings together twelve intelligence operatives from Malaysia (BID), Singapore (SID), and Indonesia (BIN) to coordinate counter-terrorism strategy across the Malacca Strait.\n• The victim, Director Azman Razak, was Malaysia's most senior handler — and unknown to most, had been feeding intelligence to a foreign power for three years.\n• The summit was a trap: someone knew Azman would be exposed tonight and moved first.",
        "the_murder": "• Director Azman Razak was found slumped at the conference table during the twenty-minute recess, a lethal dose of a fast-acting compound in his coffee cup.\n• The compound is known only to a handful of field operatives trained in chemical concealment — someone in this room had both the knowledge and the access.\n• The conference room was sealed from the inside using the electronic lock, but the security footage of the corridor has a seven-minute gap.",
        "the_solution": "• Colonel Siti Rahimah Ismail (BID) poisoned Azman after discovering he had sold Malaysian agent identities to Chinese intelligence — three of her operatives were burned because of him.\n• She was assisted by Agent Farid Osman, who erased the corridor footage and planted false evidence pointing to the Indonesian delegation.\n• The compound was synthesised from materials available in the summit's on-site medical kit, which Siti had access to as the acting security coordinator.",
        "public_clues": [
            {"round": 3, "content": "Forensics has confirmed the compound found in Director Azman's cup was synthesised from potassium chloride and a sedative only available in the summit's medical kit. The medical kit access log shows it was opened twice last night — once at 21:14 and once at 23:47. Only the acting security coordinator has a master key."}
        ]
    },
    "characters": [
        {
            "name": "Colonel Siti Rahimah Ismail",
            "public_summary": "Malaysia's acting security coordinator for the summit, decorated BID officer with twenty years of field experience and an uncompromising reputation.",
            "role_description": "• Personality: Controlled and precise — never raise your voice, never show emotion, let others fill the silence
• Connection: Azman burned three of your operatives by selling their identities — one did not come home
• Dark Secret: You synthesised the compound yourself using the medical kit and administered it during the coffee service",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "The last person who refilled my cup was the security coordinator. I thought nothing of it at the time. I should have.",
            "clues": [
                {"round": 2, "true_content": "You told the forensics team the medical kit had not been opened all evening, but the access log tells a different story that you have not yet been asked about.", "poisoned_content": "You noticed the Indonesian delegate Pak Wirawan leave the corridor during the recess and return with a different tie — as if he had changed quickly."},
                {"round": 3, "true_content": "You were observed near the coffee service station by two members of the Indonesian delegation during the recess — you told them you were checking the room temperature, but the thermostat is on the opposite wall.", "poisoned_content": "You overhead Agent Nurul speaking quietly into her earpiece during the recess, which is a protocol violation that suggests she was communicating with someone outside the building."}
            ]
        },
        {
            "name": "Agent Farid Osman",
            "public_summary": "Malaysia's youngest senior analyst, fast-tracked through BID for his technical expertise in signals intelligence and digital forensics.",
            "role_description": "• Personality: Helpful and deferential in public — you are very good at appearing transparent
• Connection: Siti mentored you and you owe her your career — when she asked for a favour, you did not ask questions
• Dark Secret: You deleted seven minutes of corridor footage and planted a forged document in the Indonesian delegation's folder",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False, "is_poisoner": True, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Someone with deep system access erased exactly the footage that would have identified the killer. That level of precision does not come from panic — it was planned.",
            "clues": [
                {"round": 2, "true_content": "You told the room you were running a network diagnostic during the recess, which explains why you were at the server terminal — but nobody asked you to run a diagnostic.", "poisoned_content": "You noticed Pak Wirawan accessing something on his phone during the closed session, which is a clear security violation that was ignored by the Indonesian side."},
                {"round": 3, "true_content": "Your access logs show you authenticated to the security system at 23:51 — four minutes after the second medical kit access — and you have not been able to explain what you were doing in the system at that hour.", "poisoned_content": "You found a chemical reference document in Pak Wirawan's briefcase during the room check — it contains synthesis information for a fast-acting sedative compound."}
            ]
        },
        {
            "name": "Director Lim Boon Kiat",
            "public_summary": "Singapore's SID delegation head, a meticulous career intelligence officer known for filing the most detailed meeting notes in the region.",
            "role_description": "• Personality: Bureaucratic and thorough — you document everything and trust nothing you cannot verify
• Connection: You had a private meeting with Azman two hours before his death about a suspected leak in the Malaysian delegation
• Dark Secret: You agreed to keep that meeting off the official record, which now looks very suspicious",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Lim knows more than he has said. He promised me discretion. I hope it was not his discretion that got me killed.",
            "clues": [
                {"round": 2, "true_content": "You documented in your private notes that Azman mentioned the security coordinator by name during your off-record meeting — he said she had been asking unusual questions about the agent identity files.", "poisoned_content": "Your notes from the pre-summit briefing show that the Indonesian technical advisor requested access to the medical facility twice, which seemed excessive at the time."},
                {"round": 3, "true_content": "Your Round 3 assessment is that either Colonel Siti Rahimah Ismail or Agent Nurul Ain Hamzah is responsible — one of them had both motive and access to the conference room during the critical window.", "poisoned_content": "Your forensic notes suggest the compound delivery method required someone with prior medical training — and the Indonesian delegation's Pak Wirawan has a documented background in field medicine."}
            ]
        },
        {
            "name": "Agent Nurul Ain Hamzah",
            "public_summary": "Malaysia's counter-intelligence liaison for the summit, responsible for securing communications between delegations and vetting all support staff.",
            "role_description": "• Personality: Professionally warm but intensely alert — you notice everything and share almost nothing
• Connection: You suspected Azman was compromised six months ago but lacked the evidence to act
• Dark Secret: You have been running an unofficial parallel investigation into Azman without authorisation from BID",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": True, "is_fool": False, "is_jester": False,
            "ghost_clue": "Nurul knew. She had been watching me for months. If she had moved faster, I might still be alive — or I might have had her silenced too.",
            "clues": [
                {"round": 2, "true_content": "During the recess, you observed the security coordinator approach the coffee service station from an angle that did not match her stated path to the thermostat — the trajectories are inconsistent.", "poisoned_content": "You intercepted a brief encrypted transmission originating from inside the building during the recess — the signal profile matches equipment carried by the Indonesian technical team."},
                {"round": 3, "true_content": "Your parallel investigation file contains a chemical procurement record showing a compound purchase linked to a BID internal account twelve days before the summit — the account belongs to the security division.", "poisoned_content": "Your surveillance notes show Pak Wirawan made three unsanctioned phone calls in the forty-eight hours before Azman's death — all to the same unregistered number."}
            ]
        },
        {
            "name": "Pak Wirawan Santoso",
            "public_summary": "Indonesia's BIN deputy director and lead negotiator, a pragmatic political survivor who has outlasted four different administrations.",
            "role_description": "• Personality: Expansive and diplomatic in public — you create the impression of openness while saying very little of substance
• Connection: Azman owed you a favour from a joint operation in 2019 that you have never collected on — until now
• Dark Secret: You came to this summit with a private agenda to acquire the Malaysian agent list, not realising someone else had the same idea with more violent intentions",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": True, "is_jester": False,
            "ghost_clue": "Wirawan wanted the list but not my death. He is guilty of many things — just not this particular one.",
            "clues": [
                {"round": 2, "true_content": "You noticed the young Malaysian analyst authenticating to the security system during the recess — unusual timing that he explained away as routine maintenance, but you have been in this business long enough to know that nothing is routine at 23:51.", "poisoned_content": "You saw the Singapore director leaving the corridor during the recess through the secondary exit, which is supposed to be alarmed — suggesting someone had already deactivated it."},
                {"round": 3, "true_content": "You observed Agent Farid at the server terminal during the recess for nearly four minutes — far longer than any diagnostic should require — and he looked up only once, directly at the security coordinator.", "poisoned_content": "You found a chemical reference page folded inside Director Lim's meeting folder during the document exchange — it should not have been there."}
            ]
        },
        {
            "name": "Dr. Ayu Permatasari",
            "public_summary": "Indonesia's BIN technical advisor and the summit's designated chemical safety officer, responsible for hazardous materials compliance.",
            "role_description": "• Personality: Academic and detail-oriented, you tend to over-explain things which makes people trust you less than they should
• Connection: You were asked to inspect the medical kit earlier in the day and noted everything was in order
• Dark Secret: You failed to log the second inspection properly and your signature was forged on the compliance sheet",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "The chemical safety officer inspected the kit. But the second access was not hers. Someone knew her schedule and moved during her gap.",
            "clues": [
                {"round": 2, "true_content": "You noticed the access log entry at 23:47 used a master key rather than your personal credentials — your inspection used your own badge, which means the second entry was someone else entirely.", "poisoned_content": "You observed Pak Wirawan handling a small sealed container during the pre-summit briefing that he quickly put away when others entered the room."},
                {"round": 3, "true_content": "Your compliance report shows the medical kit was fully intact at 21:00 — but the forensic analysis indicates the compound was synthesised from materials that would have required selective removal without triggering the tamper seal, which requires a master key and specific knowledge of the kit layout.", "poisoned_content": "Your notes document that Director Lim requested the chemical safety specifications for the summit medical kit three days before arriving — an unusual request from someone with no chemical background."}
            ]
        },
        {
            "name": "Colonel Marcus Tan",
            "public_summary": "Singapore's SID head of field operations, a former commando officer who has transitioned into intelligence with the same direct approach he used in the field.",
            "role_description": "• Personality: Blunt and impatient with process — you say what you think and expect others to do the same
• Connection: You worked directly under Azman on a joint operation in 2021 and saw firsthand how he operated
• Dark Secret: You warned Singapore headquarters three months ago that Azman was compromised — they told you to stand down and say nothing",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Marcus knew I was dirty. He reported it and was silenced. He came to this summit expecting a confrontation — not a funeral.",
            "clues": [
                {"round": 2, "true_content": "During the coffee break you watched the security coordinator circle the conference table twice before sitting — she was checking who had touched which cup, not socialising.", "poisoned_content": "You watched Agent Nurul step outside the secure perimeter during the recess to use her personal phone, which is a clear protocol breach she has not been asked to explain."},
                {"round": 3, "true_content": "You noticed the security coordinator placed one specific cup at Azman's seat before the recess ended — she did not pour from the central service, she carried a single cup from the side table and set it down deliberately.", "poisoned_content": "Your operational assessment is that Agent Nurul's parallel investigation — which you were briefed on informally — may have crossed the line from surveillance into intervention."}
            ]
        },
        {
            "name": "Agent Zara Putri Nabilah",
            "public_summary": "Malaysia's youngest field agent at the summit, assigned as Azman's personal aide and responsible for his schedule and briefing documents.",
            "role_description": "• Personality: Eager and efficient — you have worked extremely hard to be in this room and you will not do anything to jeopardise that
• Connection: You handled Azman's coffee order every morning for six months and knew exactly how he took it
• Dark Secret: Azman had been pressuring you to pass internal documents to him outside official channels — you refused twice and were terrified of what came next",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Zara brought me my last coffee as always. But she did not pour it herself this time. She handed it to me from the side table without looking me in the eye.",
            "clues": [
                {"round": 2, "true_content": "You saw Agent Farid at the server terminal during the recess for an unusually long time and when you walked past, he minimised the screen immediately — a reflex that told you he was not running a standard diagnostic.", "poisoned_content": "You noticed Pak Wirawan pass a folded note to Dr. Ayu under the table during the session — she palmed it so quickly you might have imagined it, but you did not."},
                {"round": 3, "true_content": "You remember now that the cup placed at Azman's seat during the recess was already there when the coffee service arrived — meaning it was placed before the catering staff entered the room, not during the service.", "poisoned_content": "You recall seeing Agent Nurul near the coffee service station at the very start of the recess, before anyone else had entered the room."}
            ]
        },
        {
            "name": "Dato Sri Halim Mohd Noor",
            "public_summary": "Malaysia's senior political liaison to the summit, a career diplomat who bridges the intelligence community and the ministry with practiced ease.",
            "role_description": "• Personality: Smooth and reassuring — you have spent thirty years making difficult things sound manageable
• Connection: You sponsored Azman's appointment as director five years ago and have been quietly regretting it ever since
• Dark Secret: You received a warning from a foreign contact two weeks ago that Azman was about to be publicly exposed — you said nothing because you did not want to be associated with the fallout",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": True, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Halim knew I was going to be exposed. He chose to do nothing. His silence was not loyalty — it was self-preservation.",
            "clues": [
                {"round": 2, "true_content": "You are quite certain the Indonesian deputy director was behaving suspiciously during the recess — lingering near the document table and watching the door — and that this confirms your instinct that Jakarta is behind the whole affair.", "poisoned_content": "You believe the Singapore colonel is involved — his manner is too controlled, too unsurprised by the death of a man he supposedly respected."},
                {"round": 3, "true_content": "You are now completely convinced that Pak Wirawan orchestrated everything from Jakarta and the Malaysian security team has been manipulated — your contact's warning two weeks ago mentioned Indonesian pressure, after all.", "poisoned_content": "Your instinct tells you Director Lim brought intelligence on Azman to the summit and used it as leverage — the private meeting proves it."}
            ]
        },
        {
            "name": "Agent Khairi Zulkifli",
            "public_summary": "Indonesia's BIN field liaison, a quiet and methodical operative who specialises in counter-surveillance and is rarely the most visible person in any room.",
            "role_description": "• Personality: Understated and precise — you observe more than you speak and you have trained yourself to be forgettable
• Connection: You noticed the security coordinator accessing the medical kit during your routine sweep and logged it in your private notes
• Dark Secret: You did not report the irregular access because you were testing whether it would be flagged by the Malaysian system — a professional habit that has now become a serious problem",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "The Indonesian agent swept the corridor twice. He saw the security coordinator at the medical kit and said nothing. His silence was professional. It was also fatal — for me.",
            "clues": [
                {"round": 2, "true_content": "During your counter-surveillance sweep at 23:49, you observed Colonel Siti accessing the medical kit storage near the briefing room annex — you noted the time and her body language suggested she was checking whether she had been observed.", "poisoned_content": "Your sweep documented Agent Farid entering the server room during the recess, which is standard — but he was inside for four minutes longer than any diagnostic routine requires."},
                {"round": 3, "true_content": "Your private log entry for 23:49 reads: 'SC-MY accessed medical storage, no witness, unlogged. Monitoring.' You have not shared this with the investigation team yet because you were waiting to understand the full picture before speaking.", "poisoned_content": "Your surveillance notes for the recess period show Agent Zara entering the conference room approximately ninety seconds before the catering staff — placing her alone with the coffee service at the critical moment."}
            ]
        },
        {
            "name": "Commissioner Rosnah Ahmad Basri",
            "public_summary": "Malaysia's special commissioner overseeing inter-agency cooperation at the summit, a senior figure who holds authority over all three delegations' conduct.",
            "role_description": "• Personality: Formal and commanding — people defer to you and you have learned to use that silence as a tool
• Connection: You have known Azman since his early career and always privately doubted his commitment to the service
• Dark Secret: You authorised the summit's security arrangements, which means the gap in the footage is technically your responsibility — and you are motivated to ensure the investigation does not go in a direction that exposes your oversight failures",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "Rosnah will try to control this investigation. Not because she is guilty — but because the truth of what happened will reveal how comprehensively she failed to prevent it.",
            "clues": [
                {"round": 2, "true_content": "You noticed Agent Farid requested a system access extension at 23:45 — you approved it remotely without checking the reason, which you now realise was a significant lapse in protocol.", "poisoned_content": "During the post-discovery briefing, you observed Pak Wirawan consulting a document on his phone that he immediately locked when you looked his way — the screen briefly showed what appeared to be a chemical formula."},
                {"round": 3, "true_content": "Your approval logs show you granted Agent Farid elevated system access at 23:45 — which allowed him to authenticate to the security camera management system at 23:51 without triggering the standard dual-authorisation requirement.", "poisoned_content": "The forensic team's preliminary report was altered before you received it — a section on access log anomalies was removed, and you believe Director Lim's team had access to the report before you did."}
            ]
        },
        {
            "name": "Lieutenant Syafiq Danial Roslan",
            "public_summary": "The summit's duty security officer, a military intelligence secondee responsible for physical access control and the room's electronic locking system.",
            "role_description": "• Personality: Nervous under authority and prone to over-explaining — you know more than your rank suggests you should
• Connection: You were the one who configured the electronic door lock and you know exactly how the seven-minute footage gap could have been created
• Dark Secret: Someone senior told you to ignore an access anomaly earlier in the evening and you complied — you do not know if that person is the killer",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False, "is_poisoner": False, "is_paranoid": True, "is_spy": False, "is_fool": False, "is_jester": False,
            "ghost_clue": "The duty officer knew how the footage gap was created. He was told to stay quiet. He is telling the truth when he says he does not know who ordered it — but the order came through the security division.",
            "clues": [
                {"round": 2, "true_content": "You are utterly convinced that Pak Wirawan is orchestrating this — the way he positioned himself near the commissioner during the post-discovery briefing was textbook misdirection, you have seen it in training exercises.", "poisoned_content": "You are certain Agent Zara is hiding something — the way she described handing Azman his coffee was too rehearsed, too precise, as if she had practised it."},
                {"round": 3, "true_content": "You know in your gut it was Pak Wirawan who gave the order — the anomaly you were told to ignore came through an Indonesian-registered device signature, and that is all the proof you need.", "poisoned_content": "Agent Zara's timeline does not add up — she says she entered the conference room after the catering staff, but your access log shows her badge was scanned ninety seconds earlier."}
            ]
        }
    ]
}

@app.post("/admin/spawn-preset/{preset_id}", dependencies=[Depends(verify_host)])
async def spawn_preset(request: Request, preset_id: str):
    presets = {
        "cursed_galleon":       CURSED_GALLEON_TEMPLATE,
        "operation_nusantara":  OPERATION_NUSANTARA_TEMPLATE,
    }
    if preset_id not in presets:
        raise HTTPException(status_code=404, detail="Preset not found.")

    template = presets[preset_id]
    is_crisis = preset_id == "operation_nusantara"

    game_insert = supabase.table("games").insert({
        "theme":             template["theme_title"],
        "theme_title":       template["theme_title"],
        "short_description": template["short_description"],
        "master_story":      json.dumps(template["master_story"]),
        "is_crisis_game":    is_crisis,
    }).execute()
    game_id = game_insert.data[0]["id"]

    for char in template["characters"]:
        player_id = supabase.table("players").insert({
            "game_id":         game_id,
            "access_key":      generate_key(),
            "character_name":  char["name"],
            "role_description": char["role_description"],
            "public_summary":  char["public_summary"],
            "ghost_clue":      char.get("ghost_clue", "The spirits are silent."),
            "is_killer":       char.get("is_killer", False),
            "is_accomplice":   char.get("is_accomplice", False),
            "is_investigator": char.get("is_investigator", False),
            "is_drunk":        char.get("is_drunk", False),
            "is_poisoner":     char.get("is_poisoner", False),
            "is_paranoid":     char.get("is_paranoid", False),
            "is_spy":          char.get("is_spy", False),
            "is_fool":         char.get("is_fool", False),
            "is_jester":       char.get("is_jester", False),
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
        "message":  f"Preset '{template['theme_title']}' spawned!",
        "game_id":  game_id,
        "room_url": f"{request.base_url}room/{game_id}",
        "is_crisis": is_crisis,
    }


# ── Experimental: Crisis dilemma vote ─────────────────────────────────────────

CRISIS_OPTIONS = {
    "cursed_galleon": {
        "question": "A second body has been spotted tangled in the anchor chain. Do you haul it up in full view of the crew, or cut it loose quietly to preserve order?",
        "safe":      "Haul it up — full transparency with the crew",
        "dangerous": "Cut it loose — control the information",
    },
    "operation_nusantara": {
        "question": "The building's communications have been cut. Do you allow each delegation to use their own encrypted channels to contact headquarters, or enforce a complete comms blackout until the killer is found?",
        "safe":      "Enforce comms blackout — nobody talks to the outside",
        "dangerous": "Allow individual encrypted channels — trust the delegations",
    },
}

@app.get("/admin/crisis-dilemma/{game_id}", dependencies=[Depends(verify_host)])
async def get_crisis_dilemma(game_id: str):
    game = supabase.table("games").select("theme_title, is_crisis_game, crisis_resolved, crisis_dangerous_won").eq("id", game_id).execute()
    if not game.data or not game.data[0].get("is_crisis_game"):
        raise HTTPException(status_code=400, detail="Not a crisis game.")
    g = game.data[0]
    # Determine which preset based on theme title
    preset_key = "operation_nusantara" if "Nusantara" in g["theme_title"] else "cursed_galleon"
    dilemma    = CRISIS_OPTIONS.get(preset_key, {})
    votes      = supabase.table("crisis_votes").select("vote").eq("game_id", game_id).execute()
    tally      = {"safe": 0, "dangerous": 0}
    for v in votes.data: tally[v["vote"]] = tally.get(v["vote"], 0) + 1
    return {
        "dilemma":         dilemma,
        "tally":           tally,
        "crisis_resolved": g.get("crisis_resolved", False),
        "dangerous_won":   g.get("crisis_dangerous_won", False),
    }

@app.post("/player/crisis-vote/{access_key}")
async def crisis_vote(access_key: str, vote: str):
    if vote not in ("safe", "dangerous"):
        raise HTTPException(status_code=400, detail="Vote must be 'safe' or 'dangerous'.")
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data:
        raise HTTPException(status_code=404, detail="Invalid access key.")
    p       = player_res.data[0]
    game_id = p["game_id"]
    if p.get("is_dead"):
        raise HTTPException(status_code=403, detail="Eliminated players cannot vote on the dilemma.")
    supabase.table("crisis_votes").upsert({
        "game_id":   game_id,
        "player_id": p["id"],
        "vote":      vote,
    }, on_conflict="game_id, player_id").execute()
    # Check if all alive players have voted
    alive      = supabase.table("players").select("id").eq("game_id", game_id).eq("is_dead", False).execute()
    all_votes  = supabase.table("crisis_votes").select("vote").eq("game_id", game_id).execute()
    tally      = {"safe": 0, "dangerous": 0}
    for v in all_votes.data: tally[v["vote"]] = tally.get(v["vote"], 0) + 1
    total_voted = sum(tally.values())
    return {"message": f"Vote cast: {vote}", "tally": tally, "total_alive": len(alive.data), "total_voted": total_voted}

@app.post("/admin/resolve-crisis/{game_id}", dependencies=[Depends(verify_host)])
async def resolve_crisis(game_id: str):
    votes  = supabase.table("crisis_votes").select("vote").eq("game_id", game_id).execute()
    tally  = {"safe": 0, "dangerous": 0}
    for v in votes.data: tally[v["vote"]] = tally.get(v["vote"], 0) + 1
    dangerous_won = tally["dangerous"] > tally["safe"]
    supabase.table("games").update({
        "crisis_resolved":      True,
        "crisis_dangerous_won": dangerous_won,
    }).eq("id", game_id).execute()
    if dangerous_won:
        # Grant killer an extra elimination slot (death_round = 3 target)
        # We mark a special flag on the killer so the player.html shows the extra kill panel
        supabase.table("players").update({"has_extra_kill": True}).eq(
            "game_id", game_id).eq("is_killer", True).execute()
        return {"message": "⚠️ The dangerous option won. The killer has been granted an extra elimination before Round 3.", "dangerous_won": True, "tally": tally}
    return {"message": "✅ The safe option won. No extra consequences.", "dangerous_won": False, "tally": tally}

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
