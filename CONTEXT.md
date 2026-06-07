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

### Action Clock (Skill Challenge)
An immediate, foreground mechanical tracker used exclusively by the DM Agent to pace high-stakes, multi-turn crises (e.g., escaping a collapsing temple, surviving a falling airship). Unlike Doom Clocks or Faction Projects which tick on background Heartbeat cycles, Action Clocks are resolved turn-by-turn during active gameplay and require a set number of successes before a turn limit expires.

### Faction Weaver
The subagent responsible for NPC factions, political dynamics, reputation tracking, and faction-driven events. Factions scheme independently on heartbeat cycles.

### Encounter Architect
The subagent responsible for designing and resolving combat encounters, enemy generation, enemy tactics, and loot distribution. Triggered when hostile situations arise.

### Lore Keeper
The subagent responsible for world history, hidden secrets, quest hooks, and narrative reveals. Decides when lore becomes discoverable based on player actions and context.

### Ability Tag
A named skill or trait attached to a character with a hidden numeric modifier (e.g., `swordsmanship: +3`). Tags are the fundamental unit of character capability. Not all characters share the same tags — they are accumulated through backstory, experience, items, and environment.

### Tag Progression (Learn-by-Doing)
The system by which ability tags improve through use. When a character successfully uses an innate tag in a relevant context repeatedly, the tag's modifier increases. Progression thresholds are tracked by usage count. 
- **High-Tier Maneuvers**: As tags reach higher modifier tiers (e.g., +3 or higher), the DM is instructed to unlock and offer special tactical maneuvers in combat (like 'cleave', 'double attack', or 'precision shot').

### Character Health Scaling
Max HP is not purely static. It grows in two ways:
1. **Physical Tag Progression**: Leveling up physical or combat tags (e.g., `athletics`, `combat`, `fortitude`) permanently grants a small boost (e.g., +5) to Max HP.
2. **Artifact Upgrades**: Max HP can be upgraded by finding and consuming rare items, cybernetics, or magical blessings in the world.

### Bodily Needs (Hunger & Fatigue)
Mechanical states tracked on a scale from 0 to 2 (0 = Fine, 1 = Mild, 2 = Severe) by the World Keeper subagent. If left unchecked, high hunger or fatigue can impose negative environmental modifiers on the player's ability tags.

### Recovery (Healing)
Character HP and bodily needs are recovered through two primary methods:
1. **Camping/Sleeping**: Initiating a rest resets Fatigue to 0, but increases Hunger by 1 (to represent burned calories). It naturally heals a small amount of HP (e.g., +5 HP). It does not fully restore health.
2. **Consumables**: Using medical supplies, potions, or rations provides immediate HP recovery. However, consuming these items outside of a safe Camping environment reduces their healing effectiveness by half.

### Hidden Stats
The design philosophy where all character mechanics (ability tags, modifiers, dice rolls, difficulty classes) are invisible to the player during normal gameplay. The player experiences outcomes through narrative description only. Stats can be inspected via saved JSON files or explicit Out-of-Character requests.
- **Item Descriptions**: Because stats are hidden, item descriptions act as the primary interface for understanding an item's capabilities. Descriptions are diegetically generated (e.g., "A heavy iron broadsword" instead of "Damage +2"). Common simple items have basic descriptions, while special items feature detailed notes on their appearance and known capabilities.
- **Wound States**: Character HP is hidden. Instead of numbers, low HP (<75%, <50%, or <25%) is conveyed purely through diegetic flavor text (e.g., bruised, bleeding, limping). These descriptions act as warnings but do not impose hidden mechanical penalties on ability checks.

### Stats Mode
An optional playstyle mode chosen at the start of a new campaign that overrides the **Hidden Stats** philosophy. When active, character stats, item modifiers, DCs, and dice roll occurrences are shown alongside the narrative via color-coded `[MECHANICS: ...]` blocks (green for success/hits/blocked, red for failure/misses/wounded), while keeping exact raw roll numbers hidden to preserve the DM's Narrative Authority.

### Difficulty Class (DC)
A numeric threshold that an ability check must meet or exceed to succeed. DCs are set contextually by the DM or subagents based on the situation (e.g., rusty lock = DC 8, master-forged lock = DC 20).

