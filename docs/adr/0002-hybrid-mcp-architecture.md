# 2. Hybrid MCP Architecture (Reference vs Engine)

Date: 2026-06-06

## Status
Accepted

## Context
We are planning to create a custom MCP server tailored to our game to provide D&D 5e data and custom homebrew content to the DM Agent. We needed to decide the boundaries of this MCP server: whether it should act solely as a static reference library, or if we should migrate our active game state (inventory, custom weapon instances, combat resolution) into the MCP server itself.

## Decision
We decided on the **Hybrid Approach**. The custom MCP server will act strictly as an offline "Reference Library" for D&D 5e SRD data and static homebrew templates. Our core Python engine (`main.py`, `combat.py`, `item_system.py`) will retain full ownership of the active game state, player inventory, dynamic combat resolution, and instantiated custom items.

## Consequences
- **Pros:** Maintains a clean separation of concerns. The MCP server remains a stateless knowledge base, while the Python engine handles the complex, stateful mechanics of the RPG. It prevents our core engine from becoming a hollow message-passing client.
- **Cons:** The DM Agent must query the MCP server to fetch a template, and then explicitly use the engine's tools (like `modify_inventory`) to instantiate it in the game state, adding a step to the process.
