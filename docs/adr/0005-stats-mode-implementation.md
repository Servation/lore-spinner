# 5. Stats Mode Implementation & Narrative Authority

## Status
Approved

## Context
The project was designed with a strict "Hidden Stats" philosophy, meaning all character mechanics, modifiers, and dice rolls were invisible to the player (ADR 0001). However, we identified a desire for an alternative playstyle where players can see their stats and the mechanical weight of their actions. We call this "Stats Mode".

The core challenge was reconciling Stats Mode with the DM's "Narrative Authority" — the DM's ability to fudge dice rolls for dramatic effect. If Stats Mode exposed the raw math, players would instantly detect when the DM fudged a roll, breaking immersion and making the fudge look like a system bug.

## Decision
We will implement "Stats Mode" as an optional toggle chosen at the start of a new campaign with the following rules:
1. **Obfuscated Rolls**: The occurrence of a roll, the modifiers used (e.g., `+2 stealth`), and the **Difficulty Class (DC)** are displayed in a standardized Mechanics Block at the end of the DM's narrative (e.g., `[MECHANICS: Stealth Check | Mods: +2 cloak | DC 12] (Success)`). The exact numerical die result is blocked out (shown as `??`) to preserve Narrative Authority.
2. **Outcome-Based Coloring**: The Mechanics Block will be colored to indicate success (green) or failure (red). Crucially, this coloring is based on the DM's **final narrative decision**, NOT the raw mathematical result. If a roll mathematically fails but the DM fudges it into a success, the UI will color the block green.
3. **DM Output Formatting**: The DM agent will be instructed (when Stats Mode is active) to append a structured block which the UI will parse and color accordingly. This applies to both exploration checks (`roll_ability_check`) and **combat rounds** (`apply_combat_turn`), ensuring that attack rolls, damage, and defense are also surfaced during fights.
4. **Character Stats on Checks**: When a Mechanics Block is emitted, the DM includes the relevant ability tag and its current modifier alongside any item or environmental bonuses that contributed to the roll. This lets the player see exactly which stats and equipment matter.

## Consequences
- **Preserved Narrative Authority**: The DM can continue to fudge rolls for dramatic tension without exposing the mathematical contradiction to the player.
- **Enhanced Player Feedback**: Players who prefer a "tabletop feel" can see exactly which stats and items are contributing to their checks.
- **UI Parsing Complexity**: The UI layer must now reliably parse the DM's text to apply the correct ANSI colors based on the final narrative outcome indicated in the Mechanics Block.
- **Combat Consistency**: Both exploration and combat rolls must emit Mechanics Blocks, requiring prompt changes in the DM's system instructions for both `roll_ability_check` and `apply_combat_turn` tool usage.
