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
