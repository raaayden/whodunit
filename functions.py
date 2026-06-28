"""
functions.py — All business logic for Whodunit.
Imported by main.py. No FastAPI routes here.
"""
import json
import random
import string
from fastapi import HTTPException, Header
from google import genai
from google.genai import types
import os

# ── Shared clients (initialised in main.py, passed in where needed) ───────────
# These are set by main.py on startup via init_clients()
supabase = None
gemini   = None
GEMINI_MODEL = "gemini-2.5-flash-lite"


def init_clients(_supabase, _gemini):
    """Called once from main.py after clients are created."""
    global supabase, gemini
    supabase = _supabase
    gemini   = _gemini


# ── Auth ──────────────────────────────────────────────────────────────────────

def verify_host(x_admin_token: str = Header(...)):
    if x_admin_token != os.getenv("HOST_ADMIN_PASSWORD"):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_key() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def insert_players_and_clues(game_id: str, characters: list):
    """Insert all player rows and their pre-baked clues for a given game."""
    for char in characters:
        player_id = supabase.table("players").insert({
            "game_id":          game_id,
            "access_key":       generate_key(),
            "character_name":   char["name"],
            "role_description": char["role_description"],
            "public_summary":   char["public_summary"],
            "ghost_clue":       char.get("ghost_clue") or "The spirits are silent... I took my secrets to the grave.",
            "is_killer":        char.get("is_killer",       False),
            "is_accomplice":    char.get("is_accomplice",   False),
            "is_investigator":  char.get("is_investigator", False),
            "is_drunk":         char.get("is_drunk",        False),
            "is_poisoner":      char.get("is_poisoner",     False),
            "is_paranoid":      char.get("is_paranoid",     False),
            "is_spy":           char.get("is_spy",          False),
            "is_fool":          char.get("is_fool",         False),
            "is_jester":        char.get("is_jester",       False),
            "is_undertaker":    char.get("is_undertaker",   False),
            "is_recluse":       char.get("is_recluse",      False),
            "alibi":            char.get("alibi",           None),
        }).execute().data[0]["id"]

        clues = [{
            "game_id":          game_id,
            "player_id":        player_id,
            "round_number":     c["round"],
            "content":          c.get("true_content") or c.get("content", ""),
            "poisoned_content": c.get("poisoned_content", ""),
            "is_poisoned":      False,
            "is_released":      False,
        } for c in char["clues"]]
        supabase.table("clues").insert(clues).execute()


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_game_prompt(
    theme: str, player_count: int, accomplice_count: int,
    include_drunk: bool, include_investigator: bool, include_poisoner: bool,
    include_paranoid: bool, include_spy: bool, include_fool: bool,
    include_undertaker: bool = False, include_recluse: bool = False,
    include_alibi_cards: bool = False,
) -> str:
    acc  = f"EXACTLY {accomplice_count} character(s) MUST have 'is_accomplice': true."
    drunk = (
        "EXACTLY ONE innocent character MUST have 'is_drunk': true. "
        "ALL of their clues (both true_content and poisoned_content) must be completely FALSE."
    ) if include_drunk else "NO characters may have 'is_drunk': true."
    inv = (
        "EXACTLY ONE innocent character MUST have 'is_investigator': true. "
        "Their Round 3 true_content MUST name two specific suspects: "
        "'Either [Killer Name] or [Innocent Name] is guilty.' Delivered at the final round."
    ) if include_investigator else "NO characters may have 'is_investigator': true."
    poi = (
        f"One of the {accomplice_count} accomplice character(s) MUST have both 'is_accomplice': true AND "
        "'is_poisoner': true simultaneously on the SAME character object. "
        "This is not a new character — it is an existing accomplice who also has the poisoner role. "
        "In their role_description add: '• Poisoner Ability: Each round you may secretly corrupt one player\\'s evidence on your device.'"
    ) if include_poisoner and accomplice_count > 0 else "NO characters may have 'is_poisoner': true."
    par = (
        "EXACTLY ONE innocent character MUST have 'is_paranoid': true. "
        "ALL their clues must point suspiciously at a specific OTHER innocent player, never the killer. "
        "In their role_description add: '• Paranoid Instinct: Your gut tells you that [name a specific innocent] is the killer — and it never lies.'"
    ) if include_paranoid else "NO characters may have 'is_paranoid': true."
    spy = (
        "EXACTLY ONE innocent character MUST have 'is_spy': true. "
        "In their role_description add: '• Spy Ability: Once per game you may secretly learn the true role of one other player. Use it wisely.'"
    ) if include_spy else "NO characters may have 'is_spy': true."
    fool = (
        "EXACTLY ONE innocent character MUST have 'is_fool': true. "
        "Write their role_description exactly like a killer — believable motive and a plan — "
        "but set 'is_killer': false and 'is_fool': true. Their clues are normal innocent clues. "
        "Only valid for 10+ player games."
    ) if include_fool and player_count >= 10 else "NO characters may have 'is_fool': true."
    undertaker = (
        "EXACTLY ONE innocent character MUST have 'is_undertaker': true. "
        "In their role_description add: '• Undertaker Ability: After the murder is revealed "
        "in Round 2, you will privately learn the true role of the victim.'"
    ) if include_undertaker else "NO characters may have 'is_undertaker': true."
    recluse = (
        "EXACTLY ONE innocent character MUST have 'is_recluse': true. "
        "This character IS innocent — set all evil flags to false. "
        "In their role_description add: '• Recluse: You are innocent, but something about "
        "you sets off every alarm. Detection abilities will misread you as guilty.'"
    ) if include_recluse else "NO characters may have 'is_recluse': true."
    alibi = (
        "Every character MUST have an 'alibi' field — one sentence describing where they were "
        "at the time of the murder. Write as first person ('You were…'). "
        "Innocent alibis must be true and consistent with the master story. "
        "The killer's and accomplice alibis must be false and contradict physical evidence."
    ) if include_alibi_cards else "Do NOT include an 'alibi' field on any character."

    return f"""
    Create a highly interactive social deduction murder mystery for {player_count} players. Theme: {theme}.

    --- STRICT RULES ---
    1. NO PLACEHOLDERS. Fill every detail. Never write "[Name]", "[Killer]", "[Motive]" etc.
    2. TOTAL CHARACTERS: The "characters" array MUST contain EXACTLY {player_count} objects.
       Count them before returning. {player_count} characters. Not {player_count + 1}. Not {player_count + 2}. Exactly {player_count}.
       Special roles are LABELS applied to characters that already exist. They are NOT new characters.
    3. ROLE COUNTS — every role marked "EXACTLY ONE" is MANDATORY. Skipping one is a failure:
       - EXACTLY 1 character must have "is_killer": true.
       - {acc}
       - {drunk}
       - {inv}
       - {poi}
       - {par}
       - {spy}
       - {fool}
       - {undertaker}
       - {recluse}
       - {alibi}
       Every role above marked "EXACTLY ONE" MUST appear assigned to one of the {player_count} characters.
    4. CLUE RULES — read every word carefully:
       a) ALL clues must be written as first-person observations about a THIRD PARTY — never about oneself.
       b) INNOCENT clues (true_content): subtle and indirect. Do NOT name the killer directly.
          Describe suspicious behaviour, overheard conversation, or a physical detail.
          Round 2 clues = something seen or heard. Round 3 clues = something physical found.
       c) INNOCENT clues (poisoned_content): equally indirect, equally plausible, but pointing at a DIFFERENT innocent.
       d) KILLER and ACCOMPLICE clues: convincing false alibis or observations framing an innocent.
       e) NEVER use the words "killer", "accomplice", "murderer", "guilty", or "evidence" inside a clue.
       f) POISONER: mark both "is_accomplice": true AND "is_poisoner": true on the SAME character.
    5. PUBLIC CLUE: Only ONE public clue at Round 3 (the final round only). No Round 2 public clue.
    6. GHOST CLUE RULES — every character must have a meaningful ghost_clue:
       a) Ghost clues are revealed ONLY after that character is eliminated — treat them as a final confession or dying revelation.
       b) INNOCENT characters: their ghost_clue MUST name a specific suspicious act directly involving the killer or an accomplice
          (use their actual character name). Never vague. Example: "I saw [Killer Name] pocketing the missing key minutes after the body was found."
       c) KILLER and ACCOMPLICE characters: their ghost_clue MUST frame a specific INNOCENT player with a believable but false accusation.
       d) NEVER write ghost clues like "trust no one", "look closer", or other content-free warnings.
          Every ghost clue must name a specific character and a specific observable act.

    BEFORE RETURNING verify:
    [ ] characters array has exactly {player_count} objects
    [ ] Exactly 1 has "is_killer": true
    [ ] Every role marked "EXACTLY ONE" above is assigned
    [ ] is_poisoner and is_accomplice are both true on the SAME character object
    [ ] No clue text contains: killer, accomplice, murderer, guilty, evidence
    [ ] No clue is about the character themselves

    Return ONLY a JSON object with this exact structure:
    {{
        "theme_title": "A catchy 2-4 word title",
        "short_description": "A dark atmospheric 2-sentence description of the setting and tension.",
        "master_story": {{
            "background": "• Point 1\\n• Point 2",
            "the_murder": "• Point 1\\n• Point 2",
            "the_solution": "• Point 1\\n• Point 2",
            "public_clues": [
                {{"round": 3, "content": "A single dramatic public clue revealed to ALL players at Round 3."}}
            ]
        }},
        "characters": [
            {{
                "name": "Character Name",
                "public_summary": "1-sentence summary of what everyone knows about this person.",
                "role_description": "• Personality: (how to act)\\n• Connection: (to the victim)\\n• Dark Secret: (something they hide)",
                "is_killer": false, "is_accomplice": false, "is_investigator": false,
                "is_drunk": false, "is_poisoner": false, "is_paranoid": false,
                "is_spy": false, "is_fool": false, "is_jester": false,
                "is_undertaker": false, "is_recluse": false,
                "ghost_clue": "A revealing clue about the killer or accomplice, only unlocked after this character is murdered.",
                "alibi": "(include only if alibi cards enabled — else omit this field)",
                "clues": [
                    {{
                        "round": 2,
                        "true_content": "You noticed that [specific other character name] [concrete observable action pointing toward killer].",
                        "poisoned_content": "You noticed that [different innocent name] [false but plausible observable detail]."
                    }},
                    {{
                        "round": 3,
                        "true_content": "You found [specific physical evidence] connecting to something suspicious about [another character name].",
                        "poisoned_content": "You found [fabricated evidence] near [innocent character name]'s belongings."
                    }}
                ]
            }}
        ]
    }}
    """


