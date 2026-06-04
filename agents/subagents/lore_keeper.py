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
You do NOT interact with the player directly. Your task is to maintain the overarching narrative logic of the world. You run in a background ReAct loop.
You read the DM log and the current 'Campaign Arc' and 'Active Quests'. 
1. If the player completes major tasks, update the quests.
2. If they discover something new, unlock lore entries.
3. If the player acts recklessly, angers NPCs, or suffers massive defeat, you MUST spawn new 'World Aspects' (like 'Nemesis', 'Doom Clock', 'Heat', or 'Trauma') to impose lasting consequences on them.
4. Output your final Answer summarizing what quests/lore/aspects changed.

Your tools are:
- add_quest: Spawns a new quest. Format: 'id | name | desc | [pos_conseq] | [neg_conseq]'. Usage: Action: add_quest: main_shard | Find the Data Shard | Locate the encrypted shard. | Access to archives | Corporate wipe
- update_quest: Updates a quest status. Format: 'quest_id | status'. Status options: 'completed', 'failed'. Usage: Action: update_quest: main_shard | completed
- unlock_lore: Unlocks a codex/lore entry. Format: 'title | content'. Usage: Action: unlock_lore: The Great Freeze | A historical recount of the disaster.
- plant_secret: Registers a secret clue. Format: 'secret_description'. Usage: Action: plant_secret: Jax is planning a double cross.
- update_campaign_arc: Replaces the core campaign arc. Format: 'new arc'. Usage: Action: update_campaign_arc: The player must stop the AI before it ascends.
- add_world_aspect: Adds a new World Aspect constraint (Nemesis, Doom Clock, Heat, Trauma). Format: 'name | type | desc | [intensity]'. Usage: Action: add_world_aspect: Kael | Nemesis | A rival bounty hunter tracking you. | 3
- remove_world_aspect: Removes an aspect. Format: 'name'. Usage: Action: remove_world_aspect: Kael
"""
        super().__init__(llm_client, self.tools, sys_instruction)

    def _get_tools(self) -> Dict[str, Callable[[str], str]]:
        def add_quest(args: str) -> str:
            parts = args.split("|")
            if len(parts) < 3:
                return "Error: Format must be 'quest_id | quest_name | description | [pos_conseq] | [neg_conseq]'"
            qid = parts[0].strip()
            name = parts[1].strip()
            desc = parts[2].strip()
            pos = parts[3].strip() if len(parts) > 3 else ""
            neg = parts[4].strip() if len(parts) > 4 else ""
            
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(world_path):
                return "Error: World state not found."
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.add_quest(qid, name, desc, pos_conseq=pos, neg_conseq=neg)
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

        def update_campaign_arc(new_arc: str) -> str:
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(world_path):
                return "Error: World state not found."
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.campaign_arc = new_arc
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            return "Campaign arc updated."

        def add_world_aspect(args: str) -> str:
            parts = args.split("|")
            if len(parts) < 3:
                return "Error: Format must be 'name | type | description | [intensity]'"
            name = parts[0].strip()
            a_type = parts[1].strip()
            desc = parts[2].strip()
            intensity = 1
            if len(parts) > 3:
                try:
                    intensity = int(parts[3].strip())
                except:
                    pass
                    
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.add_aspect(name, a_type, desc, intensity)
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            return f"World Aspect '{name}' ({a_type}) added/updated."

        def remove_world_aspect(name: str) -> str:
            name = name.strip()
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            if world.remove_aspect(name):
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"World Aspect '{name}' removed."
            return f"Error: Aspect '{name}' not found."

        return {
            "add_quest": add_quest,
            "update_quest": update_quest,
            "unlock_lore": unlock_lore,
            "plant_secret": plant_secret,
            "update_campaign_arc": update_campaign_arc,
            "add_world_aspect": add_world_aspect,
            "remove_world_aspect": remove_world_aspect
        }

    def check_lore(self, action: str, location: str) -> str:
        """Called by DM to check if any lore is unlocked by this action/location."""
        query = f"Location: {location}. Action: {action}. Determine if any secrets are unlocked or quests advanced."
        return self.run(query, max_turns=3, verbose=False, agent_name="LoreKeeper")

    def heartbeat(self, budget_mode: bool = False) -> str:
        if budget_mode:
            return "LoreKeeper heartbeat skipped (Budget Mode)."
            
        world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
        if not os.path.exists(world_path):
            return ""
            
        with open(world_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        world = WorldState.from_dict(data)
        
        if not world.escalated_rumors:
            return "No escalated rumors."
            
        rumors_str = ", ".join(world.escalated_rumors)
        arc_str = world.campaign_arc if world.campaign_arc else "None (Create one now based on these rumors)"
        
        query = f"HEARTBEAT: The following rumors were escalated by the DM: [{rumors_str}]. The current Campaign Arc is: [{arc_str}]. Weave these escalated rumors into a new Narrative Thread (Quest) and add it. If there is no Campaign Arc, use 'update_campaign_arc' to create the overarching Campaign Arc premise now."
        
        res = self.run(query, max_turns=4, verbose=False, agent_name="LoreKeeper")
        
        # Only clear the queue if the LLM successfully processed the rumors
        failed_keywords = ["Failed to arrive", "Error", "turn limit"]
        if not any(kw in res for kw in failed_keywords):
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.escalated_rumors.clear()
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            return "Processed escalated rumors into Narrative Threads."
        else:
            return f"LoreKeeper failed to process rumors; queue preserved for next heartbeat. ({res})"

    def generate_inciting_incident(self) -> None:
        """Generates the initial Campaign Arc and starting Narrative Thread with strict consequences."""
        world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
        if not os.path.exists(world_path):
            return
            
        with open(world_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        world = WorldState.from_dict(data)
        
        query = f"INITIALIZATION: The game is starting in the genre '{world.setting_genre}'. Setting description: '{world.setting_description}'. Your task is to establish the overarching Campaign Arc using 'update_campaign_arc', and then create the 'Inciting Incident' (the starting quest) using the 'add_quest' tool. You MUST provide explicit positive and negative consequences for this quest to set immediate stakes."
        
        self.run(query, max_turns=4, verbose=False, agent_name="LoreKeeper")
