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
async def create_game(request: Request, theme: str, player_count: int, accomplice_count: int = 0, include_drunk: bool = False, include_investigator: bool = False):
    
    accomplice_instruction = f"Ensure EXACTLY {accomplice_count} character(s) have 'is_accomplice': true."
    drunk_instruction = "Ensure EXACTLY ONE innocent character has 'is_drunk': true. ALL of their clues must be completely FALSE and misleading." if include_drunk else "Ensure NO characters have 'is_drunk': true."
    investigator_instruction = "Ensure EXACTLY ONE innocent character has 'is_investigator': true. Their Round 2 clue MUST be a 50/50 ping stating 'Either [Killer Name] or [Innocent Name] is the killer.'" if include_investigator else "Ensure NO characters have 'is_investigator': true."

    prompt = f"""
    Create a highly interactive social deduction murder mystery for {player_count} players. Theme: {theme}.
    Return ONLY a JSON object with this exact structure:
    {{
        "master_story": {{
            "background": "• Point 1\\n• Point 2",
            "the_murder": "• Point 1\\n• Point 2",
            "the_solution": "• Point 1\\n• Point 2"
        }},
        "characters": [
            {{
                "name": "Character Name",
                "public_summary": "A 1-sentence summary of what EVERYONE knows about this person.",
                "role_description": "• Personality: (How to act)\\n• Connection: (To the victim)\\n• Dark Secret: (Something they are hiding)",
                "is_killer": false, 
                "is_accomplice": false,
                "is_investigator": false,
                "is_drunk": false,
                "ghost_clue": "A highly revealing clue they ONLY unlock after they are murdered. It must point toward the killer or an accomplice.",
                "clues": [
                    {{"round": 2, "content": "• Gossip or timeline inconsistency about ANOTHER player's secret."}},
                    {{"round": 3, "content": "• Hard physical evidence relating to the crime scene or the true killer."}}
                ]
            }}
        ]
    }}
    Ensure EXACTLY one character has "is_killer": true.
    {accomplice_instruction}
    {drunk_instruction}
    {investigator_instruction}
    CRITICAL: Role descriptions and master story sections MUST be bulleted using the '•' character.
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
            "ghost_clue": char["ghost_clue"], "is_killer": char["is_killer"], "is_accomplice": char.get("is_accomplice", False),
            "is_investigator": char.get("is_investigator", False), "is_drunk": char.get("is_drunk", False)
        }).execute().data[0]["id"]

        clues_to_insert = [{"game_id": game_id, "player_id": player_id, "round_number": c["round"], "content": c["content"]} for c in char["clues"]]
        supabase.table("clues").insert(clues_to_insert).execute()

    return { "message": "Game generated!", "game_id": game_id, "room_url": f"{request.base_url}room/{game_id}" }

@app.post("/admin/release-round/{game_id}/{round_num}", dependencies=[Depends(verify_host)])
async def release_clues(game_id: str, round_num: int):
    supabase.table("games").update({"current_round": round_num, "status": "started"}).eq("id", game_id).execute()
    if round_num > 1:
        supabase.table("clues").update({"is_released": True}).eq("game_id", game_id).eq("round_number", round_num).execute()
    return {"message": f"Round {round_num} active!"}

@app.post("/admin/end-game/{game_id}", dependencies=[Depends(verify_host)])
async def end_game(game_id: str):
    supabase.table("games").update({"status": "finished"}).eq("id", game_id).execute()
    return {"message": "Game ended! The truth is now revealed on all player devices."}

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
    
    game_res = supabase.table("games").select("current_round, status, master_story").eq("id", game_id).execute()
    current_round = game_res.data[0]["current_round"]
    game_status = game_res.data[0]["status"]
    master_story = json.loads(game_res.data[0]["master_story"])

    is_currently_dead = player["is_dead"] and current_round >= player["death_round"]
    clues_res = supabase.table("clues").select("*").eq("player_id", player["id"]).eq("is_released", True).execute()
    all_players = supabase.table("players").select("id, character_name, public_summary, claimed_by_user, is_dead, death_round, is_killer, is_accomplice, is_investigator, is_drunk, voted_for").eq("game_id", game_id).execute()
    
    # Check if this player received any ghost clues from dead players
    received_ghost_req = supabase.table("players").select("character_name, ghost_clue").eq("game_id", game_id).eq("ghost_clue_recipient", player["character_name"]).execute()
    received_ghost_clues = received_ghost_req.data

    killers_count = sum(1 for p in all_players.data if p["is_killer"])
    accomplice_count = sum(1 for p in all_players.data if p["is_accomplice"])

    known_killer = None
    if player["is_accomplice"]:
        for p in all_players.data:
            if p["is_killer"]: known_killer = p["character_name"]

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

    reveal_data = None
    if game_status == "finished":
        killer_name = next((p["character_name"] for p in all_players.data if p["is_killer"]), "Unknown")
        
        votes = []
        correct_votes = 0
        alive_innocents = 0
        
        for p in all_players.data:
            is_innocent = not p["is_killer"] and not p["is_accomplice"]
            if is_innocent and not p["is_dead"]:
                alive_innocents += 1
                
            if p["voted_for"]:
                is_correct = (p["voted_for"] == killer_name)
                # Only alive innocents count toward the win condition ratio
                if is_correct and is_innocent and not p["is_dead"]: 
                    correct_votes += 1
                votes.append({"voter": p["character_name"], "player_name": p["claimed_by_user"], "target": p["voted_for"], "is_correct": is_correct})

        # Innocents win if at least 50% of alive innocents voted correctly
        needed_votes = max(1, alive_innocents / 2.0)
        killer_caught = correct_votes >= needed_votes

        true_identities = [{"name": p["character_name"], "player": p["claimed_by_user"], "is_killer": p["is_killer"], "is_accomplice": p["is_accomplice"], "is_investigator": p["is_investigator"], "is_drunk": p["is_drunk"]} for p in all_players.data]
        
        reveal_data = {
            "master_story": master_story,
            "true_identities": true_identities,
            "votes": votes,
            "killer_caught": killer_caught
        }

    return {
        "game_status": game_status, "current_round": current_round, "character_name": player["character_name"],
        "active_story": {"background": master_story.get("background", ""), "the_murder": master_story.get("the_murder", "")},
        "role_description": player["role_description"], "ghost_clue": player["ghost_clue"],
        "ghost_clue_recipient": player["ghost_clue_recipient"], "received_ghost_clues": received_ghost_clues,
        "is_killer": player["is_killer"], "is_accomplice": player["is_accomplice"], "is_investigator": player["is_investigator"],
        "known_killer": known_killer, "is_dead": is_currently_dead, "voted_for": player["voted_for"], "available_clues": clues_res.data,
        "notebook": notebook, "killers_count": killers_count, "accomplice_count": accomplice_count, "reveal_data": reveal_data
    }

@app.post("/player/eliminate/{killer_access_key}")
async def eliminate_player(killer_access_key: str, target_character: str):
    killer = supabase.table("players").select("*").eq("access_key", killer_access_key).execute()
    if not killer.data or not killer.data[0]["is_killer"]: raise HTTPException(status_code=403, detail="Unauthorized.")
    
    game_id = killer.data[0]["game_id"]
    game = supabase.table("games").select("current_round").eq("id", game_id).execute()
    next_round = game.data[0]["current_round"] + 1

    supabase.table("players").update({"is_dead": False, "death_round": 99}).eq("game_id", game_id).eq("death_round", next_round).execute()
    supabase.table("players").update({"is_dead": True, "death_round": next_round}).eq("game_id", game_id).eq("character_name", target_character).execute()
    return {"message": f"Target locked: {target_character}. They will drop dead at the start of Round {next_round}."}

@app.post("/player/send-ghost-clue/{access_key}")
async def send_ghost_clue(access_key: str, target_character: str):
    player = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if not player.data[0]["is_dead"]: raise HTTPException(status_code=403, detail="Only eliminated players can send ghost clues.")
    
    supabase.table("players").update({"ghost_clue_recipient": target_character}).eq("access_key", access_key).execute()
    return {"message": f"Message sent to {target_character} from the beyond."}

@app.post("/player/notes/{access_key}")
async def update_notes(access_key: str, target_character: str, status: str, note_text: str):
    player = supabase.table("players").select("id, game_id").eq("access_key", access_key).execute()
    supabase.table("player_notes").upsert({
        "game_id": player.data[0]["game_id"], "owner_player_id": player.data[0]["id"], 
        "target_character": target_character, "status": status, "note_text": note_text
    }, on_conflict="owner_player_id, target_character").execute()
    return {"message": "Note saved"}

@app.post("/player/vote/{access_key}")
async def cast_vote(access_key: str, suspect: str):
    player = supabase.table("players").select("*").eq("access_key", access_key).execute()
    if player.data[0]["is_dead"]: raise HTTPException(status_code=403, detail="Eliminated players cannot vote.")
    
    supabase.table("players").update({"voted_for": suspect}).eq("access_key", access_key).execute()
    return {"message": "Vote locked in!"}