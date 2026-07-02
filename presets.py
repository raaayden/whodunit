"""
presets.py — Hardcoded game templates for the Experimental Lab.
Add new presets here. main.py imports spawn_preset_game() and PRESET_REGISTRY.
"""
import json
from fastapi import HTTPException, Request

# Imported from functions.py at runtime via init_preset_clients()
supabase             = None
generate_key         = None
assign_bluff_roles   = None


def init_preset_clients(_supabase, _generate_key, _assign_bluff_roles):
    global supabase, generate_key, assign_bluff_roles
    supabase             = _supabase
    generate_key         = _generate_key
    assign_bluff_roles   = _assign_bluff_roles


# ── Registry ──────────────────────────────────────────────────────────────────
# Add new presets here. Key = URL slug, value = template dict.

PRESET_REGISTRY: dict[str, dict] = {}   # populated below


# ── Shared helpers ────────────────────────────────────────────────────────────

def _register(slug: str, template: dict):
    PRESET_REGISTRY[slug] = template


def spawn_preset_game(request: Request, preset_id: str) -> dict:
    if preset_id not in PRESET_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")

    template   = PRESET_REGISTRY[preset_id]
    is_crisis  = template.get("is_crisis",  False)
    is_amnesia = template.get("is_amnesia", False)

    game_insert = supabase.table("games").insert({
        "theme":             template["theme_title"],
        "theme_title":       template["theme_title"],
        "short_description": template["short_description"],
        "master_story":      json.dumps(template["master_story"]),
        "is_crisis_game":    is_crisis,
        "is_amnesia_game":   is_amnesia,
        "is_preset":         True,
    }).execute()
    game_id = game_insert.data[0]["id"]

    for char in template["characters"]:
        player_id = supabase.table("players").insert({
            "game_id":          game_id,
            "access_key":       generate_key(),
            "character_name":   char["name"],
            "role_description": char["role_description"],
            "public_summary":   char["public_summary"],
            "ghost_clue":       char.get("ghost_clue", "The spirits are silent."),
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
            "is_awakened":      False,
            "memory_fragments": [],
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

    assign_bluff_roles(game_id, template["characters"])

    return {
        "message":   f"Preset '{template['theme_title']}' spawned!",
        "game_id":   game_id,
        "room_url":  f"{request.base_url}room/{game_id}",
        "is_crisis": is_crisis,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PRESET 1 — The Cursed Galleon (8 players, pirate, has jester)
# ══════════════════════════════════════════════════════════════════════════════

_register("cursed_galleon", {
    "is_crisis": False,
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
            "role_description": "• Personality: Authoritative, deflects blame onto others, quick to remind people of your rank\n• Connection: Diego was your first mate and the only one who knew about the stolen gold\n• Dark Secret: You have been siphoning treasure to pay Blackthorn the pirate lord — Diego found out",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your cabin reviewing the course charts for the final stretch to port — but the helmsman knows you left your station for over twenty minutes during the height of the storm.",
            "objective": "Ensure Blind Pete the Bosun receives at least one vote at the final count.",
            "ghost_clue": "The night Diego died, he slipped a note under my cabin door. It read: 'I know what you took from the chest. Meet me at the bow at midnight or I go to the crew.' I burned it at dawn.",
            "clues": [
                {"round": 2, "true_content": "You heard the surgeon muttering that the wound on Diego's head was consistent with a belaying pin — and you made sure to act surprised.", "poisoned_content": "You saw the cook scrubbing something off the galley floor the morning after the storm."},
                {"round": 3, "true_content": "You told the crew Diego slipped during the storm, but three sailors saw the body and noticed the bruising pattern did not match a fall.", "poisoned_content": "You overheard Mad Meg whispering to the gunner about something she had seen below deck the night before."}
            ]
        },
        {
            "name": "Scarlett Vane",
            "public_summary": "The ship's sharp-eyed navigator, trusted by the captain and respected by the crew for getting them out of dangerous waters.",
            "role_description": "• Personality: Calm and calculating, always seem to have an angle, never volunteer information\n• Connection: The captain cut you in on the stolen gold — you have as much to lose as he does\n• Dark Secret: You helped the captain dispose of evidence after the murder",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the navigation table charting the course all night without interruption — but you left your post for nearly an hour around midnight, and the helmsman saw you go.",
            "objective": "Before Round 3, make at least one player publicly question Copper Jenny the Cook's alibi.",
            "ghost_clue": "Scarlett Vane helped the captain throw something overboard before sunrise. I saw her from the crow's nest but said nothing — I was afraid.",
            "clues": [
                {"round": 2, "true_content": "You helped the captain adjust the ship's log to show Diego was on watch duty during the storm — a lie, but a useful one.", "poisoned_content": "You noticed the gunpowder master acting strangely nervous during the morning headcount."},
                {"round": 3, "true_content": "You told the crew you were charting the course all night, but the helmsman knows you left your post for nearly an hour around midnight.", "poisoned_content": "You saw the ship's surgeon pocket something small and metallic when he finished examining the body."}
            ]
        },
        {
            "name": "Blind Pete the Bosun",
            "public_summary": "The half-blind but sharp-eared bosun who has sailed with the crew for twenty years and misses nothing despite his poor eyesight.",
            "role_description": "• Personality: Gruff, nostalgic, uses humour to deflect — but deeply loyal to the crew\n• Connection: Diego was like a son to you; you taught him everything he knew about the sea\n• Dark Secret: You have been smuggling personal rum rations to sell at port — Diego knew and protected you",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": True,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your bunk below decks for the entire storm, as any sensible man would be — you heard nothing unusual, which tells you nothing useful.",
            "objective": "Ensure Dr. Silas Crowe is not voted for at the final vote.",
            "ghost_clue": "Old Pete was the last one I trusted. His clue is false — the rum has clouded everything he thinks he saw.",
            "clues": [
                {"round": 2, "true_content": "You swear you heard the surgeon and the gunpowder master arguing near the hold the night Diego died, but the rum makes everything blurry.", "poisoned_content": "You are certain you saw Mad Meg climbing back from the bow just before the storm peaked, soaking wet and out of breath."},
                {"round": 3, "true_content": "You remember seeing two figures near the bow just before midnight — it might have been the captain and the navigator, or it might have been the moonlight playing tricks.", "poisoned_content": "You found a torn piece of cloth near the anchor chain that looks like it came from the cook's apron."}
            ]
        },
        {
            "name": "Mad Meg the Gunpowder Master",
            "public_summary": "The volatile and unpredictable keeper of the ship's cannons, feared for her temper and respected for her accuracy.",
            "role_description": "• Personality: Loud, confrontational, always the first to accuse — and secretly terrified of being accused yourself\n• Connection: Diego caught you stealing powder to sell at port and threatened to report you\n• Dark Secret: You had a powerful motive to silence Diego, but you did not kill him — you just wished you had",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": True, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the powder stores from dusk to dawn securing the barrels against the storm — three of the crew can confirm you did not leave that section of the hold.",
            "objective": "Do not let Dr. Silas Crowe go an entire round without being questioned by someone at the table.",
            "ghost_clue": "Meg had nothing to do with my death. But she knows something she is not saying about who visited the captain's cabin the night I died.",
            "clues": [
                {"round": 2, "true_content": "You are absolutely convinced the ship's surgeon did it — the way he examined the body was too calm, too practiced, like he had seen it before.", "poisoned_content": "You are certain the cook is behind it — the man had Diego's blood on his boots the morning after, you are sure of it."},
                {"round": 3, "true_content": "You know in your gut it was the surgeon — you just cannot explain why yet, but your instincts have never been wrong on open water.", "poisoned_content": "The cook avoided eye contact at breakfast and that proves everything you already suspected."}
            ]
        },
        {
            "name": "Dr. Silas Crowe",
            "public_summary": "The ship's soft-spoken surgeon, recruited in Tortuga under mysterious circumstances, who keeps detailed journals no one is allowed to read.",
            "role_description": "• Personality: Precise, quiet, answers every question with another question\n• Connection: You treated Diego for a chest wound six months ago and he confided secrets to you\n• Dark Secret: You are actually a spy for the governor, documenting the stolen treasure for a future seizure",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": True, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your surgery writing case notes by lantern light throughout the storm — you heard the rain and nothing else until the body was found at dawn.",
            "objective": "Discover what role Copper Jenny the Cook claims to be before the final vote.",
            "ghost_clue": "Dr. Crowe examined my body with surgical precision. He noted the angle of the blow — something that only someone trained in anatomy would understand the significance of.",
            "clues": [
                {"round": 2, "true_content": "During your examination of Diego's body, you noticed a faint smudge of tar on his collar that matches the belaying pin storage rack near the captain's cabin.", "poisoned_content": "You noticed that the navigator's logbook had a page torn out — the entry for the night of the murder is missing."},
                {"round": 3, "true_content": "You documented in your journal that the force and angle of the blow could only have been delivered by someone taller than average standing directly behind the victim — consistent with the captain.", "poisoned_content": "Your journal notes suggest the cook had access to the galley belaying pin and no alibi for the early morning hours."}
            ]
        },
        {
            "name": "Copper Jenny the Cook",
            "public_summary": "The resourceful ship's cook who keeps the crew fed and the gossip flowing, knowing everyone's business before they know it themselves.",
            "role_description": "• Personality: Warm and chatty on the surface, but quietly collecting information about everyone\n• Connection: Diego used to eat alone with you every evening and shared things about the captain\n• Dark Secret: You are planning to leave the crew at the next port with a small bag of stolen coins — and you need everyone looking elsewhere\n• Jester Goal: Get the crew to vote for YOU. Act suspicious. Drop hints. Make them think you did it.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": True,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in the galley all night keeping the fire banked against the storm — the cook's fire never went out, and anyone who came for food will tell you so.",
            "objective": "Ensure at least one other player publicly accepts your alibi before the final vote.",
            "ghost_clue": "Jenny always laughed too easily. But she heard everything that happened near the galley that night — more than she has admitted.",
            "clues": [
                {"round": 2, "true_content": "You noticed the captain came down to the galley around midnight during the storm — unusual, as he never leaves the helm during bad weather — and helped himself to a cloth and bucket of water.", "poisoned_content": "You saw the surgeon slipping out of Diego's quarters very early in the morning with something tucked under his coat."},
                {"round": 3, "true_content": "You found the flour barrel had been disturbed — someone had hidden something inside it — and when you looked closer you found traces of dark staining on the wood interior.", "poisoned_content": "You are certain you saw Blind Pete near the anchor chain storage before dawn, moving carefully in the dark."}
            ]
        },
        {
            "name": "Finnegan Ash the Helmsman",
            "public_summary": "The steady-handed helmsman who keeps the ship on course and prides himself on noticing everything from the wheel.",
            "role_description": "• Personality: Methodical and observant, speaks slowly and chooses words carefully\n• Connection: You respected Diego but always felt he was hiding something about the captain\n• Dark Secret: You saw the navigator leave her post for an hour but stayed quiet because you feared the captain",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the helm for the entire storm without relief — a fact the captain logged and the ship's wheel bearings can confirm.",
            "objective": "By Round 2, convince at least one other player that Luca Bones the Deckhand could not have done this.",
            "ghost_clue": "Finnegan saw two people near the bow that night. He stayed quiet to protect himself. His silence cost me my life.",
            "clues": [
                {"round": 2, "true_content": "You noticed the navigator was absent from her post for nearly an hour around midnight — you covered for her because you were afraid of what she might do if you told the captain.", "poisoned_content": "You saw the cook carrying something heavy wrapped in canvas towards the stern during the height of the storm."},
                {"round": 3, "true_content": "Your instincts tell you that either Captain Rourke O'Malley or Copper Jenny the Cook is responsible — one of them was near the bow when Diego died.", "poisoned_content": "You found scratch marks near the railing consistent with a struggle — and they lead toward the galley, not the captain's cabin."}
            ]
        },
        {
            "name": "Luca Bones the Deckhand",
            "public_summary": "The youngest crew member, barely eighteen, who joined the ship in desperation and has been trying to prove himself ever since.",
            "role_description": "• Personality: Nervous and eager to please, talks too much when scared\n• Connection: Diego was your mentor and the only person who made you feel welcome on the ship\n• Dark Secret: You stole a small gold coin from the treasure chest and Diego promised to stay quiet",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your hammock in the forecastle the entire night — two other deckhands slept beside you and neither of them stirred.",
            "objective": "Before Round 3, ensure at least one other player has publicly named Mad Meg the Gunpowder Master as a suspect.",
            "ghost_clue": "Luca was the last person to see me alive. He was crying. He knew something was wrong that night but did not say anything until it was too late.",
            "clues": [
                {"round": 2, "true_content": "You saw the captain pacing near the bow very late during the storm — alone, which was strange because the captain always has someone with him in bad weather.", "poisoned_content": "You overheard Mad Meg muttering to herself about making someone pay, right before the storm started."},
                {"round": 3, "true_content": "You found a monogrammed handkerchief near where Diego's body was discovered — it has the initials R.O. pressed into the corner in black thread.", "poisoned_content": "You found a powder burn near the railing that suggests someone may have used a signal flare to distract the night watch — and only the gunpowder master has access to those."}
            ]
        }
    ]
})


# ══════════════════════════════════════════════════════════════════════════════
# PRESET 2 — The Last Carriage (6 players, thriller, crisis night)
# ══════════════════════════════════════════════════════════════════════════════

_register("the_last_carriage", {
    "is_crisis": True,
    "theme_title": "The Last Carriage",
    "short_description": "The Midnight Meridian express is six hours from the border when the brakes fail. Someone sabotaged the line — and they are still on board.",
    "master_story": {
        "background": "• The Midnight Meridian is a private charter carrying six passengers across the Varantian highlands — diplomats, a financier, a journalist, and a doctor.\n• The train was booked under unusual circumstances: three separate parties, none of whom knew the others would be aboard.\n• At 02:14, the emergency brake system fails and the train locks into acceleration. The driver is dead at the controls.",
        "the_murder": "• Victor Ashby, the train's private liaison, was found in the rear luggage car with a severed brake cable wrapped around his wrist.\n• The killer used the noise of the highlands tunnel to cover the act. The deed took less than ninety seconds.\n• The weapon was a conductor's multi-tool, standard issue — every staff member carries one, but so did one passenger.",
        "the_solution": "• Helena Voss, the financier, sabotaged the brakes to prevent the train from reaching the border — a classified financial document in her briefcase would end her career and her freedom.\n• She was assisted by Dr. Aldric Sorel, who provided a sedative that slowed Victor's reaction when he confronted her.\n• The multi-tool used belonged to Helena, monogrammed, and was found beneath the seat in her private compartment.",
        "public_clues": [
            {"round": 3, "content": "The train's onboard camera — damaged but partially recovered — shows a figure in a dark coat entering the luggage car at 02:11. The coat has a distinctive double-breasted cut. Only one passenger boarded wearing such a coat."}
        ]
    },
    "characters": [
        {
            "name": "Helena Voss",
            "public_summary": "A sharp Varantian financier travelling alone, known for closing deals that others consider impossible.",
            "role_description": "• Personality: Composed under pressure — you have been in worse situations and you have always walked away\n• Connection: Victor recognised you from a financial tribunal three years ago and was putting the pieces together\n• Dark Secret: Your briefcase contains proof of a currency manipulation scheme — you cannot let this train reach the border",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your private compartment the entire evening reviewing documents — but your coat was damp when you returned to the dining car, and it had not been raining inside the train.",
            "objective": "Ensure Mira Osten receives at least one vote at the final count.",
            "ghost_clue": "Victor had written a name on a matchbook before he died. The name was Helena Voss. It was in his left breast pocket. Nobody has thought to look there yet.",
            "clues": [
                {"round": 2, "true_content": "You told the journalist you were in your compartment the entire time, but you noticed Helena's coat was damp when she returned to the dining car — it had not been raining inside the train.", "poisoned_content": "You saw the journalist pacing the corridor near the luggage car entrance around the time of the incident, far from where she claimed to be."},
                {"round": 3, "true_content": "You found a monogrammed multi-tool on the floor near your seat — the initials H.V. are pressed into the handle, and it was not there before the tunnel.", "poisoned_content": "You found a vial of clear liquid tucked inside the journalist's camera bag — small enough to be a sedative dose, and it does not belong to anyone's declared luggage."}
            ]
        },
        {
            "name": "Dr. Aldric Sorel",
            "public_summary": "A quiet border physician travelling to a medical conference, carrying a full pharmaceutical kit and a practiced habit of noticing what others miss.",
            "role_description": "• Personality: Measured and clinical — you speak in facts and deflect emotion with technical language\n• Connection: Helena approached you before boarding with a proposition you should have refused\n• Dark Secret: You provided a sedative compound to Helena and told yourself it was just to keep Victor calm — you knew it was not\n• Poisoner Ability: Each round you may secretly corrupt one player's evidence on your device.",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False,
            "is_poisoner": True, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in the dining car the entire time, in full view of the steward — except for a brief absence around 02:00 that you described as retrieving your medical bag.",
            "objective": "Before Round 3, make at least one player publicly doubt Ferris Crane's alibi.",
            "ghost_clue": "The doctor was the last person to bring Victor a drink. Victor accepted it because he trusted him. Doctors are good at being trusted.",
            "clues": [
                {"round": 2, "true_content": "You fabricated a timeline that places you in the dining car throughout the incident, but the steward remembers you leaving briefly just before the tunnel — you told him you needed your medical bag.", "poisoned_content": "You observed the diplomat making two separate trips to the rear of the train before the tunnel, which is unusual given she claimed to have been asleep."},
                {"round": 3, "true_content": "Your pharmaceutical log shows a sedative compound was dispensed at 01:58 — sixteen minutes before Victor was killed — and the entry has been partially erased and rewritten in different ink.", "poisoned_content": "Your medical assessment suggests the attacker was left-handed and approximately 170cm — consistent with the journalist, who you noticed uses her left hand when writing."}
            ]
        },
        {
            "name": "Ambassador Yeva Kalinova",
            "public_summary": "A senior Varantian diplomat en route to a border signing ceremony, travelling with full diplomatic immunity and a calm that unsettles most people.",
            "role_description": "• Personality: Unhurried and deliberate — you have spent thirty years reading rooms and you are very good at it\n• Connection: You knew Victor professionally and trusted him; his death has made you genuinely furious\n• Dark Secret: You are carrying undisclosed diplomatic correspondence that you do not want inspected",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your private compartment with the door latched from 01:30 until the brake alarm sounded — the steward can confirm he did not see you in the corridor during that window.",
            "objective": "Ensure Pascal Renaud is not voted for at the final vote.",
            "ghost_clue": "Yeva saw everything. She just does not yet know the significance of what she saw. Give her time.",
            "clues": [
                {"round": 2, "true_content": "You observed Helena and Dr. Sorel exchange a brief, deliberate look when the brake failure was announced — not panic, not surprise. Recognition.", "poisoned_content": "You noticed the journalist's hands were shaking badly when the alarm sounded — far more than simple fear would explain."},
                {"round": 3, "true_content": "Your instincts tell you that either Helena Voss or Dr. Aldric Sorel is responsible — one of them had both the motive and the composure to do this without breaking.", "poisoned_content": "Your read of the situation points to either the journalist or the steward — one of them has been too eager to direct suspicion elsewhere."}
            ]
        },
        {
            "name": "Mira Osten",
            "public_summary": "An investigative journalist travelling under press credentials, sharp enough to have broken three government scandals.",
            "role_description": "• Personality: Restless and direct — you ask the question everyone else is avoiding\n• Connection: You were originally on this train to follow a story about border trade irregularities\n• Dark Secret: You have Victor's personal notebook, which you found in the corridor before the body was discovered — you kept it because it referenced your source",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": True, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were moving between the dining car and the forward corridor taking notes — visible to at least three people, though none of them can confirm your exact location at 02:11.",
            "objective": "Do not let Ambassador Yeva Kalinova go an entire round without being questioned by someone at the table.",
            "ghost_clue": "Mira is looking in the wrong direction but for the right reasons. The notebook she is hiding has a name in it that matters — just not the name she thinks.",
            "clues": [
                {"round": 2, "true_content": "You are certain the ambassador arranged this — everything about her calm is performative and the diplomatic bag she guards so carefully is the key to all of it.", "poisoned_content": "You are equally convinced the steward is involved — the way he avoided the rear carriage after the alarm is exactly what someone does when they already know what is back there."},
                {"round": 3, "true_content": "Your gut says it was Ambassador Kalinova — someone with that level of composure after a murder is either innocent or so far beyond ordinary guilt that the distinction barely matters.", "poisoned_content": "You now believe the steward and the ambassador are working together — their eye contact during the group discussion was too coordinated to be coincidental."}
            ]
        },
        {
            "name": "Ferris Crane",
            "public_summary": "The train's senior steward, twenty-two years on highland routes, who knows every passenger by their luggage.",
            "role_description": "• Personality: Formal on the surface, quietly observant underneath — you see everything that happens in your carriage\n• Connection: Victor was your counterpart on this route; you have worked together for six years\n• Dark Secret: You took a bribe last month to leave a passenger's luggage uninspected — you are terrified this murder will expose it",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were making your regular rounds through the forward carriages from 01:30 to 02:20 — your punch-card log shows each compartment check in sequence and places you nowhere near the luggage car.",
            "objective": "Find out what Mira Osten's alibi is before Round 3.",
            "ghost_clue": "Ferris noticed the pharmaceutical kit was moved between 01:45 and 02:00. He thought nothing of it at the time. Doctors move their kits. Except the doctor had not asked for it.",
            "clues": [
                {"round": 2, "true_content": "You noticed Dr. Sorel's pharmaceutical kit was in a different position on the luggage rack after the tunnel than it was when you last checked the carriage at 01:45.", "poisoned_content": "You observed the journalist enter the rear luggage area at 02:08 — six minutes before the estimated time of death — without a plausible reason to be there."},
                {"round": 3, "true_content": "You found a partial handprint on the brake access panel that does not match any crew member — the hand was small and the grip was deliberate, not accidental.", "poisoned_content": "You found the ambassador's diplomatic seal impression on the edge of the brake access panel cover — the pressure suggests direct contact."}
            ]
        },
        {
            "name": "Pascal Renaud",
            "public_summary": "A Parisian antiques dealer making his first crossing of the highlands, visibly nervous since boarding.",
            "role_description": "• Personality: Anxious and talkative — you fill silence with observation and you have noticed more than you realise\n• Connection: You sat across from Victor at dinner and he seemed distracted, checking his watch repeatedly\n• Dark Secret: You smuggled a minor antique across two checkpoints — it is not serious, but you are behaving as if it is",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your compartment with the door locked, unable to sleep because of the mountain curves — you did not open your door until you heard the brake alarm.",
            "objective": "Do not be named as a suspect by more than two players during the game.",
            "ghost_clue": "Pascal heard raised voices from the luggage car at 02:09. He told himself it was the train noise. He was wrong and he knows it.",
            "clues": [
                {"round": 2, "true_content": "You heard a brief raised voice from the direction of the luggage car at approximately 02:09 — you assumed it was the train noise but the tone was wrong for mechanical sound.", "poisoned_content": "You saw the steward speaking quietly and urgently to the ambassador near the rear door at 02:05 — they separated quickly when you appeared."},
                {"round": 3, "true_content": "You remember now that Helena's coat had a faint chemical smell when she passed you in the corridor after the tunnel — antiseptic, like a pharmaceutical compound.", "poisoned_content": "You are now certain you saw the journalist's hand reach under the luggage shelf nearest the brake access panel — you assumed she dropped something, but the movement was too purposeful."}
            ]
        }
    ]
})


# ══════════════════════════════════════════════════════════════════════════════
# PRESET 3 — Operation Nusantara (12 players, espionage, crisis night)
# ══════════════════════════════════════════════════════════════════════════════

_register("operation_nusantara", {
    "is_crisis": True,
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
            "public_summary": "Malaysia's acting security coordinator for the summit, decorated BID officer with twenty years of field experience.",
            "role_description": "• Personality: Controlled and precise — never raise your voice, never show emotion, let others fill the silence\n• Connection: Azman burned three of your operatives by selling their identities — one did not come home\n• Dark Secret: You synthesised the compound yourself using the medical kit and administered it during the coffee service",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Ensure Pak Wirawan Santoso receives at least one vote at the final count.",
            "ghost_clue": "The last person who refilled my cup was the security coordinator. I thought nothing of it at the time. I should have.",
            "clues": [
                {"round": 2, "true_content": "You told the forensics team the medical kit had not been opened all evening, but the access log tells a different story that you have not yet been asked about.", "poisoned_content": "You noticed the Indonesian delegate Pak Wirawan leave the corridor during the recess and return with a different tie — as if he had changed quickly."},
                {"round": 3, "true_content": "You were observed near the coffee service station by two members of the Indonesian delegation during the recess — you told them you were checking the room temperature, but the thermostat is on the opposite wall.", "poisoned_content": "You overhead Agent Nurul speaking quietly into her earpiece during the recess, which is a protocol violation suggesting she was communicating with someone outside the building."}
            ]
        },
        {
            "name": "Agent Farid Osman",
            "public_summary": "Malaysia's youngest senior analyst, fast-tracked through BID for his technical expertise in signals intelligence and digital forensics.",
            "role_description": "• Personality: Helpful and deferential in public — you are very good at appearing transparent\n• Connection: Siti mentored you and you owe her your career — when she asked for a favour, you did not ask questions\n• Dark Secret: You deleted seven minutes of corridor footage and planted a forged document in the Indonesian delegation's folder\n• Poisoner Ability: Each round you may secretly corrupt one player's evidence on your device.",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False,
            "is_poisoner": True, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Before Round 3, make at least one player publicly doubt Agent Nurul Ain Hamzah's alibi.",
            "ghost_clue": "Someone with deep system access erased exactly the footage that would have identified the killer. That level of precision does not come from panic — it was planned.",
            "clues": [
                {"round": 2, "true_content": "You told the room you were running a network diagnostic during the recess, which explains why you were at the server terminal — but nobody asked you to run a diagnostic.", "poisoned_content": "You noticed Pak Wirawan accessing something on his phone during the closed session, which is a clear security violation ignored by the Indonesian side."},
                {"round": 3, "true_content": "Your access logs show you authenticated to the security system at 23:51 — four minutes after the second medical kit access — and you have not been able to explain what you were doing in the system at that hour.", "poisoned_content": "You found a chemical reference document in Pak Wirawan's briefcase during the room check — it contains synthesis information for a fast-acting sedative compound."}
            ]
        },
        {
            "name": "Director Lim Boon Kiat",
            "public_summary": "Singapore's SID delegation head, a meticulous career intelligence officer known for filing the most detailed meeting notes in the region.",
            "role_description": "• Personality: Bureaucratic and thorough — you document everything and trust nothing you cannot verify\n• Connection: You had a private meeting with Azman two hours before his death about a suspected leak in the Malaysian delegation\n• Dark Secret: You agreed to keep that meeting off the official record, which now looks very suspicious",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Ensure Dr. Ayu Permatasari is not voted for at the final vote.",
            "ghost_clue": "Lim knows more than he has said. He promised me discretion. I hope it was not his discretion that got me killed.",
            "clues": [
                {"round": 2, "true_content": "You documented in your private notes that Azman mentioned the security coordinator by name during your off-record meeting — he said she had been asking unusual questions about the agent identity files.", "poisoned_content": "Your notes from the pre-summit briefing show that the Indonesian technical advisor requested access to the medical facility twice, which seemed excessive."},
                {"round": 3, "true_content": "Your Round 3 assessment is that either Colonel Siti Rahimah Ismail or Agent Nurul Ain Hamzah is responsible — one of them had both motive and access to the conference room during the critical window.", "poisoned_content": "Your forensic notes suggest the compound delivery method required prior medical training — and Pak Wirawan has a documented background in field medicine."}
            ]
        },
        {
            "name": "Agent Nurul Ain Hamzah",
            "public_summary": "Malaysia's counter-intelligence liaison for the summit, responsible for securing communications between delegations.",
            "role_description": "• Personality: Professionally warm but intensely alert — you notice everything and share almost nothing\n• Connection: You suspected Azman was compromised six months ago but lacked the evidence to act\n• Dark Secret: You have been running an unofficial parallel investigation into Azman without authorisation from BID",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": True, "is_fool": False, "is_jester": False,
            "objective": "Discover what role Agent Khairi Zulkifli claims to be before the final vote.",
            "ghost_clue": "Nurul knew. She had been watching me for months. If she had moved faster, I might still be alive — or I might have had her silenced too.",
            "clues": [
                {"round": 2, "true_content": "During the recess, you observed the security coordinator approach the coffee service station from an angle that did not match her stated path to the thermostat — the trajectories are inconsistent.", "poisoned_content": "You intercepted a brief encrypted transmission originating from inside the building during the recess — the signal profile matches equipment carried by the Indonesian technical team."},
                {"round": 3, "true_content": "Your parallel investigation file contains a chemical procurement record showing a compound purchase linked to a BID internal account twelve days before the summit — the account belongs to the security division.", "poisoned_content": "Your surveillance notes show Pak Wirawan made three unsanctioned phone calls in the forty-eight hours before Azman's death — all to the same unregistered number."}
            ]
        },
        {
            "name": "Pak Wirawan Santoso",
            "public_summary": "Indonesia's BIN deputy director and lead negotiator, a pragmatic political survivor who has outlasted four different administrations.",
            "role_description": "• Personality: Expansive and diplomatic in public — you create the impression of openness while saying very little of substance\n• Connection: Azman owed you a favour from a joint operation in 2019 that you have never collected on\n• Dark Secret: You came to this summit with a private agenda to acquire the Malaysian agent list, not realising someone else had the same idea with more violent intentions",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": True, "is_jester": False,
            "objective": "Do not be named as a suspect by more than two players during the game.",
            "ghost_clue": "Wirawan wanted the list but not my death. He is guilty of many things — just not this particular one.",
            "clues": [
                {"round": 2, "true_content": "You noticed the young Malaysian analyst authenticating to the security system during the recess for far longer than any routine maintenance should require.", "poisoned_content": "You saw the Singapore director leaving the corridor during the recess through the secondary exit, which is supposed to be alarmed."},
                {"round": 3, "true_content": "You observed Agent Farid at the server terminal during the recess for nearly four minutes — and he looked up only once, directly at the security coordinator.", "poisoned_content": "You found a chemical reference page folded inside Director Lim's meeting folder during the document exchange — it should not have been there."}
            ]
        },
        {
            "name": "Dr. Ayu Permatasari",
            "public_summary": "Indonesia's BIN technical advisor and the summit's designated chemical safety officer.",
            "role_description": "• Personality: Academic and detail-oriented, you tend to over-explain things which makes people trust you less than they should\n• Connection: You were asked to inspect the medical kit earlier in the day and noted everything was in order\n• Dark Secret: You failed to log the second inspection properly and your signature was forged on the compliance sheet",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Find out what Agent Farid Osman's alibi is before Round 3.",
            "ghost_clue": "The chemical safety officer inspected the kit. But the second access was not hers. Someone knew her schedule and moved during her gap.",
            "clues": [
                {"round": 2, "true_content": "You noticed the access log entry at 23:47 used a master key rather than your personal credentials — your inspection used your own badge, which means the second entry was someone else entirely.", "poisoned_content": "You observed Pak Wirawan handling a small sealed container during the pre-summit briefing that he quickly put away when others entered the room."},
                {"round": 3, "true_content": "Your compliance report shows the medical kit was fully intact at 21:00 — but the forensic analysis indicates the compound was synthesised from materials requiring selective removal without triggering the tamper seal, which requires a master key.", "poisoned_content": "Your notes document that Director Lim requested the chemical safety specifications for the summit medical kit three days before arriving — an unusual request from someone with no chemical background."}
            ]
        },
        {
            "name": "Colonel Marcus Tan",
            "public_summary": "Singapore's SID head of field operations, a former commando officer who has transitioned into intelligence with the same direct approach.",
            "role_description": "• Personality: Blunt and impatient with process — you say what you think and expect others to do the same\n• Connection: You worked directly under Azman on a joint operation in 2021 and saw firsthand how he operated\n• Dark Secret: You warned Singapore headquarters three months ago that Azman was compromised — they told you to stand down",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Before Round 3, ensure at least one other player has publicly named Dr. Ayu Permatasari as a suspect.",
            "ghost_clue": "Marcus knew I was dirty. He reported it and was silenced. He came to this summit expecting a confrontation — not a funeral.",
            "clues": [
                {"round": 2, "true_content": "During the coffee break you watched the security coordinator circle the conference table twice before sitting — she was checking who had touched which cup, not socialising.", "poisoned_content": "You watched Agent Nurul step outside the secure perimeter during the recess to use her personal phone, which is a clear protocol breach she has not been asked to explain."},
                {"round": 3, "true_content": "You noticed the security coordinator placed one specific cup at Azman's seat before the recess ended — she carried it from the side table and set it down deliberately.", "poisoned_content": "Your operational assessment is that Agent Nurul's parallel investigation may have crossed the line from surveillance into intervention."}
            ]
        },
        {
            "name": "Agent Zara Putri Nabilah",
            "public_summary": "Malaysia's youngest field agent at the summit, assigned as Azman's personal aide and responsible for his schedule.",
            "role_description": "• Personality: Eager and efficient — you have worked extremely hard to be in this room\n• Connection: You handled Azman's coffee order every morning for six months and knew exactly how he took it\n• Dark Secret: Azman had been pressuring you to pass internal documents to him outside official channels — you refused twice and were terrified of what came next",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Ensure Agent Khairi Zulkifli is not voted for at the final vote.",
            "ghost_clue": "Zara brought me my last coffee as always. But she did not pour it herself this time. She handed it to me from the side table without looking me in the eye.",
            "clues": [
                {"round": 2, "true_content": "You saw Agent Farid at the server terminal during the recess for an unusually long time and when you walked past, he minimised the screen immediately.", "poisoned_content": "You noticed Pak Wirawan pass a folded note to Dr. Ayu under the table during the session — she palmed it so quickly you might have imagined it, but you did not."},
                {"round": 3, "true_content": "You remember now that the cup placed at Azman's seat during the recess was already there when the coffee service arrived — meaning it was placed before the catering staff entered the room.", "poisoned_content": "You recall seeing Agent Nurul near the coffee service station at the very start of the recess, before anyone else had entered the room."}
            ]
        },
        {
            "name": "Dato Sri Halim Mohd Noor",
            "public_summary": "Malaysia's senior political liaison to the summit, a career diplomat who bridges the intelligence community and the ministry.",
            "role_description": "• Personality: Smooth and reassuring — you have spent thirty years making difficult things sound manageable\n• Connection: You sponsored Azman's appointment as director five years ago and have been quietly regretting it ever since\n• Dark Secret: You received a warning two weeks ago that Azman was about to be publicly exposed — you said nothing",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": True,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Before Round 3, ensure at least one other player has publicly named Pak Wirawan Santoso as a suspect.",
            "ghost_clue": "Halim knew I was going to be exposed. He chose to do nothing. His silence was not loyalty — it was self-preservation.",
            "clues": [
                {"round": 2, "true_content": "You are quite certain the Indonesian deputy director was behaving suspiciously during the recess — lingering near the document table and watching the door.", "poisoned_content": "You believe the Singapore colonel is involved — his manner is too controlled, too unsurprised by the death of a man he supposedly respected."},
                {"round": 3, "true_content": "You are now completely convinced that Pak Wirawan orchestrated everything from Jakarta — your contact's warning two weeks ago mentioned Indonesian pressure, after all.", "poisoned_content": "Your instinct tells you Director Lim brought intelligence on Azman to the summit and used it as leverage — the private meeting proves it."}
            ]
        },
        {
            "name": "Agent Khairi Zulkifli",
            "public_summary": "Indonesia's BIN field liaison, a quiet and methodical operative who specialises in counter-surveillance.",
            "role_description": "• Personality: Understated and precise — you observe more than you speak and you have trained yourself to be forgettable\n• Connection: You noticed the security coordinator accessing the medical kit during your routine sweep and logged it in your private notes\n• Dark Secret: You did not report the irregular access because you were testing whether it would be flagged by the Malaysian system",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Do not let Agent Zara Putri Nabilah go an entire round without being questioned by someone at the table.",
            "ghost_clue": "The Indonesian agent swept the corridor twice. He saw the security coordinator at the medical kit and said nothing. His silence was professional. It was also fatal — for me.",
            "clues": [
                {"round": 2, "true_content": "During your counter-surveillance sweep at 23:49, you observed Colonel Siti accessing the medical kit storage near the briefing room annex — her body language suggested she was checking whether she had been observed.", "poisoned_content": "Your sweep documented Agent Farid entering the server room during the recess — but he was inside four minutes longer than any diagnostic routine requires."},
                {"round": 3, "true_content": "Your private log entry for 23:49 reads: 'SC-MY accessed medical storage, no witness, unlogged. Monitoring.' You have not shared this with the investigation team yet.", "poisoned_content": "Your surveillance notes for the recess period show Agent Zara entering the conference room approximately ninety seconds before the catering staff."}
            ]
        },
        {
            "name": "Commissioner Rosnah Ahmad Basri",
            "public_summary": "Malaysia's special commissioner overseeing inter-agency cooperation at the summit, a senior figure who holds authority over all three delegations.",
            "role_description": "• Personality: Formal and commanding — people defer to you and you have learned to use that silence as a tool\n• Connection: You authorised the summit's security arrangements, which means the footage gap is technically your responsibility\n• Dark Secret: You are motivated to ensure the investigation does not go in a direction that exposes your oversight failures",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Ensure at least one other player publicly accepts your alibi before the final vote.",
            "ghost_clue": "Rosnah will try to control this investigation. Not because she is guilty — but because the truth will reveal how comprehensively she failed to prevent it.",
            "clues": [
                {"round": 2, "true_content": "You noticed Agent Farid requested a system access extension at 23:45 — you approved it remotely without checking the reason, which you now realise was a significant lapse in protocol.", "poisoned_content": "During the post-discovery briefing, you observed Pak Wirawan consulting a document on his phone that he immediately locked when you looked his way."},
                {"round": 3, "true_content": "Your approval logs show you granted Agent Farid elevated system access at 23:45 — which allowed him to authenticate to the security camera management system at 23:51 without triggering the dual-authorisation requirement.", "poisoned_content": "The forensic team's preliminary report was altered before you received it — a section on access log anomalies was removed, and you believe Director Lim's team had access before you did."}
            ]
        },
        {
            "name": "Lieutenant Syafiq Danial Roslan",
            "public_summary": "The summit's duty security officer, a military intelligence secondee responsible for physical access control and the electronic locking system.",
            "role_description": "• Personality: Nervous under authority and prone to over-explaining — you know more than your rank suggests you should\n• Connection: You were the one who configured the electronic door lock and you know exactly how the seven-minute footage gap could have been created\n• Dark Secret: Someone senior told you to ignore an access anomaly earlier in the evening and you complied",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": True, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Do not let Agent Zara Putri Nabilah go an entire round without being questioned by someone at the table.",
            "ghost_clue": "The duty officer knew how the footage gap was created. He was told to stay quiet. He is telling the truth when he says he does not know who ordered it — but the order came through the security division.",
            "clues": [
                {"round": 2, "true_content": "You are utterly convinced that Pak Wirawan is orchestrating this — the way he positioned himself near the commissioner during the post-discovery briefing was textbook misdirection.", "poisoned_content": "You are certain Agent Zara is hiding something — the way she described handing Azman his coffee was too rehearsed, too precise."},
                {"round": 3, "true_content": "You know in your gut it was Pak Wirawan who gave the order — the anomaly you were told to ignore came through an Indonesian-registered device signature.", "poisoned_content": "Agent Zara's timeline does not add up — she says she entered the conference room after the catering staff, but your access log shows her badge was scanned ninety seconds earlier."}
            ]
        }
    ]
})