def generate_game_with_ai(prompt: str) -> dict:
    """Call Gemini and return parsed game data."""
    response = gemini.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


# ── Undertaker result (called from release-round after Round 2) ──────────────

def apply_undertaker_result(game_id: str):
    """Finds who died in Round 2 and tells the undertaker their true role."""
    undertaker = supabase.table("players").select("id").eq(
        "game_id", game_id).eq("is_undertaker", True).execute()
    if not undertaker.data:
        return
    dead = supabase.table("players").select(
        "character_name, is_killer, is_accomplice, is_poisoner, is_investigator, "
        "is_drunk, is_paranoid, is_spy, is_fool, is_jester, is_recluse, is_undertaker"
    ).eq("game_id", game_id).eq("death_round", 2).execute()
    if not dead.data:
        return
    v = dead.data[0]
    if   v["is_killer"]:               role = "Killer"
    elif v.get("is_poisoner"):         role = "Poisoner (Accomplice)"
    elif v["is_accomplice"]:           role = "Accomplice"
    elif v.get("is_investigator"):     role = "Investigator"
    elif v.get("is_drunk"):            role = "Drunk"
    elif v.get("is_paranoid"):         role = "Paranoid"
    elif v.get("is_spy"):              role = "Spy"
    elif v.get("is_fool"):             role = "Fool (Innocent)"
    elif v.get("is_jester"):           role = "Jester"
    elif v.get("is_recluse"):          role = "Recluse (was Innocent)"
    elif v.get("is_undertaker"):       role = "Undertaker (was Innocent)"
    else:                              role = "Innocent"
    supabase.table("players").update({
        "undertaker_result": f"The victim {v['character_name']} was: {role}"
    }).eq("id", undertaker.data[0]["id"]).execute()


