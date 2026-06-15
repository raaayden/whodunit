from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from supabase import create_client, Client
import google.generativeai as genai
import random
import string
import json
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
app.mount("/static", StaticFiles(directory="static"), name="static")

def verify_host(x_admin_token: str = Header(...)):
    if x_admin_token != os.getenv("HOST_ADMIN_PASSWORD"):
        raise HTTPException(status_code=401, detail="Unauthorized")

def generate_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.get("/")
async def host_dashboard(): return FileResponse("static/index.html")

@app.get("/room/{game_id}")
async def lobby_view(game_id: str): return FileResponse("static/room.html")

@app.get("/play")
async def player_view(): return FileResponse("static/player.html")

@app.post("/admin/create-game", dependencies=[Depends(verify_host)])
async def create_game(request: Request, theme: str, player_count: int, include_accomplice: bool = False):
    accomplice_instruction = "Ensure EXACTLY one character is the accomplice." if include_accomplice else "Ensure NO characters are the accomplice."
    
    prompt = f"""
    Create a murder mystery game for {player_count} players. Theme: {theme}.
    Return ONLY a JSON object with this exact structure:
    {{
        "master_story": {{
            "background": "The overarching plot and setting.",
            "the_murder": "Exactly how the victim died and why the killer did it.",
            "the_solution": "How the specific clues in round 3 prove who the killer is."
        }},
        "characters": [
            {{
                "name": "Character Name",
                "public_summary": "A 1-sentence summary of what EVERYONE in the room knows about this person.",
                "role_description": "A short, punchy 3-sentence backstory. Keep it concise.",
                "is_killer": false, 
                "is_accomplice": {"true" if include_accomplice else "false"},
                "clues": [
                    {{"round": 1, "content": "• First detail. • Second detail."}},
                    {{"round": 2, "content": "• First revealing detail. • Second revealing detail."}},
                    {{"round": 3, "content": "• First hard evidence. • Second hard evidence."}}
                ]
            }}
        ]
    }}
    Ensure EXACTLY one character has "is_killer": true.
    {accomplice_instruction}
    CRITICAL: Clue content MUST use the bullet character (•) to separate details.
    """
    
    model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
    response = model.generate_content(prompt)
    game_data = json.loads(response.text)

    game_insert = supabase.table("games").insert({
        "theme": theme, "master_story": json.dumps(game_data["master_story"])
    }).execute()
    game_id = game_insert.data[0]["id"]

    for char in game_data["characters"]:
        player_id = supabase.table("players").insert({
            "game_id": game_id, "access_key": generate_key(), "character_name": char["name"],
            "role_description": char["role_description"], "public_summary": char["public_summary"],
            "is_killer": char["is_killer"], "is_accomplice": char.get("is_accomplice", False)
        }).execute().data[0]["id"]

        clues_to_insert = [
            {"game_id": game_id, "player_id": player_id, "round_number": c["round"], "content": c["content"]}
            for c in char["clues"]
        ]
        supabase.table("clues").insert(clues_to_insert).execute()

    # DYNAMIC URL FIX: Automatically uses your Render domain in production
    return { "message": "Game generated!", "game_id": game_id, "room_url": f"{request.base_url}room/{game_id}" }

@app.post("/admin/release-round/{game_id}/{round_num}", dependencies=[Depends(verify_host)])
async def release_clues(game_id: str, round_num: int):
    supabase.table("games").update({"current_round": round_num, "status": "started"}).eq("id", game_id).execute()
    data = supabase.table("clues").update({"is_released": True}).eq("game_id", game_id).eq("round_number", round_num).execute()
    return {"message": f"Round {round_num} released!", "clues_updated": len(data.data)}

@app.get("/admin/game/{game_id}", dependencies=[Depends(verify_host)])
async def get_god_mode(game_id: str):
    game = supabase.table("games").select("*").eq("id", game_id).execute()
    players = supabase.table("players").select("*").eq("game_id", game_id).execute()
    return {"game": game.data[0], "players": players.data}