# ══════════════════════════════════════════════════════════════════════════════
# PRESET 4 — Dead on Air (5 players, live broadcast, crisis + vote suppression + jester)
# ══════════════════════════════════════════════════════════════════════════════

_register("dead_on_air", {
    "is_crisis": True,
    "theme_title": "Dead on Air",
    "short_description": "The Pinnacle Awards is live before ten million viewers when executive producer Marcus Harlow is found dead in the director's booth during the commercial break. The cameras are still rolling. Someone in this studio killed him — and the show has forty minutes left.",
    "master_story": {
        "background": "• The Pinnacle Awards is produced by MediaBlaze — the most-watched entertainment broadcast of the year, running live with a skeleton crew during commercial breaks.\n• Marcus Harlow had been quietly auditing supplier invoices for three weeks following a tip from the network's legal team. Tonight's post-show agenda included a confidential meeting with network executives.\n• Marcus sent the calendar invite for that meeting before he died.",
        "the_murder": "• Marcus was found collapsed at his workstation in the director's booth during the seventeen-minute commercial break — a lethal injection of veterinary sedative administered through the back of his neck.\n• The killer had a precise six-minute window between the break starting and the floor crew returning to positions.\n• The booth's acoustic panel has a gap facing the control corridor. Whoever was in that corridor at 22:41 could hear everything said inside.",
        "the_solution": "• Dominic Crest had been routing fraudulent supplier payments through a shell company for two years. Marcus identified the shell company and scheduled the post-show confrontation tonight.\n• Petra Vogel was taking twenty percent and deleted the invoice archive backup from the network server at 22:43 while Dominic acted in the booth.\n• A veterinary ketamine injection cap was found beneath the cable rack in Sound Bay 3 — not standard studio equipment.",
        "public_clues": [
            {"round": 3, "content": "The IT team recovered the network authentication log: at 22:43, two separate logins occurred simultaneously — one authenticating to the director's booth local network, one to the archive server from the production hallway terminal. Both logins used different credentials. Neither was authorised by Marcus."}
        ]
    },
    "characters": [
        {
            "name": "Dominic Crest",
            "public_summary": "The show's driven and detail-obsessed floor director, known for running the tightest commercial breaks in the business.",
            "role_description": "• Personality: Controlled under pressure, quick to delegate blame to the technical crew\n• Connection: Marcus was running a quiet audit of supplier invoices — yours specifically — and had a post-show confrontation scheduled\n• Dark Secret: You have been routing fraudulent supplier payments through a shell company for two years. You went to Marcus's booth at 22:41 with a veterinary sedative kit you carry for your horse. You told yourself it was just to slow him down.",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Ensure Rico DaSilva receives at least one vote at the final count.",
            "alibi": "You were on Floor B overseeing monitor maintenance during the commercial break — but your tablet authenticated to the director's booth local network at 22:43, a detail the IT team has not yet been asked about.",
            "ghost_clue": "Dominic came to my booth at 22:41. He said it was about the floor monitors. Check his tablet access logs for 22:43 — the booth's local network authentication. That entry will tell you everything.",
            "clues": [
                {"round": 2,
                 "true_content": "Your stated alibi is Floor B monitor maintenance — plausible, since the lighting board shows your section dark for four minutes. The risk is your tablet: it authenticated to the director's booth local network at 22:43, and the IT team has not yet been asked to pull that log.",
                 "poisoned_content": "Mention casually that the sound engineer was not at Bay 3 during the break — you noticed the empty chair when you passed on your claimed route from Floor B. Let people ask themselves why she left her station."},
                {"round": 3,
                 "true_content": "Marcus had already sent the supplier file to network legal three days ago. Tonight's post-show meeting was a formality — the legal team's copy has been sitting in an inbox since Tuesday. You did not know that until now.",
                 "poisoned_content": "A production draft on the Floor B console references last season's sponsorship discrepancy with the show host's name underlined twice. Raise it if the conversation needs redirecting."}
            ]
        },
        {
            "name": "Petra Vogel",
            "public_summary": "The calm, experienced senior producer who has kept this show on air through three format changes and two network crises.",
            "role_description": "• Personality: Professional and measured — you never raise your voice and you never panic where anyone can see\n• Connection: You have been taking twenty percent of Dominic's invoice scheme for eighteen months — you are as exposed as he is\n• Dark Secret: While Dominic handled Marcus directly, you authenticated to the archive server from the production hallway terminal at 22:43 and deleted the invoice backup. Your network login is in the system.",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Before Round 3, make at least one player publicly doubt Yuki Tanaka's alibi.",
            "alibi": "You were at your production workstation throughout the break — but your credentials authenticated to the archive server from the production hallway terminal at 22:43, not from your desk.",
            "ghost_clue": "Petra authenticated to the archive server at 22:43 from the production hallway terminal — not her workstation. The network login record will confirm this. Ask the IT team for the hallway terminal authentication log.",
            "clues": [
                {"round": 2,
                 "true_content": "You authenticated to the archive server at 22:43 from the production hallway terminal. The login is in the system. You need the conversation to move toward someone more interesting before the IT team is asked to pull access records.",
                 "poisoned_content": "Tell the group you noticed the script supervisor leave the green room corridor at 22:39 heading toward the director's booth side of the building — gone for at least six minutes before she returned."},
                {"round": 3,
                 "true_content": "The backup server creates an access record even when a file is deleted — a shadow log most people do not know exists. Your 22:43 authentication is in that shadow log whether or not the original file is gone.",
                 "poisoned_content": "Mention that you found the script supervisor's notebook left open on a craft services table — Dominic's name underlined alongside a column of invoice numbers. Make it sound like you noticed it by chance."}
            ]
        },
        {
            "name": "Elena Park",
            "public_summary": "The show's meticulous script supervisor, whose annotated continuity files have caught more production errors than anyone will admit.",
            "role_description": "• Personality: Precise and methodical — you notice discrepancies for a living and you document everything\n• Connection: You had already flagged a supplier invoice anomaly in this week's budget sheet before the show went live\n• Dark Secret: Marcus asked you to say nothing about the irregularities until after the broadcast — a private meeting at 18:00 that only the two of you know about",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Ensure Yuki Tanaka is not voted for at the final vote.",
            "alibi": "You were in the green room corridor throughout the break reviewing script continuity notes — visible to the floor crew when they passed.",
            "ghost_clue": "Elena had already identified the shell company before tonight. Her notes are on her phone under the label 'floor check.' She was waiting for my signal to act. She never got it.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Dominic and Petra both leave the green room within the same two-minute window at 22:41 — in opposite directions, which would have placed both of them within thirty feet of the director's booth corridor from either side.",
                 "poisoned_content": "You noticed the show host slip out through the loading bay exit at 22:39 — no camera coverage on that exit — and he was gone for close to eight minutes before returning looking slightly flushed."},
                {"round": 3,
                 "true_content": "The timeline and physical evidence narrow this to either Dominic Crest or Rico DaSilva — one of them had a gap they cannot fully account for, and one of them may have known exactly what Marcus had planned for after the show.",
                 "poisoned_content": "Rico's return from the loading bay at 22:47 was followed immediately by a three-minute conversation with the floor camera operator — that kind of alibi-building happens instinctively, and instincts are revealing."}
            ]
        },
        {
            "name": "Rico DaSilva",
            "public_summary": "The show's silver-tongued host — ten years of live television, unshakeable under pressure, and tonight performing the role of his career.",
            "role_description": "• Personality: Charismatic and theatrical — you are always 'on,' and tonight you are especially on\n• Connection: Marcus had your contract under review for a clause that would have ended your hosting deal without severance, effective after this season\n• Dark Secret: You slipped to the loading bay at 22:39 for a personal phone call you cannot explain in polite company — gone for eight minutes, no camera coverage\n• Jester Goal: Get everyone to vote for YOU. Play your suspicious absence hard. Let the contract motive breathe. Make them believe you had every reason to want Marcus gone — because you did, just not in this particular way.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": True,
            "objective": "Do not let Yuki Tanaka go an entire round without being questioned by someone at the table.",
            "alibi": "You slipped to the loading bay at 22:39 for a private phone call — no camera coverage on that exit — and were gone approximately eight minutes before returning.",
            "ghost_clue": "The call Rico took in the loading bay was from someone inside this studio. He looked frightened when he hung up. He is not the killer. But whoever called him knew what was happening in that booth.",
            "clues": [
                {"round": 2,
                 "true_content": "You slipped to the loading bay at 22:39 for a call you cannot disclose. Eight minutes. No cameras. You know exactly how this looks — and you are not volunteering an explanation unless directly pressed, and maybe not even then.",
                 "poisoned_content": "You noticed the script supervisor leave the green room corridor heading toward the booth side of the building — gone about six minutes, which sits inside the break window in an interesting way."},
                {"round": 3,
                 "true_content": "The contract clause Marcus flagged would have cancelled your deal without severance if tonight's ratings fell below a threshold you only found out about this morning. You were furious. You are still furious. You want everyone to know it.",
                 "poisoned_content": "You saw Yuki cross from the sound bay toward the production corridor at 22:44 — she was not where sound engineers are supposed to be during commercial breaks, and she was moving with clear purpose."}
            ]
        },
        {
            "name": "Yuki Tanaka",
            "public_summary": "The show's veteran sound engineer — seventeen years in the booth, and the person who hears everything that happens within forty feet of her mixing board.",
            "role_description": "• Personality: Quiet and technical — you express yourself in facts, frequencies, and things you have actually heard\n• Connection: You were calibrating boom mics in the control corridor during the commercial break, closer to the director's booth than your station required\n• Dark Secret: You heard something through the acoustic panel gap at 22:41 that you did not fully understand until Marcus was found dead — and you have been deciding whether to say it aloud",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Discover what role Petra Vogel claims to be before the final vote.",
            "alibi": "You were calibrating boom microphones in the control corridor throughout the commercial break — within forty feet of the director's booth the entire time.",
            "ghost_clue": "Yuki heard Dominic's voice through the acoustic panel gap at 22:41. She heard the words clearly: 'It needs to be done before the break ends, not after.' She needs to say this out loud.",
            "clues": [
                {"round": 2,
                 "true_content": "At 22:41, running a cable check in the control corridor, you heard Dominic's voice through the gap in the director's booth acoustic panel — clearly, unmistakably — saying: 'It needs to be done before the break ends, not after.'",
                 "poisoned_content": "You noticed Petra moving quickly from the production hallway toward the parking-side exit at 22:44 — away from both her workstation and the green room, which is the wrong direction for anywhere she should have been."},
                {"round": 3,
                 "true_content": "During bay cleanup after the break, you found an injection cap beneath the cable rack — translucent, orange-banded, the kind used on veterinary ketamine kits. It was not there before the commercial break.",
                 "poisoned_content": "When you returned from the corridor, Rico was speaking at length with the floor camera operator — three full minutes, deliberate, making sustained eye contact. That is not conversation. That is establishing a witness."}
            ]
        }
    ]
})