### Attribute Tags
A set of 6 broad, baseline characteristics that every character possesses: `strength`, `dexterity`, `intellect`, `fortitude`, `presence`, and `perception`. These are seeded at campaign start based on character backstory and act as fallback modifiers when a check is rolled for a specific skill tag the character does not own.

### Fallback Check System
The mechanism used during ability checks. When the DM Agent rolls a check, they can specify a specific skill and a fallback attribute (e.g., `lockpicking | dexterity | 15`). If the character lacks the specific skill tag, the engine uses the character's modifier for the fallback attribute instead of defaulting to `+0`.

### Combat Style
A thematic classification of a character's fighting method (e.g., "Arcane Spellslinging", "Stealthy Daggerplay", "Heavy Melee Brute") derived from their backstory during character creation. It shapes how the DM Agent generates tactical combat choices.

### Combat Maneuvers
A set of 2-3 specific special moves, spells, or tactics (e.g., "Firebolt", "Parry & Riposte") that a character can perform in combat. These are seeded during character creation and explicitly utilized by the DM Agent when generating tactical combat choices.



### Narrative Authority
The DM Agent's power to override raw mechanical outcomes (dice rolls, ability checks) when doing so serves the story. This allows the DM to "fudge" results for dramatic tension, narrative pacing, or player enjoyment. However, Narrative Authority does NOT permit the DM to hallucinate items the player does not possess or skills they do not have; narrative outcomes must respect the player's factual inventory and ability tag constraints.

### Conceptual Translation
The design philosophy instructing the DM Agent to conceptually translate genre-specific terminology into high-fantasy equivalents when querying backend D&D 5e systems (e.g., querying 'heavy crossbow' when a player fires a 'sniper rifle', or 'fireball' for a 'plasma grenade'). This ensures mechanical consistency from the D&D 5e SRD across all Setting Pitches (Sci-Fi, Cyberpunk, etc.).

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
A narrative action managed by the DM agent to break down complex or unwanted items into fundamental raw materials (e.g., Rusty Cogs, Tattered Wire, Scrap Electronics). The DM freely invents salvage names based on the setting and the item being dismantled. Used to manage inventory space and gather components for future use.

### Crafting
A freeform, narrative action by which the DM agent deducts logical raw materials from the player's inventory to generate a newly assembled item. There are no strict recipes; the DM uses its judgment to determine if the player has the right combination of random salvage to build the requested item, enforcing an ability check to determine success.

### Faction Projects
Long-term, background goals pursued autonomously by factions (e.g., "Building a checkpoint", "Researching a cure"). Tracked by the Faction Weaver via a mechanical countdown (turns/heartbeats). When a project completes, it fires a narrative event and can permanently alter the World State by introducing new Environmental Modifiers.

### Situational Overrides
Mechanical locks applied to the DM's ReAct loop to prevent the LLM from "forgetting" the current scene context and offering immersion-breaking casual exploration options. The DM uses the `set_override_state` tool to lock and unlock these modes:
- **Combat**: Triggered automatically when `encounters.json` has an active enemy. Locks all choices to tactical actions.
- **Survival**: Used when in immediate mortal danger (e.g. falling, trapped in a fire). Locks choices to frantic escape.
- **Stealth**: Used when sneaking through hostile territory. Locks choices to quiet movement, cover, and silent takedowns.
- **Social**: Used during intense negotiations or interrogations. Locks choices to dialogue and social maneuvers.
- **Investigation**: Used when solving a complex puzzle or examining a scene. Locks choices to intellectual analysis and puzzle-solving.
- **Travel**: Used during long journeys between major nodes. Locks choices to navigating the road, foraging, and dealing with hazards.
- **Camping**: Used when resting. Locks choices to camp activities (eating, sleeping) and enforces Hunger/Fatigue updates.

### Story Spine
A 5-beat adaptive dramatic structure generated at campaign start that gives the campaign a satisfying narrative arc. Each beat defines a dramatic question and tonal direction, not a scripted scene. The spine is adaptive: dramatic functions are fixed (there will always be a Betrayal, a Crisis, a Reckoning), but the specific events and characters involved mutate based on player choices. Pressure mechanisms (World Aspects, faction clocks, Nemesis) pull wandering players back to the story.

