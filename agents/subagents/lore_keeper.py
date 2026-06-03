import os
import json
from typing import Dict, Callable
from agents.base_agent import BaseAgent
from game_engine.world import WorldState

class LoreKeeper(BaseAgent):
    def __init__(self, llm_client, campaign_slug: str):
        self.campaign_slug = campaign_slug
        self.tools = self._get_tools()
        
        sys_instruction = """You are the Lore Keeper. You manage quest progressions, hidden secrets, and unlocked lore/codex entries.
Your job is to track narrative milestones, unlock historical or technological lore, and manage quests.
You do NOT interact with the player directly. You write to the lore and world state databases via tools.

You run in a ReAct loop. When called:
1. Examine the player's action, location, and quest list.
2. Determine if a quest should advance or finish.
3. Determine if any secret lore should be unlocked.
4. Output your final Answer summarizing what quests/lore changed.

Your tools are:
- add_quest: Spawns a new quest. Format: 'quest_id | quest_name | description'. Usage: Action: add_quest: main_shard | Find the Data Shard | Locate the encrypted high-density shard.
- update_quest: Updates a quest status. Format: 'quest_id | status'. Status options: 'completed', 'failed'. Usage: Action: update_quest: main_shard | completed
- unlock_lore: Unlocks a codex/lore entry. Format: 'title | content'. Usage: Action: unlock_lore: The Great Freeze | A historical recount of the disaster.
- plant_secret: Registers a secret clue. Format: 'secret_description'. Usage: Action: plant_secret: Jax is planning a double cross.
"""
        super().__init__(llm_client, self.tools, sys_instruction)

    def _get_tools(self) -> Dict[str, Callable[[str], str]]:
        def add_quest(args: str) -> str:
            if args.count("|") < 2:
                return "Error: Format must be 'quest_id | quest_name | description'"
            parts = args.split("|", 2)
            qid = parts[0].strip()
            name = parts[1].strip()
            desc = parts[2].strip()
            
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(world_path):
                return "Error: World state not found."
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.add_quest(qid, name, desc)
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            return f"Quest '{name}' (ID: {qid}) added successfully."

        def update_quest(args: str) -> str:
            if "|" not in args:
                return "Error: Format must be 'quest_id | status'"
            parts = args.split("|", 1)
            qid = parts[0].strip()
            status = parts[1].strip().lower()
            
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(world_path):
                return "Error: World state not found."
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            success = world.update_quest_status(qid, status)
            if success:
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Quest ID '{qid}' status updated to '{status}'."
            return f"Quest ID '{qid}' not found."

        def unlock_lore(args: str) -> str:
            if "|" not in args:
                return "Error: Format must be 'title | content'"
            parts = args.split("|", 1)
            title = parts[0].strip()
            content = parts[1].strip()
            
            lore_path = os.path.join("saves", self.campaign_slug, "lore.json")
            if not os.path.exists(lore_path):
                data = {"unlocked_lore": [], "secrets": []}
            else:
                with open(lore_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
            data["unlocked_lore"].append({"title": title, "content": content})
            with open(lore_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return f"Unlocked lore entry: '{title}'."

        def plant_secret(secret_desc: str) -> str:
            lore_path = os.path.join("saves", self.campaign_slug, "lore.json")
            if not os.path.exists(lore_path):
                data = {"unlocked_lore": [], "secrets": []}
            else:
                with open(lore_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
            data["secrets"].append(secret_desc.strip())
            with open(lore_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return f"Secret clue planted: {secret_desc.strip()}."

        return {
            "add_quest": add_quest,
            "update_quest": update_quest,
            "unlock_lore": unlock_lore,
            "plant_secret": plant_secret
        }

    def check_lore(self, action: str, location: str) -> str:
        """Called by DM to check if any lore is unlocked by this action/location."""
        query = f"Location: {location}. Action: {action}. Determine if any secrets are unlocked or quests advanced."
        return self.run(query, max_turns=3, verbose=False, agent_name="LoreKeeper")
