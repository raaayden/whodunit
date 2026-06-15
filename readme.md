# 🕵️‍♂️ AI Murder Mystery Party App

A fully automated, mobile-first social deduction game powered by AI. 

Instead of reading pre-written scripts from a box, this application uses Google's Gemini AI to dynamically generate a unique "Web of Suspicion"—complete with interconnected dark secrets, round-by-round clues, and a hidden killer—based on any theme the host chooses. Players join a unified lobby via their phones, receive secret identities, and use an interactive digital notebook to track alliances and vote.

## ✨ Features

* **Dynamic AI Generation:** Powered by Gemini 2.5 Flash. Generates custom characters, backstories, clues, and an overarching plot in seconds.
* **"God-Mode" Host Dashboard:** A dark-mode control panel to create games, release round-by-round clues, and monitor live player actions (votes, deaths, and roles) in real-time.
* **Mobile-First Player UI:** Players join via a single room link. The UI includes auto-polling to silently update game states without manual refreshing.
* **Interactive Digital Notebook:** Players can take notes on other characters and mark them as "Sus" or "Alright Fam." Data is saved locally.
* **Delayed Assassinations:** The Killer (and optional Accomplice) can secretly target players. Eliminated players "drop dead" at the start of the next round.
* **No-Login Architecture:** Players join using a 6-character access key generated dynamically; no passwords or sign-ups required for guests.

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI, Uvicorn
* **Database:** Supabase (PostgreSQL)
* **AI Engine:** Google Generative AI (Gemini 2.5 Flash)
* **Frontend:** Vanilla HTML, CSS, JavaScript (served directly via FastAPI)
* **Deployment:** Ready for Render

## 🚀 Getting Started (Local Development)

### 1. Prerequisites
* Python 3.8+
* A [Supabase](https://supabase.com/) account and project.
* A [Google AI Studio](https://aistudio.google.com/) API Key.

### 2. Database Setup (Supabase)
Navigate to your Supabase SQL Editor and execute the following script to create the necessary tables:

```sql
-- Store the game instances
CREATE TABLE games (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  theme TEXT NOT NULL,
  status TEXT DEFAULT 'waiting', -- waiting, started, finished
  current_round INTEGER DEFAULT 0,
  master_story TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Store the players and their roles
CREATE TABLE players (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  game_id UUID REFERENCES games(id),
  access_key TEXT UNIQUE NOT NULL,
  claimed_by_user TEXT,
  character_name TEXT,
  public_summary TEXT,
  role_description TEXT,
  is_killer BOOLEAN DEFAULT FALSE,
  is_accomplice BOOLEAN DEFAULT FALSE,
  is_dead BOOLEAN DEFAULT FALSE,
  death_round INTEGER DEFAULT 99,
  voted_for TEXT
);

-- Store clues with release controls
CREATE TABLE clues (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  game_id UUID REFERENCES games(id),
  player_id UUID REFERENCES players(id),
  round_number INTEGER NOT NULL,
  content TEXT NOT NULL,
  is_released BOOLEAN DEFAULT FALSE
);

-- Store interactive player notes
CREATE TABLE player_notes (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  game_id UUID REFERENCES games(id),
  owner_player_id UUID REFERENCES players(id),
  target_character TEXT NOT NULL,
  status TEXT DEFAULT 'neutral', -- 'sus', 'alright fam', 'neutral'
  note_text TEXT,
  UNIQUE(owner_player_id, target_character)
);