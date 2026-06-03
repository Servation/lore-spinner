# 2. Contextual Character Death

## Status
Approved

## Context
In text-based narrative RPGs, sudden character death due to a single poor combat roll can frustrate players and ruin long-running campaigns. Conversely, removing the possibility of death entirely trivializes choices and eliminates all stakes. We need a flexible system that preserves narrative weight, supports appropriate mechanical consequences, and handles character defeat intelligently.

## Decision
We decided to implement a contextual death resolution system. When character HP drops to 0:
1. **Contextual Evaluation**: The DM agent does not automatically trigger a game-over screen. Instead, the DM evaluates the narrative context of the defeat (e.g., fighting a minor street thief vs. facing a galactic emperor).
2. **Dynamic Outcomes**:
   - **Permadeath**: Triggered only during highly dramatic, narrative-climax encounters where character sacrifice makes thematic sense.
   - **Consequence / Setback**: The character survives but faces major setbacks. For example: capture by the enemy, loss of unique inventory items, receiving a permanent status scar, or waking up in chains.
   - **Checkpoint Reset**: Waking up at a nearby safe zone (e.g., local tavern, clinic, scrap yard) with minor penalties (XP loss or currency deduction) to let the player try a different route.
3. **DM Narrative Authority**: The DM agent is given the license and tools to narrate and execute this transition smoothly, updating the character sheet (HP, inventory, status effects) and world state files accordingly.

## Consequences
- **Story Continuity**: Campaigns do not abruptly end on minor encounters, preventing player frustration.
- **Narrative Stakes**: Defeat still feels meaningful because the story adapts to the player's failure.
- **Improved Roleplaying**: Players are encouraged to take narrative risks without fearing immediate deletion of their progress.
