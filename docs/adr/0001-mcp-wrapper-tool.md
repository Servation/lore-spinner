# 1. Use a Wrapper Tool for MCP Integration

Date: 2026-06-06

## Status
Accepted

## Context
We are integrating an external Model Context Protocol (MCP) server (specifically, a D&D 5e knowledge base) to provide the DM Agent with grounded, official stats for items, monsters, and spells.
The DM Agent uses a ReAct loop to interact with tools. We had to decide whether to dynamically inject the raw tools exposed by the MCP server (e.g., `search_all_categories`) directly into the DM Agent's prompt, or build a custom Python wrapper tool within our engine to intermediate the requests.

## Decision
We decided to implement a **Wrapper Tool** (e.g., `lookup_srd_data`) within `dm_agent.py` instead of exposing native MCP tools directly to the DM LLM.

## Consequences
- **Pros:** Keeps the DM Agent's prompt clean and consistent with our existing custom python tools. Allows the engine to intercept, format, and gracefully handle network or connection errors from the MCP server before the LLM sees them. Prevents the LLM from getting confused by MCP-specific schema requirements.
- **Cons:** Requires manual maintenance of the wrapper tool. If the MCP server adds new capabilities, they won't be automatically available to the DM Agent unless we update the wrapper.
