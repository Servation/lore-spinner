# 8. Combat Styles and Thematic Maneuvers

## Status
Approved

## Context
Lore Spinner is a classless, tag-based roleplaying game. While this design allows for open-ended play, it makes a character's specific combat capabilities ambiguous. Players entering combat often do not know what spells, maneuvers, or actions are available to them, and the DM Agent has no concrete guidance on what options to generate. We need a way to clarify a character's combat capabilities during startup and gameplay without resorting to a rigid class structure.

## Decision
We decided to implement the following:
1. **Character Sheet Expansion**: Add `combat_style` (a string describing their fighting style) and `combat_maneuvers` (a list of 2-3 specific combat moves or spells) to the `Character` class.
2. **Backstory Analysis Seeding**: Update `run_character_creation()` to instruct the LLM to generate these fields dynamically based on the character's backstory and genre (e.g. `"combat_style": "Stealthy Daggerplay"`, `"combat_maneuvers": ["Backstab: Deals high damage from stealth", "Parry & Riposte: Deflects and counters melee attacks"]`).
3. **DM Agent Combat Override Prompting**: In `_build_dynamic_prompt()`, if combat is active, load and inject the player's `combat_style` and `combat_maneuvers` into the system instructions. Instruct the DM Agent to explicitly include options matching these capabilities in its generated choices.
4. **OOC & Summary Displays**: Update the `ooc: stats` command output, the `/summary` command (`show_campaign_summary()`), and startup/load screen rendering to list the character's combat style and capabilities.

## Consequences
- **Clear Capabilities**: Players immediately understand their tactical choices in combat (e.g., they know they can cast a "Firebolt" or perform a "Shield" spell).
- **Aligned DM Output**: The DM Agent produces combat choices that consistently match the player's combat style and moves.
- **Enhanced Roleplaying**: Combat feels highly distinct and tailored to the character's specific backstory without adding heavy mechanical complexity.
