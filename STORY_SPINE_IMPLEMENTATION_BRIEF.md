# Story Spine Implementation Brief

> **Purpose:** This document is a self-contained handoff for an LLM to implement the Story Spine narrative system. It contains all design decisions, current code architecture, exact file changes, data structures, and verification steps. No additional context exploration should be necessary.

---

## Project Overview

This is a **text-based narrative RPG** powered by a multi-agent AI system. A **DM Agent** narrates the player-facing story while **Subagents** (Lore Keeper, Faction Weaver, World Keeper, Encounter Architect) run in the background managing world simulation. Built in Python, using LLM APIs (Gemini, OpenAI, Anthropic, Ollama). Game state is stored as JSON/Markdown files in `saves/{campaign_slug}/`.

### Key File Map

```
agent-game/
├── main.py                          # Entry point, menus, character creation, game loop
├── llm_clients.py                   # Model-agnostic LLM abstraction
├── agents/
│   ├── base_agent.py                # ReAct loop base class
│   ├── dm_agent.py                  # Player-facing DM (huge file ~1200 lines)
│   └── subagents/
│       ├── lore_keeper.py           # Story/quest/lore management
│       ├── faction_weaver.py        # Faction politics, NPCs, clocks
│       ├── world_keeper.py          # Environment, weather, bodily needs
│       └── encounter_architect.py   # Combat encounters
├── game_engine/
│   ├── character.py                 # Character dataclass
│   ├── world.py                     # WorldState, Quest, Location, WorldAspect dataclasses
│   ├── ability_system.py            # AbilityTag, AbilitySet
│   ├── item_system.py               # Item dataclass
│   ├── combat.py                    # Combat resolution
│   ├── dice.py                      # Dice rolling
│   └── themes.py                    # Terminal color themes
├── persistence/                     # Save/load utilities
├── saves/{campaign_slug}/           # Per-campaign save data
│   ├── character.json
│   ├── world_state.json
│   ├── factions.json
│   ├── encounters.json
│   ├── lore.json
│   ├── world_bible.md
│   ├── dm_log.md
│   └── turn_history.json
├── CONTEXT.md                       # Domain glossary (already updated with new terms)
└── docs/adr/                        # Architecture Decision Records
```

---

## What We're Building

Three interconnected features:

### 1. Story Spine (5-Beat Adaptive Narrative Arc)
A dramatic structure generated at campaign start that gives the story shape from beginning to end. Each beat defines a *dramatic question* and *tonal direction*, not a scripted scene.

| Beat | Name | Dramatic Purpose |
|------|------|-----------------|
| 1 | **The Hook** | Personal inciting incident — pulls the player in through backstory intersection with a world event |
| 2 | **The Deepening** | The problem is bigger than it seemed — introduces the real antagonist or true scope |
| 3 | **The Betrayal / Reversal** | Something the player trusted flips — an ally betrays, a truth is revealed, a plan fails |
| 4 | **The Crisis** | The player's concrete fear (from character creation) is directly tested. The lowest point |
| 5 | **The Reckoning** | Final confrontation — the dramatic question is answered |

**Key design rule:** The spine is **adaptive**. Dramatic functions are fixed (there WILL be a betrayal, a crisis, a reckoning) but the specific events/characters can mutate based on player choices. If the player kills an important NPC, the Lore Keeper reassigns that narrative weight. If the player ignores the story, pressure mechanisms (World Aspects, Nemesis, faction clocks) make the story come to *them*.

### 2. Structured Character Backstory
Character creation collects deeply personal material across 5 questions. Currently it's all concatenated into one `backstory` string. We're breaking it into structured fields so agents can reference specific elements programmatically (especially the fear for Beat 4).

### 3. Tiered NPC Cast System
- **Spine Characters** (2-3): Generated at campaign start with medium detail. Map to dramatic roles (Anchor, Catalyst, Adversary). Connected to the player's backstory.
- **Encountered NPCs**: Start as lightweight one-liners in `factions.json`. Can be **promoted** to full characters in `cast.json` when the player invests in them.

---

## Design Decisions (All Approved)