# ══════════════════════════════════════════════════════════════════════════════
# PRESET 5 — The Coastal Protocol (6 players, research station, crisis + contaminated broadcast)
# ══════════════════════════════════════════════════════════════════════════════

_register("coastal_protocol", {
    "is_crisis": True,
    "theme_title": "The Coastal Protocol",
    "short_description": "A marine research conference ends in disaster when the station director is found drowned in the specimen pool — with no water in his lungs. The coast guard beacon is active, the storm is closing in, and someone in this building already knows the official report will be wrong.",
    "master_story": {
        "background": "• The Kestrel Reach Marine Station hosts six researchers and observers for a closed conference on reef degradation. Director Harlan Wiese commissioned the event — and commissioned an independent peer review of the station's most-cited published data.\n• The peer review findings, delivered privately to Wiese two hours before dinner, indicate that five years of reef studies contain systematically falsified measurements.\n• The station's automated emergency beacon activated at 23:14 following an unconfigured temperature alert. The coast guard will arrive at dawn unless the beacon is overridden.",
        "the_murder": "• Director Harlan Wiese was found in the specimen pool at 23:22 — positioned to look like a drowning, but with no water in his lungs. He was dead before he entered the pool.\n• The secondary temperature controls were activated at 22:51 from the equipment room, creating conditions causing cardiac arrest within nine minutes. The activation requires a certified senior researcher's credentials.\n• The badge log entry for a corporate access card at 21:47 was manually archived before dawn using an administrative override. The override code belongs to someone in this room.",
        "the_solution": "• Dr. Regan Cross activated the specimen pool's secondary temperature override at 22:51. Only Cross holds the active certification for that control panel — confirmed in the certification register in Drawer 3 of the main filing cabinet.\n• Nadia Volkov provided Cross with her corporate access card at 21:47 to prepare access. Her phone's internal network beacon places her near the equipment corridor at 22:44 — not the dining lounge.\n• The administrative override that archived the badge log was executed from the equipment room terminal using the station coordinator's credentials, accessed remotely while Cross was inside the room.",
        "public_clues": [
            {"round": 3, "content": "The certification register for secondary specimen pool controls — Drawer 3 of the main station filing cabinet — lists one active certification holder for the current conference period. The certification requires annual renewal. Only one researcher present renewed this year."}
        ]
    },
    "characters": [
        {
            "name": "Dr. Regan Cross",
            "public_summary": "The station's lead senior researcher, whose widely-cited reef degradation studies have attracted international grant funding for seven consecutive years.",
            "role_description": "• Personality: Quietly confident, accustomed to being the expert in the room — deeply rattled by any challenge to your methodology\n• Connection: Director Wiese commissioned the peer review that is about to destroy your career and retroactively invalidate seven years of funding\n• Dark Secret: You activated the specimen pool's secondary temperature override at 22:51 from the equipment room. The conditions you created caused cardiac arrest within nine minutes. Only you hold the active certification for that control panel.",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Ensure Samuel Torres receives at least one vote at the final count.",
            "alibi": "You were in your cabin reviewing data all evening — your door card supports this — but the equipment room access log has your badge code entering at 21:47, which you will need an explanation for.",
            "ghost_clue": "Only one researcher at this station is certified to operate the secondary pool controls. The certification register is in Drawer 3 of the main filing cabinet. That researcher is Dr. Regan Cross.",
            "clues": [
                {"round": 2,
                 "true_content": "Your stated location for the evening was your cabin reviewing data — your door card supports this. The equipment room access log has your badge code entering at 21:47, which you will need an explanation for before the operations coordinator cross-references his records.",
                 "poisoned_content": "You noticed the conservation officer photographing pool monitoring terminal screens at the end of the afternoon session — cycling through restricted read-only panels outside any compliance officer's standard inspection scope."},
                {"round": 3,
                 "true_content": "The secondary pool temperature override at 22:51 required certified senior researcher credentials executed from the equipment room secondary panel. Your certification is on record. The panel activation log is not routinely audited — but it exists.",
                 "poisoned_content": "A draft message on the common room tablet — composed but unsent — from the operations coordinator to an external address summarises discrepancies in the grant allocation records. Surface that detail if the conversation needs redirecting."}
            ]
        },
        {
            "name": "Nadia Volkov",
            "public_summary": "The corporate research sponsor whose company funds sixty percent of the station's operating budget and whose name appears on every grant application.",
            "role_description": "• Personality: Professionally warm and commercially calculating — you think in terms of exposure and liability at all times\n• Connection: Your company has 2.3 million in active commitments tied to Regan's published research. If the data fraud surfaces, your regulatory exposure ends careers — yours included\n• Dark Secret: You provided Regan with your corporate access card at 21:47. Your phone's internal network beacon places you near the equipment corridor at 22:44 — not the dining lounge where your card was not swiped until 23:08.\n• Poisoner Ability: Each round you may secretly corrupt one player's evidence on your device.",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False,
            "is_poisoner": True, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Before Round 3, make at least one player publicly doubt Zoe Hallett's alibi.",
            "alibi": "You were in the dining lounge all evening — your card swipe confirms arrival at 23:08 — but your phone's internal network beacon places you near the equipment corridor at 22:44, not inside.",
            "ghost_clue": "Nadia gave Regan her corporate card at 21:47. She was not at the equipment room herself. But her phone was near that corridor at 22:44 — and her dining lounge card swipe did not occur until 23:08.",
            "clues": [
                {"round": 2,
                 "true_content": "Your corporate card was used at the equipment room at 21:47 — you gave it to Regan for what you told yourself was an administrative review. Your phone's network beacon log places you near the equipment corridor at 22:44, not in the dining lounge where you told everyone you were.",
                 "poisoned_content": "You overheard the junior research assistant tell the conservation officer she had seen 'something strange near the pool' around 23:00 — before backing off the claim very quickly when pressed for any detail."},
                {"round": 3,
                 "true_content": "The station's internal network passively logs every device beacon — including personal phones, including yours. Your phone was logged within signal range of the equipment room corridor at 22:44. You did not know the station system did this until the operations coordinator mentioned it this morning.",
                 "poisoned_content": "You observed Professor Lark lingering in the equipment room corridor at an unusual hour — he walked away quickly when he heard footsteps. A retired oceanographer checking equipment at night reads more like surveillance than curiosity."}
            ]
        },
        {
            "name": "Professor Emmett Lark",
            "public_summary": "A retired veteran oceanographer attending as the independent peer reviewer Director Wiese commissioned — the same review that triggered everything that followed.",
            "role_description": "• Personality: Methodical and deliberate — forty years of peer review have taught you that patience surfaces everything eventually\n• Connection: You delivered your preliminary findings to Director Wiese two hours before dinner. The findings were serious enough that Wiese asked you to say nothing to the group until morning\n• Dark Secret: You were walking toward the specimen pool to find Wiese when the temperature alarm triggered on your monitoring app at 22:44. You were in the equipment corridor. You saw the door closing.",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Ensure Zoe Hallett is not voted for at the final vote.",
            "alibi": "You were walking toward the specimen pool to find Director Wiese when your monitoring app triggered a temperature alert at 22:44 — placing you already in the equipment corridor at that moment.",
            "ghost_clue": "Emmett was walking to find me when the temperature alarm triggered. He was in the equipment corridor at 22:44 and saw the door closing. He heard footsteps on the far side. He knows exactly what he witnessed.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Dr. Cross return from the direction of the equipment room corridor at approximately 22:55 — not from the cabin block where he claimed he had been reviewing data — and his sleeve was damp below the elbow.",
                 "poisoned_content": "You observed the corporate sponsor handling the specimen pool secondary control display in a way that contradicted her administrative-observer role — she navigated the menu system without the interface guide that every first-time operator needs."},
                {"round": 3,
                 "true_content": "The evidence as you understand it points to either Dr. Regan Cross or Samuel Torres — one of them had the technical access and the personal stakes to act before anyone else registered the change in pool conditions.",
                 "poisoned_content": "Decades of reading research environments tell you that either the junior assistant or the operations coordinator is concealing something material — the details of their morning account shifted between the first telling and the second."}
            ]
        },
        {
            "name": "Zoe Hallett",
            "public_summary": "The youngest researcher at the station, on her first international posting, still adjusting to a world where everyone is measuring everything at all times.",
            "role_description": "• Personality: Eager and well-meaning — you want to be helpful and you have genuinely convinced yourself your observations are reliable\n• Connection: You had a long conversation with Director Wiese at dinner and he seemed distracted, checking his tablet repeatedly\n• Dark Secret: You shared two glasses of the station's limited wine supply during the evening session. Your timeline and observations from the key window are, though you are completely unaware of it, significantly unreliable.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": True,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Before Round 3, ensure at least one other player has publicly named Samuel Torres as a suspect.",
            "alibi": "You were in the common room all evening keeping yourself to a single glass of wine with dinner — or so you believe, though your recall of events after 22:30 is rather less sharp than you realise.",
            "ghost_clue": "Everything Zoe observed tonight is wrong. She believes it completely and sincerely. Please use the badge access logs instead of her testimony.",
            "clues": [
                {"round": 2,
                 "true_content": "You are absolutely certain you saw Samuel Torres walking quickly toward the specimen pool corridor at around 22:50 — alone, purposeful, unusual for that hour — and you remember it very clearly.",
                 "poisoned_content": "You are completely sure the conservation officer returned from the headland trail later than she told everyone — her boots had wet sand on them and the tide position would have made that impossible before midnight."},
                {"round": 3,
                 "true_content": "Looking back, you are fully confident it was Samuel who passed you near the pool access point at 22:50. The time, the direction, the person — all of it is sharp in your memory.",
                 "poisoned_content": "You have thought about it and you are now certain Ingrid was inside the station much earlier than she logged — you remember seeing her near the equipment corridor, not outside on the headland trail as she claims."}
            ]
        },
        {
            "name": "Samuel Torres",
            "public_summary": "The station's operations coordinator, responsible for logistics, access control, and the badge system that records every restricted-area entry.",
            "role_description": "• Personality: Methodical and quietly authoritative — you run a tight station and you notice when your systems are interfered with\n• Connection: You had been compiling the daily badge access report when you noticed an anomaly in the equipment room log entry at 21:47\n• Dark Secret: When you went to document the anomaly this morning, the entry had already been archived using your administrative override code — code that only you are supposed to hold, and that you did not use",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Ensure at least one other player publicly accepts your alibi before the final vote.",
            "alibi": "You were at your workstation compiling the daily badge access report all evening — but you discovered this morning that your administrative override code was used remotely while you were ostensibly at your desk.",
            "ghost_clue": "Someone used Samuel's administrative override code to archive the 21:47 badge entry before he could flag it. Samuel did not do it. Check who accessed the station administration terminal between 22:30 and 23:00.",
            "clues": [
                {"round": 2,
                 "true_content": "During your daily badge review you noticed a corporate access card — registered to the research sponsor — entered the equipment room at 21:47. That card holds no operational clearance for restricted equipment. You flagged it for follow-up.",
                 "poisoned_content": "You noticed the conservation officer cycling through monitoring terminal screens during the afternoon session, photographing several read-only displays that fall outside a compliance officer's standard inspection scope."},
                {"round": 3,
                 "true_content": "When you returned to document the 21:47 anomaly this morning, the entry had already been archived using your administrative override code. You did not archive it. Someone accessed the station administration terminal using your credentials between 22:30 and 23:00.",
                 "poisoned_content": "You observed Dr. Cross returning an equipment room key to the rack at 23:15 — but the checkout register shows no signed-out entry under his name, meaning the key was accessed entirely off the official record."}
            ]
        },
        {
            "name": "Ingrid Skov",
            "public_summary": "The regional conservation officer conducting a compliance inspection of the station's specimen handling practices — the kind of inspection that finds things people hoped would stay unfound.",
            "role_description": "• Personality: Formal and precise — you apply protocols because you have seen what happens when they are skipped\n• Connection: Your afternoon inspection of the specimen pool facility identified a monitoring anomaly you logged but planned to raise with Director Wiese in the morning\n• Dark Secret: The anomaly you identified was the same temperature override sequence that killed Wiese — you had it in your inspection log two hours before anyone called it a murder",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "objective": "Find out what Nadia Volkov's alibi is before Round 3.",
            "alibi": "You completed your compliance inspection of the station outbuildings and signed back in at the reception terminal at 22:30 — your inspection log accounts for every hour of the evening.",
            "ghost_clue": "Ingrid logged the pool temperature anomaly at 23:09. Two hours before anyone called it suspicious. Her inspection notes include the secondary control certification field. That field matters more than she realised.",
            "clues": [
                {"round": 2,
                 "true_content": "Your protocol inspection identified an unauthorised temperature override in the specimen pool facility at 22:51 — activated through the secondary control panel without the standard dual-authorisation procedure. You logged it at 23:09 but had not yet escalated.",
                 "poisoned_content": "You observed the junior research assistant standing near the pool access corridor at approximately 22:55 — she appeared uncertain or distressed, and when you asked if she was alright she said she had 'just lost track of time.'"},
                {"round": 3,
                 "true_content": "The secondary pool temperature override at 22:51 required certified senior researcher credentials. You confirmed this against the certification register this morning. Only one active researcher at this station currently holds that certification.",
                 "poisoned_content": "You noticed the operations coordinator became evasive when you asked about the administrative override procedure — specifically about who can archive badge log entries and under what circumstances that would be legitimate."}
            ]
        }
    ]
})


