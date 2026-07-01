"""
functions.py — All business logic for Whodunit.
Imported by main.py. No FastAPI routes here.
"""
import json
import logging
import random
import string
from fastapi import HTTPException, Header
from google import genai
from google.genai import types

log = logging.getLogger(__name__)
import os

# ── Objective pool ────────────────────────────────────────────────────────────
# Reference constant — mirrored in build_characters_prompt for Gemini.
# Objectives create innocent misdirection without changing the win condition.
OBJECTIVE_POOL = {
    "deflection": [
        "Before Round 3, ensure at least one other player has publicly named {target} as a suspect.",
        "Do not let {target} go an entire round without being questioned by someone at the table.",
    ],
    "protection": [
        "Ensure {target} is not voted for at the final vote.",
        "By Round 2, convince at least one other player that {target} could not have done this.",
    ],
    "information": [
        "Discover what role {target} claims to be before the final vote.",
        "Find out what {target}'s alibi is before Round 3.",
    ],
    "self_preservation": [
        "Do not be named as a suspect by more than two players during the entire game.",
        "Ensure at least one other player publicly accepts your alibi before the final vote.",
    ],
}

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
            "objective":        char.get("objective",       None),
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

    # Assign bluff roles after all players are in DB (queries by game_id)
    assign_bluff_roles(game_id, characters)


def assign_bluff_roles(game_id: str, characters: list):
    """Assign the killer and accomplices a fake innocent role to claim in conversation."""
    assigned_roles = set()
    for char in characters:
        if char.get("is_investigator"): assigned_roles.add("Investigator")
        if char.get("is_drunk"):        assigned_roles.add("Drunk")
        if char.get("is_paranoid"):     assigned_roles.add("Paranoid")
        if char.get("is_spy"):          assigned_roles.add("Spy")
        if char.get("is_undertaker"):   assigned_roles.add("Undertaker")
        if char.get("is_recluse"):      assigned_roles.add("Recluse")

    # Weight toward "Innocent" — most killers should claim a plain innocent role
    bluff_pool = ["Innocent", "Innocent", "Innocent"]
    all_special = ["Investigator", "Drunk", "Paranoid", "Spy", "Undertaker"]
    # Roles not in this game: safer bluff (no one can contradict by also claiming it)
    bluff_pool += [r for r in all_special if r not in assigned_roles]
    # Roles that are in the game: riskier but possible
    bluff_pool += list(assigned_roles)

    killers     = supabase.table("players").select("id").eq("game_id", game_id).eq("is_killer",     True).execute()
    accomplices = supabase.table("players").select("id").eq("game_id", game_id).eq("is_accomplice", True).execute()

    for p in killers.data + accomplices.data:
        supabase.table("players").update({"bluff_role": random.choice(bluff_pool)}).eq("id", p["id"]).execute()


# ── Layered prompt builders (Call 1 + Call 2) ────────────────────────────────

def build_skeleton_prompt(theme: str, player_count: int) -> str:
    """Call 1 of 2: Generate the story skeleton — timeline, evidence, motive only."""
    return f"""
    You are constructing the structural skeleton of a murder mystery.
    Do NOT write characters or clues yet. Only the underlying truth.

    Theme: {theme}
    Players: {player_count}

    Answer all five sections and return as JSON.

    SECTION 1 — "timeline"
    A list of 6-8 events from the evening in chronological order.
    Written as if a detective is reconstructing the night from physical evidence.
    Each event: {{"time": "22:15", "location": "specific named place", "event": "what exactly happened"}}
    The murder must appear at a specific time and place.
    At least 3 events must involve multiple characters being near each other.

    SECTION 2 — "motive"
    {{"grievance": "long-standing reason (months or years before tonight)",
      "trigger": "what happened TONIGHT that made waiting impossible"}}

    SECTION 3 — "physical_evidence"
    A list of exactly 5 specific objects or locations physically present in the setting.
    These anchor ALL clues — every clue must reference at least one item from this list.
    Each item: {{"name": "specific name", "location": "exactly where found",
                 "significance": "what it proves about the murder"}}

    SECTION 4 — "faction_knowledge"
    {{"killer_knows": "complete truth the killer knows about their crime",
      "accomplice_knows": "what the killer told the accomplice — may be slightly incomplete",
      "innocents_missed": "2-3 things innocents were near but didn't understand at the time"}}

    SECTION 5 — "damning_evidence"
    The single most conclusive piece of evidence against the killer.
    {{"what": "describe precisely",
      "why_missed": "why it was overlooked until Round 3",
      "recontextualises": "what earlier information this changes the meaning of"}}
    This becomes the Round 3 public clue.

    NO PLACEHOLDERS. Every field must contain specific, named, real content.
    Return ONLY valid JSON with keys: timeline, motive, physical_evidence, faction_knowledge, damning_evidence.
    """