| Decision | Choice | Why |
|----------|--------|-----|
| Story structure | 5-beat adaptive spine | Fixed dramatic functions, emergent specifics |
| Inciting incident | Intersection model | World event woven through character backstory — "world-changing to the player" not necessarily world-scale |
| Fear prompt | Concrete scenario + emotional wound | Must be dramatizable for Beat 4 crisis |
| Backstory storage | Structured fields on Character | Agents need programmatic access, not string parsing |
| NPC system | Tiered: Spine Characters + Promotion | Important NPCs exist from start; others grow organically |
| NPC storage | Dedicated `cast.json` | Clean separation from faction politics |
| Spine rigidity | Adaptive with pressure | Dramatic questions fixed, specifics mutate; pressure pulls wandering players back |
| Spine Character cap | Expandable (start with 3, Lore Keeper can add more) | Story may demand new important characters mid-game |

---

## Exact Changes Required

### CHANGE 1: Character Dataclass — Structured Backstory Fields

**File:** `game_engine/character.py`

**Current state:** The `Character` dataclass has a single `backstory: str` field that stores all creation answers as a pipe-delimited blob: `"Appearance: ... | Childhood: ... | Past: ... | Fear: ..."`.

**Required changes:**

Add 4 new fields to the dataclass:

```python
@dataclass
class Character:
    name: str
    backstory: str = ""              # Keep as human-readable summary
    appearance: str = ""
    childhood_event: str = ""        # NEW — Defining childhood moment
    past_life: str = ""              # NEW — Pre-adventure occupation
    fear: str = ""                   # NEW — Concrete scenario + emotional wound
    sentimental_item_story: str = "" # NEW — Why the carried item matters
    abilities: AbilitySet = field(default_factory=AbilitySet)
    hp: int = 20
    max_hp: int = 20
    currency: int = 0
    inventory: List[Item] = field(default_factory=list)
    equipped: Dict[str, Item] = field(default_factory=dict)
    status_effects: List[dict] = field(default_factory=list)
    position: str = "Start"
    relationships: Dict[str, str] = field(default_factory=dict)
    miracles: int = 1
    speed: int = 2
```

Update `to_dict()` to include the 4 new fields.
Update `from_dict()` to deserialize them with `""` defaults for backward compatibility.

---

### CHANGE 2: Story Spine Data Model

**File:** `game_engine/world.py`

**Add two new dataclasses** before `WorldState`:

```python
@dataclass
class StoryBeat:
    id: int                          # 1-5
    name: str                        # "The Hook", "The Deepening", etc.
    dramatic_question: str           # e.g., "What happened to your mentor?"
    tonal_direction: str             # e.g., "Mystery and urgency"
    status: str = "pending"          # "pending", "active", "resolved"
    resolution_notes: str = ""       # Filled by Lore Keeper when resolved
    pressure_mechanism: str = ""     # What escalates if player stalls

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "dramatic_question": self.dramatic_question,
            "tonal_direction": self.tonal_direction,
            "status": self.status,
            "resolution_notes": self.resolution_notes,
            "pressure_mechanism": self.pressure_mechanism
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StoryBeat":
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            dramatic_question=data.get("dramatic_question", ""),
            tonal_direction=data.get("tonal_direction", ""),
            status=data.get("status", "pending"),
            resolution_notes=data.get("resolution_notes", ""),
            pressure_mechanism=data.get("pressure_mechanism", "")
        )


@dataclass
class StorySpine:
    theme: str = ""
    beats: List[StoryBeat] = field(default_factory=list)
    current_beat: int = 1

    def get_active_beat(self):
        """Returns the currently active StoryBeat, or None."""
        for beat in self.beats:
            if beat.status == "active":
                return beat
        return None

    def advance_beat(self, resolution_notes: str):
        """Resolves the current active beat and activates the next one. Returns the newly active beat or None if the spine is complete."""
        active = self.get_active_beat()
        if active:
            active.status = "resolved"
            active.resolution_notes = resolution_notes

        # Find the next pending beat
        for beat in self.beats:
            if beat.status == "pending":
                beat.status = "active"
                self.current_beat = beat.id
                return beat
        return None  # Story spine complete

    def to_dict(self) -> dict:
        return {
            "theme": self.theme,
            "beats": [b.to_dict() for b in self.beats],
            "current_beat": self.current_beat
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StorySpine":
        if not data:
            return cls()
        return cls(
            theme=data.get("theme", ""),
            beats=[StoryBeat.from_dict(bd) for bd in data.get("beats", [])],
            current_beat=data.get("current_beat", 1)
        )
```

**Add to `WorldState`:**

```python
story_spine: StorySpine = field(default_factory=StorySpine)
```