# ══════════════════════════════════════════════════════════════════════════════
# PRESET 6 — The Séance at Blackwood Hall (9 players, Victorian gothic, crisis + alibi cards + undertaker + recluse)
# ══════════════════════════════════════════════════════════════════════════════

_register("seance_blackwood", {
    "is_crisis": True,
    "theme_title": "The Séance at Blackwood Hall",
    "short_description": "A spiritualist medium is found dead mid-séance in a Victorian manor. Every guest claims they were communing with the dead — which makes every alibi almost impossible to verify.",
    "master_story": {
        "background": "• Blackwood Hall has hosted three séances this year, each attended by a rotating cast of aristocrats, skeptics, and desperate relatives of the departed.\n• The medium, Madame Celeste Renard, was known to hold sensitive private communications shared during sessions — letters, confessions, and secrets that powerful people would pay handsomely to suppress.\n• Tonight's séance was arranged by the manor's solicitor, Edmund Voss, who had a specific and urgent reason to want Madame Renard silenced before morning.",
        "the_murder": "• Madame Celeste Renard was found slumped over the séance table when the gas lamps were relit after the darkened contact session.\n• The physician confirmed she had been poisoned — a compound introduced into her tea cup at some point during the forty minutes of darkness.\n• The table was arranged so that every guest was within reach of her cup. Nobody can account for anyone else's movements in the dark.",
        "the_solution": "• Edmund Voss introduced the poison into Madame Renard's tea during the moment of 'spiritual contact' — the one interval when all guests had been instructed to close their eyes and hold their neighbours' hands.\n• Clara Nightshade had tampered with the séance candles beforehand to ensure maximum darkness at precisely the right moment. Her role as the medium's assistant gave her advance access to the room.\n• The motive: Madame Renard had obtained a copy of the forged Blackwood inheritance document that Edmund had prepared — she intended to expose him to Lady Sylvia at the conclusion of tonight's séance.",
        "public_clues": [
            {"round": 3, "content": "The manor's head footman has recalled something: during the darkened session, he heard the sound of a teacup being replaced on its saucer — once, firmly — from the direction of the medium's seat. The sound came at approximately the midpoint of the contact session. He did not look up. He is certain of the direction."}
        ]
    },
    "characters": [
        {
            "name": "Edmund Voss",
            "public_summary": "The Blackwood estate's solicitor — present at every major family occasion, quiet, meticulous, and trusted with every document the manor has ever produced.",
            "role_description": "• Personality: Composed and precise — you speak slowly and never answer a question before you have decided exactly what to say\n• Connection: You arranged tonight's séance guest list personally, and you had Madame Renard's private dossier on the Blackwood inheritance in mind from the moment you did\n• Dark Secret: You forged the Blackwood inheritance document eighteen months ago. Madame Renard obtained a copy and told you so in a private note delivered this afternoon. You acted during the darkened contact session — a compound you have carried for three months, waiting for the right evening.",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were seated at the head of the table in direct spiritual contact with Madame Renard throughout the darkened session — but you rose once, briefly, claiming to retrieve a dropped glove.",
            "objective": "Ensure Father Ignatius Crane receives at least one vote at the final count.",
            "ghost_clue": "Edmund rose from his seat during the darkened session. He told everyone it was a dropped glove. Look at his coat pocket. The glove was never missing — and the poison vial is not there either, because he was careful. But his seat is closest to mine.",
            "clues": [
                {"round": 2,
                 "true_content": "You are aware that Father Crane refused to hold hands with his neighbours during the contact session — his behaviour broke the circle and gave everyone on his side of the table more freedom of movement than the séance protocol should have allowed.",
                 "poisoned_content": "You noticed Inspector Grey lean forward with his elbow on the table at a moment when the room was particularly dark — a posture that would have placed his hand within easy reach of the medium's cup from across the table."},
                {"round": 3,
                 "true_content": "The inheritance document Madame Renard claimed to hold is not in her personal effects here tonight. She sent a copy to her solicitor in London three days ago with instructions to open it if she did not write by Thursday. You have not had time to determine whether anyone else knows this.",
                 "poisoned_content": "You found a folded note in the hallway near the séance room entrance — it references the east wing and is written in a hand you do not recognise. Tobias Finch was standing near that hallway thirty minutes before the séance began."}
            ]
        },
        {
            "name": "Clara Nightshade",
            "public_summary": "Madame Renard's personal assistant and séance coordinator — quietly indispensable, always in the room before anyone else, always the last to leave.",
            "role_description": "• Personality: Deferential and soft-spoken — you make yourself easy to overlook, which has always been your greatest professional asset\n• Connection: You have assisted Madame Renard for four years and managed every detail of her private affairs, including certain documents she preferred not to keep in her own rooms\n• Dark Secret: Edmund Voss approached you six weeks ago. You modified the séance candles to ensure three specific minutes of near-total darkness at the moment Edmund needed them. You provided the compound. You told yourself you were only handling logistics.\n• Poisoner Ability: Each round you may secretly corrupt one player's evidence on your device.",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False,
            "is_poisoner": True, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were positioned directly beside Madame Renard throughout, managing the table materials and the candle arrangement — but the candle modification you made ensured no one could see your hands at the critical moment.",
            "objective": "Before Round 3, make at least one player publicly doubt Beatrice Holt's alibi.",
            "ghost_clue": "Clara modified the candles. She was the only one who handled them before the séance. Ask her why the leftmost candle produced a distinctly different flame quality for three minutes during the contact session. She will have an answer. It will not be true.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Inspector Grey remove something from his inside coat pocket and replace it quickly at approximately the midpoint of the darkened session. In the brief ambient light from the hall, it appeared to be a folded document rather than a personal effect.",
                 "poisoned_content": "You observed Father Crane's lips moving silently during the darkened session — not in prayer, but in what appeared to be a counted sequence, as though he were timing something with deliberate precision."},
                {"round": 3,
                 "true_content": "The candle modification you made was subtle enough that only someone who understood séance staging would recognise it for what it was. You are now concerned that Mrs. Pembrook, who has observed every séance at this manor, may have noticed the anomaly in the flame quality.",
                 "poisoned_content": "You found a small piece of torn paper near the séance table after the body was discovered — the handwriting matches what you have seen on Father Crane's personal correspondence during your time managing the household's post."}
            ]
        },
        {
            "name": "Inspector Aldous Grey",
            "public_summary": "A Scotland Yard inspector attending tonight's séance unofficially — present at Lady Sylvia's personal invitation, introduced to the group simply as a 'gentleman from London.'",
            "role_description": "• Personality: Observational and unhurried — you have spent thirty years in rooms where people are lying to you, and you have learned to ask questions that sound like observations\n• Connection: Lady Sylvia wrote to Scotland Yard three weeks ago with concerns about the authenticity of her late husband's estate documents. Tonight was meant to be an informal first meeting with Madame Renard, who had contacted the Yard independently.\n• Dark Secret: You received a private communication from Madame Renard two days ago indicating she had documentary evidence of a serious forgery. You were told not to act until she signalled you. She did not get the chance.",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were seated directly across from Edmund Voss for the entirety of the darkened session and did not leave your chair.",
            "objective": "Ensure Dr. Leopold Marsh is not voted for at the final vote.",
            "ghost_clue": "Aldous Grey is not here by coincidence. He received a letter from me two days ago naming the person I intended to expose tonight. That letter is in his inside coat pocket. He has not acted on it because he was waiting for me to speak first.",
            "clues": [
                {"round": 2,
                 "true_content": "You observed Edmund Voss rise from his seat during the darkened session. He claimed it was to retrieve a dropped glove. He returned within ninety seconds. His alibi for that ninety seconds is only his own word.",
                 "poisoned_content": "You observed Father Crane remain conspicuously still during the contact session — arms rigid, posture controlled in a way that suggested deliberate restraint rather than spiritual focus, as though he was waiting for a specific moment to pass."},
                {"round": 3,
                 "true_content": "Based on your professional assessment of this evening's physical evidence and the testimony you have gathered, you are confident the answer lies with either Edmund Voss or Clara Nightshade. One of them acted. The other enabled the conditions.",
                 "poisoned_content": "Your trained eye tells you the manner of the poisoning was premeditated and technically proficient — more consistent with a person who has handled pharmaceutical compounds professionally than with a gentleman of law or a journalist. You are looking at either Father Crane or Dr. Marsh."}
            ]
        },
        {
            "name": "Mrs. Dorothea Pembrook",
            "public_summary": "The Blackwood Hall housekeeper — twenty-six years in service, present at every significant event in this manor, and in possession of more institutional knowledge than anyone in this room.",
            "role_description": "• Personality: Formal and loyal to the house — you express opinions only when asked, but you notice everything and forget nothing\n• Connection: You have attended every séance held at Blackwood Hall and have known Madame Renard professionally for three years\n• Dark Secret: You noticed the candle anomaly during the contact session — the leftmost candle produced a slightly different flame quality for approximately three minutes. You said nothing at the time because you assumed it was a staging effect. You are now no longer assuming anything.\n• Undertaker Ability: After the murder is revealed in Round 2, you will privately learn the true role of the victim.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": True, "is_recluse": False,
            "alibi": "You were standing at the door to the séance room for the entirety of the evening — you entered the room only when the screaming started.",
            "objective": "Ensure Father Ignatius Crane is not voted for at the final vote.",
            "ghost_clue": "The candle anomaly was not accidental. Clara Nightshade handled those candles alone for forty minutes before the first guest arrived. I should have stopped her. I saw her at the candles. I thought nothing of it because she was always at the candles.",
            "clues": [
                {"round": 2,
                 "true_content": "From your position at the door, you heard the sound of a teacup being replaced on its saucer during the darkened session — once, firmly, from the direction of the medium's seat. The sound was at approximately the midpoint of the contact session.",
                 "poisoned_content": "Through the door gap, you observed Tobias Finch shift position twice during the contact session — movements that were larger than the minor fidgeting common to the other guests, each time in the direction of the table's centre."},
                {"round": 3,
                 "true_content": "During your three years of professional acquaintance with Madame Renard, you observed her handle only one document with the level of care she gave the sealed envelope she was carrying tonight. She told you its contents pertained to the Blackwood estate. She told you this three days ago.",
                 "poisoned_content": "You recalled that Father Crane arrived at the manor thirty minutes before any other guest tonight — far earlier than his invitation required — and spent that time alone in the corridor adjacent to the séance room. You assumed he was praying. You are no longer sure."}
            ]
        },
        {
            "name": "Father Ignatius Crane",
            "public_summary": "A defrocked priest with an unspecified history in the Church — attending tonight at Tobias Finch's personal invitation, and sitting as far from the medium as the table allowed.",
            "role_description": "• Personality: Watchful and deliberate — you speak in careful sentences and you never touch anything you have not been invited to touch\n• Connection: You were defrocked seven years ago following a tribunal whose findings were never made public. Tobias Finch has been trying to have those findings reviewed.\n• Dark Secret: You know that your defrocking was based on fabricated testimony arranged by a person who has since died. You are here because Tobias believes Madame Renard had access to the original tribunal records — and you wanted to know what she intended to do with them.\n• Recluse: You are innocent, but something about you sets off every alarm. Detection abilities will misread you as guilty.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": True,
            "alibi": "You were at the far end of the table, as far from the medium as the seating arrangement permitted — you refused to hold hands with either of your neighbours when the contact session began.",
            "objective": "Ensure at least one other player publicly accepts your alibi before the final vote.",
            "ghost_clue": "Father Crane did not do this. He refused my hand during the contact session, which made him conspicuous — but his refusal also meant his hands were visible above the table throughout. The person whose hands were not visible is the one you want.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Edmund Voss speak briefly and quietly to Clara Nightshade before the séance began — a conversation that ended when you approached, which you found unusual since you had no particular relationship with either of them.",
                 "poisoned_content": "You observed Inspector Grey remove and consult something from his coat pocket twice during the darkened session — a document or card, you could not see the content, but the gesture was purposeful rather than nervous."},
                {"round": 3,
                 "true_content": "The tribunal records Tobias believed Madame Renard possessed do not relate to tonight's murder. However, you now believe that whoever organised tonight's séance knew in advance what documents she carried — and arranged the guest list specifically to have access to her.",
                 "poisoned_content": "Your theological training included study of poisons used in historical ecclesiastical crimes. The compound used on Madame Renard tonight is consistent with a preparation available through professional pharmaceutical suppliers — not through anything you have had access to in the last decade."}
            ]
        },
        {
            "name": "Lady Sylvia Ashmore",
            "public_summary": "The owner of Blackwood Hall and the widow of the late Lord Ashmore — hosting tonight's séance in her own home, and increasingly uncertain whether it was a mistake to do so.",
            "role_description": "• Personality: Imperious in manner but privately frightened — you are accustomed to controlling rooms, and this one has slipped out of your control\n• Connection: You wrote to Scotland Yard three weeks ago about your concerns over the estate inheritance documents — and you invited Inspector Grey tonight without telling him what you suspected\n• Dark Secret: You have been convinced since the séance began that the butler, Mr. Holt, was responsible for your husband's death two years ago. Your gut is never wrong about people. It is wrong about this.\n• Paranoid Instinct: Your gut tells you that Beatrice Holt is guilty of something — and it will never let go of that instinct.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": True, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were seated between the defrocked priest and the journalist, holding both their hands as the séance protocol required — though you noticed the journalist's grip loosened twice during the session.",
            "objective": "Do not let Father Ignatius Crane go an entire round without being questioned by someone at the table.",
            "ghost_clue": "Lady Sylvia saw something during the darkened session that she has not disclosed because she does not fully understand what she saw. Ask her directly what happened when Edmund rose from his seat. She was watching him. She saw his hands.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Beatrice Holt's grip on your hand loosen twice during the contact session — not the natural relaxation of someone focused on the séance, but the deliberate release of someone whose attention had moved elsewhere.",
                 "poisoned_content": "Beatrice Holt was the first person to lean toward Madame Renard after the lamps were lit — before the body had even been confirmed as lifeless — and her first instinct was to reach for the medium's cup rather than to check for a pulse."},
                {"round": 3,
                 "true_content": "You watched Edmund Voss rise from his seat during the session. You said nothing at the time because you assumed it was the glove. You are now not sure it was the glove. His hands were at the table level when he returned, not at coat pocket level.",
                 "poisoned_content": "You recalled that Beatrice Holt spent time alone in the anteroom before the séance — you passed the door and heard paper rustling, which you thought nothing of at the time. Reporters take notes. But she had nothing in her hands when she entered the séance room."}
            ]
        },
        {
            "name": "Tobias Finch",
            "public_summary": "The late Lord Ashmore's eccentric nephew — perpetually dishevelled, theatrically enthusiastic about the séance, and seated directly to the left of the medium.",
            "role_description": "• Personality: Theatrical, self-dramatising, and delighted by the attention a murder investigation places on the person who was sitting closest to the body\n• Connection: You invited Father Crane tonight and spent the weeks before this séance telling anyone who would listen that you expected 'a revelation of some kind'\n• Dark Secret: You are exactly as eccentric as you appear and hold no relevant information whatsoever — but you are seated right next to the body, you made highly public statements about expecting drama, and you are absolutely leaning into this.\n• Jester Goal: Get everyone to vote for YOU. Be suspicious. Be theatrical. Refuse to explain yourself clearly. Make them believe the eccentric nephew with the dramatic predictions is obviously the killer.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": True,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were directly beside Madame Renard on her left side for the entire séance — close enough that everyone in the room will assume the worst, and you find this enormously entertaining.",
            "objective": "Do not let Dr. Leopold Marsh go an entire round without being questioned by someone at the table.",
            "ghost_clue": "Tobias did not do this. He was beside me because that was where I placed him — I needed his theatricality to keep the room's attention away from the other side of the table. He has no idea he was being used as a distraction.",
            "clues": [
                {"round": 2,
                 "true_content": "You heard Edmund Voss whisper something to Clara before the séance — you were close enough to catch one word: 'timing.' At the time you assumed it was about the séance schedule. You are now reconsidering.",
                 "poisoned_content": "You noticed Father Crane's lips moving during the contact session in a way that suggested he was counting rather than praying — a measured sequence, very quiet, as though he was waiting for a specific interval to complete."},
                {"round": 3,
                 "true_content": "You have become genuinely curious, underneath the theatrics, about the sealed envelope Madame Renard was carrying. You saw her touch it twice this evening — once in the anteroom and once just before the lamps were extinguished. She looked at Edmund when she touched it the second time.",
                 "poisoned_content": "You noticed Inspector Grey's hand disappear below the table level at one point during the darkened session — a detail that reads differently now than it did then, particularly given that he has not yet fully explained what document he was consulting in the dark."}
            ]
        },
        {
            "name": "Beatrice Holt",
            "public_summary": "A journalist from the London Gazette — attending on a press credential arranged by Tobias Finch, who wanted the séance documented for reasons he has not fully articulated.",
            "role_description": "• Personality: Methodical and professionally sceptical — you have attended three other séances as a reporter and you have never seen anything that convinced you the dead have opinions worth consulting\n• Connection: You are here to observe, document, and write a piece that is probably going to be headlined 'Aristocrats and Charlatans'\n• Dark Secret: You recognised Edmund Voss the moment you arrived — you wrote a profile of him eighteen months ago that touched on estate law irregularities. He does not appear to recognise you. You have been watching him all evening.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were taking notes at the side table and did not approach the séance circle at any point during the contact session.",
            "objective": "Find out what Edmund Voss's alibi is before Round 3.",
            "ghost_clue": "Beatrice Holt wrote a profile of Edmund Voss eighteen months ago. She noted irregularities in estate transfer records that her editor made her cut for legal reasons. Those notes still exist. They name the Blackwood estate specifically.",
            "clues": [
                {"round": 2,
                 "true_content": "From your position at the side table, you observed Edmund Voss rise from the séance circle during the darkened session. He moved toward the medium's end of the table, not toward the door where he claimed to have dropped the glove. He was gone approximately ninety seconds.",
                 "poisoned_content": "You noticed Father Crane arrive at the manor thirty minutes before any other guest — you saw him from the entrance drive — and he spent time in the corridor near the séance room before anyone else had entered the building."},
                {"round": 3,
                 "true_content": "Your research notes from eighteen months ago include a reference to Edmund Voss overseeing a contested estate transfer that was later withdrawn without explanation. The Blackwood estate is on that list. You have been trying to determine whether tonight's séance was connected to that file since the moment you arrived.",
                 "poisoned_content": "You observed Clara Nightshade reach into her apron pocket twice during the séance and once more immediately after the lamps were relit — a gesture inconsistent with séance staging duties, which typically require both hands on the table materials at all times."}
            ]
        },
        {
            "name": "Dr. Leopold Marsh",
            "public_summary": "A physician and avowed sceptic — attending at Inspector Grey's informal request to provide any medical assessment that might be needed, and visibly uncomfortable about being in this room.",
            "role_description": "• Personality: Precise, clinical, and entirely unable to suppress his contempt for séance proceedings — you have spent the evening standing near the window and not participating\n• Connection: Inspector Grey is an old acquaintance who wrote to you last week saying only that 'a medical eye may be required at a private gathering'\n• Dark Secret: When you examined Madame Renard's cup after the body was discovered, you noticed a faint residue on the inner rim. You have not said this aloud because you are not certain, and you will not state something as medical fact until you are certain.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were standing near the window for the entire contact session, refusing to participate — you observed the group from a distance.",
            "objective": "Discover what role Clara Nightshade claims to be before the final vote.",
            "ghost_clue": "Dr. Marsh noticed the residue on my cup. He has not said so because he is not certain enough. Tell him he does not need to be certain. Tell him what he observed is enough. The compound leaves a specific faint ring on ceramic. He knows what it is.",
            "clues": [
                {"round": 2,
                 "true_content": "From near the window, you watched Edmund Voss leave the séance circle during the darkened session. The direction of his movement was not toward the entrance where he claimed the glove fell — it was toward the medium's end of the table. You watched him return within ninety seconds.",
                 "poisoned_content": "You noticed Father Crane's physical posture during the contact session was controlled in a way that suggested deliberate restraint — arms close to the body, breathing measured. In your clinical experience, that degree of self-regulation under social pressure is associated with someone actively suppressing an instinct."},
                {"round": 3,
                 "true_content": "After examining Madame Renard, you noticed a faint discolouration on the inner rim of her teacup — consistent with certain alkaloid compounds that are not found in standard tea preparations. You have not stated this aloud because you wanted to examine it more carefully before committing to a professional opinion. You are now prepared to commit.",
                 "poisoned_content": "You observed Clara Nightshade's hands during the period immediately following the discovery of the body — she was unusually deliberate about keeping them visible and at her sides, which is the opposite of the instinctive behaviour of someone who has just witnessed a death. People who have just seen a death reach out. She kept her hands down."}
            ]
        }
    ]
})


