# Lore Spinner — Text-Based Narrative RPG with Multi-Agent DM

An immersive, text-based narrative role-playing game powered by a multi-agent AI system. The player interacts with a **Dungeon Master (DM) Agent**, who orchestrates **four autonomous subagents** (World Keeper, Faction Weaver, Encounter Architect, Lore Keeper) to simulate a dynamic, living world.

## Core Features

- **Genre-Agnostic Settings**: Mix and match sci-fi, fantasy, historical, cyberpunk, apocalyptic, or custom themes.
- **Narrative Character Creation**: A 3-question narrative interview that dynamically generates starting attributes.
- **Hidden Stats & Narrative Authority**: The player experiences outcomes purely through immersive narration rather than seeing dice rolls, difficulty classes, or raw stats. Abilities level up dynamically in the background through actions ("learn-by-doing"), and the DM weaves mechanical outcomes seamlessly into the fiction.
- **Multi-Agent DM System**:
  - **DM Agent**: Narrates events, resolves checks, and offers choices. The DM also performs strict **Contextual Verification** behind the screen, checking the player's claims against their actual inventory and skills to prevent narrative exploits.
  - **World Keeper**: Manages weather, time, and environment ambient events.
  - **Faction Weaver**: Tracks NPC faction standings, agendas, and player reputation.
  - **Encounter Architect**: Creates scaling combat encounters, enemy AI, and loot tables.
  - **Lore Keeper**: Manages world history, quest hooks, and secrets.
- **Organic Narrative Memory**: The DM is continuously fed active **Narrative Threads**, unlocked lore details, and secret clues on turn startup, allowing them to organically weave ongoing tasks into the evolving story rather than treating them like rigid checklists.
- **Autonomous Faction Projects**: Factions independently pursue long-term, background goals (e.g., "Researching a cure"). The Faction Weaver tracks these mechanical countdowns during heartbeats. Upon completion, they fire narrative events and can permanently alter the World State.
- **Intelligent Option Generation**: The DM intelligently adapts the 4 interactive choices based on context:
  - **Survival Override**: Immediate life-threatening danger forces all choices into desperate escape/survival attempts.
  - **Combat Override**: Active combat forces choices into tactical maneuvers, attacks, spells, or fleeing.
  - **Social Override**: Intense conversations force choices into dialogue options.
  - **Camping Override**: Resting shifts choices to camp activities while enforcing bodily needs (hunger/exhaustion).
  - **Exploration & Progression**: Subtly weaves in progression for *every* local quest, ignores distant quests, and rarely tempts the player with a character-specific High Risk/High Reward option.
- **Risky Freeform Crafting**: Players can invent custom items using logical scrap (MacGyver style). The DM secretly rolls ability checks and enforces creative consequences (damage, broken materials) on failure, with an anti-softlock mechanism for critical quest items.
- **Node-Graph Travel Enforcement**: Spatial positioning is strictly enforced. Players must use the dedicated system menu to travel between locations; the DM will refuse attempts to teleport via text actions.
- **Crash-Resilient Lazy Generation**: Instant saving on character creation. The heavy generation (World Bible, Map) is deferred to the first game loop to prevent API timeout wipeouts.
- **Contextual Visual Overhaul**: Terminal UI themes change dynamically based on the player's current location, with cleanly separated narrative text and grouped system menus.
- **Living World Heartbeats**: Subagents periodically trigger (every 5-10 turns) in the background, updating the world environment and faction politics in surprising ways independently of player actions.
- **Budget Mode**: Toggleable mode that reduces LLM calls by replacing subagent heartbeats with rule-based heuristics to minimize API token costs.
- **Saves & DM Logs**: Support for unlimited named save slots, fuzzy save search, and compacted markdown DM narrative logs.

---

## Setup and Installation

### 1. Prerequisites
- Python 3.10 or higher.
- A virtual environment (recommended).

### 2. Install Dependencies
Run the following command to install the required packages:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.template` to a new file named `.env`:
```bash
copy .env.template .env
```
Open `.env` and fill in the API keys for the providers you wish to use:
- `GEMINI_API_KEY` (for Google Gemini)
- `OPENAI_API_KEY` (for OpenAI)
- `ANTHROPIC_API_KEY` (for Anthropic Claude)

---

## Running the Game

You can run the game using different LLM providers or a mock provider for local testing.

### Google Gemini (Default)
```bash
python main.py --provider gemini --model gemini-2.5-flash
```

### OpenAI
```bash
python main.py --provider openai --model gpt-4o-mini
```

### Anthropic Claude
```bash
python main.py --provider anthropic --model claude-3-5-sonnet-20241022
```

### Mock Provider (Offline / No API Key required)
```bash
python main.py --provider mock
```

### Command-Line Arguments
- `--provider`: Choose from `gemini`, `openai`, `anthropic`, or `mock` (default: `gemini`).
- `--model`: Specific model ID to use for the selected provider.
- `--budget`: Starts the campaign with **Budget Mode enabled** to reduce API costs.

---

## In-Game Controls & Commands

During your turn, you can choose from the generated choices, type a custom action, or use one of the following special commands:

- **`save`**: Force-saves the current campaign state.
- **`quit`** or **`exit`**: Saves your progress and returns to the main menu.
- **`budget on` / `budget off`**: Enables or disables Budget Mode in real-time.
- **`/summary`**: Compiles an immersive, comprehensive overview of the character status, equipped slot gear, relationships, active quests, unlocked lore details, and active faction project clocks.
- **`OOC: <query>`** (Out-of-Character): Intercepts the query locally to view hidden state without calling the LLM. Examples:
  - `OOC: stats` or `OOC: character` — View character HP, Level, XP, equipped gear, inventory, and hidden ability tags.
  - `OOC: world` or `OOC: quests` — View current turn count, time of day, active quests, and environmental modifiers.
  - `OOC: lore` or `OOC: secrets` — View unlocked historical lore details and secret clues.
  - `OOC: log` — View the recent history log.

---

## Running Tests
Run the unit test suite to verify the game engine mechanics:
```bash
python test_engine.py
```