# ── Poison swap (called from release-round) ───────────────────────────────────

def apply_poison_swap(game_id: str, round_num: int):
    """If poisoner has a target locked, swap their clue to the poisoned version."""
    poisoner_res = supabase.table("players").select("poison_target").eq(
        "game_id", game_id).eq("is_poisoner", True).execute()

    if not poisoner_res.data or not poisoner_res.data[0].get("poison_target"):
        return

    target_name = poisoner_res.data[0]["poison_target"]
    target_res  = supabase.table("players").select("id").eq(
        "game_id", game_id).eq("character_name", target_name).execute()

    if target_res.data:
        target_id = target_res.data[0]["id"]
        clue_res  = supabase.table("clues").select("id, poisoned_content").eq(
            "player_id", target_id).eq("round_number", round_num).execute()

        if clue_res.data and clue_res.data[0].get("poisoned_content"):
            supabase.table("clues").update({
                "content":     clue_res.data[0]["poisoned_content"],
                "is_poisoned": True,
            }).eq("id", clue_res.data[0]["id"]).execute()

    # Reset — poisoner must re-select each round
    supabase.table("players").update({"poison_target": None}).eq(
        "game_id", game_id).eq("is_poisoner", True).execute()


# ── Recap builder (called from end-game) ─────────────────────────────────────