Update `WorldState.to_dict()` to include `"story_spine": self.story_spine.to_dict()`.
Update `WorldState.from_dict()` to deserialize: `story_spine=StorySpine.from_dict(data.get("story_spine", {}))`.

**Keep `campaign_arc` for backward compatibility.** When `story_spine` has beats, `campaign_arc` should still be populated — set it to the spine's theme during generation so old code paths that read `campaign_arc` still work.

---

### CHANGE 3: Cast System (New File for Save Data)

**No new Python module needed** — the cast is managed via JSON read/write in the Lore Keeper and DM Agent tools, same pattern as `factions.json`.

**Save file:** `saves/{campaign_slug}/cast.json`

**Schema:**

```json
{
    "spine_characters": {
        "anchor_01": {
            "name": "Master Aldric",
            "role": "anchor",
            "appearance": "A weathered man with deep-set eyes and ink-stained hands",
            "personality": "Patient but secretive; speaks in riddles when cornered",
            "hidden_agenda": "Has been hiding a forbidden artifact for 20 years",
            "relationship_to_player": "Former mentor — taught the player their craft",
            "dramatic_function": "Emotional anchor for Beat 1; disappearance triggers the quest",
            "status": "alive",
            "current_location": ""
        }
    },
    "promoted_npcs": {}
}
```

Both `spine_characters` and `promoted_npcs` entries share the same field structure. The key difference is `role`: spine characters have `"anchor"`, `"catalyst"`, or `"adversary"`; promoted NPCs have `"promoted"`.

---

### CHANGE 4: Character Creation — Fear Prompt Reframe

**File:** `main.py`

**Line ~130:** Change the question text:

```python
# OLD:
"What is your greatest fear or weakness?"

# NEW:
"What is the one situation, person, or force your character would do anything to avoid facing again?"
```

**Line ~147:** Change the LLM instruction:

```python
# OLD:
extra_inst = "Focus on distinct psychological flaws, traumatic fears, or severe personality weaknesses."

# NEW:
extra_inst = "Generate fears that combine a specific triggerable scenario with a deep personal reason. Each fear must name a concrete external threat AND the emotional wound behind it. (e.g., 'Being trapped underground — they were buried alive during a mine collapse and still hear the rocks shifting in their nightmares.' NOT vague concepts like 'fear of failure' or 'fear of the unknown')."
```

---

### CHANGE 5: Character Creation — Store Structured Fields

**File:** `main.py`, around line 305-312

**Current code:**
```python
char = Character(
    name=name,
    backstory=f"Appearance: {answers[0]} | Childhood: {answers[1]} | Past: {answers[2]} | Fear: {answers[3]}",
    appearance=appearance_text,
    abilities=abilities,
    currency=currency,
    inventory=[starting_item]
)
```

**New code:**
```python
char = Character(
    name=name,
    backstory=f"Appearance: {answers[0]} | Childhood: {answers[1]} | Past: {answers[2]} | Fear: {answers[3]}",
    appearance=appearance_text,
    childhood_event=answers[1],
    past_life=answers[2],
    fear=answers[3],
    sentimental_item_story=answers[4],
    abilities=abilities,
    currency=currency,
    inventory=[starting_item]
)
```

The `backstory` string is kept as a human-readable summary. The structured fields give agents direct access.

---

### CHANGE 6: Campaign Initialization — Generate Story Spine

**File:** `main.py`, function `initialize_world()` (around line 722)

**Current flow:**
1. World Bible generated
2. `lore_keeper.generate_inciting_incident()` called
3. Starting location generated

**New flow:**
1. World Bible generated (unchanged)
2. **`lore_keeper.generate_story_spine(character)` called** (replaces `generate_inciting_incident`)
3. Starting location generated (unchanged)

---

### CHANGE 7: Lore Keeper — Major Retooling

**File:** `agents/subagents/lore_keeper.py`

This is the biggest change. The Lore Keeper becomes the spine manager.

#### 7a. New Tools

Add these tools to `_get_tools()`:

**`advance_spine_beat`** — Marks the current beat as resolved and activates the next one:
```python
def advance_spine_beat(args: str) -> str:
    """Format: 'resolution_notes'. Resolves the current active story beat and activates the next.
    Usage: Action: advance_spine_beat: The player discovered the mentor was taken by the Collector."""
    world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
    if not os.path.exists(world_path):
        return "Error: World state not found."
    with open(world_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    world = WorldState.from_dict(data)

    if not world.story_spine.beats:
        return "Error: No story spine exists."

    next_beat = world.story_spine.advance_beat(args.strip())
    with open(world_path, "w", encoding="utf-8") as f:
        json.dump(world.to_dict(), f, indent=4)

    if next_beat:
        return f"Beat resolved. Now active: Beat {next_beat.id} — '{next_beat.name}': {next_beat.dramatic_question}"
    return "Story spine complete — all beats resolved. The story has reached its conclusion."
```

**`modify_cast_member`** — Updates a cast member's fields:
```python
def modify_cast_member(args: str) -> str:
    """Format: 'character_id | field | value'. Updates a field on a cast member.
    Valid fields: status, current_location, relationship_to_player, hidden_agenda, personality, dramatic_function.
    Usage: Action: modify_cast_member: anchor_01 | status | dead"""
    parts = [p.strip() for p in args.split("|")]
    if len(parts) < 3:
        return "Error: Format must be 'character_id | field | value'"
    char_id, field_name, value = parts[0], parts[1], parts[2]

    cast_path = os.path.join("saves", self.campaign_slug, "cast.json")
    if not os.path.exists(cast_path):
        return "Error: Cast file not found."
    with open(cast_path, "r", encoding="utf-8") as f:
        cast = json.load(f)

    # Search in both spine_characters and promoted_npcs
    target = None
    for section in ["spine_characters", "promoted_npcs"]:
        if char_id in cast.get(section, {}):
            target = cast[section][char_id]
            break

    if not target:
        return f"Error: Cast member '{char_id}' not found."

    valid_fields = ["status", "current_location", "relationship_to_player", "hidden_agenda", "personality", "dramatic_function"]
    if field_name not in valid_fields:
        return f"Error: Invalid field. Valid fields: {', '.join(valid_fields)}"

    target[field_name] = value
    with open(cast_path, "w", encoding="utf-8") as f:
        json.dump(cast, f, indent=4)
    return f"Updated cast member '{char_id}': {field_name} = {value}"
```

**`promote_npc`** — Promotes a lightweight NPC to the cast:
```python
def promote_npc(args: str) -> str:
    """Format: 'npc_name | role | appearance | personality | hidden_agenda | relationship_to_player | dramatic_function'.
    Promotes a lightweight NPC to a full cast member in cast.json.
    Usage: Action: promote_npc: Sera | promoted | Tall woman with a scar | Calculating but loyal | Secretly working for the Collector | Trusted informant | Provides intel that drives Beat 3"""
    parts = [p.strip() for p in args.split("|")]
    if len(parts) < 5:
        return "Error: Format must be 'npc_name | role | appearance | personality | hidden_agenda | relationship_to_player | dramatic_function'"
    
    import uuid
    npc_id = f"promoted_{uuid.uuid4().hex[:8]}"
    name = parts[0]
    role = parts[1] if len(parts) > 1 else "promoted"
    appearance = parts[2] if len(parts) > 2 else ""
    personality = parts[3] if len(parts) > 3 else ""
    hidden_agenda = parts[4] if len(parts) > 4 else ""
    rel = parts[5] if len(parts) > 5 else ""
    dramatic_func = parts[6] if len(parts) > 6 else ""

    cast_path = os.path.join("saves", self.campaign_slug, "cast.json")
    if not os.path.exists(cast_path):
        cast = {"spine_characters": {}, "promoted_npcs": {}}
    else:
        with open(cast_path, "r", encoding="utf-8") as f:
            cast = json.load(f)

    cast.setdefault("promoted_npcs", {})[npc_id] = {
        "name": name,
        "role": role,
        "appearance": appearance,
        "personality": personality,
        "hidden_agenda": hidden_agenda,
        "relationship_to_player": rel,
        "dramatic_function": dramatic_func,
        "status": "alive",
        "current_location": ""
    }
    with open(cast_path, "w", encoding="utf-8") as f:
        json.dump(cast, f, indent=4)
    return f"NPC '{name}' promoted to cast (ID: {npc_id})."
```

#### 7b. Update System Instruction

Replace the Lore Keeper's system instruction to include spine awareness. The key additions:

```
You also manage the Story Spine — a 5-beat adaptive narrative arc. You track which beat is active and advance the spine when the current beat's dramatic question has been answered through player actions.

The 5 beats are:
1. The Hook — the personal inciting incident
2. The Deepening — the problem is bigger than it seemed
3. The Betrayal/Reversal — something trusted flips
4. The Crisis — the player's deepest fear is tested
5. The Reckoning — the final confrontation

When deciding to advance a beat, consider: Has the current beat's dramatic question been meaningfully answered by player actions? Don't advance prematurely — each beat should feel earned.

You also manage the Cast (important NPCs). Use 'modify_cast_member' to update their status, location, or relationships as the story evolves. Use 'promote_npc' when a recurring NPC deserves full characterization.
```

Add the new tools to the system instruction's tool list.

#### 7c. Replace `generate_inciting_incident` with `generate_story_spine`

```python
def generate_story_spine(self, char_data: dict) -> None:
    """Generates the full 5-beat Story Spine, Spine Characters, and opening quest."""
    world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
    if not os.path.exists(world_path):
        return

    with open(world_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    world = WorldState.from_dict(data)

    # Extract character backstory fields
    fear = char_data.get("fear", char_data.get("backstory", ""))
    childhood = char_data.get("childhood_event", "")
    past_life = char_data.get("past_life", "")
    sentimental_item = char_data.get("sentimental_item_story", "")
    char_name = char_data.get("name", "the player")

    query = (
        f"INITIALIZATION — GENERATE STORY SPINE.\n"
        f"Genre: '{world.setting_genre}'.\n"
        f"Setting: '{world.setting_description}'.\n"
        f"World Bible Summary: '{world.world_bible_summary}'.\n\n"
        f"Character Name: '{char_name}'.\n"
        f"Character's Defining Childhood Event: '{childhood}'.\n"
        f"Character's Past Life / Occupation: '{past_life}'.\n"
        f"Character's Deepest Fear (concrete scenario + emotional wound): '{fear}'.\n"
        f"Character's Sentimental Item: '{sentimental_item}'.\n\n"
        f"YOUR TASKS (complete ALL of them using tools):\n"
        f"1. Design a 5-beat Story Spine. Each beat needs: a dramatic_question, tonal_direction, and pressure_mechanism. "
        f"The story must be personally meaningful to THIS character — 'world-changing to the player' not necessarily world-scale. "
        f"Beat 1 (The Hook) must intersect a world event with the character's backstory. "
        f"Beat 4 (The Crisis) MUST directly weaponize the character's fear: '{fear}'. "
        f"Output the spine as a JSON object and use 'update_campaign_arc' to store the theme.\n"
        f"2. Generate 3 Spine Characters and store them using tools:\n"
        f"   - The Anchor: emotionally tied to the character's childhood or past life. The reason the player cares.\n"
        f"   - The Catalyst: someone who appears helpful but has hidden knowledge or a hidden agenda. Drives Beats 2-3.\n"
        f"   - The Adversary: a personal rival whose goals directly conflict with the player's. Persistent across multiple beats.\n"
        f"3. Create the Inciting Incident (Beat 1 quest) using 'add_quest' with priority 'main'. "
        f"It MUST have explicit positive and negative consequences and be personal to the character.\n"
        f"4. Call 'update_story_beat' with a specific directive for the DM's opening scene that introduces the Anchor character.\n"
    )
    self.run(query, max_turns=6, verbose=False, agent_name="LoreKeeper")
```

**IMPORTANT:** This method also needs to write the spine to `world_state.json` and the cast to `cast.json`. Since the Lore Keeper operates via tools in a ReAct loop, you need to add a tool that lets it store the spine:

**`store_story_spine`** tool:
```python
def store_story_spine(args: str) -> str:
    """Format: JSON string of the story spine object.
    Example: {"theme": "Redemption through sacrifice", "beats": [{"id": 1, "name": "The Hook", "dramatic_question": "...", "tonal_direction": "...", "status": "active", "pressure_mechanism": "..."}, ...]}
    Usage: Action: store_story_spine: {"theme": "...", "beats": [...]}"""
    try:
        spine_data = json.loads(args.strip())
    except json.JSONDecodeError:
        return "Error: Invalid JSON. Must be a valid story spine object."

    world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
    with open(world_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    world = WorldState.from_dict(data)
    world.story_spine = StorySpine.from_dict(spine_data)
    world.campaign_arc = spine_data.get("theme", "")
    with open(world_path, "w", encoding="utf-8") as f:
        json.dump(world.to_dict(), f, indent=4)
    return "Story Spine stored successfully."
```