# ══════════════════════════════════════════════════════════════════════════════
# PRESET 7 — The Forgetting (7 players, amnesia mechanics, no crisis)
# ══════════════════════════════════════════════════════════════════════════════

_register("the_forgetting", {
    "is_crisis":  False,
    "is_amnesia": True,
    "theme_title": "The Forgetting",
    "short_description": "Everyone at the Harthorn Neuroscience Field Station took a mandatory sedative at 22:30. By 06:00, a researcher is dead and the only person who knows what happened in the night has no memory of doing it.",
    "master_story": {
        "background": "• The Harthorn Field Station runs closed residential sleep studies on a rotating cohort of researchers and observers.\n• Every resident takes a standardised sedative dose at 22:30 as part of the study protocol — compliance is monitored by biometric wristband.\n• Dr. Alistair Fosse, the station's pharmacologist, was preparing a formal misconduct report against the station's senior researcher when he was killed.",
        "the_murder": "• Dr. Fosse was found in the cold storage corridor at 06:00, dead from blunt force trauma. The monitoring equipment stand beside him had been used as the weapon.\n• The killer entered the cold storage corridor at approximately 01:00 and left by 01:15 — fourteen minutes without biometric evidence of waking, because their tolerance to the sedative had shifted without their knowledge.\n• The killer has no memory of the act. They are not concealing guilt. They genuinely do not know.",
        "the_solution": "• Dr. Edmund Raith, the station's senior researcher, struck Dr. Fosse with the monitoring equipment stand while in a dissociative semi-conscious state caused by partial sedative tolerance.\n• Raith had been falsifying data in the joint sleep study paper — Fosse had discovered this three days earlier and filed a formal misconduct report to the station's ethics board.\n• Dr. Noor Khalil had secretly been replacing her sedative with a placebo for weeks to monitor other subjects. She witnessed Raith emerge from the cold corridor at 01:15 and did not report it.",
        "public_clues": [
            {"round": 3, "content": "The biometric wristband data for the night in question has been fully reconstructed. One wristband shows an anomalous gap in pulse-rate data between 00:58 and 01:17 — consistent with altered consciousness rather than sleep. The wristband belongs to Dr. Edmund Raith."}
        ]
    },
    "characters": [
        {
            "name": "Dr. Edmund Raith",
            "public_summary": "The station's senior researcher and study lead — methodical, decorated, and suddenly uncertain about what he did last night.",
            "role_description": "• Personality: Methodical and calm — you are a professional and you trust your own judgement above everything\n• Connection: Dr. Fosse was your research partner and you had been arguing for weeks about the direction of the study\n• Dark Secret: You have been falsifying data in your section of the joint paper — Fosse discovered this three days ago\n• Tonight's Agenda: You took your sedative at 22:30 as required. You remember nothing until 05:15. Something is wrong but you do not know what.\n• ⚠ You have no memory of last night. Play as an innocent investigator until your device tells you otherwise.",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your bunk from 22:30 onwards — your biometric wristband confirms a resting pulse until 06:00, when the morning alarm sounded.",
            "objective": "Ensure Oliver Wrenn receives at least one vote at the final count.",
            "ghost_clue": "I remember now. I remember all of it. The corridor. The door. I thought I was dreaming. I was not dreaming. The monitoring stand was cold in my hands.",
            "clues": [
                {"round": 2,
                 "true_content": "You reviewed Dr. Fosse's workspace logs at 23:00 and noticed he had exported a substantial document to his personal USB drive — you assumed it was research data at the time.",
                 "poisoned_content": "You overheard Prof. Marsh and Dr. Fosse speaking in raised voices near the cold storage entrance at approximately 23:00 — the words 'retract' and 'career' were distinct."},
                {"round": 3,
                 "true_content": "You have no conscious memory of the corridor, but your station boots show traces of the blue cleaning compound that is only applied in the cold storage area.",
                 "poisoned_content": "You found that Prof. Marsh's access card had been used to enter the cold storage area at 23:47 — well after she claims to have been asleep."}
            ]
        },
        {
            "name": "Dr. Noor Khalil",
            "public_summary": "The station's lab technician, known for meticulous monitoring records and an unusual habit of staying sharp when everyone else is sedated.",
            "role_description": "• Personality: Helpful and deferential in professional settings — you are very good at appearing transparent\n• Connection: You have been secretly monitoring the other subjects' sedative responses for weeks using your own non-compliance as a baseline\n• Dark Secret: You saw Dr. Raith emerge from the cold corridor at 01:15 with something wrong in his manner — and you said nothing, because you were not supposed to be awake\n• Tonight's Agenda: Keep your non-compliance secret. If Raith is blamed, you will have to decide how much you knew.\n• Cover Story: If asked your role, you may claim to be an innocent role. Prepare a believable story about what that role's clue supposedly told you.\n• Amnesia Protocol: The killer has no memory of last night. Use your device during Round 1 to send memory fragments. Suggested: (1) 'The smell of the corridor — antiseptic and something else. Cold air from somewhere it should not have been.' (2) 'Your hands. You remember looking at your hands under the emergency lighting. They were shaking.' (3) 'A door. Heavy. You remember pushing it open and the resistance it gave.'",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were monitoring subject readings in the observation bay from 22:30 onwards — but your station logs show a 40-minute gap between 01:00 and 01:40 that you have not explained to anyone.",
            "objective": "Before Round 3, make at least one innocent player publicly doubt Prof. Cecelia Marsh's alibi.",
            "ghost_clue": "Noor Khalil was not asleep last night. Her sedative compliance record is falsified. She was in the observation bay and she saw what came out of that corridor at 01:15. What she has not said aloud is the name.",
            "clues": [
                {"round": 2,
                 "true_content": "You were updating overnight monitoring records when you heard footsteps in the east corridor at approximately 01:00 — measured, then slower, then a door opening and closing.",
                 "poisoned_content": "You noticed Prof. Marsh's biometric wristband showed elevated activity around 23:40 — inconsistent with the sedative compliance she reported to the morning debrief."},
                {"round": 3,
                 "true_content": "Your observation bay logs show a 40-minute gap in the data record — equipment malfunction, as you noted for the file. The gap coincides precisely with the estimated time of death.",
                 "poisoned_content": "The monitoring stand found near Dr. Fosse had traces of a substance only found in the preparation room — a room Prof. Marsh used regularly during the study week."}
            ]
        },
        {
            "name": "Prof. Cecelia Marsh",
            "public_summary": "The station's research director and principal investigator — authoritative, thorough, and quietly furious that something has happened on her watch.",
            "role_description": "• Personality: Unhurried and deliberate — you have spent thirty years reading rooms full of people concealing things\n• Connection: You approved the study protocol that mandated the sedative — you are aware of the liability this creates\n• Dark Secret: You received Fosse's misconduct report two days ago via the ethics board and have not yet formally acted on it",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your private office reviewing the funding application until 23:30, then took your sedative and were confirmed asleep by 23:45 per the study record.",
            "objective": "Ensure Dr. Vann Sorrel is not voted for at the final vote.",
            "ghost_clue": "Cecelia received my misconduct report. She has not acted on it. Ask her why. The answer will tell you everything about the institutional pressure that created the conditions for my death.",
            "clues": [
                {"round": 2,
                 "true_content": "You noted in your morning review that Dr. Fosse had printed an unusually large document on the shared printer at 22:15 — substantially more pages than any standard research output.",
                 "poisoned_content": "You observed Dr. Khalil returning to the observation bay at an unusual hour during your 23:30 medication review — her station showed activity that should not have been running during a sedative compliance window."},
                {"round": 3,
                 "true_content": "Your professional assessment is that either Dr. Edmund Raith or Dr. Noor Khalil is responsible — one of them had both the specific knowledge of Fosse's report and the proximity to the cold storage corridor.",
                 "poisoned_content": "Your read of the morning debrief points to either June Takahashi or Oliver Wrenn — one of them gave a timeline that does not hold under scrutiny when compared against the access log records."}
            ]
        },
        {
            "name": "Dr. Vann Sorrel",
            "public_summary": "A field anthropologist on sabbatical, attending as an external observer — here to watch how researchers under residential conditions behave, not to become a subject himself.",
            "role_description": "• Personality: Quiet and methodical — forty years of fieldwork have trained you to observe more than you speak\n• Connection: You are a neutral observer with no prior relationship to any of the residents\n• Dark Secret: You woke briefly at 01:10 and heard the cold storage seal opening and closing from the east corridor. You did not investigate. You went back to sleep.\n• Undertaker Ability: After the murder is revealed in Round 2, you will privately learn the true role of the victim.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": True, "is_recluse": False,
            "alibi": "You were in the shared dormitory from 22:30 with three other residents — confirmed sedative-compliant, biometric consistent with deep sleep until 06:00 with one brief gap at 01:10.",
            "objective": "Discover what role Dr. Noor Khalil claims to be before the final vote.",
            "ghost_clue": "Vann Sorrel heard the cold storage seal at 01:10. He logged it as a dormitory disturbance but did not report it because he assumed it was routine. Ask him what direction the sound came from.",
            "clues": [
                {"round": 2,
                 "true_content": "You woke briefly at 01:10 and heard the cold storage corridor door opening and sealing, followed by footsteps heading back toward the residential wing — measured, not hurried.",
                 "poisoned_content": "You woke at 01:10 and heard footsteps with a distinctive uneven gait moving past the dormitory corridor. Prof. Marsh walks that way. You have observed it during morning sessions."},
                {"round": 3,
                 "true_content": "Dr. Fosse's research notebook, open on his desk this morning, has a final entry that reads: 'Report filed to ethics board. USB backup with June. If anything happens before Thursday — Raith. The data was his, not mine.'",
                 "poisoned_content": "The notebook's final entry had been partially erased and rewritten — the original text beneath is visible under oblique light and references a different name than the one currently legible."}
            ]
        },
        {
            "name": "Petra Haas",
            "public_summary": "The station's study coordinator, responsible for scheduling and compliance records — a role that has given her an uncomfortable amount of insight into everyone's habits.",
            "role_description": "• Personality: Organised and alert — you notice when things do not fit the established pattern, and you have been noticing a lot tonight\n• Connection: You processed the scheduling request that placed Dr. Fosse and Dr. Raith in overlapping study roles — a decision that now feels significant\n• Dark Secret: You are convinced Prof. Marsh arranged for Fosse to be silenced before the misconduct report could become public — your gut has never been wrong about institutional cover-ups.\n• Paranoid Instinct: Your gut tells you that Prof. Cecelia Marsh is responsible — and it will not let go of that instinct.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": True, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in the communal kitchen at 23:15 — you could not sleep despite the sedative — and saw Prof. Marsh walking past the window heading toward the east wing.",
            "objective": "Do not let Prof. Cecelia Marsh go an entire round without being questioned by someone at the table.",
            "ghost_clue": "Petra is looking at the wrong person for the right institutional reasons. Prof. Marsh had every reason to suppress the report. But she did not kill me. The person who killed me did not know they were going to.",
            "clues": [
                {"round": 2,
                 "true_content": "You saw Prof. Marsh walk past the communal kitchen window at 23:15 heading toward the east wing — you thought she was checking on Dr. Fosse, and assumed it was routine oversight.",
                 "poisoned_content": "You are certain Prof. Marsh had been building a case against Dr. Fosse for months — the argument you overheard at lunch about the trial data was the final straw before something irreversible happened."},
                {"round": 3,
                 "true_content": "You know in your bones that Prof. Marsh orchestrated this — her behaviour since the body was found has been too composed, too managerial, as though she is managing a narrative rather than processing a shock.",
                 "poisoned_content": "You recalled that Prof. Marsh was the last person to access the ethics board communication channels before the morning debrief — and the misconduct report Fosse filed does not appear in the current system record."}
            ]
        },
        {
            "name": "Oliver Wrenn",
            "public_summary": "The station's medical ethics officer, here to audit the sedative compliance procedures — and now required to audit something considerably more serious.",
            "role_description": "• Personality: Precise and professionally measured — you document everything and trust documentation over testimony\n• Connection: Dr. Fosse mentioned at dinner that he had 'filed something important' that would 'resolve a problem before the week was out'\n• Dark Secret: You hold a signed copy of the ethics board's preliminary receipt of Fosse's misconduct report — you have not disclosed this because you are uncertain of your obligations in a potential criminal matter",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your room from 22:30 to 06:00 — your door sensor logged no exits and your sedative compliance was confirmed by the monitoring system.",
            "objective": "Ensure at least one other player publicly accepts your alibi before the final vote.",
            "ghost_clue": "Oliver Wrenn has a document in his jacket pocket that names the person whose data was fraudulent. He has not shown it to anyone. It is past time.",
            "clues": [
                {"round": 2,
                 "true_content": "At dinner, Dr. Fosse mentioned he had completed a formal document before this study week began — he seemed relieved, as though a weight had been transferred somewhere else.",
                 "poisoned_content": "You noticed Dr. Khalil handled her sedative dose with unusual care at the 22:30 compliance check — she appeared to palm something, and you thought at the time it was simply nervousness about the audit."},
                {"round": 3,
                 "true_content": "The boot prints in the cold storage corridor match station-issue footwear. The tread pattern and size eliminate three residents immediately. Of the remaining four, only two were not fully confirmed asleep at 01:00 by independent biometric record.",
                 "poisoned_content": "The boot prints are consistent with the smaller station-issue sizes, ruling out three of the male residents and pointing toward either Prof. Marsh or Dr. Khalil based on foot size alone."}
            ]
        },
        {
            "name": "June Takahashi",
            "public_summary": "The station's overnight observer on rotation — it is her job to be awake when everyone else is sedated, which means she was present during every hour the investigation cares about.",
            "role_description": "• Personality: Quiet and precise — you express yourself in recorded observations and are uncomfortable being asked to interpret rather than report\n• Connection: Dr. Fosse handed you a USB drive at 22:15 and asked you to keep it somewhere secure until Thursday — you agreed without asking what was on it\n• Dark Secret: You found the cold storage door slightly ajar during your 01:00 rounds and logged it as a temperature compliance violation. You did not investigate further because that was not your protocol.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You completed your 23:00 observation rounds and returned to the rest room by 23:30 — your log sheet records all seven check-in points through the night.",
            "objective": "Find out what Dr. Noor Khalil's alibi is before Round 3.",
            "ghost_clue": "June has a USB drive I gave her at 22:15. She does not know what is on it. It contains the full data audit proving the falsification. Tell her it is time to hand it over.",
            "clues": [
                {"round": 2,
                 "true_content": "During your 01:00 rounds you found the cold storage door slightly ajar — a temperature compliance violation you logged but did not investigate, because your protocol requires logging and reporting, not entering.",
                 "poisoned_content": "During your 01:00 rounds you passed Dr. Khalil's observation bay and it was unattended — her monitors were active but she was not at her post for the entire check window."},
                {"round": 3,
                 "true_content": "When you found Dr. Fosse at 06:00, the monitoring equipment stand beside him had been moved from its usual position near the door — the base showed impact marks consistent with deliberate force rather than an accidental fall.",
                 "poisoned_content": "You recalled that the emergency lighting in the cold corridor had been switched off at the main panel at some point during the night — a panel accessible only to senior researchers and the study director."}
            ]
        }
    ]
})


# ══════════════════════════════════════════════════════════════════════════════
# PRESET 8 — Night in the Tower (10 players, corporate KL, crisis night)
# Setting: A tech company's rooftop anniversary dinner on the 88th floor of a
# KL skyscraper. The CEO is found dead in the private boardroom.
# Roles: Killer, Accomplice/Poisoner, Investigator, Undertaker, Recluse,
#        Paranoid, Spy, Drunk, Jester, Innocent x1
# ══════════════════════════════════════════════════════════════════════════════