def build_recap(game_id: str) -> str:
    """Generate a noir recap via Gemini. Returns empty string for preset games."""
    game_res = supabase.table("games").select(
        "theme_title, master_story, is_preset"
    ).eq("id", game_id).execute()
    all_players = supabase.table("players").select("*").eq("game_id", game_id).execute()

    game_row    = game_res.data[0]
    if game_row.get("is_preset"):
        return ""   # Preset games have hardcoded stories — no AI recap needed

    theme_title = game_row.get("theme_title", "the manor")
    try:    master_story = json.loads(game_row["master_story"])
    except: master_story = {}

    killer      = next((p for p in all_players.data if p["is_killer"]), None)
    accomplices = [p for p in all_players.data if p.get("is_accomplice") and not p["is_killer"]]
    dead        = [p for p in all_players.data if p.get("is_dead")]
    poisoner    = next((p for p in all_players.data if p.get("is_poisoner")), None)
    paranoid    = next((p for p in all_players.data if p.get("is_paranoid")), None)
    spy         = next((p for p in all_players.data if p.get("is_spy")), None)
    fool        = next((p for p in all_players.data if p.get("is_fool")), None)
    jester      = next((p for p in all_players.data if p.get("is_jester")), None)
    undertaker  = next((p for p in all_players.data if p.get("is_undertaker")), None)
    recluse     = next((p for p in all_players.data if p.get("is_recluse")), None)

    killer_name   = killer["character_name"] if killer else "Unknown"
    killer_player = killer["claimed_by_user"] if killer else "?"

    alive_innocents = [p for p in all_players.data
                       if not p["is_killer"] and not p.get("is_accomplice") and not p.get("is_dead")]
    correct_votes   = [p for p in alive_innocents if p.get("voted_for") == killer_name]
    killer_caught   = len(correct_votes) >= max(1, len(alive_innocents) / 2.0)

    jester_name  = jester["character_name"] if jester else None
    jester_votes = sum(1 for p in all_players.data if p.get("voted_for") == jester_name) if jester_name else 0
    jester_won   = bool(jester_name and jester_votes >= max(1, len(alive_innocents) / 2.0))

    deaths_text     = ", ".join(p["character_name"] for p in dead) or "nobody"
    accomplice_text = ", ".join(p["character_name"] for p in accomplices) or "none"
    poisoner_text   = f"{poisoner['character_name']} secretly corrupted evidence each round" if poisoner else "no poisoner"
    paranoid_text   = f"{paranoid['character_name']} was convinced the wrong person was guilty" if paranoid else "no paranoid"
    spy_text        = f"{spy['character_name']} was secretly gathering intelligence" if spy else "no spy"
    fool_text       = f"{fool['character_name']} believed themselves to be the killer but was innocent" if fool else "no fool"
    undertaker_text = f"{undertaker['character_name']} was the Undertaker and secretly learned the victim's true role" if undertaker else "no undertaker"
    recluse_text    = f"{recluse['character_name']} was the Recluse — innocent but registered as guilty to all detection" if recluse else "no recluse"
    jester_text     = f"{jester_name} was the Jester and tricked everyone into voting for them!" if jester_won else ("no jester" if not jester_name else f"{jester_name} was the Jester but failed to get voted out")
    outcome_text    = ("The Jester won — everyone voted for the wrong person!" if jester_won
                       else ("The killer was caught" if killer_caught else f"{killer_name} got away with murder"))

    prompt = f"""
    Write a noir-style post-game story recap for a murder mystery called "{theme_title}".
    Write exactly 5 paragraphs of rich atmospheric prose. Each paragraph 4-6 sentences.
    Use character names only, never player names. No markdown, headers, or bullet points.

    Structure:
    - Paragraph 1: Set the scene — the setting, mood, and discovery of the murder.
    - Paragraph 2: The web of suspicion — who suspected whom, red herrings, how special roles stirred confusion.
    - Paragraph 3: Behind the scenes — what the killer and accomplices were really doing.
    - Paragraph 4: The turning point — ghost clue, investigator's ping, public announcement, or exile vote.
    - Paragraph 5: The verdict — final vote, outcome, cinematic closing line.

    Facts to weave in naturally:
    - Killer: {killer_name} (played by {killer_player})
    - Accomplices: {accomplice_text}
    - {poisoner_text}
    - {paranoid_text}
    - {spy_text}
    - {fool_text}
    - {jester_text}
    - {undertaker_text}
    - {recluse_text}
    - Characters who died: {deaths_text}
    - Outcome: {outcome_text}
    - The true story: {master_story.get("the_solution", "")}
    """

    try:
        resp = gemini.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return resp.text.strip()
    except Exception:
        return (
            f"The night of secrets finally came to an end at {theme_title}. "
            f"{killer_name} had woven an intricate web of lies — and "
            f"{'justice caught up with them at last' if killer_caught else 'walked free into the darkness'}."
        )