**`store_cast_member`** tool (for initial spine character creation):
```python
def store_cast_member(args: str) -> str:
    """Format: 'character_id | name | role | appearance | personality | hidden_agenda | relationship_to_player | dramatic_function'.
    Roles: 'anchor', 'catalyst', 'adversary'.
    Usage: Action: store_cast_member: anchor_01 | Master Aldric | anchor | Weathered man with ink-stained hands | Patient but secretive | Hiding a forbidden artifact | Former mentor | Emotional anchor for Beat 1"""
    parts = [p.strip() for p in args.split("|")]
    if len(parts) < 4:
        return "Error: Need at least 'id | name | role | appearance'."

    char_id = parts[0]
    entry = {
        "name": parts[1],
        "role": parts[2],
        "appearance": parts[3] if len(parts) > 3 else "",
        "personality": parts[4] if len(parts) > 4 else "",
        "hidden_agenda": parts[5] if len(parts) > 5 else "",
        "relationship_to_player": parts[6] if len(parts) > 6 else "",
        "dramatic_function": parts[7] if len(parts) > 7 else "",
        "status": "alive",
        "current_location": ""
    }

    cast_path = os.path.join("saves", self.campaign_slug, "cast.json")
    if not os.path.exists(cast_path):
        cast = {"spine_characters": {}, "promoted_npcs": {}}
    else:
        with open(cast_path, "r", encoding="utf-8") as f:
            cast = json.load(f)

    cast.setdefault("spine_characters", {})[char_id] = entry
    with open(cast_path, "w", encoding="utf-8") as f:
        json.dump(cast, f, indent=4)
    return f"Spine Character '{parts[1]}' (role: {parts[2]}) stored in cast."
```

#### 7d. Update Heartbeat for Spine Awareness

In the `heartbeat()` method, after processing escalated rumors, add spine progression checking:

```python
# After existing rumor processing, add:

# Check spine progression pressure
if world.story_spine and world.story_spine.beats:
    active_beat = world.story_spine.get_active_beat()
    if active_beat:
        spine_query = (
            f"SPINE CHECK: The current story beat is Beat {active_beat.id} — '{active_beat.name}'. "
            f"Dramatic question: '{active_beat.dramatic_question}'. "
            f"Pressure mechanism if stalling: '{active_beat.pressure_mechanism}'. "
            f"Review the DM log and quest statuses. "
            f"If the dramatic question has been answered, call 'advance_spine_beat' with resolution notes. "
            f"If the player seems to be ignoring the main story, activate the pressure mechanism "
            f"(e.g., add a World Aspect, spawn a faction event, or update the story beat to escalate urgency). "
            f"If things are progressing naturally, just update the Director's Brief via 'update_story_beat'."
        )
        self.run(spine_query, max_turns=4, verbose=False, agent_name="LoreKeeper")
```

---

### CHANGE 8: DM Agent — Context Block & Cast Query

**File:** `agents/dm_agent.py`

#### 8a. Add `query_cast` tool

In `_get_dm_tools()`, add:

```python
def query_cast(dummy: str) -> str:
    """Returns the full cast of important NPCs (Spine Characters and Promoted NPCs).
    Usage: Action: query_cast"""
    cast_path = os.path.join("saves", self.campaign_slug, "cast.json")
    if not os.path.exists(cast_path):
        return "No cast file found."
    with open(cast_path, "r", encoding="utf-8") as f:
        return f.read()
```

Add `"query_cast": query_cast` to the tools dict.
Add to the system prompt's tool list:
```
- query_cast: Returns the full cast of important NPCs (personality, agenda, status). Usage: Action: query_cast
```

#### 8b. Update Context Block

In `process_turn()`, around line 1034 where `context_str` is built, add spine and cast info:

```python
# Load story spine info
spine_str = "None"
if world.story_spine and world.story_spine.beats:
    active_beat = world.story_spine.get_active_beat()
    if active_beat:
        spine_str = f"Beat {active_beat.id} — '{active_beat.name}': {active_beat.dramatic_question} (Tone: {active_beat.tonal_direction})"
    else:
        spine_str = "All beats resolved — story approaching conclusion"

# Load cast summary
cast_summary = "None"
cast_path = os.path.join("saves", self.campaign_slug, "cast.json")
if os.path.exists(cast_path):
    try:
        with open(cast_path, "r", encoding="utf-8") as f:
            cast_data = json.load(f)
        cast_entries = []
        for section in ["spine_characters", "promoted_npcs"]:
            for cid, cinfo in cast_data.get(section, {}).items():
                cast_entries.append(f"{cinfo['name']} ({cinfo['role']}, {cinfo['status']})")
        if cast_entries:
            cast_summary = ", ".join(cast_entries)
    except Exception:
        pass
```