def build_characters_prompt(
    theme: str,
    player_count: int,
    accomplice_count: int,
    skeleton: dict,
    include_drunk: bool,
    include_investigator: bool,
    include_poisoner: bool,
    include_paranoid: bool,
    include_spy: bool,
    include_fool: bool,
    include_undertaker: bool = False,
    include_recluse: bool = False,
) -> str:
    """Call 2 of 2: Generate characters and clues grounded in the skeleton."""
    acc        = (
        f"EXACTLY {accomplice_count} character(s) MUST have 'is_accomplice': true. "
        f"There must be {accomplice_count} separate character objects each with 'is_accomplice': true. "
        f"Count them before returning — if fewer than {accomplice_count}, you have made an error."
    )
    drunk      = ("EXACTLY ONE innocent MUST have 'is_drunk': true. ALL their clues (true and poisoned) must be FALSE."
                  ) if include_drunk else "NO characters may have 'is_drunk': true."
    inv        = ("EXACTLY ONE innocent MUST have 'is_investigator': true. Their Round 3 true_content MUST name "
                  "exactly two suspects: 'Either [Name] or [Name] is responsible.'"
                  ) if include_investigator else "NO characters may have 'is_investigator': true."
    poi        = (f"ONE of those {accomplice_count} accomplice characters must ADDITIONALLY have 'is_poisoner': true. "
                  f"Does NOT reduce the accomplice count — still need EXACTLY {accomplice_count} with 'is_accomplice': true. "
                  "Add to role_description: '• Poisoner Ability: Each round you may secretly corrupt one player\\'s evidence on your device.'"
                  ) if include_poisoner and accomplice_count > 0 else "NO characters may have 'is_poisoner': true."
    par        = ("EXACTLY ONE innocent MUST have 'is_paranoid': true. ALL clues point at a specific OTHER innocent. "
                  "Add: '• Paranoid Instinct: Your gut tells you that [specific innocent name] is responsible.'"
                  ) if include_paranoid else "NO characters may have 'is_paranoid': true."
    spy        = ("EXACTLY ONE innocent MUST have 'is_spy': true. "
                  "Add: '• Spy Ability: Once per game, secretly learn one other player\\'s true role on your device.'"
                  ) if include_spy else "NO characters may have 'is_spy': true."
    fool       = ("EXACTLY ONE innocent MUST have 'is_fool': true. Write role_description like a killer but set "
                  "is_killer: false, is_fool: true. Normal innocent clues. Only for 10+ player games."
                  ) if include_fool and player_count >= 10 else "NO characters may have 'is_fool': true."
    undertaker = ("EXACTLY ONE innocent MUST have 'is_undertaker': true. "
                  "Add: '• Undertaker Ability: After Round 2 murder is revealed, you privately learn the victim\\'s true role.'"
                  ) if include_undertaker else "NO characters may have 'is_undertaker': true."
    recluse    = ("EXACTLY ONE innocent MUST have 'is_recluse': true. All evil flags false. "
                  "Add: '• Recluse: You are innocent, but detection abilities misread you as guilty. Never told this is happening.'"
                  ) if include_recluse else "NO characters may have 'is_recluse': true."

    evidence_list = "\n".join(
        f"  {i+1}. {e['name']} (at {e['location']}) — {e['significance']}"
        for i, e in enumerate(skeleton.get("physical_evidence", []))
    )
    timeline_str = "\n".join(
        f"  {t['time']} [{t['location']}] {t['event']}"
        for t in skeleton.get("timeline", [])
    )
    damning = skeleton.get("damning_evidence", {}).get("what", "A conclusive piece of physical evidence.")

    return f"""
    You are writing characters and clues for a murder mystery.
    The story skeleton below is FIXED — build within it exactly. Do not contradict it.

    Theme: {theme} | Players: {player_count}

    ══ FIXED SKELETON ══════════════════════════════════════════════

    TIMELINE (what actually happened):
{timeline_str}

    PHYSICAL EVIDENCE (every clue MUST reference at least one):
{evidence_list}

    KILLER'S MOTIVE:
    Grievance: {skeleton.get('motive', {}).get('grievance', '')}
    Trigger:   {skeleton.get('motive', {}).get('trigger', '')}

    DAMNING EVIDENCE (becomes Round 3 public clue):
    {damning}

    ══ ROLE ASSIGNMENTS ════════════════════════════════════════════

    TOTAL CHARACTERS: Exactly {player_count}. Count before returning.
    Special roles are labels on existing characters — NOT extra characters.

    - EXACTLY 1 character: "is_killer": true
    - {acc}
    - {drunk}
    - {inv}
    - {poi}
    - {par}
    - {spy}
    - {fool}
    - {undertaker}
    - {recluse}

    ══ CHARACTER REQUIREMENTS ══════════════════════════════════════

    For each character write:

    1. "name" and "public_summary" (1 sentence, what everyone knows)

    2. "role_description" with EXACTLY these four bullets:
       • Personality: how to perform this character at the table
       • Connection: relationship to the victim
       • Dark Secret: something personal hidden UNRELATED to the murder
       • Tonight's Agenda: what they personally wanted from being here tonight
       Killer and accomplice role_description MUST also include:
       • Cover Story: If asked your role, you may claim to be an innocent role.
         Prepare a believable story about what that role's clue supposedly told you.

    3. "alibi": ONE sentence, first person ("You were…"), referencing a REAL location
       and REAL time window from the skeleton timeline.
       REQUIREMENT: At least two pairs of characters must share the same location or
       time window — one confirming, one contradicting the other.
       Killer and accomplice alibis are false and contradict physical evidence.

    4. "objective": ONE private goal. Replace {{target}} with a specific character name.
       Assign objectives so at least two innocent pairs have conflicting objectives
       (one protecting someone the other is steering suspicion toward).

       DEFLECTION: "Before Round 3, ensure at least one other player has publicly named {{target}} as a suspect."
                   "Do not let {{target}} go an entire round without being questioned by someone."
       PROTECTION: "Ensure {{target}} is not voted for at the final vote."
                   "By Round 2, convince at least one other player that {{target}} could not have done this."
       INFORMATION: "Discover what role {{target}} claims to be before the final vote."
                    "Find out what {{target}}'s alibi is before Round 3."
       SELF-PRESERVATION: "Do not be named as a suspect by more than two players during the game."
                          "Ensure at least one other player publicly accepts your alibi before the final vote."
       Killer objective: "Ensure {{specific innocent}} receives at least one vote at the final count."
       Accomplice objective: "Before Round 3, make at least one innocent player publicly doubt {{target}}."

    5. "ghost_clue": First person, from beyond death.
       Must reference a SPECIFIC item from the physical evidence list.
       Must name a specific character and a specific observable act.
       NEVER write vague ghost clues like "trust no one" or "look closer."
       Innocent ghost clues expose something about the killer or accomplice.
       Killer/accomplice ghost clues frame a specific innocent.

    6. "clues": Round 2 and Round 3.
       CLUE WEB — before writing, identify 2-3 shared moments from the timeline where
       multiple characters were near each other or near the same evidence.
       Write clues as different perspectives on THOSE SAME MOMENTS.
       Each clue MUST reference at least one item from the physical evidence list.
       At least two pairs must have directly contradicting clues about the same event.
       NEVER use: killer, accomplice, murderer, guilty, evidence, suspect
       NEVER write a clue about the character themselves.

    ══ VERIFICATION BEFORE RETURNING ═══════════════════════════════

    [ ] characters array has exactly {player_count} objects
    [ ] Exactly 1 has "is_killer": true
    [ ] Exactly {accomplice_count} have "is_accomplice": true (poisoner does NOT reduce this count)
    [ ] Every mandatory role is assigned
    [ ] is_poisoner and is_accomplice both true on SAME character
    [ ] Every alibi references a real location from the timeline
    [ ] At least 2 character pairs have alibis referencing the same place/time
    [ ] Every clue references at least 1 item from the physical evidence list
    [ ] At least 2 character pairs have directly contradicting clues
    [ ] At least 2 innocent pairs have conflicting objectives
    [ ] No clue contains: killer, accomplice, murderer, guilty, evidence

    Return ONLY a JSON object:
    {{
        "theme_title": "A catchy 2-4 word title",
        "short_description": "A dark atmospheric 2-sentence description.",
        "master_story": {{
            "background": "• Point 1\\n• Point 2\\n• Point 3",
            "the_murder": "• Point 1\\n• Point 2\\n• Point 3",
            "the_solution": "• Point 1\\n• Point 2\\n• Point 3",
            "public_clues": [{{"round": 3, "content": "{damning}"}}]
        }},
        "characters": [
            {{
                "name": "Character Name",
                "public_summary": "1-sentence public summary.",
                "role_description": "• Personality: ...\\n• Connection: ...\\n• Dark Secret: ...\\n• Tonight's Agenda: ...",
                "is_killer": false, "is_accomplice": false, "is_investigator": false,
                "is_drunk": false, "is_poisoner": false, "is_paranoid": false,
                "is_spy": false, "is_fool": false, "is_jester": false,
                "is_undertaker": false, "is_recluse": false,
                "alibi": "You were [location] at [time] — [what you were doing].",
                "objective": "One private goal with a specific character name filled in for {{target}}.",
                "ghost_clue": "First person, names a character, references a physical evidence item.",
                "clues": [
                    {{
                        "round": 2,
                        "true_content": "You [observed/heard] [character name] [action] near [evidence item] at [time from timeline].",
                        "poisoned_content": "You [observed/heard] [different innocent name] [false plausible action] near [same location]."
                    }},
                    {{
                        "round": 3,
                        "true_content": "You found [evidence item] [detail connecting it to a character].",
                        "poisoned_content": "You found [same/related evidence item] [false detail pointing at an innocent]."
                    }}
                ]
            }}
        ]
    }}
    """