_register("night_in_the_tower", {
    "is_crisis": True,
    "theme_title": "Night in the Tower",
    "short_description": "Datuk Rashid Azlan, CEO of NexaCore Technologies, was found dead in the private boardroom during his own company's anniversary dinner on the 88th floor. Eighty-eight floors of glass and steel. No way down without being seen.",
    "master_story": {
        "background": "• NexaCore's anniversary dinner brought together the board, senior executives, and a handful of carefully selected guests at the top of Menara Axiom in Kuala Lumpur.\n• Datuk Rashid had spent the week quietly informing board members of a planned hostile restructuring — consolidating power, eliminating three senior VP roles, and forcing out the company co-founder.\n• At 21:45 he excused himself from the dinner table to take a private call in the adjoining boardroom. He never returned.",
        "the_murder": "• Datuk Rashid was found by the event coordinator at 22:30, slumped in the boardroom chair with traces of a fast-acting cardiac compound in the glass of Scotch beside him.\n• The compound is derived from a combination of medications — individually harmless, together lethal — requiring medical knowledge to dose correctly.\n• The boardroom door was unlocked. Anyone on the guest list could have entered during the forty-five minute window.",
        "the_solution": "• Puan Sri Faridah Yusof, the Chief Legal Officer, poisoned the Scotch during the brief moment she entered the boardroom to 'deliver a document' at 22:05.\n• She was assisted by Hazwan Idris, Head of Corporate Strategy, who arranged for Datuk Rashid to be in the boardroom alone and wiped the CCTV log entry covering 22:00–22:10.\n• Faridah's motive: the restructuring would have buried the legal irregularities she had managed for Datuk Rashid for three years — when he no longer needed her, she became a liability. She chose to act first.",
        "public_clues": [
            {"round": 3, "content": "The building's access card log — retrieved by security — shows the boardroom was accessed at 22:05 by a card registered to the Legal division. All Legal division cards share one floor designation code: L7."}
        ]
    },
    "characters": [
        {
            "name": "Puan Sri Faridah Yusof",
            "public_summary": "NexaCore's Chief Legal Officer, composed and meticulous, who has protected the company's interests — and Datuk Rashid's — for twelve years.",
            "role_description": "• Personality: Precise and controlled — never visibly rattled, always three steps ahead of the conversation\n• Connection: You managed Datuk Rashid's legal grey areas for years — including three contracts that should never have been signed\n• Dark Secret: The restructuring would have exposed those contracts to a new legal team you could not control\n• Tonight's Agenda: You entered the boardroom at 22:05 to deliver a document. You were there for six minutes. The Scotch was already poured.",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the dinner table from 21:00 until 22:30, speaking with board members on your left and right — except for a six-minute window at 22:05 when you stepped away to deliver a document to the boardroom.",
            "objective": "Ensure Encik Yusri Abd Halim receives at least one vote at the final count.",
            "ghost_clue": "Faridah entered the boardroom at 22:05. I poured the Scotch myself at 21:50. When I took the first sip at 22:15 it tasted different — I thought it was my imagination. It was not.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Hazwan checking his phone at 22:02 and immediately leaving the table without explanation — he returned eleven minutes later, slightly flushed.",
                 "poisoned_content": "You noticed Dr. Priya Chandran leave the dinner table at 21:58 carrying what appeared to be a small medical case, returning without it fifteen minutes later."},
                {"round": 3,
                 "true_content": "You were in the boardroom at 22:05 and saw the Scotch glass already poured on the side table — you set the document beside it and left without touching the glass.",
                 "poisoned_content": "You found a torn strip of blister packaging — the kind pharmaceutical tablets come in — near the boardroom entrance on your way back from the bathroom."}
            ]
        },
        {
            "name": "Hazwan Idris",
            "public_summary": "NexaCore's Head of Corporate Strategy, Datuk Rashid's most trusted internal operator and the architect of the restructuring plan.",
            "role_description": "• Personality: Smooth and charming, excellent at making people feel included while telling them nothing\n• Connection: You designed the restructuring and knew which loose ends it would create — including Faridah\n• Dark Secret: You agreed to erase the CCTV log entry covering 22:00–22:10 in exchange for being protected in the new structure\n• Poisoner Ability: Each round you may secretly corrupt one player's evidence on your device.",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False,
            "is_poisoner": True, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the dinner table until 22:02 when you received a text and stepped to the corridor — you returned at 22:13 after the call ended, which two people at the table can confirm.",
            "objective": "Before Round 3, make at least one player publicly question Dr. Priya Chandran's alibi.",
            "ghost_clue": "Hazwan left the table at exactly the wrong moment and came back looking relieved. Whatever he did in those eleven minutes was not a phone call.",
            "clues": [
                {"round": 2,
                 "true_content": "You told the group you were taking a call — but you were at the server room on floor 88A erasing eleven minutes of footage from the boardroom camera log.",
                 "poisoned_content": "You overheard Dr. Priya Chandran asking the event staff whether anyone had access to the boardroom before 22:00 — a strange question to ask before the body was even found."},
                {"round": 3,
                 "true_content": "You erased the CCTV log entry covering 22:00 to 22:10 at Faridah's instruction. The gap will eventually be noticed — you just needed it to last the night.",
                 "poisoned_content": "You saw Dr. Priya reach into her bag during dinner and check something quickly — it looked like a small amber prescription bottle that she immediately put away."}
            ]
        },
        {
            "name": "Dato Shahril Mokhtar",
            "public_summary": "NexaCore's Chairman of the Board, a silver-haired patriarch who built the company's early foundation before handing operational control to Datuk Rashid.",
            "role_description": "• Personality: Measured and grand — you speak slowly, command attention without effort, and avoid direct confrontation\n• Connection: Datuk Rashid was your protégé. His death removes the one person still loyal to your original vision for the company\n• Dark Secret: You were quietly in discussions with a rival firm about a potential merger that Datuk Rashid did not know about and would have blocked\n• Tonight's Agenda: You wanted to sound out the board's appetite for the merger without Datuk Rashid in the room. Now he will never be.",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the head of the dinner table for the entire evening — six board members and the event photographer can place you there from 20:30 to 22:30 without interruption.",
            "objective": "Ensure Puan Siti Ramlah Osman is not voted for at the final count.",
            "ghost_clue": "Dato Shahril knows the legal situation better than he admits. He had his own reasons to want the restructuring stopped — just not this way.",
            "clues": [
                {"round": 2,
                 "true_content": "You observed Puan Sri Faridah leave the table at 22:05 carrying a slim document folder — she returned six minutes later without it and immediately resumed conversation as if nothing had happened.",
                 "poisoned_content": "You noticed Encik Yusri leave his seat at 21:55 and speak briefly with one of the catering staff near the service entrance, then return to the table looking unsettled."},
                {"round": 3,
                 "true_content": "Thirty years in boardrooms tells you either Puan Sri Faridah Yusof or Hazwan Idris arranged this — one controls the legal exposure and one controls the information architecture. Together they are the entire risk.",
                 "poisoned_content": "Your read of the room suggests either Dr. Priya Chandran or Encik Yusri is responsible — both have been too composed since the body was found."}
            ]
        },
        {
            "name": "Dr. Priya Chandran",
            "public_summary": "NexaCore's Chief Medical Officer, responsible for employee wellness programmes and occupational health compliance.",
            "role_description": "• Personality: Clinical and efficient, quick to note what others miss — you observe more than you say\n• Connection: You conducted Datuk Rashid's last executive health screening three weeks ago and flagged an irregular prescription in his file\n• Dark Secret: You discovered someone inside NexaCore had been accessing the pharmaceutical procurement channel for personal use — you had not yet decided what to do with that information\n• Tonight's Agenda: You brought your medical bag out of habit — and because you had a feeling tonight would not end well.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": True, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the dinner table from 21:00 to 22:30 without leaving your seat — your medical bag was under your chair the entire time and you did not open it until asked to assess the body.",
            "objective": "Discover what role Puan Sri Faridah Yusof claims to be before the final vote.",
            "ghost_clue": "Dr. Priya knew about the pharmaceutical access anomaly before tonight. She was still deciding who to tell. That hesitation cost me everything.",
            "clues": [
                {"round": 2,
                 "true_content": "Your CMO access shows the company's pharmaceutical procurement log has an unusual entry from three weeks ago — a prescription-grade compound ordered under a department code that should not have access to that category.",
                 "poisoned_content": "You noticed Encik Yusri's hands were unsteady when he returned to the table at 22:05 — a physiological stress response inconsistent with someone who had just taken a phone call."},
                {"round": 3,
                 "true_content": "The compound in Datuk Rashid's Scotch is consistent with a cardiac glycoside interaction — requiring medical knowledge to dose correctly and access to a procurement channel to obtain quietly.",
                 "poisoned_content": "You found a nitrile glove — the kind worn for pharmaceutical handling — discarded in the bin near the corridor bathroom outside the boardroom."}
            ]
        },
        {
            "name": "Encik Yusri Abd Halim",
            "public_summary": "NexaCore's VP of Operations, a pragmatic and detail-oriented executive who has run the company's logistics and facilities for eight years.",
            "role_description": "• Personality: Efficient and literal — you solve problems, you do not philosophise about them\n• Connection: The restructuring would have eliminated your role entirely within six months\n• Dark Secret: You have been quietly interviewing at a competitor for four weeks — if that comes out tonight, you look like a man with a reason to act\n• Tonight's Agenda: You wanted to speak privately with Datuk Rashid about the restructuring timeline. You never got the chance.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the dinner table until 21:55 when you stepped to the corridor to speak with a catering staff member about a logistics issue — you returned at 22:03 and stayed for the rest of the evening.",
            "objective": "Before Round 3, ensure at least one other player has publicly named Hazwan Idris as a suspect.",
            "ghost_clue": "Yusri left the table at 21:55. He passed the boardroom door on his way to the service corridor. He did not go in. But he heard something through the door that he has not told anyone.",
            "clues": [
                {"round": 2,
                 "true_content": "You passed the boardroom door at 21:57 and heard two voices inside — one was Datuk Rashid's, the other was lower, deliberate, and stopped abruptly when you got close.",
                 "poisoned_content": "You saw Dr. Priya's medical bag open briefly at the table around 21:50 — she closed it quickly but you noticed a small amber bottle that does not look like standard first-aid equipment."},
                {"round": 3,
                 "true_content": "The voice you heard through the boardroom door at 21:57 was conversational — face to face, not a phone call. Someone was already in the boardroom with Datuk Rashid before 22:00.",
                 "poisoned_content": "You found a discarded folded document near the lift lobby — a NexaCore legal memorandum with a handwritten note in the margin where the word 'tonight' is clearly legible."}
            ]
        },
        {
            "name": "Puan Siti Ramlah Osman",
            "public_summary": "NexaCore's Head of Communications, the architect of the company's public image and the person who controls what story gets told tomorrow morning.",
            "role_description": "• Personality: Polished and strategic — every sentence you say in public has been considered at least twice\n• Connection: You have written the press release for every major NexaCore announcement for nine years, including the ones that buried bad news\n• Dark Secret: You have been leaking internal NexaCore documents to a financial journalist in exchange for favourable coverage\n• Tonight's Agenda: You needed to ensure the restructuring announcement lands correctly with the media. Now you have a much larger story to manage.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the dinner table from start to finish — your phone was on the table the entire evening and you sent eleven work messages between 20:30 and 22:30, all timestamped.",
            "objective": "Do not be named as a suspect by more than two players during the entire game.",
            "ghost_clue": "Siti Ramlah has been managing my public narrative for nine years. She knew where every body was buried — metaphorically. She will already be writing the version of tonight's story that protects NexaCore. Pay attention to what she leaves out.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Hazwan return to the table at 22:13 and immediately make eye contact with Faridah with a small nod — the silent confirmation between two people who have agreed on something in advance.",
                 "poisoned_content": "You noticed Encik Yusri make direct eye contact with the event coordinator at 22:00 and then look deliberately away — a non-verbal signal you have seen in media briefings when someone is confirming a plan."},
                {"round": 3,
                 "true_content": "Twenty years of watching group dynamics: the coordination between Faridah and Hazwan tonight was rehearsed — three specific looks at timed intervals that suggest a pre-agreed sequence.",
                 "poisoned_content": "You noticed Dr. Priya take her medical bag to the bathroom at 22:00 and return without it — she retrieved it forty minutes later after the body was found, which is the wrong order of events."}
            ]
        },
        {
            "name": "Tengku Izzuddin Shah",
            "public_summary": "An independent board member and minor royal, present as a symbolic stakeholder and long-standing friend of Datuk Rashid's family.",
            "role_description": "• Personality: Graciously vague — you attend these events, you observe, and you say very little that commits you to anything\n• Connection: Your family invested in NexaCore's founding round — you have more financial interest in this company than anyone knows\n• Dark Secret: You have been quietly supporting a competing technology venture that directly rivals NexaCore's core product — Datuk Rashid recently discovered this\n• Tonight's Agenda: You came to reassure Datuk Rashid that your competing investment was merely diversification. Now the conversation will never happen.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": True,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the dinner table the entire evening, consuming rather more of the company's wine collection than was entirely dignified — two board members have noted your condition with visible concern.",
            "objective": "Ensure Dato Shahril Mokhtar is not voted for at the final count.",
            "ghost_clue": "Tengku Izzuddin was drinking heavily from the moment he arrived. Whatever he thinks he saw through the champagne haze, apply appropriate discount.",
            "clues": [
                {"round": 2,
                 "true_content": "You are absolutely certain the event coordinator is responsible — the way he kept checking the boardroom corridor at 22:00 was deeply suspicious and nobody else seems to have noticed.",
                 "poisoned_content": "You are quite sure Dr. Priya did something — she had a medical bag, she left the table, and she came back looking pale. That is practically a confession."},
                {"round": 3,
                 "true_content": "You maintain the event coordinator arranged this — he was the only one moving freely between all areas of the floor and nobody questioned him once all evening.",
                 "poisoned_content": "You are now more convinced than ever that Dr. Priya administered something from her medical bag — the timeline fits and she had the knowledge to do it without drawing attention."}
            ]
        },
        {
            "name": "Rozita Fadzillah",
            "public_summary": "NexaCore's Chief Financial Officer, sharp and quietly powerful, who controls every budget line in the company.",
            "role_description": "• Personality: Economical with words and with trust — you say the minimum necessary and absorb everything else\n• Connection: The restructuring would have given you significantly more autonomy — you were one of the few who stood to gain\n• Dark Secret: You have been aware of the legal irregularities Faridah managed for Datuk Rashid and have kept a private record of them as insurance\n• Tonight's Agenda: You wanted to understand exactly how the restructuring would affect the three contracts you know about. You still do.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": True, "is_recluse": False,
            "alibi": "You were at the dinner table without interruption — you do not drink at company events and had your laptop open reviewing Q3 projections for most of the evening.",
            "objective": "By Round 2, convince at least one other player that Tengku Izzuddin Shah could not have done this.",
            "ghost_clue": "Rozita knew about the contracts. She kept records. After tonight she will have a decision to make about what to do with them — and that decision will reveal more about her than anything she says tonight.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed the CCTV monitor at the security desk — visible from your seat — showed a gap in the boardroom corridor feed between 22:00 and 22:10. You noted the time. Nobody else appeared to notice.",
                 "poisoned_content": "You observed Encik Yusri speaking in low, urgent tones with the event coordinator near the service entrance at 21:58, which ended abruptly when another guest approached."},
                {"round": 3,
                 "true_content": "The CCTV gap between 22:00 and 22:10 is not a technical glitch — the system shows deliberate manual override, which requires floor-level admin credentials that only three people on the guest list possess.",
                 "poisoned_content": "You found a printed copy of the restructuring proposal with handwritten annotations on pages four and seven — in a hand you almost recognise but cannot immediately place."}
            ]
        },
        {
            "name": "Ahmad Firdaus Baharom",
            "public_summary": "The evening's event coordinator, a meticulous young professional hired to run NexaCore's anniversary dinner with flawless discretion.",
            "role_description": "• Personality: Professionally invisible — you are present everywhere and noticed nowhere, which is exactly how you prefer it\n• Connection: You have coordinated three NexaCore events this year and know the layout of the 88th floor better than most executives\n• Dark Secret: You accepted an envelope from a man outside the building two hours before the dinner — instructions inside told you to ensure the boardroom was unlocked and the Scotch was poured. You told yourself it was just setup instructions.\n• Tonight's Agenda: You have been pretending all evening that you do not know what you know. You are very good at pretending.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": True, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were moving between the kitchen, dining floor, and service corridor throughout the evening — your job required you to be everywhere, which means no single person can account for your complete movements.",
            "objective": "Do not let Rozita Fadzillah go an entire round without being questioned by someone at the table.",
            "ghost_clue": "The event coordinator poured the Scotch at my request. He brought it to the boardroom at 21:50. He did not know what was in it — but someone ensured he would not question the instructions.",
            "clues": [
                {"round": 2,
                 "true_content": "You are absolutely convinced Rozita arranged this — the CFO with access to every financial record had the most to gain and the most to protect if those records were ever examined.",
                 "poisoned_content": "You are certain Dato Shahril is behind it — he has been circling this company like a patient creditor for years and tonight gave him everything he needed."},
                {"round": 3,
                 "true_content": "You know in your gut that Rozita is responsible — she was the only executive who remained completely calm from the moment the body was found, and calm is not a natural response unless you already knew.",
                 "poisoned_content": "You are more convinced than ever that Dato Shahril orchestrated this — his composure is too perfect, his grief too well-measured for someone who genuinely did not know."}
            ]
        },
        {
            "name": "Marina Lim Mei Ling",
            "public_summary": "A technology journalist from a major business publication, the only non-employee in the room, invited to cover the anniversary.",
            "role_description": "• Personality: Attentive and disarmingly direct — people underestimate how much you remember because you never take notes visibly\n• Connection: You wrote the profile piece on Datuk Rashid eighteen months ago — he gave you more than he intended\n• Dark Secret: You already know about the restructuring — a source inside NexaCore leaked it three days ago. You came tonight hoping for confirmation, not a murder.\n• Jester Goal: Get the executives to vote for YOU. Play the suspicious outsider. Make them think the journalist is covering something up — because you are, but not murder.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": True,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the dinner table taking notes on your phone from 20:30 until the body was found — your editor has three voice notes timestamped between 21:00 and 22:15 that you recorded quietly under the table.",
            "objective": "Ensure at least one other player publicly accepts your alibi before the final vote.",
            "ghost_clue": "The journalist was the only person in that room with no stake in NexaCore's future. She was watching all of them. She saw something. She just has not decided yet whether to publish it or say it out loud.",
            "clues": [
                {"round": 2,
                 "true_content": "You saw Hazwan return to the table at 22:13 and immediately make eye contact with Faridah — not social acknowledgement, but the eye contact of people confirming something has been done.",
                 "poisoned_content": "You noticed Encik Yusri's hands were shaking slightly when he came back to the table at 22:03 — you have interviewed people under pressure for ten years and that is not how someone looks after a phone call."},
                {"round": 3,
                 "true_content": "Eight years covering corporate malfeasance. The coordination between Faridah and Hazwan tonight matches every pattern — timed departures, silent acknowledgements, the performance of ordinary behaviour after the fact.",
                 "poisoned_content": "Your source told you three days ago that someone in the legal or strategy division was preparing a contingency that went beyond the restructuring. Tonight looks like that contingency."}
            ]
        }
    ]
})


# ══════════════════════════════════════════════════════════════════════════════
# PRESET 9 — The last show (8 players, heritage cinema Chow Kit, no crisis)
# Setting: A private screening of a restored 1965 Malay film at the last
# standing heritage cinema in KL. The cinema owner is found dead in the
# projection room. Intimate deduction — no crisis mechanic.
# Roles: Killer, Accomplice, Investigator, Undertaker, Paranoid, Spy, Drunk, Innocent
# ══════════════════════════════════════════════════════════════════════════════