### Story Beat
One of 5 dramatic turning points in the Story Spine:
1. **The Hook**: Personal inciting incident — pulls the player in through backstory intersection with a world event.
2. **The Deepening**: The problem is bigger than it seemed — introduces the real antagonist or true scope.
3. **The Betrayal / Reversal**: Something the player trusted flips — an ally betrays, a truth is revealed, a plan fails.
4. **The Crisis**: The player's concrete fear (from character creation) is directly tested. The lowest point.
5. **The Reckoning**: Final confrontation — the dramatic question is answered and the player's arc resolves.

Each beat has a status (pending, active, resolved) tracked by the Lore Keeper.

### Spine Characters
A small set of 2-3 important NPCs generated at campaign start with medium detail (personality, hidden agenda, dramatic function, relationship to the player). Each maps to a dramatic role:
- **The Anchor**: Emotional tie to Beat 1 — connected to the player's childhood or past life.
- **The Catalyst**: Drives Beats 2-3 — an ally with hidden knowledge or a hidden agenda.
- **The Adversary**: Opposes the player across multiple beats — a persistent, personal rival.

Spine Characters are stored in `cast.json` and are distinct from lightweight faction NPCs.

### NPC Promotion
The process by which a lightweight NPC (a one-line description in `factions.json`) is upgraded to a fleshed-out character in `cast.json` with personality, hidden agenda, and dramatic function. Promotion triggers include: 3+ player interactions, being added as a Key Relationship, or the Lore Keeper needing to fill a vacated dramatic role.

### Cast
The dedicated registry (`cast.json`) of all important NPCs — both Spine Characters and Promoted NPCs. Stored separately from `factions.json` to keep narrative identity distinct from political affiliation. Referenced by both the DM and Lore Keeper for consistent characterization.

## Technical Details
- Built in Python.
- Uses LLM APIs (Gemini, OpenAI, Anthropic).
- Data is stored in local `.json` files and `.md` files in the `saves/<campaign_slug>/` directory.
- Relies on **questionary** for a rich, interactive Terminal User Interface (TUI) allowing for WASD/Arrow key navigation.

### AI-Enhanced Custom Input
An interactive UI feature where the player can submit a draft custom action and request the LLM to enhance it. The engine passes the player's draft and the current scene context to the LLM, which returns 4 polished, highly-descriptive alternatives. The player can select one of the 4 enhanced options, keep their original draft, or cancel to write a new one. This ensures narrative quality without stripping player agency.

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

### Director's Brief (Next Story Beat)
A specific, actionable 1-2 sentence narrative directive generated by the Lore Keeper during each heartbeat cycle. Injected at the top of the DM's context block to tell it exactly what the next narrative moment should focus on (e.g., "Have an NPC reveal the smuggler's betrayal"). This is the DM's primary creative compass.

### Quest Priority
Quests are marked as either `main` (primary story arc) or `side` (secondary). The Lore Keeper assigns priority by default (inciting incident = main). The player can override priority via the OOC `focus quest` command to shift the DM's attention to a different quest line.

### Turn History
A rolling record of the last 3 player turns (player action + DM response summary), stored in `saves/{campaign}/turn_history.json`. Injected into the DM's context block to provide minimal narrative continuity between turns, since the DM agent has no persistent conversation memory.

### Context Map (Secondary Index)
An in-memory property graph (e.g., built using NetworkX) used exclusively by subagents like the Faction Weaver and Lore Keeper to perform complex relationship traversals across the game state. The graph is **not** the primary source of truth. It is completely rebuilt from the flat JSON save files (`cast.json`, `factions.json`, `world.json`) at the start of every Heartbeat cycle, avoiding complex synchronization logic and preventing desyncs. When constructed, the graph abstracts entity sources—for example, both **Cast** members and **Faction NPC Records** are represented as generic `Character` nodes with distinguishing properties (e.g., `is_cast=True/False`), simplifying subagent queries and gracefully handling NPC Promotion. To prevent LLM hallucinations from polluting the graph, the builder enforces a **Strict Schema** for relationship edges; any unrecognized relationships generated by the DM in the JSON are defaulted to generic edge types (e.g., `KNOWS`).
