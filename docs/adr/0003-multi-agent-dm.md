# 3. Multi-Agent DM Architecture

## Status
Approved

## Context
Orchestrating an entire narrative RPG requires an LLM to manage multiple complex responsibilities simultaneously: narration tone, environmental elements, faction reactions, combat rules, and quest progression. For a single LLM, this causes prompt bloat, high error rates in state management, and generic world events. 

## Decision
We decided to split the DM role into a multi-agent system:
1. **Dungeon Master (DM) Agent**: The primary, player-facing interface. Coordinates turn flow, handles player actions, interprets dice rolls, and integrates subagent inputs into the narrative.
2. **Four Specialized Subagents**:
   - **World Keeper**: Simulates time of day, weather cycles, and environmental modifiers.
   - **Faction Weaver**: Simulates political factions, NPC actions, and player reputation.
   - **Encounter Architect**: Spawns threat-appropriate combat encounters and designs loot tables.
   - **Lore Keeper**: Tracks unlocked secrets, world history, and quest progress.
3. **Heartbeat Triggers**: The World Keeper and Faction Weaver run on periodic, randomized heartbeats (every 5-10 turns) to evolve the background state independently of player choices.
4. **Budget Mode**: Because multi-agent calls are expensive, we implemented a Budget Mode that disables background heartbeats and uses rule-based, deterministic heuristics to update weather, time, and factions, reducing LLM calls from ~4 per turn to exactly 1.

## Consequences
- **High Simulation Fidelity**: The world environment and faction politics behave with far more depth and consistency.
- **Enhanced Narration**: The DM agent is freed from tracking mechanical details and can dedicate its prompt window to rich, stylistic prose.
- **Cost Management**: The inclusion of a toggleable Budget Mode ensures the game is playable on low-cost APIs or when token budgets are limited.
