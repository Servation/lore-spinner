# 5. Stats Mode Implementation & Narrative Authority

## Status
Approved

## Context
The project was designed with a strict "Hidden Stats" philosophy, meaning all character mechanics, modifiers, and dice rolls were invisible to the player (ADR 0001). However, we identified a desire for an alternative playstyle where players can see their stats and the mechanical weight of their actions. We call this "Stats Mode".

The core challenge was reconciling Stats Mode with the DM's "Narrative Authority" — the DM's ability to fudge dice rolls for dramatic effect. If Stats Mode exposed the raw math, players would instantly detect when the DM fudged a roll, breaking immersion and making the fudge look like a system bug.

## Decision
We will implement "Stats Mode" as an optional toggle chosen at the start of a new campaign with the following rules:
1. **Obfuscated Rolls**: The occurrence of a roll and the modifiers used (e.g., `+2 stealth`) are displayed in a standardized Mechanics Block at the end of the DM's narrative, but the exact numerical die result is blocked out or hidden (e.g., `Rolled ?? vs DC 12`).
2. **Outcome-Based Coloring**: The Mechanics Block will be colored to indicate success (green) or failure (red). Crucially, this coloring is based on the DM's **final narrative decision**, NOT the raw mathematical result. If a roll mathematically fails but the DM fudges it into a success, the UI will color the block green.
3. **DM Output Formatting**: The DM agent will be instructed (when Stats Mode is active) to append a structured block (e.g., `[MECHANICS: Stealth Check | Mods: +2 cloak] (Success)`) which the UI will parse and color accordingly.

## Consequences
- **Preserved Narrative Authority**: The DM can continue to fudge rolls for dramatic tension without exposing the mathematical contradiction to the player.
- **Enhanced Player Feedback**: Players who prefer a "tabletop feel" can see exactly which stats and items are contributing to their checks.
- **UI Parsing Complexity**: The UI layer must now reliably parse the DM's text to apply the correct `rich` colors based on the final narrative outcome indicated in the Mechanics Block.