def generate_game_with_ai_layered(
    theme: str,
    player_count: int,
    accomplice_count: int,
    include_drunk: bool,
    include_investigator: bool,
    include_poisoner: bool,
    include_paranoid: bool,
    include_spy: bool,
    include_fool: bool,
    include_undertaker: bool = False,
    include_recluse: bool = False,
) -> dict:
    """
    Two-call Gemini generation.
    Call 1: story skeleton (timeline, evidence, motive).
    Call 2: characters and clues grounded in the skeleton.
    """
    # ── Call 1: Skeleton ──────────────────────────────────────────────────────
    log.info("[AI FORGE] Call 1/2 — skeleton | theme=%r | players=%d", theme, player_count)
    skeleton_prompt = build_skeleton_prompt(theme, player_count)
    skel_resp = gemini.models.generate_content(
        model=GEMINI_MODEL, contents=skeleton_prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    try:
        skeleton = json.loads(skel_resp.text)
    except json.JSONDecodeError as e:
        log.error("[AI FORGE] Skeleton JSON failed | error=%s | preview=%r", e, skel_resp.text[:200])
        raise
    log.info("[AI FORGE] Skeleton OK | timeline=%d events | evidence=%d items",
             len(skeleton.get("timeline", [])), len(skeleton.get("physical_evidence", [])))

    # ── Call 2: Characters ────────────────────────────────────────────────────
    log.info("[AI FORGE] Call 2/2 — characters | player_count=%d", player_count)
    chars_prompt = build_characters_prompt(
        theme, player_count, accomplice_count, skeleton,
        include_drunk, include_investigator, include_poisoner,
        include_paranoid, include_spy, include_fool,
        include_undertaker, include_recluse,
    )
    chars_resp = gemini.models.generate_content(
        model=GEMINI_MODEL, contents=chars_prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    try:
        game_data = json.loads(chars_resp.text)
    except json.JSONDecodeError as e:
        log.error("[AI FORGE] Characters JSON failed | error=%s | preview=%r", e, chars_resp.text[:200])
        raise
    evil = [c["name"] for c in game_data.get("characters", []) if c.get("is_killer") or c.get("is_accomplice")]
    log.info("[AI FORGE] OK | title=%r | characters=%d | evil=%s",
             game_data.get("theme_title"), len(game_data.get("characters", [])), evil)
    return game_data


# ── Killer awakening (amnesia games — called from release_clues at Round 2) ──

def apply_killer_awakening(game_id: str):
    """For amnesia games: set is_awakened=True on the killer at Round 2."""
    game = supabase.table("games").select("is_amnesia_game").eq("id", game_id).execute()
    if not game.data or not game.data[0].get("is_amnesia_game"):
        return
    supabase.table("players").update({"is_awakened": True}).eq(
        "game_id", game_id).eq("is_killer", True).execute()
    log.info("[AMNESIA] Killer awakened | game=%s", game_id)


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
        log.info("[POISON] No target set | game=%s | round=%d", game_id, round_num)
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
            log.info("[POISON] Swapped clue for %r at R%d | game=%s", target_name, round_num, game_id)
        else:
            log.warning("[POISON] No poisoned_content found for %r at R%d | game=%s", target_name, round_num, game_id)
    else:
        log.warning("[POISON] Target %r not found in game=%s", target_name, game_id)

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
        log.info("[RECAP] Skipped — preset game | game=%s", game_id)
        return ""

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

    log.info("[RECAP] Generating | game=%s | killer=%r | outcome=%s", game_id, killer_name, outcome_text)
    try:
        resp = gemini.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        log.info("[RECAP] OK | game=%s | length=%d chars", game_id, len(resp.text))
        return resp.text.strip()
    except Exception as e:
        log.error("[RECAP] FAILED | game=%s | error=%s: %s", game_id, type(e).__name__, e)
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
