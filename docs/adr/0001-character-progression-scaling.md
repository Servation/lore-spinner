# Title: 0001 Character Progression and Scaling
**Status**: Accepted
**Context**: The combat engine scales enemy HP, Damage, and Defense linearly based on Threat Level. However, the player's Max HP was fixed at 20, and player damage scaling was heavily gated behind finding better loot, leading to a massive survivability imbalance in late-game encounters (Threat Level 5+). We needed a defined progression model for how the player character naturally improves to match escalating threats.
**Decision**: 
1. **Dynamic Max HP Growth**: When a player naturally levels up a physical or combat-related ability tag (e.g., `athletics`, `combat`, `stamina`, `fortitude`) through the learn-by-doing usage system, their Max HP is permanently increased by +5.
2. **Artifact Upgrades**: Players can permanently increase their Max HP by finding and consuming rare items (e.g., cybernetics, strange artifacts, magical blessings) in the world.
3. **High-Tier Maneuvers**: Rather than having skills drastically alter the underlying damage math directly (which risks breaking the `1d6 + modifier` bounds), reaching high tiers (+3 or higher) in a combat tag unlocks "Special Maneuvers" (e.g., Cleave, Double Attack, Precision Shot). The DM LLM is instructed to offer these as tactical options in the prompt, creating narrative-driven mechanical rewards.
**Consequences**: 
- We must modify the `tick_usage` function in the ability system to return information about *which* tag leveled up, so the game engine can apply the HP bonus if the tag is physical.
- We must update the `dm_agent.py` system prompt to recognize high-tier tags and offer specialized narrative choices.
