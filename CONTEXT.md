# Domain Context

This project is a text-based narrative RPG powered by a multi-agent AI system. A lead **Dungeon Master Agent** orchestrates the player-facing experience while **autonomous Subagents** independently manage world simulation, faction politics, combat encounters, and hidden lore. Forked from the simple-agent ReAct project, it reuses the model-agnostic LLM client abstraction.

## Glossary

### Dungeon Master (DM) Agent
The player-facing orchestrator agent that narrates the story, presents choices, resolves player actions, and weaves subagent outputs into a coherent narrative. The DM has **narrative authority** — it can override strict mechanical outcomes when doing so improves the story.

### Subagents
Smaller, asynchronous LLM instances that handle background simulation. They do not talk to the player.
- **Lore Keeper**: Watches the DM logs and player actions to update the Campaign Arc, spawn Inciting Incidents, track Narrative Threads, and organically introduce **World Aspects** (like Nemeses or Doom Clocks).
- **Faction Weaver**: Manages the hidden agendas, clocks, and reputations of Factions.
- **World Keeper**: Handles environmental states, weather, and physical world decay.

### World Aspects
Dynamic, persistent narrative constraints or entities attached to the World State. Depending on the story and player actions, the Lore Keeper can introduce these to make actions matter. Examples include:
- **Nemesis**: A specific rival who remembers the player and actively hunts them.
- **Doom Clock**: A world-ending countdown (e.g., "The Blight Spreads").
- **Heat / Notoriety**: A level of criminal status causing guards/bounties to appear.
- **Trauma / Scars**: Permanent physical or mental conditions affecting the character.
These are managed by the Lore Keeper and continuously fed to the DM so they impact the active narrative.

### Faction Weaver
The subagent responsible for NPC factions, political dynamics, reputation tracking, and faction-driven events. Factions scheme independently on heartbeat cycles.

### Encounter Architect
The subagent responsible for designing and resolving combat encounters, enemy generation, enemy tactics, and loot distribution. Triggered when hostile situations arise.

### Lore Keeper
The subagent responsible for world history, hidden secrets, quest hooks, and narrative reveals. Decides when lore becomes discoverable based on player actions and context.

### Ability Tag
A named skill or trait attached to a character with a hidden numeric modifier (e.g., `swordsmanship: +3`). Tags are the fundamental unit of character capability. Not all characters share the same tags — they are accumulated through backstory, experience, items, and environment.

### Tag Progression (Learn-by-Doing)
The system by which ability tags improve through use. When a character successfully uses a tag in a relevant context repeatedly, the tag's modifier increases. Progression thresholds are tracked by usage count.

### Hidden Stats
The design philosophy where all character mechanics (ability tags, modifiers, dice rolls, difficulty classes) are invisible to the player during normal gameplay. The player experiences outcomes through narrative description only. Stats can be inspected via saved JSON files or explicit Out-of-Character requests.

### Difficulty Class (DC)
A numeric threshold that an ability check must meet or exceed to succeed. DCs are set contextually by the DM or subagents based on the situation (e.g., rusty lock = DC 8, master-forged lock = DC 20).

### Narrative Authority
The DM Agent's power to override raw mechanical outcomes (dice rolls, ability checks) when doing so serves the story. This allows the DM to "fudge" results for dramatic tension, narrative pacing, or player enjoyment. However, Narrative Authority does NOT permit the DM to hallucinate items the player does not possess or skills they do not have; narrative outcomes must respect the player's factual inventory and ability tag constraints.

### Contextual Verification
The process by which the DM Agent checks the player's stated actions against their current inventory, equipped gear, and active abilities. If the player attempts an action using items or skills they do not possess, the DM enforces narrative constraints, leading to logical in-story setbacks or failures rather than letting the player self-narrate unauthorized capabilities.

### Heartbeat
A periodic trigger (every 5-10 turns) where background subagents (World Keeper, Faction Weaver) are called to advance the world state independently of player actions. Creates emergent surprises and a living world feel.

### Contextual Death
The death system where character death consequences vary based on narrative weight. Low-stakes failures may reset to a checkpoint. Mid-stakes defeats may result in consequences (capture, item loss, tag reduction). High-stakes situations with clear warnings may result in permanent character death.

### Out-of-Character (OOC)
A player communication mode prefixed with `OOC:` that breaks the narrative frame. Used to ask mechanical questions ("What are my stats?"), request meta information, or discuss the game itself. The DM responds factually rather than in character.

### Setting Pitch
A genre-blended world description generated by the DM at the start of a new game. The player selects from 4-5 generated pitches or combines elements. Settings are genre-agnostic — fantasy, sci-fi, cyberpunk, post-apocalyptic, historical, or blends thereof.

