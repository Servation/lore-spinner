import os
import json
from typing import Dict, Callable
from agents.base_agent import BaseAgent
from game_engine.combat import generate_enemy

class EncounterArchitect(BaseAgent):
    def __init__(self, llm_client, campaign_slug: str):
        self.campaign_slug = campaign_slug
        self.tools = self._get_tools()
        
        sys_instruction = """You are the Encounter Architect. You design combat encounters, enemy stat blocks, tactical maneuvers, and loot drops.
Your job is to spawn enemies appropriate to the current world location and level, and detail their behaviors.
CRITICAL ENCOUNTER VARIETY: You MUST provide a dynamic mix of encounters so the world feels organic! 
- ~50% of the time: Heavily weave the encounter into the provided Active Quest (e.g., the enemy holds a required quest item or guards a plot clue).
- ~30% of the time: Spawn an enemy that drops loot sparking an entirely NEW mini side-quest (e.g., a smuggler carrying a strange treasure map or cryptic coded letter).
- ~20% of the time: Spawn a pure, natural environmental hazard (like a hungry beast or broken security bot) that has absolutely NO relation to any quest.
You do NOT interact with the player directly. You write to the encounters state via tools.

You run in a ReAct loop. When called:
1. Examine the current threat level, location, and genre.
2. Spawn an enemy with stats and a tactical behavior description.
3. Detail loot drops if combat is resolved.
4. Output your final Answer explaining what encounter was configured.

Your tools are:
- spawn_encounter: Spawns enemies. Format: 'enemy_name | threat_level | setting_genre | count | narrative_desc'. Usage: Action: spawn_encounter: Security Droid | 2 | cyberpunk | 3 | A patrol of 3 droids.
- add_loot: Configures loot. For the description, write a narrative description that implies what the item does without raw numbers. Format: 'item_name | description | slot | tag_modifiers_json'. Usage: Action: add_loot: Reflex Booster | A sleek implant that noticeably quickens your reflexes | accessory | {"evasion": 1}
- clear_encounter: Resets the active encounter when combat is finished. Usage: Action: clear_encounter
"""
        super().__init__(llm_client, self.tools, sys_instruction)

    def _get_tools(self) -> Dict[str, Callable[[str], str]]:
        def spawn_encounter(args: str) -> str:
            if args.count("|") < 4:
                return "Error: Format must be 'enemy_name | threat_level | setting_genre | count | narrative_desc'"
            parts = args.split("|", 4)
            name = parts[0].strip()
            try:
                threat = int(parts[1].strip())
            except ValueError:
                return "Error: Threat level must be an integer."
            genre = parts[2].strip()
            
            try:
                count = int(parts[3].strip())
                count = max(1, min(count, 5)) # Cap between 1 and 5 enemies
            except ValueError:
                return "Error: Count must be an integer."
                
            desc = parts[4].strip()
            
            # Get player speed and turn_count to roll initiative and scale difficulty
            player_speed = 2
            turn_count = 1
            char_path = os.path.join("saves", self.campaign_slug, "character.json")
            if os.path.exists(char_path):
                try:
                    with open(char_path, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                        player_speed = c_data.get("speed", 2)
                except Exception:
                    pass

            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if os.path.exists(world_path):
                try:
                    with open(world_path, "r", encoding="utf-8") as f:
                        w_data = json.load(f)
                        turn_count = w_data.get("turn_count", 0)
                except Exception:
                    pass

            # Clamp difficulty based on turn count to ensure smooth ramp-up in early game
            if turn_count <= 10:
                count = min(count, 2)
                if count > 1:
                    threat = min(threat, 1)
                else:
                    threat = min(threat, 2)
            elif turn_count <= 25:
                count = min(count, 3)
                if count > 1:
                    threat = min(threat, 2)
                else:
                    threat = min(threat, 3)
            
            # Generate the enemy objects
            enemies = []
            for i in range(count):
                enemy = generate_enemy(f"{name} {chr(65+i)}" if count > 1 else name, threat, genre)
                enemies.append(enemy)
                    
            from game_engine.dice import roll
            
            initiatives = []
            initiatives.append({"id": "player", "name": "Player", "roll": roll(20) + player_speed})
            
            for idx, enemy in enumerate(enemies):
                initiatives.append({"id": f"enemy_{idx}", "name": enemy.name, "roll": roll(20) + enemy.speed})
                
            # Sort by roll descending
            initiatives.sort(key=lambda x: x["roll"], reverse=True)
            
            path = os.path.join("saves", self.campaign_slug, "encounters.json")
            data = {
                "active_encounter": {
                    "enemies": [e.to_dict() for e in enemies],
                    "initiative_order": initiatives,
                    "description": desc
                },
                "recent_loot": []
            }
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return f"Spawned encounter '{name}' x{count} (Threat {threat}) successfully."

        def add_loot(args: str) -> str:
            if args.count("|") < 3:
                return "Error: Format must be 'item_name | description | slot | tag_modifiers_json'"
            parts = args.split("|", 3)
            item_name = parts[0].strip()
            desc = parts[1].strip()
            slot = parts[2].strip()
            if slot.lower() == "none":
                slot = None
                
            try:
                mods = json.loads(parts[3].strip())

                if not isinstance(mods, dict):
                    return "Error: Tag modifiers must be a JSON dictionary."
                for k, v in mods.items():
                    if not isinstance(k, str) or not isinstance(v, int) or isinstance(v, bool):
                        return "Error: Tag modifiers must have string keys and integer values, e.g. {\"stealth\": 1}"
            except json.JSONDecodeError:
                return "Error: Tag modifiers must be a valid JSON string, e.g. {\"stealth\": 1}"
                
            path = os.path.join("saves", self.campaign_slug, "encounters.json")
            if not os.path.exists(path):
                data = {"active_encounter": None, "recent_loot": []}
            else:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
            item = {
                "name": item_name,
                "description": desc,
                "slot": slot,
                "tag_modifiers": mods,
                "consumable": False,  # Default False; consumable=True must be set explicitly
                "charges": 0
            }
            data["recent_loot"].append(item)
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return f"Added loot item '{item_name}' to pending loot."

        def clear_encounter(dummy: str) -> str:
            path = os.path.join("saves", self.campaign_slug, "encounters.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["active_encounter"] = None
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            return "Active encounter cleared."

        return {
            "spawn_encounter": spawn_encounter,
            "add_loot": add_loot,
            "clear_encounter": clear_encounter
        }

    def generate_fight(self, enemy_name: str, threat_level: int, genre: str, desc: str) -> str:
        """Helper to directly trigger setup of a fight."""
        query = f"Setup an encounter for name: {enemy_name}, threat: {threat_level}, genre: {genre}, details: {desc}"
        return self.run(query, max_turns=3, verbose=False, agent_name="EncounterArchitect")
