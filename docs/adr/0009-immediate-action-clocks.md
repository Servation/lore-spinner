# 9. Immediate Action Clocks Managed by DM Agent

Date: 2026-06-06

## Status
Accepted

## Context
The game system requires a mechanic to handle immediate, high-stakes crises that span multiple turns (e.g., a falling airship, escaping a collapsing ruin). We already possess "Faction Clocks" (managed by the Faction Weaver) and "Doom Clocks" (managed by the Lore Keeper as World Aspects) that track progress mechanically. The question arose whether these background subagents (or the World Keeper) should also manage these immediate "Action Clocks" (Skill Challenges) to unify the logic of tracking time/progress.

However, the architecture dictates that background subagents operate strictly on a "Heartbeat" cycle, executing only every 5-10 turns. An immediate crisis like a falling airship resolves turn-by-turn and typically concludes within 3-4 turns. 

## Decision
We decided to keep **Action Clocks** (Skill Challenges) managed exclusively by the foreground **DM Agent**. We will introduce specific tools (`start_skill_challenge`, `update_skill_challenge`) to the DM Agent's toolset and inject active clock state into the DM's Situational Override prompt blocks. 

We explicitly decided **not** to alter the Heartbeat architecture or have subagents run on every turn when an Action Clock is active.

## Consequences
- **Positive:** We maintain low latency and lower API costs by preserving the Heartbeat cycle. The DM Agent retains full narrative authority and immediate contextual awareness of the crisis without needing to wait for asynchronous subagent interjections.
- **Negative:** There is a slight fragmentation in "clock" mechanics. Long-term clocks (Doom/Faction) are managed by subagents, while short-term clocks (Action Clocks) are managed by the DM. The system must clearly distinguish between these to avoid confusing the LLMs.