Then add to the context string:
```python
f"Story Beat: {spine_str} | "
f"Key Cast: {cast_summary} | "
```

#### 8c. Add Foreshadowing Instruction to System Prompt

Add this to the DM system prompt (in `_build_dynamic_prompt()`), perhaps after the existing rule #11:

```
14. Character Continuity: When Spine Characters or Promoted NPCs appear in a scene, you MUST use 'query_cast' to get their personality, hidden agenda, and current status. Write their dialogue and behavior consistent with their personality. Subtly foreshadow upcoming story beats through NPC behavior without being heavy-handed (e.g., if The Catalyst has a hidden agenda, show small inconsistencies in their behavior that a perceptive player might notice).
```

---

### CHANGE 9: Update `initialize_world` in main.py

**File:** `main.py`, around line 763-766

Replace:
```python
if not world.current_location_id:
    with Halo(text='Weaving the starting Inciting Incident...', spinner='dots', color='yellow'):
        lore_keeper = LoreKeeper(llm_client, campaign_slug)
        lore_keeper.generate_inciting_incident()
```

With:
```python
if not world.current_location_id:
    with Halo(text='Forging the Story Spine...', spinner='dots', color='yellow'):
        lore_keeper = LoreKeeper(llm_client, campaign_slug)
        # Load character data to pass backstory fields
        char_path = os.path.join("saves", campaign_slug, "character.json")
        with open(char_path, "r", encoding="utf-8") as f:
            char_for_spine = json.load(f)
        lore_keeper.generate_story_spine(char_for_spine)
```

---

### CHANGE 10: ADR Document (Already Created)

**File:** `docs/adr/0004-story-spine-adaptive-narrative.md` — Already exists. No action needed.

---

### CHANGE 11: CONTEXT.md (Already Updated)

**File:** `CONTEXT.md` — Already updated with new glossary terms (Story Spine, Story Beat, Spine Characters, NPC Promotion, Cast). No action needed.

---

## Verification Plan

### Automated Tests

Run existing tests to ensure nothing is broken:
```bash
python -m pytest test_engine.py -v
```

Add new tests for:
- `StoryBeat` and `StorySpine` serialization round-trip
- `StorySpine.advance_beat()` logic (resolves current, activates next, returns None when complete)
- `Character` with new structured fields — backward compat (old save without fields loads with empty strings)
- `WorldState` with `story_spine` field — backward compat (old save without spine loads with empty StorySpine)

### Manual Verification

1. **Start a new game** — verify the fear prompt generates concrete scenarios, the Story Spine is generated and stored in `world_state.json`, 3 Spine Characters appear in `cast.json`, and the inciting incident quest is personal to the character
2. **Play 10+ turns** — verify the DM's context block shows the current story beat and cast, and the DM references Spine Characters by name
3. **Load an old save** — verify it doesn't crash (all new fields have safe defaults)

---

## Important Implementation Notes

1. **The Lore Keeper's `generate_story_spine` will need a higher `max_turns`** (6 instead of 4) because it needs to make multiple tool calls: `store_story_spine`, `store_cast_member` (×3), `add_quest`, `update_story_beat`, and `update_campaign_arc`.

2. **Import paths:** `StoryBeat`, `StorySpine` are defined in `game_engine/world.py`. The Lore Keeper already imports `WorldState` from there, so the new classes will be available.

3. **The `cast.json` file does not exist by default.** All code that reads it must handle `FileNotFoundError` gracefully and initialize with `{"spine_characters": {}, "promoted_npcs": {}}`.

4. **SaveManager compatibility:** Check `persistence/` to see if `SaveManager.load_game()` and `SaveManager.save_game()` need to be updated to handle `cast.json`. They likely handle character, world, factions, encounters, and lore as separate files. You may need to add cast as a 6th file, or manage it independently (preferred — keep it independent like `dm_log.md`).

5. **Token budget:** The cast summary in the DM context block should be kept concise. Only inject name, role, and status — not full personality text. The DM can `query_cast` when it needs the full details for a specific scene.