@app.post("/api/room/{game_id}/join")
async def join_room(game_id: str, player_name: str):
    game = supabase.table("games").select("status").eq("id", game_id).execute()
    if not game.data: raise HTTPException(status_code=404, detail="Game not found.")
    if game.data[0]["status"] != "waiting": raise HTTPException(status_code=400, detail="Game has already started.")

    unclaimed = supabase.table("players").select("*").eq("game_id", game_id).is_("claimed_by_user", "null").execute()
    if not unclaimed.data: raise HTTPException(status_code=400, detail="Room is full.")
    
    character = random.choice(unclaimed.data)
    supabase.table("players").update({"claimed_by_user": player_name}).eq("id", character["id"]).execute()

    return { "access_key": character["access_key"], "character_name": character["character_name"] }

@app.get("/player/dashboard/{access_key}")
async def get_player_dashboard(access_key: str):
    player_res = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player_res.data: raise HTTPException(status_code=404, detail="Invalid access key")
    
    player = player_res.data[0]
    game_id = player["game_id"]
    
    game_res = supabase.table("games").select("current_round, status").eq("id", game_id).execute()
    current_round = game_res.data[0]["current_round"]
    game_status = game_res.data[0]["status"]

    is_currently_dead = player["is_dead"] and current_round >= player["death_round"]
    clues_res = supabase.table("clues").select("*").eq("player_id", player["id"]).eq("is_released", True).execute()
    
    all_players = supabase.table("players").select("id, character_name, public_summary, claimed_by_user, is_dead, death_round, is_killer, is_accomplice").eq("game_id", game_id).execute()
    
    killers_count = sum(1 for p in all_players.data if p["is_killer"])
    accomplice_count = sum(1 for p in all_players.data if p["is_accomplice"])

    my_notes = supabase.table("player_notes").select("*").eq("owner_player_id", player["id"]).execute()
    notes_dict = {n["target_character"]: n for n in my_notes.data}

    notebook = []
    for p in all_players.data:
        if p["id"] != player["id"]:
            notebook.append({
                "character_name": p["character_name"], "claimed_by": p["claimed_by_user"],
                "public_summary": p["public_summary"], "is_publicly_dead": p["is_dead"] and current_round >= p["death_round"],
                "my_note": notes_dict.get(p["character_name"], {"status": "neutral", "note_text": ""})
            })

    return {
        "game_status": game_status, "current_round": current_round, "character_name": player["character_name"],
        "role_description": player["role_description"], "is_killer": player["is_killer"], "is_accomplice": player["is_accomplice"],
        "is_dead": is_currently_dead, "voted_for": player["voted_for"], "available_clues": clues_res.data,
        "notebook": notebook, "killers_count": killers_count, "accomplice_count": accomplice_count
    }

@app.post("/player/eliminate/{killer_access_key}")
async def eliminate_player(killer_access_key: str, target_character: str):
    killer = supabase.table("players").select("*").eq("access_key", killer_access_key).execute()
    if not killer.data or not killer.data[0]["is_killer"]: raise HTTPException(status_code=403, detail="Unauthorized.")
    
    game_id = killer.data[0]["game_id"]
    game = supabase.table("games").select("current_round").eq("id", game_id).execute()
    next_round = game.data[0]["current_round"] + 1

    supabase.table("players").update({"is_dead": True, "death_round": next_round}).eq("game_id", game_id).eq("character_name", target_character).execute()
    return {"message": f"Target locked. {target_character} will be eliminated when Round {next_round} begins."}

@app.post("/player/notes/{access_key}")
async def update_notes(access_key: str, target_character: str, status: str, note_text: str):
    player = supabase.table("players").select("id, game_id").eq("access_key", access_key).execute()
    owner_id = player.data[0]["id"]
    game_id = player.data[0]["game_id"]

    existing = supabase.table("player_notes").select("id").eq("owner_player_id", owner_id).eq("target_character", target_character).execute()
    if existing.data:
        supabase.table("player_notes").update({"status": status, "note_text": note_text}).eq("id", existing.data[0]["id"]).execute()
    else:
        supabase.table("player_notes").insert({
            "game_id": game_id, "owner_player_id": owner_id, "target_character": target_character, "status": status, "note_text": note_text
        }).execute()

    return {"message": "Note saved"}

@app.post("/player/vote/{access_key}")
async def cast_vote(access_key: str, suspect: str):
    supabase.table("players").update({"voted_for": suspect}).eq("access_key", access_key).execute()
    return {"message": "Vote locked in!"}