import os
import json
import random
from typing import Dict, Callable
from agents.base_agent import BaseAgent
from game_engine.world import WorldState

class FactionWeaver(BaseAgent):
    def __init__(self, llm_client, campaign_slug: str):
        self.campaign_slug = campaign_slug
        self.tools = self._get_tools()
        
        sys_instruction = """You are the Faction Weaver. You manage faction standings, reputations, NPC alignments, faction intrigues, and faction clocks.
Your job is to update faction reputations and spawn faction-specific events in the background based on player actions.
You do NOT interact with the player directly or write dialog. You update the factions database via tools.

You run in a ReAct loop. If queried on a heartbeat:
1. Review the factions, reputations, and active clocks.
2. Advance plots or register new clocks using tools.
3. Output your final Answer summarizing what faction plots developed.
CRITICAL RULE: A faction should NEVER have more than 1 or 2 active project clocks at a time. If a faction already has active clocks, do NOT register new ones. Instead, add flavor events or wait for them to resolve.

Your tools are:
- update_reputation: Modifies player reputation with a faction. Format: 'faction_id | change_amount'. Usage: Action: update_reputation: rebels | 5
- add_npc: Adds or updates an NPC's description and faction alignment. Format: 'npc_name | faction_id | description'. Usage: Action: add_npc: Jax | rebels | An augmentation specialist.
- add_faction_event: Records a faction scheme/event. Format: 'faction_id | event_description'. Usage: Action: add_faction_event: corporation | Preparing a sweep of the lower levels.
- add_faction_clock: Registers a background project with a countdown. Format: 'faction_id | clock_id | name | description | turns_remaining | outcome_description | [modifier_name] | [modifier_value]'. Usage: Action: add_faction_clock: corporation | gate | Slums Gate Checkpoint | Building checkpoint | 3 | Slums gate is locked down | slum_gate_modifier | -2
- resolve_faction_clock: Resolves or deletes a faction clock. Format: 'faction_id | clock_id | outcome'. Outcome options: 'succeeded' or 'thwarted'. Usage: Action: resolve_faction_clock: corporation | gate | thwarted
"""
        super().__init__(llm_client, self.tools, sys_instruction)

    def _get_tools(self) -> Dict[str, Callable[[str], str]]:
        def update_reputation(args: str) -> str:
            if "|" not in args:
                return "Error: Format must be 'faction_id | change_amount'"
            parts = args.split("|", 1)
            faction_id = parts[0].strip()
            try:
                val = int(parts[1].strip())
            except ValueError:
                return "Error: Change amount must be an integer."
                
            path = os.path.join("saves", self.campaign_slug, "factions.json")
            if not os.path.exists(path):
                # Initialize default structure
                data = {"factions": {}, "faction_events": [], "last_tick_turn": 0}
            else:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
            if faction_id not in data["factions"]:
                data["factions"][faction_id] = {"name": faction_id.replace("_", " ").title(), "reputation": 0, "npcs": {}, "clocks": []}
                
            data["factions"][faction_id]["reputation"] += val
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return f"Reputation with '{faction_id}' modified by {val}. New total: {data['factions'][faction_id]['reputation']}."

        def add_npc(args: str) -> str:
            if args.count("|") < 2:
                return "Error: Format must be 'npc_name | faction_id | description'"
            parts = args.split("|", 2)
            name = parts[0].strip()
            faction_id = parts[1].strip()
            desc = parts[2].strip()
            
            path = os.path.join("saves", self.campaign_slug, "factions.json")
            if not os.path.exists(path):
                data = {"factions": {}, "faction_events": [], "last_tick_turn": 0}
            else:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
            if faction_id not in data["factions"]:
                data["factions"][faction_id] = {"name": faction_id.replace("_", " ").title(), "reputation": 0, "npcs": {}, "clocks": []}
                
            if "npcs" not in data["factions"][faction_id]:
                data["factions"][faction_id]["npcs"] = {}
                
            data["factions"][faction_id]["npcs"][name] = desc
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return f"NPC '{name}' registered to faction '{faction_id}'."

        def add_faction_event(args: str) -> str:
            if "|" not in args:
                return "Error: Format must be 'faction_id | event_description'"
            parts = args.split("|", 1)
            faction_id = parts[0].strip()
            event_desc = parts[1].strip()
            
            path = os.path.join("saves", self.campaign_slug, "factions.json")
            if not os.path.exists(path):
                data = {"factions": {}, "faction_events": [], "last_tick_turn": 0}
            else:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
            data["faction_events"].append({
                "faction_id": faction_id,
                "event": event_desc,
                "timestamp_turn": data.get("last_tick_turn", 0)
            })
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return f"Recorded event for faction '{faction_id}': {event_desc}."

        def add_faction_clock(args: str) -> str:
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 6:
                return "Error: Format must be 'faction_id | clock_id | name | description | turns_remaining | outcome_description | [modifier_name] | [modifier_value]'"
            
            faction_id = parts[0]
            clock_id = parts[1]
            name = parts[2]
            desc = parts[3]
            try:
                turns = int(parts[4])
            except ValueError:
                return "Error: turns_remaining must be an integer."
            outcome = parts[5]
            
            mod_name = parts[6] if len(parts) > 6 and parts[6] else None
            mod_val = None
            if len(parts) > 7 and parts[7]:
                try:
                    mod_val = int(parts[7])
                except ValueError:
                    return "Error: modifier value must be an integer."
                    
            path = os.path.join("saves", self.campaign_slug, "factions.json")
            if not os.path.exists(path):
                data = {"factions": {}, "faction_events": [], "last_tick_turn": 0}
            else:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
            if faction_id not in data["factions"]:
                data["factions"][faction_id] = {"name": faction_id.replace("_", " ").title(), "reputation": 0, "npcs": {}, "clocks": []}
                
            if "clocks" not in data["factions"][faction_id]:
                data["factions"][faction_id]["clocks"] = []
                
            # Check if clock already exists
            for c in data["factions"][faction_id]["clocks"]:
                if c["id"] == clock_id:
                    return f"Error: Clock with ID '{clock_id}' already exists for faction '{faction_id}'."
                    
            data["factions"][faction_id]["clocks"].append({
                "id": clock_id,
                "name": name,
                "description": desc,
                "turns_remaining": turns,
                "trigger_event": outcome,
                "modifier_name": mod_name,
                "modifier_value": mod_val
            })
            
            # Initialize last_tick_turn to current turn if not set
            if "last_tick_turn" not in data:
                world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
                if os.path.exists(world_path):
                    try:
                        with open(world_path, "r", encoding="utf-8") as wf:
                            w_data = json.load(wf)
                        data["last_tick_turn"] = w_data.get("turn_count", 0)
                    except Exception:
                        data["last_tick_turn"] = 0
                else:
                    data["last_tick_turn"] = 0
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                
            return f"Registered faction clock '{name}' (ID: {clock_id}) for faction '{faction_id}' with {turns} turns remaining."

        def resolve_faction_clock(args: str) -> str:
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 3:
                return "Error: Format must be 'faction_id | clock_id | outcome'"
                
            faction_id = parts[0]
            clock_id = parts[1]
            outcome = parts[2].lower() # 'succeeded' or 'thwarted'
            
            path = os.path.join("saves", self.campaign_slug, "factions.json")
            if not os.path.exists(path):
                return "Error: Factions database not found."
                
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if faction_id not in data["factions"] or "clocks" not in data["factions"][faction_id]:
                return f"Error: No clocks found for faction '{faction_id}'."
                
            target_clock = None
            remaining_clocks = []
            for c in data["factions"][faction_id]["clocks"]:
                if c["id"] == clock_id:
                    target_clock = c
                else:
                    remaining_clocks.append(c)
                    
            if not target_clock:
                return f"Error: Clock with ID '{clock_id}' not found for faction '{faction_id}'."
                
            data["factions"][faction_id]["clocks"] = remaining_clocks
            
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            world = None
            if os.path.exists(world_path):
                with open(world_path, "r", encoding="utf-8") as f:
                    world = WorldState.from_dict(json.load(f))
                    
            msg = ""
            if outcome == "succeeded":
                evt_str = f"MANUAL RESOLUTION: Faction project '{target_clock['name']}' succeeded: {target_clock['trigger_event']}"
                data["faction_events"].append({
                    "faction_id": faction_id,
                    "event": evt_str,
                    "timestamp_turn": data.get("last_tick_turn", 0)
                })
                if target_clock.get("modifier_name") and target_clock.get("modifier_value") is not None and world:
                    world.add_environmental_modifier(target_clock["modifier_name"], target_clock["modifier_value"])
                msg = f"Clock '{target_clock['name']}' resolved as succeeded."
            elif outcome == "thwarted":
                evt_str = f"THWARTED: Faction project '{target_clock['name']}' was thwarted by the player's actions!"
                data["faction_events"].append({
                    "faction_id": faction_id,
                    "event": evt_str,
                    "timestamp_turn": data.get("last_tick_turn", 0)
                })
                msg = f"Clock '{target_clock['name']}' resolved as thwarted."
            else:
                return "Error: Outcome must be 'succeeded' or 'thwarted'."
                
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                
            if world and outcome == "succeeded":
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                    
            return msg

        return {
            "update_reputation": update_reputation,
            "add_npc": add_npc,
            "add_faction_event": add_faction_event,
            "add_faction_clock": add_faction_clock,
            "resolve_faction_clock": resolve_faction_clock
        }

    def heartbeat(self, budget_mode: bool = False, context_map = None) -> str:
        """Executes faction scheming turn and ticks down active faction clocks."""
        path = os.path.join("saves", self.campaign_slug, "factions.json")
        world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
        
        # Load factions
        if not os.path.exists(path):
            data = {"factions": {}, "faction_events": [], "last_tick_turn": 0}
        else:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
        # Load world state to get current turn
        current_turn = 0
        world = None
        if os.path.exists(world_path):
            with open(world_path, "r", encoding="utf-8") as f:
                w_data = json.load(f)
            world = WorldState.from_dict(w_data)
            current_turn = world.turn_count
            
        # Tick clocks
        last_tick = data.get("last_tick_turn", 0)
        elapsed = current_turn - last_tick
        
        clock_trigger_events = []
        if elapsed > 0:
            data["last_tick_turn"] = current_turn
            # Iterate through factions and tick clocks
            for faction_id, faction_info in data.get("factions", {}).items():
                if "clocks" not in faction_info:
                    faction_info["clocks"] = []
                
                remaining_clocks = []
                for clock in faction_info["clocks"]:
                    clock["turns_remaining"] -= elapsed
                    if clock["turns_remaining"] <= 0:
                        # Clock triggers!
                        outcome_desc = clock["trigger_event"]
                        evt_str = f"CLOCK TRIGGERED: Faction project '{clock['name']}' completed: {outcome_desc}"
                        
                        # Add faction event
                        data["faction_events"].append({
                            "faction_id": faction_id,
                            "event": evt_str,
                            "timestamp_turn": current_turn
                        })
                        
                        # Apply world state modifier if any
                        if clock.get("modifier_name") and clock.get("modifier_value") is not None and world:
                            world.add_environmental_modifier(clock["modifier_name"], clock["modifier_value"])
                            
                        clock_trigger_events.append(f"[{faction_info.get('name', faction_id)}] {evt_str}")
                    else:
                        remaining_clocks.append(clock)
                faction_info["clocks"] = remaining_clocks
                
            # Save factions
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            # Save world if updated
            if world and clock_trigger_events:
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                    
        # Format clocks for budget or LLM summary
        clocks_summary_list = []
        for fid, finfo in data.get("factions", {}).items():
            for c in finfo.get("clocks", []):
                clocks_summary_list.append(f"[{finfo.get('name', fid)}] {c['name']} (ID: {c['id']}, {c['turns_remaining']} turns remaining)")
        clocks_str = " | ".join(clocks_summary_list) if clocks_summary_list else "None"
        
        if budget_mode:
            # Rule-based fallback: 20% chance of random faction scheming event
            scheming_event = ""
            if random.random() < 0.2 and data["factions"]:
                faction_id = random.choice(list(data["factions"].keys()))
                scheming_event = f"{faction_id.replace('_', ' ').title()} is regrouping and preparing resources in the shadows."
                data["faction_events"].append({
                    "faction_id": faction_id,
                    "event": scheming_event,
                    "timestamp_turn": current_turn
                })
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            
            res_parts = []
            if clock_trigger_events:
                res_parts.append("Clock triggers: " + " / ".join(clock_trigger_events))
            if scheming_event:
                res_parts.append(scheming_event)
            if not res_parts:
                res_parts.append("Factions remain quiet.")
            return " ".join(res_parts)
            
        # LLM-guided heartbeat
        query = (
            f"Current Factions: {list(data['factions'].keys())}. "
            f"Reputations: { {k: v['reputation'] for k, v in data['factions'].items()} }. "
            f"Active Faction Clocks: {clocks_str}. "
            f"Clocks Triggered This Heartbeat: {', '.join(clock_trigger_events) if clock_trigger_events else 'None'}. "
        )
        if context_map:
            query += f"Context Map Summary: {context_map.summary()}. "
        query += "Decide if any faction registers a new scheme/clock, or triggers a plot event."
        
        return self.run(query, max_turns=3, verbose=False, agent_name="FactionWeaver")