# ── Outcome calculator (called from end-game and dashboard) ──────────────────

def compute_outcome(all_players_data: list) -> dict:
    """Returns killer_caught, jester_won, jester_name for a finished game."""
    killer_name = next((p["character_name"] for p in all_players_data if p["is_killer"]), "Unknown")
    jester      = next((p for p in all_players_data if p.get("is_jester")), None)
    jester_name = jester["character_name"] if jester else None

    alive_innocents = [p for p in all_players_data
                       if not p["is_killer"] and not p.get("is_accomplice") and not p.get("is_dead")]
    threshold = max(1, len(alive_innocents) / 2.0)

    correct_votes = sum(1 for p in alive_innocents if p.get("voted_for") == killer_name)
    killer_caught = correct_votes >= threshold

    jester_votes = sum(1 for p in all_players_data if p.get("voted_for") == jester_name) if jester_name else 0
    jester_won   = bool(jester_name and jester_votes >= threshold)

    return {
        "killer_caught": killer_caught,
        "jester_won":    jester_won,
        "jester_name":   jester_name,
        "killer_name":   killer_name,
    }


# ── Crisis mechanics ──────────────────────────────────────────────────────────

CRISIS_DILEMMAS = {
    "The Cursed Galleon": {
        "question": "A second body has been spotted tangled in the anchor chain. Haul it up in full view of the crew, or cut it loose quietly to preserve order?",
        "safe":      "Haul it up — full transparency with the crew",
        "dangerous": "Cut it loose — control the information",
    },
    "Operation Nusantara": {
        "question": "The building's communications have been cut. Enforce a complete comms blackout until the killer is found, or allow each delegation to use their own encrypted channels?",
        "safe":      "Enforce comms blackout — nobody talks to the outside",
        "dangerous": "Allow individual encrypted channels — trust the delegations",
    },
    "The Last Carriage": {
        "question": "The train is still accelerating. Stop at the next station and wait for authorities — or keep moving to prevent the saboteur from slipping away in the chaos?",
        "safe":      "Stop and wait — let the authorities handle it",
        "dangerous": "Keep moving — don't let them escape",
    },
    "Dead on Air": {
        "question": "Network security has arrived at the studio entrance — Marcus's emergency alert went out before he died. Let them in and hand over the investigation, or lock the doors and finish the live broadcast for the remaining forty minutes?",
        "safe":      "Let security in — hand over immediately",
        "dangerous": "Lock them out — finish the broadcast first",
    },
    "The Coastal Protocol": {
        "question": "The station's automated emergency beacon has activated and is transmitting a distress signal to the coast guard. Override and disable it — or allow the signal to continue and let external authorities respond at dawn?",
        "safe":      "Let it run — coast guard arrives in the morning",
        "dangerous": "Override the beacon — handle this internally",
    },
    "The Séance at Blackwood Hall": {
        "question": "The planchette has begun moving on its own — spelling out a name and the words 'east wing'. Do you follow the spirit's instruction and search the east wing, or dismiss it as manipulation and keep the group together?",
        "safe":      "Stay together — do not let the group be split by a trick",
        "dangerous": "Search the east wing — follow what the spirit is showing us",
    },
}


def get_crisis_dilemma(theme_title: str) -> dict:
    """Return the crisis dilemma for a given theme title."""
    for key, dilemma in CRISIS_DILEMMAS.items():
        if key.lower() in theme_title.lower():
            return dilemma
    return {}