### DM Personality Traits
Randomized character traits assigned to the DM when a world is generated. Traits match the chosen genre (e.g., sardonic and noir for cyberpunk, theatrical and dramatic for high fantasy). Stored in world state.

### Save Slot
One of multiple independent game save directories. Each slot stores the complete game state (character, world, factions, encounters, lore, DM log) as separate JSON and Markdown files.

### DM Log
The narrative history of a game session stored as Markdown (`dm_log.md`). Subject to compaction when it exceeds 30 entries — raw entries are archived and the active log is summarized by the LLM to manage context window size.

### ReAct Loop
The Reason-Act-Observe orchestration pattern inherited from the simple-agent project. Each agent (DM and subagents) operates in this loop: Thought → Action → Observe → Answer.

### LLM Client
The model-agnostic abstraction layer that standardizes calls to different LLM providers (Gemini, OpenAI, Ollama). Inherited from the simple-agent project.

### Key Relationships
Long-term character connections (e.g. family, close friends, rivals, love interests) stored directly inside the character sheet JSON, ensuring the DM dynamically remembers personal ties and narrative anchors throughout the story.

### Faction NPC Records
The database of discovered side characters and their faction affiliations stored inside the factions ledger. Used by the DM and Faction Weaver to maintain continuity of NPC descriptions across multiple story beats.

### Discovered Locations
A persistent geographical registry of major cities, natural wonders, dungeons, or points of interest registered in the world state. Used by the DM and World Keeper to maintain spatial consistency and remember landmarks throughout the campaign.

### Consumable Items
Items in the player's inventory that possess a finite number of charges (e.g., Healing Salves, Energy Cells). Using these items provides a direct mechanical benefit or status change, decrements the charge count, and automatically destroys the item when depleted.

### Salvaging
The mechanical action of breaking down complex or unwanted items into fundamental raw materials (e.g., Junk Metal, Scrap Electronics, Scrap Leather, Scrap Cloth, Copper Wire). Salvaging is used to manage inventory space and gather components for future use.

### Crafting
The mechanical action by which the DM agent permanently deducts specified raw materials from the player's inventory to generate a newly assembled item. Crafting requests must make logical sense within the fiction and setting.

### Faction Projects
Long-term, background goals pursued autonomously by factions (e.g., "Building a checkpoint", "Researching a cure"). Tracked by the Faction Weaver via a mechanical countdown (turns/heartbeats). When a project completes, it fires a narrative event and can permanently alter the World State by introducing new Environmental Modifiers.

### Situational Overrides
Mechanical locks applied to the DM's ReAct loop to prevent the LLM from "forgetting" the current scene context and offering immersion-breaking casual exploration options. The DM uses the `set_override_state` tool to lock and unlock these modes:
- **Combat**: Triggered automatically when `encounters.json` has an active enemy. Locks all choices to tactical actions.
- **Survival**: Used when in immediate mortal danger (e.g. falling, trapped in a fire). Locks choices to frantic escape.
- **Stealth**: Used when sneaking through hostile territory. Locks choices to quiet movement, cover, and silent takedowns.
- **Social**: Used during intense negotiations or interrogations. Locks choices to dialogue and social maneuvers.
- **Camping**: Used when resting. Locks choices to camp activities (eating, sleeping) and enforces Hunger/Fatigue updates.

## Technical Details
- Built in Python.
- Uses LLM APIs (Gemini, OpenAI, Anthropic).
- Data is stored in local `.json` files and `.md` files in the `saves/<campaign_slug>/` directory.
- Relies on **questionary** for a rich, interactive Terminal User Interface (TUI) allowing for WASD/Arrow key navigation.

### Inciting Incident
A special type of Narrative Thread granted at the absolute start of the game. It possesses explicit positive and negative consequences to give the player immediate stakes and direction. This incident kicks off the primary Campaign Arc.

### Narrative Threads
Ongoing tasks, hooks, or personal missions actively tracked by the World State (internally known as 'quests'). The DM is fed these threads continuously to organically weave them into the evolving story, rather than treating them as a rigid checklist.

### Campaign Arc
An overarching, high-stakes storyline composed of multiple Narrative Threads. When the player engages with localized Rumors and the DM escalates them, the Lore Keeper subagent dynamically converts those escalated rumors into new Narrative Threads tied directly to the central Campaign Arc.

### Local Rumors
Small, location-specific hooks or points of interest attached to specific Discovered Locations. These are NOT main quests. The DM uses these to flavor a location. If the player interacts with a rumor, the DM resolves it. If the DM marks it as "escalated", it gets passed to the Lore Keeper to be upgraded into a formal Narrative Thread.

### World Bible
A comprehensive, static lore document generated at the start of a campaign. It contains the overarching history, pantheons, mythos, and primary cultures of the world. Because it is too large to inject into memory on every turn, a short summary is kept in the World State, while the DM Agent can actively query the full document when players ask deep lore questions.
