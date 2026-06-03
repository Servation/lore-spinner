# 1. Hidden Tag-Based Ability System

## Status
Approved

## Context
Traditional tabletop and video RPGs display numeric stats (e.g., Strength: 18, Stealth: +7) directly to players. While this makes mechanics clear, it encourages min-maxing behavior and breaks narrative immersion. We want a narrative-first roleplaying game where actions and outcomes are described textually rather than numerically, yet we still require a robust, deterministic system underneath to resolve choices fairly.

## Decision
We decided to implement a hidden tag-based ability system:
1. **Backstory Tag Derivation**: During character creation, the player responds to three narrative questions. The answers are analyzed by the LLM to seed 4–6 initial ability tags (e.g., `combat: +2`, `stealth: +1`, `hacking: +2`) mapping to their backstory.
2. **Hidden Modifiers**: All ability modifiers are hidden from the player during normal gameplay. The DM client narrates check results entirely through flavor text (e.g., instead of saying "stealth check succeeded with 18 vs DC 12," the DM narrates "you slip silently into the shadows, undetected by the scanning droids").
3. **Learn-by-Doing Progression**: Every time the player successfully rolls an ability check, a hidden usage counter for that tag is incremented. When it crosses a threshold (dependent on current level), the tag modifier levels up.
4. **Out-of-Character Commands**: If players explicitly wish to see their stats, they can type `OOC: stats` to bypass the narrative layer and query the local JSON files directly without incurring API cost.

## Consequences
- **Improved Immersion**: Players focus on describing actions in-character rather than worrying about stat optimizations.
- **Organic Progression**: Characters naturally grow stronger in skills they actually practice.
- **Clean Interfaces**: The main output of the game remains purely textual, reading like an interactive novel.