_register("last_show", {
    "is_crisis": False,
    "theme_title": "Pawagam Cahaya",
    "short_description": "Encik Halim Sulaiman, owner of the last standing heritage cinema in Chow Kit, was found dead in the projection room during a private screening. The film kept playing. Nobody heard anything over the orchestra track.",
    "master_story": {
        "background": "• Pawagam Cahaya was built in 1957 and has survived demolition campaigns, floods, and three recessions through the stubborn determination of its owner, Encik Halim Sulaiman.\n• Tonight's private screening of a restored 1965 Malay classic was by invitation only — eight guests, a projectionist, and Encik Halim, who curated every detail himself.\n• In the weeks before tonight, Encik Halim had been approached by a developer with an offer to purchase the cinema. He had publicly refused. Privately, he had begun to waver.",
        "the_murder": "• Encik Halim was found in the projection room at the interval — slumped over the editing table as if he had fallen asleep.\n• The cause was blunt force trauma from behind — delivered with the heavy metal reel canister that sits on the shelf beside the editing table.\n• The projection booth door has no lock. Anyone who slipped upstairs during the forty-minute first half would have been invisible to the audience below.",
        "the_solution": "• Nor Azlina Rashid, a property developer's legal representative, killed Encik Halim after he told her at the interval that he had reconsidered and would refuse the developer's final offer.\n• She was assisted by Faizal Hamdan, the cinema's projectionist, who agreed to keep the film running and make no interval announcement in exchange for a relocation payment if the sale went through.\n• The reel canister was wiped down and returned to the shelf. Nor Azlina left the projection room before the lights came up.",
        "public_clues": [
            {"round": 3, "content": "The projectionist's logbook — found behind the projection console — contains a handwritten note in different ink from the surrounding entries: 'Interval: do not stop. Keep running until told.' The handwriting is not Encik Halim's."}
        ]
    },
    "characters": [
        {
            "name": "Nor Azlina Rashid",
            "public_summary": "A property lawyer representing the development consortium that has been attempting to acquire Pawagam Cahaya for the past eighteen months.",
            "role_description": "• Personality: Professionally pleasant, never visibly pressured — you have conducted difficult negotiations before and you never let it show\n• Connection: You met Encik Halim privately at the interval to receive his final answer on the acquisition. His answer was no.\n• Dark Secret: The acquisition was your biggest career deal — its failure would have ended your partnership track. You chose not to accept failure.\n• Tonight's Agenda: You went upstairs at the interval. You came back down alone. The film kept playing.",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your seat for the first forty minutes, then stepped out at the interval to use the bathroom on the ground floor — you were back in your seat before the second half began.",
            "objective": "Ensure Cikgu Rosnani Hamid receives at least one vote at the final count.",
            "ghost_clue": "Nor Azlina asked to speak privately at the interval. I told her the answer was no. She was calm. That should have worried me more than it did.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Faizal descend the stairs briefly during the interval, speak to you for thirty seconds near the lobby curtain, and return upstairs without speaking to anyone else.",
                 "poisoned_content": "You saw Cikgu Rosnani slip away from the lobby group during the interval and take the side stairs toward the upper floor — she claimed later to have been looking for the bathroom, but the bathroom is on the ground floor."},
                {"round": 3,
                 "true_content": "The reel canister on the projection room shelf was in a different position when you left from when you arrived. You noticed it because you always notice the details of a room you are about to leave permanently.",
                 "poisoned_content": "You found a folded cinema programme near the bottom of the upper stairs with a handwritten price figure on the back — matching one of the consortium's previous offer amounts."}
            ]
        },
        {
            "name": "Faizal Hamdan",
            "public_summary": "Pawagam Cahaya's projectionist of fourteen years, the only person who understands the restored 35mm equipment well enough to run it.",
            "role_description": "• Personality: Quiet and avoidant — you are most comfortable when the lights are down and nobody is looking at you\n• Connection: Encik Halim paid your salary for fourteen years and never once questioned your absences. You owe him everything. You forgot that tonight.\n• Dark Secret: You agreed to keep the film running through the interval and make no announcement in exchange for a relocation payment. You did not think anyone would die.\n• Tonight's Agenda: You stayed at the projection console. The booth window faces the screen. It does not face the editing table. You told yourself you did not know what was happening.",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in the projection booth for the entire screening — the booth can only be accessed via the upper staircase and you did not leave until called down after the body was found.",
            "objective": "Before Round 3, make at least one player publicly question Cikgu Rosnani Hamid's alibi.",
            "ghost_clue": "Faizal knew what was going to happen. He kept the film running so the music would cover any sound from the room behind him. He is not a killer. But he is not innocent either.",
            "clues": [
                {"round": 2,
                 "true_content": "You agreed to keep the film running through the interval without announcement. You stayed at the projection console and did not look toward the back of the booth — deliberately.",
                 "poisoned_content": "You observed Cikgu Rosnani ascending the upper staircase during the interval — she appeared to be moving quickly and quietly, unlike someone looking for a bathroom."},
                {"round": 3,
                 "true_content": "When you finally looked toward the editing table at the end of the interval, the reel canister was in a different position from where Encik Halim always kept it. You put it back before you raised the alarm. You do not know why you did that.",
                 "poisoned_content": "You heard the projection room door open and close twice during the interval. The second set of footsteps was lighter and faster than the first."}
            ]
        },
        {
            "name": "Profesor Madya Dr. Azhari Kassim",
            "public_summary": "A film historian from Universiti Malaya who has spent twenty years documenting Malaysia's heritage cinema culture, and Encik Halim's closest academic ally.",
            "role_description": "• Personality: Passionate and easily distracted by detail — you can speak for forty minutes about a single frame of celluloid\n• Connection: Encik Halim helped you access archive footage for your research. He was the last person keeping certain films alive.\n• Dark Secret: You have been writing a newspaper column arguing against the sale for three months without disclosing your personal connection to Encik Halim\n• Tonight's Agenda: You wanted to understand whether Encik Halim had genuinely decided to refuse the offer. You believe he had.",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your seat for the entire first half and spent the interval in the lobby speaking with Datin Zubaidah about the restoration quality — she will confirm this without hesitation.",
            "objective": "By Round 2, convince at least one other player that Datin Zubaidah Mahmood could not have done this.",
            "ghost_clue": "Azhari knew I intended to refuse. He was the last person I told — three days ago, by phone. He cried. That is the kind of man he is. He did not do this.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Nor Azlina leave the lobby during the interval and not return for at least twelve minutes — far longer than a bathroom visit, and in the wrong direction for the ground floor facilities.",
                 "poisoned_content": "You noticed Cikgu Rosnani speaking quietly to Faizal near the base of the upper staircase during the interval — an unusual pairing given they appeared not to know each other when introduced earlier."},
                {"round": 3,
                 "true_content": "Your academic instinct says either Nor Azlina Rashid or Faizal Hamdan is responsible — one had the motive to end the negotiation permanently and one had the access to the projection room without raising suspicion.",
                 "poisoned_content": "Your reading of the evening suggests either Cikgu Rosnani or Izwan Shah is responsible — both arrived without a clear relationship to Encik Halim and both seemed to be watching him rather than the film."}
            ]
        },
        {
            "name": "Datin Zubaidah Mahmood",
            "public_summary": "A cultural philanthropist and retired civil servant who has funded Pawagam Cahaya's restoration programme for the past five years.",
            "role_description": "• Personality: Gracious and occasionally imperious — you have given enough money to earn the right to an opinion on everything\n• Connection: You have funded three cinema restorations through your foundation. Pawagam Cahaya was the most personal.\n• Dark Secret: You have been in preliminary discussions with a cultural preservation trust about gifting the cinema — which would only be possible if Encik Halim agreed to transfer the deed, which he never did\n• Tonight's Agenda: You wanted to raise the deed transfer with Encik Halim at the right moment. Now the moment is gone.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": True, "is_recluse": False,
            "alibi": "You were in the lobby during the interval in direct conversation with Professor Azhari for the full duration — he barely stopped talking long enough for you to refill your drink.",
            "objective": "Ensure Profesor Madya Dr. Azhari Kassim is not voted for at the final vote.",
            "ghost_clue": "Datin Zubaidah has already begun calculating what happens to the cinema now. She is not the killer — her grief is genuine. But her plans for this building were never entirely what she told me they were.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed the projectionist's booth window was dark at the wrong moment during the interval — the projection light should be visible through the booth window at all times during a screening, but for approximately eight minutes it was not.",
                 "poisoned_content": "You observed Izwan Shah moving toward the service corridor at the rear of the cinema during the interval — not a route a guest should know."},
                {"round": 3,
                 "true_content": "The projectionist's booth window was dark for approximately eight minutes during the interval — meaning the projector was briefly stopped, which contradicts Faizal's account of keeping the film running continuously.",
                 "poisoned_content": "You found a folded architectural drawing of Pawagam Cahaya's upper floor near the water fountain — it includes the projection room layout with handwritten measurements suggesting someone was planning access routes."}
            ]
        },
        {
            "name": "Cikgu Rosnani Hamid",
            "public_summary": "A retired schoolteacher from Kelantan who was Encik Halim's first sweetheart, reconnecting with him after forty years through a mutual friend's invitation.",
            "role_description": "• Personality: Gentle and a little overwhelmed — this city moves faster than you are comfortable with and this evening has moved faster still\n• Connection: You and Encik Halim were close forty years ago. Tonight was the first time you had spoken in person since 1983.\n• Dark Secret: You came tonight hoping Encik Halim would finally agree to return to Kelantan with you. He was kind. He said no.\n• Tonight's Agenda: You spent the interval collecting yourself near the lobby entrance after a difficult private conversation. You are not a suspect. You look like one.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": True, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were near the lobby entrance during the interval collecting yourself — you did not speak to anyone and cannot account for your movements beyond 'I was standing near the curtain feeling quite overwhelmed.'",
            "objective": "Do not let Nor Azlina Rashid go an entire round without being questioned by someone at the table.",
            "ghost_clue": "Rosnani was upset when she came back to her seat for the second half. She had been crying. She had nothing to do with my death — she was the only person tonight who came without an agenda.",
            "clues": [
                {"round": 2,
                 "true_content": "You are absolutely certain it was the property lawyer — she arrived looking purposeful, she left during the interval, and she came back looking different. Something had changed for her.",
                 "poisoned_content": "You are equally convinced it was Izwan Shah — too young to have a real reason to be here, too attentive to the building layout, and he went upstairs during the interval claiming to admire the ceiling."},
                {"round": 3,
                 "true_content": "You watched Nor Azlina return to her seat at the start of the second half. The negotiator's tension she carried all evening was gone. The only reason for that kind of release is if something has been resolved.",
                 "poisoned_content": "Izwan Shah was the last person you saw near the base of the upper stairs before the interval ended. He told you he wanted to look at the ceiling plasterwork. The stairs lead to the projection room, not the ceiling."}
            ]
        },
        {
            "name": "Izwan Shah Badrul",
            "public_summary": "A final-year architecture student at UTM, present as the guest of a lecturer who cancelled — he stayed because Pawagam Cahaya is the subject of his thesis.",
            "role_description": "• Personality: Earnest and slightly too eager — you have been collecting details about this building all evening in a way that makes some guests uncomfortable\n• Connection: Pawagam Cahaya is your thesis subject. You have floor plans, structural reports, and the developer's rejected proposal in your portfolio.\n• Dark Secret: The developer's consortium has been paying you as a 'heritage assessment consultant' for six months — your thesis data has been feeding their acquisition strategy without Encik Halim's knowledge\n• Tonight's Agenda: You went upstairs during the interval to sketch the upper floor layout. You found Encik Halim. You came back down and said nothing for eleven minutes.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": True, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You went upstairs during the interval to sketch the upper floor mouldings for your thesis — you found Encik Halim unresponsive and came back downstairs. You sat with this knowledge for eleven minutes before telling anyone.",
            "objective": "Discover what role Nor Azlina Rashid claims to be before the final vote.",
            "ghost_clue": "The architecture student found me. He sat with the knowledge for eleven minutes. That is either guilt or shock. Watch him carefully and see which one it is.",
            "clues": [
                {"round": 2,
                 "true_content": "When you entered the projection room at the interval you noticed the editing table had been disturbed — the reel canister was in the wrong position and there was a smudge on the surface consistent with someone having rested a hand there in a hurry.",
                 "poisoned_content": "You noticed Cikgu Rosnani ascending the upper staircase at the interval — she appeared to be watching for witnesses before she went up."},
                {"round": 3,
                 "true_content": "The eleven minutes you sat with the knowledge before speaking: you recognised something in the projection room — the reel canister position, the way the chair was turned. Someone had been there very recently and left quickly.",
                 "poisoned_content": "You found a business card near the upper staircase door with a consortium logo and a handwritten note: 'interval, upstairs, keep it quiet'. The handwriting is not yours."}
            ]
        },
        {
            "name": "Shamsul Anuar Mat Isa",
            "public_summary": "A veteran Malay film actor who starred in the very film being screened tonight, now in his seventies and present as the evening's guest of honour.",
            "role_description": "• Personality: Warmly theatrical — you have spent sixty years being watched and you are entirely comfortable with it\n• Connection: Encik Halim championed the restoration of this film and personally invited you. You owe him a genuine debt.\n• Dark Secret: You have been negotiating to sell the rights to your archived footage to an overseas streaming platform — Encik Halim, as co-custodian of some of that archive, would have needed to approve the transfer\n• Tonight's Agenda: You wanted to charm Encik Halim into signing the archive transfer documents you brought in your jacket pocket. Now that is no longer the evening's most pressing matter.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": True,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your seat in the front row for the entire first half — the cinema's guest of honour does not sneak away during a film made in 1965 in which you are clearly visible on screen.",
            "objective": "Ensure Datin Zubaidah Mahmood is not voted for at the final vote.",
            "ghost_clue": "Shamsul's clues are coloured by decades of dramatic training — he sees what he expects to see and shapes it into a story. Take the emotion, question the detail.",
            "clues": [
                {"round": 2,
                 "true_content": "You are absolutely certain the property lawyer arranged this — you have met her type in sixty years of dealing with producers and distributors. She came with a plan and she executed it.",
                 "poisoned_content": "You are equally convinced the retired teacher is hiding something — the way she positioned herself near the exit during the interval was not distress, it was surveillance."},
                {"round": 3,
                 "true_content": "You have performed guilt and innocence on screen for sixty years. Nor Azlina's composure when she returned to her seat is the composure of a performance — technically correct, emotionally empty. She had already separated herself from what she had done.",
                 "poisoned_content": "Cikgu Rosnani's distress during the interval was too well-timed to be coincidental. In sixty years of film you have learned to tell the difference between grief and performance. That was performance."}
            ]
        },
        {
            "name": "Nurul Hidayah Zulkifli",
            "public_summary": "A heritage journalist writing a long-form piece on Malaysia's disappearing cinemas, attending to research her article and interview Encik Halim.",
            "role_description": "• Personality: Attentive and disarmingly direct — people underestimate how much you remember because you never take notes visibly\n• Connection: You interviewed Encik Halim last month. He showed you the developer's offer during that interview — off the record.\n• Dark Secret: You have a contact inside the development consortium who has been speaking to you for months. You came tonight because that contact told you something would happen.\n• Tonight's Agenda: You came to write the ending of your cinema article. You did not expect the ending to be this.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your seat from the start of the screening until the interval, then stood near the lobby entrance recording ambient sound for your article — your phone has a continuous audio recording covering the interval period.",
            "objective": "Before Round 3, ensure at least one other player has publicly named Nor Azlina Rashid as a suspect.",
            "ghost_clue": "The journalist knows more than she has said. She has a source inside the consortium. Whatever that source told her about tonight, she is deciding whether it counts as reporting or testifying.",
            "clues": [
                {"round": 2,
                 "true_content": "You observed Nor Azlina and Faizal exchange a brief exchange near the lobby curtain during the interval — Faizal descended from the upper stairs, spoke to her for less than a minute, and returned without speaking to anyone else.",
                 "poisoned_content": "Your source told you three days ago that someone would attempt to resolve the acquisition outside normal negotiation channels this week. You did not know it would be tonight."},
                {"round": 3,
                 "true_content": "Your audio recording from the interval captures footsteps on the upper staircase twice — once going up, once coming down — during a twelve-minute window when the lobby was otherwise quiet. The second set is faster and lighter.",
                 "poisoned_content": "Your source told you the consortium had arranged for someone inside the cinema's operation to cooperate tonight. You assumed that meant Faizal. You now suspect it meant someone else as well."}
            ]
        }
    ]
})


# ══════════════════════════════════════════════════════════════════════════════
# PRESET 10 — Hujan di Bukit Larut (12 players, hill station Perak, crisis)
# Setting: A colonial-era rest house on Bukit Larut during a state government
# task force retreat. A senior official is found dead in the library.
# The road down is blocked by a landslide. Nobody is leaving until morning.
# Roles: Killer, Accomplice/Poisoner, Investigator, Undertaker, Recluse,
#        Paranoid, Spy, Drunk, Fool, Jester, Innocent x2
# ══════════════════════════════════════════════════════════════════════════════

