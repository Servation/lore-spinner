# ADR 0004: Adaptive Story Spine with Tiered NPC System

## Status
Proposed

## Context
The game generates narratively rich settings and characters but lacks structural story progression. The `campaign_arc` is a single mutable string with no dramatic shape. NPCs are stored as one-line descriptions (`"Jax": "An augmentation specialist"`) with no personality, goals, or dramatic function. The Inciting Incident generator has no access to the player's backstory, producing generic world-event hooks that feel impersonal.

Players need a story that feels personally meaningful from beginning to end, with characters they care about and dramatic beats that pay off their character creation choices.

## Decision
Implement a **5-beat adaptive Story Spine** with a **tiered NPC cast system**:

### Story Spine
- 5 dramatic beats (Hook → Deepening → Betrayal/Reversal → Crisis → Reckoning) generated at campaign start
- Each beat defines a **dramatic question** and **tonal direction**, not a scripted scene
- Beat 4 (The Crisis) explicitly weaponizes the player's fear from character creation
- The spine is adaptive: dramatic functions are fixed, but specifics mutate based on player choices
- Pressure mechanisms (World Aspects, faction clocks, Nemesis) pull wandering players back to the story

### Inciting Incident — Intersection Model
- The Hook (Beat 1) is generated using both the world setting AND the player's structured backstory
- Creates a personal stake within a larger context ("world-changing to the player," not necessarily world-scale)

### Tiered NPC System
- **Spine Characters** (2-3): Generated at campaign start with medium detail (personality, hidden agenda, dramatic function). Connected to the player's backstory.
- **Encountered NPCs**: Start as lightweight one-liners. Promoted to medium detail when the player invests in them (3+ interactions, relationship added, or Lore Keeper needs a role filled).
- Stored in dedicated `cast.json`, separate from faction politics.

### Structured Backstory
- Character creation answers stored as individual fields (`fear`, `childhood_event`, `past_life`, `sentimental_item_story`) instead of a concatenated string blob, giving agents programmatic access.

## Alternatives Considered

1. **Rigid spine with pre-scripted scenes**: Guarantees dramatic payoff but fights the emergent gameplay design. Rejected as railroady.
2. **Purely emergent story (current approach)**: Relies entirely on rumor escalation and LLM improvisation. Produces meandering narratives without satisfying arcs. Rejected.
3. **Heavy NPC sheets for all characters**: Full backstories and mini-arcs for every NPC. Too expensive in context window and generation cost. Rejected in favor of tiered promotion.
4. **Backstory-derived (not intersected) inciting incident**: Starting quest generated purely from character backstory. Risks feeling small-scale and disconnected from the world. Rejected in favor of intersection.

## Consequences

### Positive
- Campaigns have a satisfying dramatic arc with personal stakes
- Character creation choices matter throughout the entire story (especially the fear → Beat 4)
- Important NPCs feel like real characters with personalities and agendas
- Adaptive design preserves player agency while maintaining narrative pressure

### Negative
- Story Spine generation requires an additional LLM call at campaign start (longer initialization)
- The Lore Keeper's complexity increases significantly (spine tracking, beat advancement, NPC promotion)
- Existing saves need graceful fallback handling (no spine = legacy mode)
- Risk of LLM failing to advance beats correctly; needs monitoring and safety nets
