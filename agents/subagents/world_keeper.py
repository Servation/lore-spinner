import os
import json
import random
from typing import Dict, Callable
from agents.base_agent import BaseAgent
from game_engine.world import WorldState

class WorldKeeper(BaseAgent):
    def __init__(self, llm_client, campaign_slug: str):
        self.campaign_slug = campaign_slug
        self.tools = self._get_tools()
        
        sys_instruction = """You are the World Keeper. You manage the physical world environment: weather, time, terrain, and ambient events.
Your goal is to simulate a living world that reacts to the player's presence and time passing.
You do NOT interact with the player directly or write dialogue. You only update the world state via tools.

You run in a ReAct loop. If queried on a heartbeat:
1. Review the current time of day, location, and weather.
2. Advance time or change weather if appropriate.
3. Add or remove environmental modifiers (like storms, extreme heat, toxic fog) as appropriate.
4. Output your final Answer summarizing what environmental changes occurred.

Your tools are:
- advance_time: Advances to the next time of day. Usage: Action: advance_time
- set_weather: Sets weather condition. Usage: Action: set_weather: Stormy
- add_env_modifier: Adds a modifier (e.g. 'sandstorm | -2' gives -2 to athletics/combat). Usage: Action: add_env_modifier: storm | -2
- remove_env_modifier: Removes a modifier. Usage: Action: remove_env_modifier: storm
"""
        super().__init__(llm_client, self.tools, sys_instruction)

    def _get_tools(self) -> Dict[str, Callable[[str], str]]:
        def advance_time(dummy: str) -> str:
            path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(path):
                return "Error: World state not found."
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            new_time = world.advance_time()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            return f"Time advanced to {new_time}."

        def set_weather(weather: str) -> str:
            path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(path):
                return "Error: World state not found."
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            # Store weather in its own dedicated field, NOT as an environmental modifier
            world.weather = weather.strip()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            return f"Weather set to {weather}."

        def add_env_modifier(args: str) -> str:
            if "|" not in args:
                return "Error: Format must be 'modifier_name | amount'"
            parts = args.split("|", 1)
            name = parts[0].strip()
            try:
                val = int(parts[1].strip())
            except ValueError:
                return "Error: Modifier amount must be an integer."
                
            path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(path):
                return "Error: World state not found."
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.add_environmental_modifier(name, val)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            return f"Added environmental modifier '{name}' with value {val}."

        def remove_env_modifier(name: str) -> str:
            path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(path):
                return "Error: World state not found."
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.remove_environmental_modifier(name)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            return f"Removed environmental modifier '{name}'."

        def set_bodily_needs(args: str) -> str:
            """Format: 'hunger | fatigue'. Values: 0=Fine, 1=Mildly affected, 2=Severely affected.
            Usage: Action: set_bodily_needs: 1 | 0"""
            parts = args.split("|")
            if len(parts) < 2:
                return "Error: Format must be 'hunger_level | fatigue_level' (0-2 each)."
            try:
                hunger = max(0, min(2, int(parts[0].strip())))
                fatigue = max(0, min(2, int(parts[1].strip())))
            except ValueError:
                return "Error: Values must be integers 0-2."
            path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(path):
                return "Error: World state not found."
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.hunger = hunger
            world.fatigue = fatigue
            with open(path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            hunger_labels = ["Full", "Hungry", "Starving"]
            fatigue_labels = ["Rested", "Tired", "Exhausted"]
            return f"Bodily needs updated: {hunger_labels[hunger]}, {fatigue_labels[fatigue]}."

        return {
            "advance_time": advance_time,
            "set_weather": set_weather,
            "add_env_modifier": add_env_modifier,
            "remove_env_modifier": remove_env_modifier,
            "set_bodily_needs": set_bodily_needs
        }

    def heartbeat(self, budget_mode: bool = False, context_map = None) -> str:
        """Executes the heartbeat turn. Evolves time and weather."""
        if budget_mode:
            # Rule-based fallback: 25% chance to advance time, 20% weather change
            path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(path):
                return "No state found."
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            
            changes = []
            if random.random() < 0.3:
                new_time = world.advance_time()
                changes.append(f"Time advanced to {new_time}")
                
            # Random weather change
            if random.random() < 0.25:
                weathers = ["Clear", "Rainy", "Overcast", "Windy", "Foggy"]
                new_w = random.choice(weathers)
                world.add_environmental_modifier(new_w, 0)
                changes.append(f"Weather changed to {new_w}")
                
            if changes:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return "; ".join(changes) + "."
            return "World environment remains stable."
            
        # LLM-guided heartbeat
        path = os.path.join("saves", self.campaign_slug, "world_state.json")
        if not os.path.exists(path):
            return "No state found."
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        world = WorldState.from_dict(data)
        
        # Resolve actual current location name from ID rather than stale string field
        current_loc_name = world.current_location
        if hasattr(world, 'current_location_id') and world.current_location_id:
            loc_obj = next((l for l in world.discovered_locations if l.id == world.current_location_id), None)
            if loc_obj:
                current_loc_name = f"{loc_obj.name} ({loc_obj.type})"
        
        query = f"World Genre: {world.setting_genre}. Current time: {world.time_of_day}. Location: {current_loc_name}. Active environmental modifiers: {[m.name for m in world.environmental_modifiers]}."
        if context_map:
            query += f" Context Map Summary: {context_map.summary()}"
        query += " Update the environment if appropriate."
        
        return self.run(query, max_turns=3, verbose=False, agent_name="WorldKeeper")
