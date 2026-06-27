"""
presets.py — Hardcoded game templates for the Experimental Lab.
Add new presets here. main.py imports spawn_preset_game() and PRESET_REGISTRY.
"""
import json
from fastapi import HTTPException, Request

# Imported from functions.py at runtime via init_preset_clients()
supabase       = None
generate_key   = None


def init_preset_clients(_supabase, _generate_key):
    global supabase, generate_key
    supabase     = _supabase
    generate_key = _generate_key


# ── Registry ──────────────────────────────────────────────────────────────────
# Add new presets here. Key = URL slug, value = template dict.

PRESET_REGISTRY: dict[str, dict] = {}   # populated below


# ── Shared helpers ────────────────────────────────────────────────────────────

def _register(slug: str, template: dict):
    PRESET_REGISTRY[slug] = template


def spawn_preset_game(request: Request, preset_id: str) -> dict:
    if preset_id not in PRESET_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")

    template  = PRESET_REGISTRY[preset_id]
    is_crisis = template.get("is_crisis", False)

    game_insert = supabase.table("games").insert({
        "theme":             template["theme_title"],
        "theme_title":       template["theme_title"],
        "short_description": template["short_description"],
        "master_story":      json.dumps(template["master_story"]),
        "is_crisis_game":    is_crisis,
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
            "ghost_clue": "The duty officer knew how the footage gap was created. He was told to stay quiet. He is telling the truth when he says he does not know who ordered it — but the order came through the security division.",
            "clues": [
                {"round": 2, "true_content": "You are utterly convinced that Pak Wirawan is orchestrating this — the way he positioned himself near the commissioner during the post-discovery briefing was textbook misdirection.", "poisoned_content": "You are certain Agent Zara is hiding something — the way she described handing Azman his coffee was too rehearsed, too precise."},
                {"round": 3, "true_content": "You know in your gut it was Pak Wirawan who gave the order — the anomaly you were told to ignore came through an Indonesian-registered device signature.", "poisoned_content": "Agent Zara's timeline does not add up — she says she entered the conference room after the catering staff, but your access log shows her badge was scanned ninety seconds earlier."}
            ]
        }
    ]
})