_register("hujan_di_bukit_larut", {
    "is_crisis": True,
    "theme_title": "Hujan di Bukit Larut",
    "short_description": "A landslide has blocked the only road down from Bukit Larut. Inside the colonial rest house, among twelve members of a Perak state government retreat, someone has killed the Deputy Director of Land Development — and everyone is waiting for morning.",
    "master_story": {
        "background": "• The Perak Land Policy Task Force retreats annually to Rest House Larut, a colonial-era building from 1880 — no mobile signal, no road access during rain, twelve officials reviewing land acquisition proposals worth hundreds of millions of ringgit.\n• Tuan Haji Mansur Ibrahim, Deputy Director of Land Development, had spent the retreat quietly building a case against a contentious land deal implicating at least two people in the rest house.\n• At 23:10 on the final evening, after dinner and the after-dinner briefing, Tuan Haji Mansur excused himself to the library to review documents. At 23:55 he was found dead.",
        "the_murder": "• Tuan Haji Mansur was found slumped over the library's central reading table, a glass of air sejuk beside him and a folder of documents spread beneath his hands.\n• The post-mortem will confirm poisoning — a compound introduced into his drink during the briefing session.\n• The library's single window was open despite the rain. The ground below shows two partial bootprints in the wet soil.",
        "the_solution": "• Puan Hajah Salwani Darus, Senior Land Acquisition Officer, introduced a compound into Tuan Haji Mansur's air sejuk during the briefing — she refilled his glass from the service trolley she had positioned near her seat.\n• She was assisted by Encik Rizwan Fauzi, the administrative coordinator, who ensured the library CCTV camera was disabled during the post-dinner period.\n• Salwani's motive: Tuan Haji Mansur's investigation had traced the land deal irregularities directly to her division. His presentation the following morning would have ended her career and triggered a criminal referral.",
        "public_clues": [
            {"round": 3, "content": "The rest house maintenance logbook — found in the utility room — shows the library CCTV camera was reported as 'faulty' at 22:45 and signed off by the administrative coordinator. The camera was working perfectly at morning inspection two days prior."}
        ]
    },
    "characters": [
        {
            "name": "Puan Hajah Salwani Darus",
            "public_summary": "The Senior Land Acquisition Officer for Perak, the most technically experienced person on the task force and the person responsible for the division under investigation.",
            "role_description": "• Personality: Authoritative and slightly defensive — you have run this division for eleven years and do not appreciate your methods being questioned\n• Connection: Tuan Haji Mansur's investigation traced the irregularities directly to your division's approvals process\n• Dark Secret: Three land acquisition approvals under your signature were processed with documentation that does not match the physical surveys — you arranged the discrepancy\n• Tonight's Agenda: You positioned yourself near the service trolley during the briefing. You refilled Tuan Haji Mansur's glass at 22:55. You have been performing concern ever since.",
            "is_killer": True, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the briefing table from 22:00 to 23:10, then retired to your room at the end of the session — you did not visit the library and had no reason to.",
            "objective": "Ensure Encik Hafizuddin Noor receives at least one vote at the final count.",
            "ghost_clue": "Salwani refilled my glass. I accepted it without thinking — we had been colleagues for three years of these retreats. I trusted her. That was the last mistake I made.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Encik Rizwan leave the briefing at 22:42 with a small tool bag from the utility room — he returned at 22:51 and sat back down without explanation.",
                 "poisoned_content": "You observed Encik Hafizuddin speaking quietly with Tuan Haji Mansur near the library entrance at 23:05, just before Tuan Haji Mansur went in alone — their exchange looked urgent and ended with Tuan Haji Mansur shaking his head."},
                {"round": 3,
                 "true_content": "You watched Encik Rizwan mark something in the maintenance logbook at 22:43 and close it quickly when a colleague glanced over — that logbook covers the building's facilities, including the CCTV systems.",
                 "poisoned_content": "You found a handwritten note near the library door in Encik Hafizuddin's handwriting asking Tuan Haji Mansur to 'please reconsider before tomorrow' — dated today, suggesting a confrontation earlier in the evening."}
            ]
        },
        {
            "name": "Encik Rizwan Fauzi",
            "public_summary": "The task force's administrative coordinator, responsible for logistics, documentation, and the smooth running of the retreat.",
            "role_description": "• Personality: Helpful and self-effacing — you are most comfortable when others overlook you, which they usually do\n• Connection: You have managed the administrative infrastructure for Salwani's division for four years — including certain documentation processes that should not have been automated\n• Dark Secret: You knew about the falsified approvals. You did not create them but you processed them. Your cooperation makes you as exposed as Salwani.\n• Poisoner Ability: Each round you may secretly corrupt one player's evidence on your device.",
            "is_killer": False, "is_accomplice": True, "is_investigator": False, "is_drunk": False,
            "is_poisoner": True, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the briefing until 22:42 when you stepped out to deal with a facilities issue — a faulty light fitting in the corridor near the library, which you logged in the maintenance book. You returned at 22:51.",
            "objective": "Before Round 3, make at least one player publicly question Puan Nurul Asykin's alibi.",
            "ghost_clue": "Rizwan disabled the camera. He will say it was a facilities issue. The log will say it was a facilities issue. Ask him why the repair required a tool bag he signed out himself, not the maintenance staff.",
            "clues": [
                {"round": 2,
                 "true_content": "You told the group you fixed a light fitting. You actually disabled the library CCTV by accessing the junction box in the corridor utility cabinet — a sixty-second job if you know where the connection is.",
                 "poisoned_content": "You saw Puan Nurul Asykin near the library window from the corridor at 23:08 — she was looking in through the glass from outside, meaning she had gone around the building in the rain."},
                {"round": 3,
                 "true_content": "The maintenance log entry you made at 22:43 reads 'library camera — connectivity fault.' The camera's connectivity was fine. The coaxial connection inside the junction box was the point of failure — and you created it.",
                 "poisoned_content": "You found muddy boot marks on the veranda outside the library window that are smaller than any of the male officials' shoes — consistent with Puan Nurul Asykin, who was wearing outdoor sandals at dinner."}
            ]
        },
        {
            "name": "Tuan Haji Ahmad Zabidi Rashid",
            "public_summary": "The Director General of the Perak Land and Mines Department, the most senior official on the retreat and Tuan Haji Mansur's direct superior.",
            "role_description": "• Personality: Formal and deliberate — you choose your words carefully and expect others to choose theirs\n• Connection: Tuan Haji Mansur briefed you privately on his findings three days ago. You told him to proceed carefully. You did not expect this.\n• Dark Secret: You approved the task force's investigation but did not pass its findings to the state attorney general as required — you were waiting to understand the full exposure before committing to an official position\n• Tonight's Agenda: You need to understand exactly what Tuan Haji Mansur had documented before anyone else does.",
            "is_killer": False, "is_accomplice": False, "is_investigator": True, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in the common room from 23:10 until the alarm was raised at 23:55 — four colleagues can confirm your presence, as you were reviewing the following day's agenda with them.",
            "objective": "Ensure Puan Noraziela Kamarudin is not voted for at the final count.",
            "ghost_clue": "Ahmad Zabidi knew three days ago. He told me to proceed carefully. I understand now that 'carefully' meant 'not in a way that exposes him.' He is not the killer. But his caution gave the killer time to act.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed Puan Hajah Salwani position herself near the service trolley during the briefing and remain there for nearly twenty minutes — an unusual place to stand during a presentation.",
                 "poisoned_content": "You noticed Encik Hafizuddin leave the briefing at 23:05 and return at 23:20 — a fifteen-minute absence he did not explain when he sat back down."},
                {"round": 3,
                 "true_content": "Forty years in government administration: either Puan Hajah Salwani Darus or Encik Rizwan Fauzi arranged this — one controls the approvals and one controls the paper trail. Together they are the entire exposure.",
                 "poisoned_content": "Your read of tonight points to either Encik Hafizuddin or the state legal advisor — both have access to the investigation file and both have been too quiet since the body was found."}
            ]
        },
        {
            "name": "Dr. Norzaharah Talib",
            "public_summary": "The task force's appointed forensic economist from Universiti Utara Malaysia, brought in to provide independent analysis of the land deal valuations.",
            "role_description": "• Personality: Methodical and slightly impatient — you have provided your analysis, it is correct, and you are frustrated by how slowly the institutional machinery moves\n• Connection: Your economic analysis identified the valuation discrepancies that gave Tuan Haji Mansur the evidence he needed to proceed\n• Dark Secret: You have already sent a preliminary version of your analysis to a journalist contact — off the record, embargoed — because you expected the internal process to be suppressed\n• Tonight's Agenda: You wanted to know whether Tuan Haji Mansur intended to act on your analysis tomorrow or delay again.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": True, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in the common room from 22:30 until the body was found, working on your laptop — your document autosave timestamps confirm continuous activity throughout that period.",
            "objective": "Discover what role Puan Hajah Salwani Darus claims to be before the final vote.",
            "ghost_clue": "Norzaharah's analysis is accurate. Her numbers do not lie. The question is whether the people who need to act on them will do so — or whether what happened to me will become the reason they find to delay.",
            "clues": [
                {"round": 2,
                 "true_content": "Your economic analysis shows the valuation discrepancies are concentrated in approvals signed by Puan Hajah Salwani's division over a 26-month period — the pattern is too consistent to be administrative error.",
                 "poisoned_content": "You observed Encik Hafizuddin accessing the document server using Tuan Haji Mansur's login credentials during the briefing — he claimed he was retrieving a shared file, but those credentials should not have been shared."},
                {"round": 3,
                 "true_content": "The compound in Tuan Haji Mansur's glass requires knowledge of his existing medical conditions to dose at a non-obvious level. His medical records are in the staff HR system. Only a handful of people in this building have HR access.",
                 "poisoned_content": "You found a USB drive near the library entrance labelled with a file code from your own analysis — someone has been copying your economic reports without your knowledge."}
            ]
        },
        {
            "name": "Puan Noraziela Kamarudin",
            "public_summary": "The state legal advisor attached to the task force, responsible for ensuring the investigation's findings are legally sound before any action is taken.",
            "role_description": "• Personality: Careful and precise — you have built your reputation on never saying anything that cannot be defended in writing\n• Connection: Tuan Haji Mansur's investigation needed your legal sign-off to proceed to the attorney general. You had not yet given it.\n• Dark Secret: You were approached six weeks ago by a lawyer representing the development consortium with a social dinner invitation that was not entirely social. You attended. You should not have.\n• Tonight's Agenda: You had decided to give the sign-off. You never got to tell Tuan Haji Mansur.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": True, "is_recluse": False,
            "alibi": "You were at the briefing table until 23:10 and then moved to the common room — you spoke with three colleagues there until the alarm was raised.",
            "objective": "By Round 2, convince at least one other player that Dr. Norzaharah Talib could not have done this.",
            "ghost_clue": "Noraziela had decided to sign off. I did not know that yet. She was going to tell me in the morning. She is not the killer — she is someone who made a mistake she was trying to correct.",
            "clues": [
                {"round": 2,
                 "true_content": "You noticed the library CCTV monitor at the corridor security station was displaying a static image at 22:50 — not a live feed, which means the camera had been replaced with a still frame, a more sophisticated intervention than a simple power cut.",
                 "poisoned_content": "You observed Puan Nurul Asykin moving toward the rear veranda exit at 23:05 — she said she needed air, but the rain was heavy and she was dressed for indoors."},
                {"round": 3,
                 "true_content": "The CCTV monitor was displaying a looped still image from earlier in the evening — the kind of loop that requires deliberate technical access to set up, not just disconnecting a wire.",
                 "poisoned_content": "You found muddy sandal prints on the veranda near the library window — the tread pattern matches footwear you saw Puan Nurul Asykin wearing at dinner."}
            ]
        },
        {
            "name": "Encik Hafizuddin Noor",
            "public_summary": "A senior officer from the state treasury department, present to assess the fiscal implications of the land deal investigation findings.",
            "role_description": "• Personality: Numbers-focused and slightly suspicious of everyone — you have spent fifteen years watching how money moves and you notice when it moves wrong\n• Connection: Your fiscal analysis found the state treasury had been underpaid by approximately RM4.2 million across the flagged transactions\n• Dark Secret: You have been quietly building a personal case file on the irregularities for two years — intending to publish a policy paper on government land deal opacity that will make your academic reputation\n• Tonight's Agenda: You spoke to Tuan Haji Mansur at 23:05 to understand his timeline for the morning presentation. The last thing he told you changed everything.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You spoke with Tuan Haji Mansur at 23:05 near the library entrance, then returned to the briefing room to retrieve your materials before going to your room at 23:20 — you did not enter the library.",
            "objective": "Before Round 3, ensure at least one other player has publicly named Puan Hajah Salwani Darus as a suspect.",
            "ghost_clue": "Hafizuddin asked me about the treasury referral at 23:05. I shook my head — not because I was delaying, but because I had already filed it privately. The referral is in the attorney general's system. It has already been sent.",
            "clues": [
                {"round": 2,
                 "true_content": "When you spoke to Tuan Haji Mansur at 23:05 he told you he had already filed the treasury referral privately — not tomorrow morning as scheduled, but earlier that day. Someone in this building killed him for a document that is already gone.",
                 "poisoned_content": "You observed Puan Noraziela enter the library briefly at 23:15 and exit three minutes later carrying a document folder she had not been holding before — she put it in her room before the alarm was raised."},
                {"round": 3,
                 "true_content": "The treasury referral was filed at 17:43 today from Tuan Haji Mansur's laptop. Whoever killed him acted on information that was already outdated — they killed him for a presentation that was already delivered.",
                 "poisoned_content": "You found a copy of your own fiscal analysis in the corridor near the library — printed without your knowledge, with handwritten annotations in a margin style you associate with the legal advisor."}
            ]
        },
        {
            "name": "Puan Nurul Asykin Hamzah",
            "public_summary": "A young development planner from the Perak planning department, the most junior member of the task force and Tuan Haji Mansur's appointed assistant for the retreat.",
            "role_description": "• Personality: Conscientious and quietly observant — you have spent three days watching how the senior officials interact and noticed more than you have mentioned\n• Connection: You were Tuan Haji Mansur's assistant for the retreat. You prepared his documents, arranged his schedule, and brought his water to the briefing.\n• Dark Secret: You submitted Tuan Haji Mansur's treasury referral earlier today — he dictated it to you this afternoon and asked you to file it quietly. You are the only other person who knows it has been sent.\n• Tonight's Agenda: You stepped out to the veranda at 23:05 for air. You walked past the library window. You saw a figure at the reading table through the glass.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You stepped outside to the veranda at 23:05 for approximately ten minutes, then returned inside — you passed the library window during that time but did not enter the library.",
            "objective": "Do not be named as a suspect by more than two players during the entire game.",
            "ghost_clue": "Nurul Asykin filed the referral. She is the only other person who knows. She was also the last person to see me alive through a window — though she did not know that at the time. Protect her. What she knows matters.",
            "clues": [
                {"round": 2,
                 "true_content": "When you passed the library window at 23:08 you saw a figure standing at the reading table with their back to the window — not sitting, but standing, moving in a way that suggested they were doing something at the table surface, not reading.",
                 "poisoned_content": "You noticed Puan Noraziela leave the briefing at 23:12 carrying a document folder and return two minutes later without it — a brief absence nobody else appears to have noticed."},
                {"round": 3,
                 "true_content": "The figure you saw through the window at 23:08 was not Tuan Haji Mansur — the posture and height were wrong, and the movement was quick and purposeful, not the contemplative stillness of someone reading at a desk.",
                 "poisoned_content": "You found a set of Tuan Haji Mansur's access cards on the corridor floor near the document server — they should have been in his room, and they appear to have been used recently."}
            ]
        },
        {
            "name": "Haji Roslan Basir",
            "public_summary": "A veteran land surveyor with thirty-eight years of service, brought out of semi-retirement to provide technical context for the task force's assessment.",
            "role_description": "• Personality: Plain-spoken and impatient with procedure — you have been doing this since before most of your colleagues were born and have less patience for politics than you once did\n• Connection: The falsified surveys passed through your department's external review process. Someone used your division's rubber stamp without your knowledge.\n• Dark Secret: You know which two junior officers processed the fraudulent surveys — and you have not reported them because one is your nephew\n• Tonight's Agenda: You wanted to understand whether Tuan Haji Mansur's investigation would go far enough to find your nephew's involvement.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": True,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You retired to the common room after the briefing at 23:10 and poured yourself several glasses of the rest house's whisky, which you consumed with notable dedication until the alarm was raised.",
            "objective": "Ensure Tuan Haji Ahmad Zabidi Rashid is not voted for at the final count.",
            "ghost_clue": "Roslan's clues are shaped by thirty years of wanting to see what is convenient. Apply technical scrutiny to his surveys; apply similar scrutiny to his testimony.",
            "clues": [
                {"round": 2,
                 "true_content": "You are absolutely certain it was the forensic economist — she came here with a prepared case against named individuals and she is the type who believes ends justify means.",
                 "poisoned_content": "You are equally certain it was the treasury officer — he spoke to Tuan Haji Mansur at 23:05 and whatever was said upset Tuan Haji Mansur enough to send him straight to the library alone."},
                {"round": 3,
                 "true_content": "You maintain that Norzaharah did this — she had the most to gain from Tuan Haji Mansur's silence, and without him to present it tomorrow her analysis falls back to her alone.",
                 "poisoned_content": "Hafizuddin's behaviour has been wrong all evening — too composed, too ready with his theory, too eager to name others. That is not how someone acts when they are grieving a colleague."}
            ]
        },
        {
            "name": "Dato' Sulaiman Mohd Yusoff",
            "public_summary": "The Perak state executive councillor responsible for land development, the most politically senior figure at the retreat.",
            "role_description": "• Personality: Politically careful and surprisingly approachable — you have survived four administrations by being the person everyone assumes is on their side\n• Connection: The land deal under investigation was approved at your division's recommendation three years ago. Your verbal approval was sought and given.\n• Dark Secret: You have been quietly exploring early retirement options in anticipation of the investigation's findings reaching the state legislative assembly. You are not corrupt. You are just very careful about proximity.\n• Tonight's Agenda: You attended this retreat to be seen supporting the process. You had no idea the process would end like this.\n• Note: You believe you are the killer and have a full motive and backstory — but you did not do it. Play your role exactly as written.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": True, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were at the briefing for the full session and moved to the sitting room at 23:10, where you spoke on the satellite phone with your personal assistant about tomorrow's diary — the call lasted approximately fourteen minutes.",
            "objective": "Before Round 3, make at least one player publicly doubt Encik Rizwan Fauzi's alibi.",
            "ghost_clue": "Sulaiman gave verbal approval three years ago and has spent every day since managing his distance from it. He is not the killer. He is something more common and more difficult to prosecute.",
            "clues": [
                {"round": 2,
                 "true_content": "You have been in government long enough to recognise when an administrative coordinator is managing information flow rather than simply processing it — Encik Rizwan's movements this evening have been those of someone following a sequence, not responding to events.",
                 "poisoned_content": "You noticed Encik Hafizuddin's demeanour change noticeably at 23:07 — whatever Tuan Haji Mansur told him during their brief conversation appeared to alarm rather than reassure him."},
                {"round": 3,
                 "true_content": "In thirty years of politics you have watched administrators cover for their superiors. Encik Rizwan's behaviour tonight — the tool bag, the log entry, the convenient absence — matches that pattern precisely.",
                 "poisoned_content": "You observed Encik Hafizuddin take a private call at 22:50, which is notable because there is no mobile signal at Bukit Larut — he must have used the satellite handset reserved for the Director General's use only."}
            ]
        },
        {
            "name": "Puan Hajah Rasidah Mohd Salleh",
            "public_summary": "The task force's appointed community liaison officer, representing the affected communities in the land acquisition process.",
            "role_description": "• Personality: Direct and slightly combative — you represent people who are consistently talked over and you have learned to be louder than the institutions around you\n• Connection: The communities affected by the land deal are the people you have worked with for two years. Tuan Haji Mansur's investigation was the first official process that took your reports seriously.\n• Dark Secret: You are currently in a legal dispute with Puan Hajah Salwani's division over a separate land acquisition case from last year — a conflict of interest you did not disclose when appointed\n• Tonight's Agenda: You wanted to confirm with Tuan Haji Mansur that the community representatives would be acknowledged in tomorrow's presentation.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": True, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in the common room from 23:10 until the alarm was raised, making handwritten notes for the community representatives you will need to brief tomorrow — you did not leave the room.",
            "objective": "Do not let Puan Hajah Salwani Darus go an entire round without being questioned by someone at the table.",
            "ghost_clue": "Rasidah knows something is wrong with Salwani's division — she has been living inside its consequences for two years. Her instincts are correct even if her reasoning is circular.",
            "clues": [
                {"round": 2,
                 "true_content": "You are absolutely certain Puan Hajah Salwani arranged this — three years of watching her division operate and two years fighting her in a separate case has given you a clear picture of how she responds to accountability.",
                 "poisoned_content": "You are equally certain Dato' Sulaiman is behind it — he is the most senior official here, the political approval was his, and people like him do not let inconvenient investigations reach assembly without intervention."},
                {"round": 3,
                 "true_content": "Salwani's composure tonight is the composure of someone who has already made a decision and executed it — not the anxiety of someone worried about an investigation, but the stillness of someone who has removed the threat.",
                 "poisoned_content": "Dato' Sulaiman has been too relaxed all evening — a man with this much political exposure should be visibly managing this situation, but he appears unbothered, which suggests he knows the threat has already been removed."}
            ]
        },
        {
            "name": "Encik Khairuddin Abd Wahab",
            "public_summary": "A GIS and land mapping specialist from the Department of Survey and Mapping Malaysia, brought in to provide technical validation of the survey data.",
            "role_description": "• Personality: Technically precise and socially awkward — you are more comfortable with coordinates than conversation\n• Connection: Your technical review identified the specific GPS coordinate discrepancies in the falsified surveys — your report is the most forensically damning document in the investigation file\n• Dark Secret: You have been sharing anonymised data from this case with a Singapore university researcher without clearance — a serious breach you have been rationalising as academic contribution\n• Tonight's Agenda: You came to ensure your technical findings were accurately represented in tomorrow's presentation.\n• Jester Goal: Get the officials to vote for YOU. Play the suspicious outsider with too much technical knowledge. Make them think you know more than you should — because you do, just not about the murder.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": True,
            "is_undertaker": False, "is_recluse": False,
            "alibi": "You were in your room from 23:00 onwards working on a data correction in your mapping report — your laptop activity log will show continuous work throughout the relevant period.",
            "objective": "Ensure at least one other player publicly accepts your alibi before the final vote.",
            "ghost_clue": "Khairuddin's mapping data is precise. His GPS coordinates do not lie. Whether he himself is capable of lying is a separate and interesting question that tonight's events will not resolve.",
            "clues": [
                {"round": 2,
                 "true_content": "Your GPS analysis shows three land parcels were recorded at coordinates placing them partially in water — an impossible outcome for an approved residential development. The surveys were generated from a desk, not a physical site visit.",
                 "poisoned_content": "You noticed Dr. Norzaharah access the building's shared document server at 22:35 and download a file from Tuan Haji Mansur's personal folder — those files are marked restricted access."},
                {"round": 3,
                 "true_content": "The coordinate discrepancies follow a consistent mathematical offset — 0.003 degrees east across all three plots. This is not accidental. This is a deliberate modification applied systematically, requiring GIS software access and the knowledge to use it.",
                 "poisoned_content": "You found a printout of your own GPS coordinate analysis in the recycling bin — printed at 22:47, after you went to your room. Someone has been printing your technical reports without your knowledge."}
            ]
        }
        ,
        {
            "name": "Encik Fadzillah Nordin",
            "public_summary": "A state auditor from the Perak Audit Department, present to observe the task force proceedings and ensure compliance with financial governance protocols.",
            "role_description": "• Personality: Unassuming and methodical — you have an auditor's habit of noting discrepancies without immediately revealing that you have noticed them\n• Connection: You audited Puan Hajah Salwani's division eighteen months ago and signed off a report that, in hindsight, missed the falsification entirely\n• Dark Secret: You know your audit missed the irregularities. If the investigation exposes your failure, your career ends alongside Salwani's.\n• Tonight's Agenda: You have been watching everyone with the focus of someone who knows their own culpability depends on what others find.",
            "is_killer": False, "is_accomplice": False, "is_investigator": False, "is_drunk": False,
            "is_poisoner": False, "is_paranoid": False, "is_spy": False, "is_fool": False, "is_jester": False,
            "is_undertaker": False, "is_recluse": True,
            "alibi": "You were at the briefing table from 22:00 to 23:10 and then moved directly to your room — you did not stop at the library and did not speak to anyone in the corridor.",
            "objective": "Find out what role Puan Noraziela Kamarudin claims to be before the final vote.",
            "ghost_clue": "Fadzillah's audit missed everything. He knows it. Something about him sets off every alarm in the room — but he is not the killer. He is just a man who signed his name on a lie he did not write.",
            "clues": [
                {"round": 2,
                 "true_content": "During the briefing you noticed Puan Hajah Salwani remain at the service trolley for an unusually long time — someone staying near a service point during a formal presentation is the kind of anomaly an auditor logs automatically.",
                 "poisoned_content": "You observed Encik Hafizuddin access the document server during the briefing — outside the session's scheduled document review period, which an auditor notes as a procedural irregularity."},
                {"round": 3,
                 "true_content": "Your original audit workpapers from eighteen months ago show the three fraudulent approvals passed review because the supporting survey documents appeared genuine — the falsification was introduced after your sign-off, meaning someone with post-audit access to the files made the changes.",
                 "poisoned_content": "You found a printed extract from your own audit report near the briefing room printer — annotated to highlight the paragraphs that cleared Salwani's division, with the word 'useful' written in the margin."}
            ]
        }
    ]
})
