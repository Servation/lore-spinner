# 6. In-Memory Context Map for Subagent Queries

Date: 2026-06-05

## Status

Accepted

## Context

Our game relies on autonomous subagents (Faction Weaver, Lore Keeper) that need to understand complex relationships in the world to simulate emergent narrative events. For example, they might need to find "all characters located in Neon City who are hostile to the Thieves Guild and have a connection to the player." 

Currently, the game state is stored in multiple flat JSON files (`cast.json`, `factions.json`, `world.json`, `encounters.json`). Querying complex, multi-hop relationships across these disjointed files requires verbose and brittle filtering logic. 

We considered replacing the JSON files with a dedicated graph database (like Neo4j) to act as the primary save state. We also considered writing an event-driven synchronization system to push JSON delta updates into a graph.

## Decision

1. We will introduce an **in-memory property graph** (a "Context Map", e.g., using NetworkX) specifically to act as a secondary index for subagent queries.
2. We will **not** replace the JSON save files. JSON remains the primary source of truth for the game state, maintaining file portability and simplicity.
3. We will **not** use event-driven delta updates. Instead, the graph will be completely **rebuilt on every Heartbeat cycle** directly from the latest JSON files.
4. When building the graph, we will **abstract entity types**. For instance, entries from `cast.json` and `factions.json` will both become generic `Character` nodes in the graph with an `is_cast` boolean property, allowing agents to query across all known NPCs seamlessly.
5. The graph builder will enforce a **Strict Schema** for relationship edges. Because the DM Agent (an LLM) may hallucinate novel relationship types (e.g., `OWES_MONEY_TO`) in the JSON, the graph builder will default unrecognized types to a generic fallback (e.g., `KNOWS`). This ensures subagents can rely on a predictable set of edges for their queries.

## Consequences

- **Pros:** 
  - Subagents can leverage powerful graph traversal algorithms and simple query logic.
  - Rebuilding the graph on a heartbeat is computationally trivial for the expected dataset size and completely eliminates the risk of state desynchronization.
  - Abstracted nodes (like generic `Character` nodes) natively handle mechanics like "NPC Promotion" without requiring subagents to change their queries.
- **Cons:** 
  - The in-memory graph is ephemeral and cannot be directly mutated by subagents; if a subagent wants to change the world state based on a graph query, it must issue an update command targeting the underlying JSON file, which will then reflect in the next heartbeat's graph rebuild.
