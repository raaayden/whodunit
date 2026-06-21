# 🕵️ Whodunit — AI Murder Mystery Party App

A mobile-first social deduction party game powered by AI. Gather your friends in a room, scan a QR code, and let the mystery unfold — no scripts, no boxes, no prep required.

---

## 🎭 How It Works

### For the Host
The host opens the dashboard and generates a mystery in seconds — just pick a theme (e.g. *"1920s speakeasy"*, *"corporate retreat gone wrong"*) and choose the optional roles to include. The AI generates a full cast of characters, interconnected dark secrets, round-by-round clues, and a hidden killer — all unique every time.

Once the game is created, the host shares a room link (or QR code) with the players and controls the pace of the game from their device — releasing clues each round and ending the game when the group is ready to vote.

### For the Players
Players join by opening the room link on their phone and entering their real name. They're assigned a secret character identity with a role sheet only they can see. From that point on, the game is social — players talk, bluff, accuse, and defend themselves in person while checking their phones for new clues each round.

At the end of the final round, every player votes for who they think the killer is. The results and true identities are revealed on every device simultaneously.

---

## 🃏 Roles

Every game has a **Killer** and a cast of **Innocents**. Optional roles can be toggled by the host at game creation:

| Role | What they do |
|---|---|
| 🔪 **Killer** | Eliminates one player between rounds. Must deflect suspicion. |
| 🤝 **Accomplice** | Knows who the killer is. Feeds disinformation and protects them. |
| ☠️ **Poisoner** | An accomplice variant. Secretly corrupts one innocent's clues each round — the victim never knows their evidence is false. |
| 🔎 **Investigator** | Receives a 50/50 ping in Round 2 — one of two named players is the killer. |
| 🍺 **Drunk** | Thinks they're a normal innocent. All their clues are completely false. |
| 🧠 **Paranoid** | Sincerely believes a specific innocent player is the killer. Not lying — just wrong. |

---

## 🔄 A Round of Play

1. **Host releases the round** — private clues appear on each player's phone, and any public announcements appear on everyone's screen simultaneously.
2. **Players talk in person** — compare clues, share (or misrepresent) what they know, form alliances, cast suspicion.
3. **The killer (and poisoner) act** — the killer secretly locks in their next elimination target. The poisoner secretly picks whose next clue gets corrupted.
4. **Repeat** for 3 rounds, then everyone votes.

Eliminated players are still physically present and can keep talking — they just lose their vote and unlock a **ghost clue** they can pass to one living player from beyond the grave.

---

## 📖 After the Game

When the host ends the game, the AI writes a short **noir story recap** narrating the night's events — who died, whether the poisoner struck, and whether the killer escaped or was caught. Every player sees it simultaneously on their phone.

---

## ✨ Key Features

- **No login required** — players join with a 6-character access key, no accounts or sign-ups
- **Fully dynamic** — every game is uniquely generated from a theme prompt; no two games are alike
- **Mobile-first** — designed to be played on phones in a room with other people
- **Replayable templates** — generated games are saved as templates and can be replayed with a new group instantly (no AI call needed)
- **God-mode host dashboard** — live view of all roles, votes, eliminations, and player actions in real time
- **Interactive notebook** — players mark others as 🔴 Sus or 🟢 Alright Fam and take private notes
- **Pre-generated poisoned clues** — no runtime AI calls mid-game; everything is ready at game start

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL) |
| AI Engine | Google Gemini 2.5 Flash Lite (`google-genai`) |
| Frontend | Vanilla HTML, CSS, JavaScript |
| Deployment | Render |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- A [Supabase](https://supabase.com/) project
- A [Google AI Studio](https://aistudio.google.com/) API key

### Environment Variables
Create a `.env` file in the project root:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
GEMINI_API_KEY=your_gemini_api_key
HOST_ADMIN_PASSWORD=your_chosen_host_password
```

### Install & Run
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open `http://localhost:8000` for the host dashboard, and share `http://localhost:8000/room/<game_id>` with players.

---

## 🤖 Simulation Mode

A `simulation.py` script is included for testing games end-to-end without real players. Bots powered by **Gemini AI** join as all characters, make intelligent decisions (the killer picks targets strategically, voters reason through their clues), and print each player's full perspective — clues, notebook, ghost clues — after every round.

```bash
# Run against an existing room:
python simulation.py https://your-app.onrender.com/room/<game_id>

# Or let it create a fresh game from the first template:
python simulation.py
```
