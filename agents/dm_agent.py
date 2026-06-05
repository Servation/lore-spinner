import os
import json
import random
from typing import Dict, Callable, List, Optional
from agents.base_agent import BaseAgent
from agents.subagents.world_keeper import WorldKeeper
from agents.subagents.faction_weaver import FactionWeaver
from agents.subagents.encounter_architect import EncounterArchitect
from agents.subagents.lore_keeper import LoreKeeper
from agents.subagents.story_critic import StoryCritic
from game_engine.character import Character
from game_engine.world import WorldState
from game_engine.dice import roll_check
from game_engine.combat import Enemy
from persistence.log_manager import write_dm_log

class DMAgent(BaseAgent):
    def __init__(self, llm_client, campaign_slug: str, budget_mode: bool = False, verbose: bool = False):
        self.campaign_slug = campaign_slug
        self.budget_mode = budget_mode
        self.verbose = verbose
        self.llm_client = llm_client
        
        # Instantiate subagents
        self.world_keeper = WorldKeeper(llm_client, campaign_slug)
        self.faction_weaver = FactionWeaver(llm_client, campaign_slug)
        self.encounter_architect = EncounterArchitect(llm_client, campaign_slug)
        self.lore_keeper = LoreKeeper(llm_client, campaign_slug)
        self.story_critic = StoryCritic(llm_client, campaign_slug)
        
        self.tools = self._get_tools()
        self.system_instruction = "" # Will be built dynamically before running
        super().__init__(llm_client, self.tools, "")

    def _get_tools(self) -> Dict[str, Callable[[str], str]]:
        def get_character_sheet(dummy: str) -> str:
            path = os.path.join("saves", self.campaign_slug, "character.json")
            if not os.path.exists(path):
                return "Error: Character state not found."
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        def get_world_details(dummy: str) -> str:
            path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(path):
                return "Error: World state not found."
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        def query_world_bible(dummy: str) -> str:
            """Usage: Action: query_world_bible"""
            path = os.path.join("saves", self.campaign_slug, "world_bible.md")
            if not os.path.exists(path):
                return "Error: World Bible not found."
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        def query_unlocked_lore(query: str) -> str:
            """Usage: Action: query_unlocked_lore: [title or keyword]"""
            path = os.path.join("saves", self.campaign_slug, "lore.json")
            if not os.path.exists(path):
                return "Error: lore.json not found."
            with open(path, "r", encoding="utf-8") as f:
                lore_data = json.load(f)
            
            results = []
            q_lower = query.lower()
            for entry in lore_data.get("unlocked_lore", []):
                if q_lower in entry.get("title", "").lower() or q_lower in entry.get("text", "").lower():
                    results.append(f"LORE - {entry.get('title')}: {entry.get('text')}")
            for secret in lore_data.get("secrets", []):
                if q_lower in secret.lower():
                    results.append(f"SECRET: {secret}")
            
            if results:
                return "\n".join(results)
            return f"No lore or secrets found matching '{query}'."

        def get_active_encounter(dummy: str) -> str:
            path = os.path.join("saves", self.campaign_slug, "encounters.json")
            if not os.path.exists(path):
                return "No encounter setup."
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ae = data.get("active_encounter")
            if not ae:
                return "No active encounter/fight is currently happening."
            return json.dumps(ae)

        def clear_active_encounter(dummy: str) -> str:
            path = os.path.join("saves", self.campaign_slug, "encounters.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["active_encounter"] = None
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            return "Active encounter cleared. Combat has ended."

        def roll_ability_check(args: str) -> str:
            """Format: 'tag_name | DC'. E.g. 'stealth | 12' or fallback 'stealth'"""
            if "|" in args:
                parts = args.split("|", 1)
                tag_name = parts[0].strip()
                try:
                    dc = int(parts[1].strip())
                except ValueError:
                    return "Error: DC must be an integer."
            else:
                tag_name = args.strip()
                dc = 12
                
            # Load character
            char_path = os.path.join("saves", self.campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char_data = json.load(f)
            char = Character.from_dict(char_data)
            
            # Load world to get environmental mods
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                world_data = json.load(f)
            world = WorldState.from_dict(world_data)
            
            # Check modifier
            mod = char.get_effective_modifier(tag_name, world.environmental_modifiers)
            res = roll_check(mod, dc)
            
            # If check succeeded, tick usage (learn-by-doing)
            prog_triggered = False
            new_mod = mod
            if res["success"]:
                prog_triggered, new_mod, leveled_tag = char.abilities.tick_usage(tag_name)
                if prog_triggered:
                    physical_tags = ["athletics", "combat", "fortitude", "stamina", "melee_weapons", "brawling", "evasion"]
                    if leveled_tag in physical_tags:
                        char.max_hp += 5
                        char.hp += 5
                        res["hp_growth"] = f"Physical ability '{leveled_tag}' leveled up! Max HP increased by 5."
                
            # Save character back
            with open(char_path, "w", encoding="utf-8") as f:
                json.dump(char.to_dict(), f, indent=4)
                
            res["progression_triggered"] = prog_triggered
            res["new_modifier"] = new_mod
            return json.dumps(res)

        def equip_item(item_name: str) -> str:
            """Usage: Action: equip_item: item_name"""
            char_path = os.path.join("saves", self.campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char = Character.from_dict(json.load(f))
            
            err = char.equip(item_name)
            if err:
                return f"Error: {err}"
                
            with open(char_path, "w", encoding="utf-8") as f:
                json.dump(char.to_dict(), f, indent=4)
                
            return f"Successfully equipped '{item_name}'."

        def heal_character(amount_str: str) -> str:
            """Usage: Action: heal_character: amount"""
            try:
                amount = int(amount_str.strip())
            except ValueError:
                return "Error: Amount must be an integer."
                
            char_path = os.path.join("saves", self.campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char = Character.from_dict(json.load(f))
                
            healed = char.heal(amount)
            
            with open(char_path, "w", encoding="utf-8") as f:
                json.dump(char.to_dict(), f, indent=4)
                
            return f"Healed character by {healed} HP. Current HP: {char.hp}/{char.max_hp}."

        def apply_combat_turn(args: str) -> str:
            """Format: 'target_index | action_tag_name' (e.g. '0 | melee_weapons')"""
            parts = args.split("|")
            if len(parts) < 2:
                return "Error: Format must be 'target_index | action_tag_name'"
            try:
                target_index = int(parts[0].strip())
            except ValueError:
                return "Error: target_index must be an integer."
            action_tag_name = parts[1].strip()
            char_path = os.path.join("saves", self.campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char = Character.from_dict(json.load(f))
                
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                world = WorldState.from_dict(json.load(f))
                
            enc_path = os.path.join("saves", self.campaign_slug, "encounters.json")
            with open(enc_path, "r", encoding="utf-8") as f:
                enc_data = json.load(f)
                
            ae = enc_data.get("active_encounter")
            if not ae or not ae.get("enemies"):
                return "Error: No active enemy to fight."
                
            from game_engine.combat import Enemy, resolve_combat_round
            enemies = [Enemy.from_dict(e_data) for e_data in ae["enemies"]]
            initiative_order = ae.get("initiative_order", [])
            
            # Resolve exchange
            res = resolve_combat_round(char, action_tag_name, target_index, enemies, initiative_order, world.environmental_modifiers)
            
            # Update objects and save
            ae["enemies"] = [e.to_dict() for e in enemies]
            if res.get("all_enemies_dead"):
                enc_data["active_encounter"] = None
                # Add loot if any exists in recent_loot to player inventory
                loot_received = []
                for item_dict in enc_data.get("recent_loot", []):
                    from game_engine.item_system import Item
                    item = Item.from_dict(item_dict)
                    char.add_item(item)
                    loot_received.append(item.name)
                enc_data["recent_loot"] = []
                res["loot_dropped"] = loot_received
            else:
                enc_data["active_encounter"] = ae
                
            with open(char_path, "w", encoding="utf-8") as f:
                json.dump(char.to_dict(), f, indent=4)
            with open(enc_path, "w", encoding="utf-8") as f:
                json.dump(enc_data, f, indent=4)
                
            return json.dumps(res)

        def trigger_world_keeper(query: str) -> str:
            if self.budget_mode:
                return self.world_keeper.heartbeat(budget_mode=True)
            return self.world_keeper.run(query, max_turns=3, verbose=False, agent_name="WorldKeeper")

        def trigger_faction_weaver(query: str) -> str:
            if self.budget_mode:
                return self.faction_weaver.heartbeat(budget_mode=True)
            return self.faction_weaver.run(query, max_turns=3, verbose=False, agent_name="FactionWeaver")

        def trigger_encounter_architect(query: str) -> str:
            # We always run EncounterArchitect as it sets up battles (crucial)
            return self.encounter_architect.run(query, max_turns=3, verbose=False, agent_name="EncounterArchitect")

        def trigger_lore_keeper(query: str) -> str:
            # Always run LoreKeeper as it handles quest rewards/codex unlocks
            return self.lore_keeper.run(query, max_turns=3, verbose=False, agent_name="LoreKeeper")

        def modify_inventory(args: str) -> str:
            """Format: 'add | Item Name | optional description | optional slot | optional consumable | optional charges' or 'remove | Item Name'
            Examples:
            - Action: modify_inventory: add | Steel Dagger | A sharp steel blade | weapon
            - Action: modify_inventory: add | Healing Salve | Heals minor burns | None | True | 2
            - Action: modify_inventory: remove | Backstory Trinket
            """
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 2:
                return "Error: Format must be 'add | Item Name | [desc] | [slot] | [consumable] | [charges]' or 'remove | Item Name'"
                
            op = parts[0].lower()
            item_name = parts[1]
            
            char_path = os.path.join("saves", self.campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char = Character.from_dict(json.load(f))
                
            if op == "add":
                desc = parts[2] if len(parts) > 2 else "A newly acquired item."
                slot = parts[3] if len(parts) > 3 and parts[3].lower() != "none" else None
                if slot and slot.lower() not in ["weapon", "armor", "accessory"]:
                    slot = None
                    
                consumable = False
                if len(parts) > 4:
                    consumable = parts[4].lower() in ["true", "yes", "1"]
                    
                charges = 0
                if len(parts) > 5:
                    try:
                        charges = int(parts[5])
                    except ValueError:
                        pass
                
                tag_mods = {}
                if consumable:
                    import re
                    match = re.search(r"heals?\s+(\d+)", desc.lower())
                    if match:
                        tag_mods["heal"] = int(match.group(1))
                    else:
                        tag_mods["heal"] = 8  # default healing amount
                        
                from game_engine.item_system import Item
                item = Item(name=item_name, description=desc, slot=slot, consumable=consumable, charges=charges, tag_modifiers=tag_mods)
                char.add_item(item)
                
                with open(char_path, "w", encoding="utf-8") as f:
                    json.dump(char.to_dict(), f, indent=4)
                return f"Successfully added '{item_name}' to inventory."
                
            elif op == "remove":
                success = char.remove_item(item_name)
                if success:
                    with open(char_path, "w", encoding="utf-8") as f:
                        json.dump(char.to_dict(), f, indent=4)
                    return "Removed item."
                return f"Error: '{item_name}' not found in inventory."
            else:
                return "Error: Operation must be 'add' or 'remove'."

        def modify_currency(args: str) -> str:
            try:
                amt = int(args.strip())
            except ValueError:
                return "Error: Amount must be an integer."
            char_path = os.path.join("saves", self.campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char = Character.from_dict(json.load(f))
            char.currency += amt
            if char.currency < 0: char.currency = 0
            with open(char_path, "w", encoding="utf-8") as f:
                json.dump(char.to_dict(), f, indent=4)
            return f"Added {amt} currency." if amt > 0 else f"Removed {abs(amt)} currency."

        def disassemble_item(item_name: str) -> str:
            """Usage: Action: disassemble_item: Rusty Blade"""
            char_path = os.path.join("saves", self.campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char = Character.from_dict(json.load(f))
                
            clean_name = item_name.strip().lower()
            target_item = None
            for item in char.inventory:
                if item.name.lower() == clean_name:
                    target_item = item
                    break
                    
            if not target_item:
                return f"Error: Item '{item_name}' not found in inventory."
                
            char.inventory.remove(target_item)
            
            yield_items = []
            name_lower = target_item.name.lower()
            desc_lower = target_item.description.lower()
            slot = target_item.slot.lower() if target_item.slot else ""
            
            from game_engine.item_system import Item
            if "electronic" in name_lower or "electronic" in desc_lower or "wire" in name_lower or "battery" in name_lower:
                yield_items.append(Item(name="Scrap Electronics", description="Various circuit boards and electrical components."))
                yield_items.append(Item(name="Copper Wire", description="Conductive copper wiring."))
            elif slot == "weapon" or "iron" in name_lower or "steel" in name_lower or "metal" in name_lower or "blade" in name_lower:
                yield_items.append(Item(name="Junk Metal", description="Bent metal shards and rusty plates."))
            elif slot == "armor" or "leather" in name_lower or "hide" in name_lower or "skin" in name_lower:
                yield_items.append(Item(name="Scrap Leather", description="Torn pieces of cured hide."))
            elif "cloth" in name_lower or "fabric" in name_lower or "robe" in name_lower or "cloak" in name_lower:
                yield_items.append(Item(name="Scrap Cloth", description="Tattered rags and fiber weave."))
            else:
                yield_items.append(Item(name="Junk Scrap", description="Miscellaneous unusable bits and pieces."))
                
            for item in yield_items:
                char.add_item(item)
                
            with open(char_path, "w", encoding="utf-8") as f:
                json.dump(char.to_dict(), f, indent=4)
                
            yield_names = [item.name for item in yield_items]
            return f"Disassembled '{target_item.name}' into: {', '.join(yield_names)}."

        def use_consumable_item(item_name: str) -> str:
            """Usage: Action: use_consumable_item: Healing Potion"""
            char_path = os.path.join("saves", self.campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char = Character.from_dict(json.load(f))
                
            clean_name = item_name.strip().lower()
            target_item = None
            for item in char.inventory:
                if item.name.lower() == clean_name:
                    target_item = item
                    break
                    
            if not target_item:
                return f"Error: Item '{item_name}' not found in inventory."
                
            if not target_item.consumable:
                return f"Error: Item '{target_item.name}' is not consumable."
                
            effect_msg = []
            heal_amt = target_item.tag_modifiers.get("heal") or target_item.tag_modifiers.get("hp")
            if heal_amt:
                world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
                with open(world_path, "r", encoding="utf-8") as f:
                    world_data = json.load(f)
                in_camp = world_data.get("is_camping", False)
                
                if not in_camp:
                    heal_amt = max(1, heal_amt // 2)
                    
                healed = char.heal(heal_amt)
                msg = f"Healed {healed} HP"
                if not in_camp:
                    msg += " (Reduced effectiveness outside of camp)"
                effect_msg.append(msg)
                
            other_mods = {k: v for k, v in target_item.tag_modifiers.items() if k not in ["heal", "hp"]}
            if other_mods:
                effect_name = f"Consumable: {target_item.name}"
                char.status_effects.append({
                    "name": effect_name,
                    "modifiers": other_mods,
                    "duration": 3
                })
                effect_msg.append(f"Applied status effect '{effect_name}' ({other_mods}) for 3 turns")
                
            if target_item.charges > 1:
                target_item.charges -= 1
                effect_msg.append(f"Used 1 charge. {target_item.charges} charges remaining.")
            else:
                char.inventory.remove(target_item)
                effect_msg.append("Item consumed and removed from inventory.")
                
            with open(char_path, "w", encoding="utf-8") as f:
                json.dump(char.to_dict(), f, indent=4)
                
            return f"Successfully used '{target_item.name}': " + ", ".join(effect_msg)

        def get_faction_details(dummy: str) -> str:
            """Usage: Action: get_faction_details"""
            path = os.path.join("saves", self.campaign_slug, "factions.json")
            if not os.path.exists(path):
                return "No factions or NPC records found."
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        def modify_relationship(args: str) -> str:
            """Format: 'add | Name | Description' or 'remove | Name'
            Usage: Action: modify_relationship: add | Aria | Love Interest - tech scavenger
            """
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 2:
                return "Error: Format must be 'add | Name | Description' or 'remove | Name'"
                
            op = parts[0].lower()
            name = parts[1]
            
            char_path = os.path.join("saves", self.campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char = Character.from_dict(json.load(f))
                
            if op == "add":
                desc = parts[2] if len(parts) > 2 else "Acquaintance"
                char.relationships[name] = desc
                with open(char_path, "w", encoding="utf-8") as f:
                    json.dump(char.to_dict(), f, indent=4)
                return f"Successfully added/updated relationship for '{name}'."
            elif op == "remove":
                if name in char.relationships:
                    del char.relationships[name]
                    with open(char_path, "w", encoding="utf-8") as f:
                        json.dump(char.to_dict(), f, indent=4)
                    return f"Successfully removed relationship for '{name}'."
                else:
                    return f"Error: No relationship found for '{name}'."
            else:
                return "Error: Operation must be 'add' or 'remove'."

        def modify_location(args: str) -> str:
            """Format: 'add | Name | Type | Description' or 'update | Name | Description'
            Types: 'city', 'natural wonder', 'point of interest', 'dungeon', etc.
            Example: Action: modify_location: add | Obsidian Spire | natural wonder | A massive towering peak of obsidian magma rock.
            """
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 2:
                return "Error: Format must be 'add | Name | Type | Description' or 'update | Name | Description'"
                
            op = parts[0].lower()
            name = parts[1]
            
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                world = WorldState.from_dict(json.load(f))
                
            if op == "add":
                loc_type = parts[2] if len(parts) > 2 else "point of interest"
                desc = parts[3] if len(parts) > 3 else "A newly discovered point of interest."
                
                # Check if already exists, if so update it
                exists = False
                for loc in world.discovered_locations:
                    if loc.name.lower() == name.lower():
                        loc.description = desc
                        loc.type = loc_type
                        exists = True
                        break
                if not exists:
                    from game_engine.world import Location
                    loc = Location(name=name, type=loc_type, description=desc, discovered_turn=world.turn_count)
                    world.discovered_locations.append(loc)
                    
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Successfully registered discovered location '{name}'."
                
            elif op == "update":
                desc = parts[2] if len(parts) > 2 else ""
                for loc in world.discovered_locations:
                    if loc.name.lower() == name.lower():
                        loc.description = desc
                        with open(world_path, "w", encoding="utf-8") as f:
                            json.dump(world.to_dict(), f, indent=4)
                        return f"Successfully updated location '{name}'."
                return f"Error: Location '{name}' not found."
            else:
                return "Error: Operation must be 'add' or 'update'."

        def add_location_rumor(args: str) -> str:
            """Format: 'Location Name | Rumor text'
            Example: Action: add_location_rumor: Cinder Spire | The fire elementals are restless.
            """
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 2:
                return "Error: Format must be 'Location Name | Rumor text'"
            loc_name, rumor = parts[0], parts[1]
            
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                world = WorldState.from_dict(json.load(f))
                
            for loc in world.discovered_locations:
                if loc.name.lower() == loc_name.lower():
                    loc.rumors.append(rumor)
                    with open(world_path, "w", encoding="utf-8") as f:
                        json.dump(world.to_dict(), f, indent=4)
                    return f"Added rumor to '{loc.name}'."
            return f"Error: Location '{loc_name}' not found."

        def resolve_location_rumor(args: str) -> str:
            """Format: 'Location Name | Rumor text | escalated(true/false)'
            Example: Action: resolve_location_rumor: Cinder Spire | The fire elementals are restless | true
            """
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 2:
                return "Error: Format must be 'Location Name | Rumor text | true/false'"
            loc_name, rumor = parts[0], parts[1]
            escalated = False
            if len(parts) > 2:
                escalated = parts[2].lower() in ["true", "yes", "1"]
            
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                world = WorldState.from_dict(json.load(f))
                
            for loc in world.discovered_locations:
                if loc.name.lower() == loc_name.lower():
                    if rumor in loc.rumors:
                        loc.rumors.remove(rumor)
                        if escalated:
                            world.escalated_rumors.append(rumor)
                        with open(world_path, "w", encoding="utf-8") as f:
                            json.dump(world.to_dict(), f, indent=4)
                        if escalated:
                            return f"Escalated rumor from '{loc.name}'. The Lore Keeper will process it."
                        return f"Resolved/removed rumor from '{loc.name}'."
                    return f"Error: Rumor not found in '{loc.name}'."
            return f"Error: Location '{loc_name}' not found."

        def advance_time(turns_str: str) -> str:
            """Format: 'number_of_turns'. Example: Action: advance_time: 3"""
            try:
                turns = int(turns_str.strip())
            except ValueError:
                return "Error: Turns must be an integer."
                
            if turns <= 0:
                return "Error: Turns must be positive."
                
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                world = WorldState.from_dict(json.load(f))
                
            logs = []
            for _ in range(turns):
                world.increment_turn()
                world.advance_time()
                
                # Check heartbeat
                if world.turn_count >= world.next_heartbeat_turn:
                    world.next_heartbeat_turn = world.turn_count + random.randint(5, 10)
                    wk_res = self.world_keeper.heartbeat(budget_mode=self.budget_mode)
                    fw_res = self.faction_weaver.heartbeat(budget_mode=self.budget_mode)
                    lk_res = self.lore_keeper.heartbeat(budget_mode=self.budget_mode)
                    logs.append(f"Heartbeat at turn {world.turn_count}")
                    
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
                
            msg = f"Advanced time by {turns} turns. It is now {world.time_of_day} on turn {world.turn_count}."
            if logs:
                msg += f" {len(logs)} background heartbeats occurred."
            return msg

        def write_log_entry(text: str) -> str:
            # Log compaction uses llm_client
            return write_dm_log(self.campaign_slug, text, self.llm_client)

        def modify_world_aspect(args: str) -> str:
            """Format: 'add | Name | Type | Description | [intensity]' or 'remove | Name'.
            Types: Nemesis, Doom Clock, Heat, Trauma, Rule."""
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 2:
                return "Error: Format must be 'add | Name | Type | Desc | [intensity]' or 'remove | Name'."
            op = parts[0].lower()
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                world = WorldState.from_dict(json.load(f))
            if op == "add":
                if len(parts) < 4:
                    return "Error: add requires Name | Type | Description."
                name, a_type, desc = parts[1], parts[2], parts[3]
                intensity = int(parts[4]) if len(parts) > 4 else 1
                world.add_aspect(name, a_type, desc, intensity)
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Added/updated World Aspect '{name}' (Type: {a_type}, Intensity: {intensity})."
            elif op == "remove":
                success = world.remove_aspect(parts[1])
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Removed World Aspect '{parts[1]}'." if success else f"Error: Aspect '{parts[1]}' not found."
            return "Error: Operation must be 'add' or 'remove'."

        def add_quest_note(args: str) -> str:
            """Format: 'Quest Name | Note text'. Appends a contextual note to an active quest."""
            if "|" not in args:
                return "Error: Format must be 'Quest Name | Note text'."
            quest_name, note = args.split("|", 1)
            quest_name, note = quest_name.strip(), note.strip()
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                world = WorldState.from_dict(json.load(f))
            for q in world.active_quests:
                if q.name.lower() == quest_name.lower():
                    world.add_quest_note(q.id, note)
                    with open(world_path, "w", encoding="utf-8") as f:
                        json.dump(world.to_dict(), f, indent=4)
                    return f"Added note to quest '{q.name}'."
            return f"Error: Quest '{quest_name}' not found."

        def set_override_state(args: str) -> str:
            """Locks the game into a Situational Override state so it persists across turns.
            Format: 'state | description'.
            States: 'survival', 'social', 'stealth', 'investigation', 'travel', 'camping'.
            Use 'clear' to end a state: 'clear | stealth' or 'clear | all'.
            Examples:
              Action: set_override_state: survival | Falling from the bridge with no handhold
              Action: set_override_state: social | Interrogation by Captain Voss — she suspects the player
              Action: set_override_state: stealth | Sneaking through the Corporate Data-Vault
              Action: set_override_state: investigation | Hacking the mainframe terminal
              Action: set_override_state: travel | 3-day journey across the Blasted Wastes to reach the Capital
              Action: set_override_state: camping | Player's campfire in the Blighted Woods
              Action: set_override_state: clear | social
            """
            if "|" not in args:
                return "Error: Format must be 'state | description' or 'clear | state'."
            state, desc = args.split("|", 1)
            state, desc = state.strip().lower(), desc.strip()
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                world = WorldState.from_dict(json.load(f))
            if state == "clear":
                target = desc.lower()
                if target in ("survival", "all"): world.survival_situation = ""
                if target in ("social", "all"): world.social_encounter = ""
                if target in ("stealth", "all"): world.stealth_mission = ""
                if target in ("investigation", "all"): world.investigation_focus = ""
                if target in ("travel", "all"): world.travel_journey = ""
                if target in ("camping", "all"): world.is_camping = False
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Cleared override state: '{target}'."
            elif state == "survival":
                world.survival_situation = desc
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Survival Override activated: '{desc}'."
            elif state == "social":
                world.social_encounter = desc
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Social Override activated: '{desc}'."
            elif state == "stealth":
                world.stealth_mission = desc
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Stealth Override activated: '{desc}'."
            elif state == "investigation":
                world.investigation_focus = desc
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Investigation Override activated: '{desc}'."
            elif state == "travel":
                world.travel_journey = desc
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Travel Override activated: '{desc}'."
            elif state == "camping":
                world.is_camping = True
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Camping Override activated: '{desc}'."
            return "Error: State must be 'survival', 'social', 'stealth', 'investigation', 'travel', 'camping', or 'clear'."

        def register_and_move_location(args: str) -> str:
            """Moves the player to a local area within the current town. Creates the location if it doesn't exist.
            Format: 'Name | Description | Type'.
            Usage: Action: register_and_move_location: Hemlock's Store | A dusty general store run by an old man | shop
            """
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 3:
                return "Error: Format must be 'Name | Description | Type'."
            
            loc_name = parts[0]
            loc_desc = parts[1]
            loc_type = parts[2]
            
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            with open(world_path, "r", encoding="utf-8") as f:
                world = WorldState.from_dict(json.load(f))
            
            # --- DEDUP CHECK ---
            # If a location with the same name (case-insensitive) already exists,
            # just move the player there instead of creating a duplicate node.
            existing = None
            for loc in world.discovered_locations:
                if loc.name.lower() == loc_name.lower():
                    existing = loc
                    break
            
            if existing:
                world.current_location_id = existing.id
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                return f"Moved player to existing location: '{existing.name}'."
            
            # --- CREATE NEW NODE ---
            import uuid
            from game_engine.world import Location
            
            old_location_id = world.current_location_id
            
            new_loc = Location(
                id=str(uuid.uuid4()),
                name=loc_name,
                description=loc_desc,
                type=loc_type,
                discovered_turn=world.turn_count,
                theme="default"
            )
            
            # Wire bidirectional connections to the previous location
            new_loc.connections.append(old_location_id)
            for loc in world.discovered_locations:
                if loc.id == old_location_id:
                    loc.connections.append(new_loc.id)
                    break
            
            world.discovered_locations.append(new_loc)
            world.current_location_id = new_loc.id
            
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            
            return f"Successfully moved player to new location: '{loc_name}'."

        def query_cast(dummy: str) -> str:
            """Returns the full cast of important NPCs (Spine Characters and Promoted NPCs).
            Usage: Action: query_cast"""
            cast_path = os.path.join("saves", self.campaign_slug, "cast.json")
            if not os.path.exists(cast_path):
                return "No cast file found."
            with open(cast_path, "r", encoding="utf-8") as f:
                return f.read()

        return {
            "register_and_move_location": register_and_move_location,
            "query_cast": query_cast,
            "query_world_bible": query_world_bible,
            "query_unlocked_lore": query_unlocked_lore,
            "get_active_encounter": get_active_encounter,
            "clear_active_encounter": clear_active_encounter,
            "roll_ability_check": roll_ability_check,
            "equip_item": equip_item,
            "heal_character": heal_character,
            "apply_combat_turn": apply_combat_turn,
            "trigger_world_keeper": trigger_world_keeper,
            "trigger_faction_weaver": trigger_faction_weaver,
            "trigger_encounter_architect": trigger_encounter_architect,
            "trigger_lore_keeper": trigger_lore_keeper,
            "modify_inventory": modify_inventory,
            "modify_currency": modify_currency,
            "disassemble_item": disassemble_item,
            "use_consumable_item": use_consumable_item,
            "get_faction_details": get_faction_details,
            "modify_relationship": modify_relationship,
            "modify_location": modify_location,
            "add_location_rumor": add_location_rumor,
            "resolve_location_rumor": resolve_location_rumor,
            "advance_time": advance_time,
            "write_log_entry": write_log_entry,
            "modify_world_aspect": modify_world_aspect,
            "add_quest_note": add_quest_note,
            "set_override_state": set_override_state,
            "query_world_bible": query_world_bible,
            "query_unlocked_lore": query_unlocked_lore
        }

    def _build_dynamic_prompt(self) -> str:
        # Load world state
        world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
        with open(world_path, "r", encoding="utf-8") as f:
            world_data = json.load(f)
        world = WorldState.from_dict(world_data)
        
        genre = world.setting_genre
        traits = ", ".join(world.dm_traits)
        
        if self.verbose:
            presentation_rule = 'IMPORTANT PRESENTATION RULE: To assist the player, you MUST explicitly prepend an asterisk (*) to any option that progresses a quest or moves the main story forward. Do NOT add asterisks or any special tags to casual flavor options. For example: "2. * Confront the Smuggler." vs "1. Browse the local merchant\'s wares." End with a note that they can describe their own action. You MUST randomize the order of the 3-4 options so that the story-progressing choice is not always option #1.'
        else:
            presentation_rule = 'IMPORTANT PRESENTATION RULE: Do NOT use meta-labels, tags, or asterisks for ANY of the options. Keep them completely immersive and natural. End with a note that they can describe their own action. You MUST randomize the order of the 3-4 options so that the story-progressing choice is not always option #1.'
        
        # Determine active override
        enc_path = os.path.join("saves", self.campaign_slug, "encounters.json")
        is_combat = False
        if os.path.exists(enc_path):
            try:
                with open(enc_path, "r", encoding="utf-8") as f:
                    enc_data = json.load(f)
                ae = enc_data.get("active_encounter")
                if ae and ae.get("enemies"):
                    for e in ae["enemies"]:
                        if e.get("hp", 0) > 0:
                            is_combat = True
                            break
            except Exception:
                pass

        override_rules = ""
        if is_combat:
            override_rules = "   - COMBAT OVERRIDE: If in active combat, ALL choices must be tactical combat maneuvers, attacks, spells, or fleeing. You MUST dedicate at least one option to actively utilizing the specific 'Current Location' environment (e.g., throwing a tavern chair, pushing an enemy into a hazard, or taking cover behind market stalls). If the player has any physical/combat Ability Tag at +3 or higher, you MUST dedicate one option to a 'Special Maneuver' (e.g., Cleave, Double Attack, Precision Shot) reflecting their high-tier skill. You MUST diegetically describe the danger of the enemy based on their Threat Level (e.g. Threat 1-2 is weak, Threat 3-4 is dangerous, Threat 5+ is terrifyingly powerful). Combat is locked mechanically via encounters.json — you do not need to manually set it."
        elif world.survival_situation:
            override_rules = "   - SURVIVAL OVERRIDE: If in immediate, life-threatening danger (e.g., drowning, falling, trapped in a fire), you MUST call 'set_override_state: survival | [description of threat]' to lock this mode, and ALL choices must focus on desperately escaping/surviving. When the threat is resolved, call 'set_override_state: clear | survival'."
        elif world.stealth_mission:
            override_rules = "   - STEALTH OVERRIDE: If the player enters a hostile area but combat hasn't started (e.g., sneaking through a compound), you MUST call 'set_override_state: stealth | [target location or enemy]' to lock this mode. ALL choices must be restricted to quiet movement, observing patrols, finding cover, or silent takedowns. When the player gets caught (combat starts) or escapes, call 'set_override_state: clear | stealth'."
        elif world.social_encounter:
            override_rules = "   - SOCIAL OVERRIDE: If the player enters an intense, locked conversation or negotiation (interrogation, tense standoff, seduction, diplomacy), you MUST call 'set_override_state: social | [who + the stakes]' to lock this mode, and ALL choices must be dialogue options or social actions. When the conversation resolves, call 'set_override_state: clear | social'."
        elif world.investigation_focus:
            override_rules = "   - INVESTIGATION OVERRIDE: If the player is solving a specific puzzle, hacking a terminal, or examining a crime scene, you MUST call 'set_override_state: investigation | [puzzle description]' to lock this mode. ALL choices must be focused intellectual actions (scanning, deducing, bypassing, examining). When the puzzle is solved or abandoned, call 'set_override_state: clear | investigation'."
        elif world.travel_journey:
            override_rules = "   - TRAVEL OVERRIDE: If the player initiates a long journey to a new major location via the node map, you MUST call 'set_override_state: travel | [journey description]' to lock this mode. ALL choices must focus on navigating the road (foraging, resting, dealing with weather/bandits/hazards). Use 'trigger_world_keeper' to advance time, which naturally depletes Hunger/Fatigue over the trip. When they arrive at the destination, call 'set_override_state: clear | travel'."
        elif world.is_camping:
            override_rules = "   - CAMPING OVERRIDE: If the player sets up camp or rests, you MUST call 'set_override_state: camping | [camp description]' to lock this mode. ALL choices must be camp activities (eating, tending wounds, crafting, sleeping, bonding). The 'Hunger' and 'Fatigue' fields in Context are the ground truth for bodily needs — use 'trigger_world_keeper' with 'set_bodily_needs' to update them when the player eats or sleeps. IMPORTANT RECOVERY RULE: Sleeping resets Fatigue to 0 but INCREASES Hunger by 1 (call 'set_bodily_needs' to apply this). Sleeping also passively heals a small amount of HP (e.g., +5 HP using 'heal_character'). To fully heal or cure Hunger, the player MUST consume medical supplies or rations using 'use_consumable_item'. When the player breaks camp, call 'set_override_state: clear | camping'."
        else:
            override_rules = (
                "   - DEFAULT EXPLORATION: Weave the DIRECTOR'S BRIEF naturally into the scene. "
                "At least ONE of your 3-4 options should relate to the main quest or Director's Brief, "
                "but it should feel like an organic discovery — not a forced redirect. "
                "The other options should reflect what the player is currently doing and the environment they're in. "
                "If the player is clearly pursuing their own goal (shopping, socializing, exploring), "
                "RESPECT their agency and let them finish before nudging them toward the main story thread. "
                "You MUST make quest-related options insightful by weaving in player inventory, "
                "Unlocked Lore, and Secrets as contextual advantages. "
                "You may also dedicate one option to exploring a nearby sub-location or point of interest. "
                "Rarely (10% of the time), include a High Risk / High Reward option. "
                "Remaining non-quest options MUST be highly thematic to the 'Current Location' Type "
                "but kept as low-stakes background flavor so they are not overwhelming. "
                "Do NOT offer high-stakes thematic events (like deadly traps or gang ambushes) every turn; keep them rare. "
                "You MUST randomize the order of the 3-4 options so that the story-progressing choice is not always option #1."
            )

        if not is_combat and not override_rules.startswith("   - DEFAULT EXPLORATION"):
            override_rules += "\n   *BREAKOUT OPTIONS & CUSTOM ACTIONS:*\n   For Stealth, Social, Investigation, Travel, and Camping overrides ONLY, you MUST usually dedicate one option to logically abandoning the task or breaking out of the mode (e.g., \"Abandon the hack and step away from the terminal\", \"Insult the Captain and draw your weapon\", \"Turn back from the road\"). If a player selects this option, or if they type a Custom Action that intentionally ignores the override context to do something drastically different (e.g., pulling a gun mid-negotiation), you must evaluate if the breakout makes narrative sense. If it does, naturally transition the scene, call 'set_override_state: clear | [state]', and trigger the appropriate tools (like 'trigger_encounter_architect' for sudden violence)."

        return f"""You are the Dungeon Master (DM) for a text-based RPG set in the genre '{genre}'.
Your DM personality traits are: {traits}. Maintain this narrative voice and styling at all times!

Your task is to respond to the player's action. You run in a ReAct loop.
If you need to call a tool, you MUST output a single 'Thought:' line, followed by a single 'Action:' line, and then the word 'PAUSE' on a new line. You must stop generating immediately after 'PAUSE'.
Once you receive the tool's 'Observation:', you can decide whether to run another tool or provide your final narrative response.
When you are ready to give your final narrative response to the player, output 'Thought:' followed by 'Answer:' containing your narration and player choices.

Example tool use:
Thought: I need to check the character's sheet to see their items.
Action: get_character_sheet
PAUSE

Example final response:
Thought: I have the information needed. I will describe the dark corridor and give choices.
Answer: You stand in a dark, cold stone corridor...
What do you do?
1. Search the floor.
2. Listen at the door.

Follow these strict DM instructions:
1. ALWAYS begin each response with the prefix 'Thought:' followed by your tactical plans.
2. NEVER reveal raw numbers, stats, DC values, HP, or rolls in your final Answer. Narrate them flavorfully instead. WOUND STATE RULE: You MUST persistently weave the player's physical condition into your narrative responses (both in combat and exploration) based on their current HP. If HP drops below 75%, describe them as bruised, winded, or scraped. If HP drops below 50%, describe them as bleeding, panting, or limping. If HP drops below 25%, describe them as critically wounded and struggling to survive. This is purely flavor to warn the player; do not impose secret mechanical penalties on their rolls because of low HP.
3. You have NARRATIVE AUTHORITY: if a dice roll fails by a small margin but success makes the story much more exciting or fun, you can fudge the narrative.
4. Option Generation: You MUST end every narration by offering exactly 3-4 actionable choices for the player in a numbered list (1, 2, 3, etc.). You must strictly follow these Situational Overrides based on the CURRENT CONTEXT:
{override_rules}
   
   {presentation_rule}
5. Factual Adherence & Lore Accuracy: Do NOT invent observations or contradictory lore. Use 'query_world_bible' and 'query_unlocked_lore' for history, mythos, and secrets. Always call tools if you need to know stats, roll checks, or subagent states.
6. ALWAYS write a log entry summarizing the outcome via the 'write_log_entry' tool. You MUST wait for the 'Observation:' before outputting your 'Answer:'. NEVER output 'Action:' and 'Answer:' in the same response!
7. Combat Escalation & Execution: If a situation turns hostile (e.g., the player fails a stealth check, threatens an armed NPC, or is ambushed), you MUST instantly use 'trigger_encounter_architect' to formally start the combat engine. IMPORTANT AMBUSH RULE: When the encounter starts, check the Threat Level and Enemy Count in the Context block. If any enemy is Threat Level 5+ OR if there are 3+ enemies, you MUST NOT instantly attack. Instead, narrate the overwhelming, impending danger (a tense standoff) and offer the player a chance to retreat, hide, or prepare tactically. Only low-threat enemies (Threat 1-3) are allowed to freely ambush the player and throw the first punch. While an Active Encounter exists, you MUST use 'apply_combat_turn' on every single turn to execute the rounds mechanically.
   - LOOT: If `apply_combat_turn` returns `enemy_dead: true` and `loot_dropped`, you MUST explicitly narrate the player finding and looting those items in your Answer!
8. Crafting is Freeform but Risky: If the player attempts to MacGyver or invent a custom item, verify they have logical materials in their inventory. You MUST call 'roll_ability_check' (e.g., logic, crafting, tinkering) to determine if they succeed.
   - If successful: Remove the materials and add the custom item with appropriate mechanical stats using 'modify_inventory'.
   - If failed: Narrate a creative consequence (e.g., destroying the materials, taking physical damage from a backfire, or alerting enemies). 
   - Anti-Softlock: If the player fails to craft an item that was strictly required to progress their Active Quest, you MUST subtly weave an alternative solution or path into the environment so they are not permanently stuck.
9. Player Validity & Spatial Limits: Cross-reference all player claims against the Context block (Inventory, Skills). The player can ONLY interact with entities and structures present in their 'Current Location'. If they attempt to use an item they don't have, attempt a feat requiring a skill they don't possess, or interact with something located elsewhere, narrate their mechanical failure and refuse the action.
10. Contested Resolution: If a player attempts any difficult, risky, or contested action, you MUST call 'roll_ability_check' using the most relevant ability tag. Never let the player narrate their own guaranteed success.
11. Story Progression, Pacing & Scene Transitions: Always weave 'Local Rumors' or 'Active Quests' into exploration. SCENE TRANSITION RULE: If the player decides to move to a new location within the current town/area (e.g. "I head to the general store" or "I walk to the inn"), you MUST instantly transition the scene to their arrival at that new destination. Do NOT drag out the walk or have NPCs stall them with conversational filler unless there is a scripted ambush. CRITICAL: You MUST call 'register_and_move_location' to mechanically move the player to the new location. If you only narrate the move without calling this tool, the player will rubber-band back to their previous location on the next turn because the engine's map was never updated! Furthermore, when a player succeeds at a quest, weave a diegetic confirmation AND narrate a significant leap forward in the story to avoid boring point-and-click loops. IMPORTANT: If a quest requires turning in an item, you MUST use 'modify_inventory' to remove it, and explicitly instruct 'trigger_lore_keeper' to mark it finished.
12. Travel Enforcement: The game now uses a strict Node-Graph for travel. The player MUST use the system [Travel] menu to move between locations. If they attempt to "travel to the capital" or walk to a new city via a custom text action, explicitly refuse the action and tell them they must use the [Travel] menu to navigate the map.
13. World Mechanics (Time & Aspects): Actively enforce 'Active World Aspects' (Nemesis, Heat, Trauma) to impose narrative complications. If the player attempts a long activity (sleeping, crafting, stakeouts), use the 'advance_time' tool to push the world clock forward 2-4 turns.
14. Character Continuity: When Spine Characters or Promoted NPCs appear in a scene, you MUST use 'query_cast' to get their personality, hidden agenda, and current status. Write their dialogue and behavior consistent with their personality. Subtly foreshadow upcoming story beats through NPC behavior without being heavy-handed (e.g., if The Catalyst has a hidden agenda, show small inconsistencies in their behavior that a perceptive player might notice).

Available Tools:
[Core]
- roll_ability_check: Performs a d20 roll check. Format: 'tag_name | DC'. Usage: Action: roll_ability_check: stealth | 12
- write_log_entry: Writes a narrative log entry for the player. ALWAYS call this right before 'Answer'. Usage: Action: write_log_entry: The player discovered the datapad.
- heal_character: Restores the character's HP. Usage: Action: heal_character: 10
- modify_inventory: Adds or removes items. For the description, write a narrative description that implies what the item does without raw numbers (e.g., 'A thick coat' not 'Defense 1'). Format: 'add | Name | [desc] | [slot] | [consumable] | [charges]' or 'remove | Name'. Usage: Action: modify_inventory: add | Healing Salve | A soothing paste that closes wounds | None | True | 2
- use_consumable_item: Uses a consumable item (e.g. healing items or temporary stat boosts). Usage: Action: use_consumable_item: healing salve
- modify_currency: Adds or removes world currency. Format: 'amount'. Usage: Action: modify_currency: 50
- equip_item: Equips an item from the character inventory. Usage: Action: equip_item: sword

[Combat]
- get_active_encounter: Returns active combat details if any. Usage: Action: get_active_encounter
- clear_active_encounter: Clears the current combat encounter (e.g., if the player successfully flees). Usage: Action: clear_active_encounter
- trigger_encounter_architect: Queries EncounterArchitect. You MUST include the Current Location and the relevant Active Quest in your query so the encounter is heavily tied to the plot rather than just random filler. Usage: Action: trigger_encounter_architect: spawn an enemy in the Ruins holding the datapad for the smuggler quest
- apply_combat_turn: Resolves a combat round. Format: 'target_index | tag_name'. Usage: Action: apply_combat_turn: 0 | lasers

[World]
- trigger_world_keeper: Queries WorldKeeper subagent. Usage: Action: trigger_world_keeper: storm coming
- trigger_faction_weaver: Queries FactionWeaver subagent. Usage: Action: trigger_faction_weaver: player attacked gang
- trigger_lore_keeper: Queries LoreKeeper. Use this to explicitly instruct the LoreKeeper to update/complete active quests, unlock lore, or plant secrets. Usage: Action: trigger_lore_keeper: complete the 'Smuggler's Run' quest because the player delivered the datapad.
- advance_time: Pushes the world clock forward by X turns, triggering background faction/lore heartbeats. Format: 'turns'. Usage: Action: advance_time: 3

[Narrative]
- modify_relationship: Adds or removes long-term relationships (love interest, rival, friend). Format: 'add | Name | Desc' or 'remove | Name'. Usage: Action: modify_relationship: add | Sarah | Love Interest - Rebel courier
- modify_location: Adds or updates a discovered city, landmark, ruins, wonder, or POI. Format: 'add | Name | Type | Desc' or 'update | Name | Desc'. Usage: Action: modify_location: add | Cinder Spire | natural wonder | Burning glass pillar.
- register_and_move_location: Moves the player to a local area within the current town (e.g. a shop, alley, or temple). If the location already exists on the map, moves the player there. If it doesn't exist, creates it and connects it to the current location. Format: 'Name | Description | Type'. Usage: Action: register_and_move_location: Hemlock's Store | A dusty general store run by an old man | shop
- add_location_rumor: Adds a localized hook/rumor to a location. Format: 'Location Name | Rumor'. Usage: Action: add_location_rumor: The Spire | Barkeep is acting suspicious.
- resolve_location_rumor: Removes a rumor from a location once handled. If escalated is true, the rumor is sent to the Lore Keeper to become a main story quest. Format: 'Location Name | Rumor | true/false'. Usage: Action: resolve_location_rumor: The Spire | Barkeep is suspicious | true
- modify_world_aspect: Modifies world aspects. Format: 'add | name | type | desc | [intensity]' or 'remove | name'. Usage: Action: modify_world_aspect: add | High Heat | Trauma | Guard patrols everywhere | 2
- add_quest_note: Appends a contextual discovery note to an active quest (e.g. a found passcard, a heard rumor). Format: 'Quest Name | Note'. Usage: Action: add_quest_note: The Lost Shipment | Found a partial manifest in the smuggler's coat.
- set_override_state: Applies or clears a narrative lock. Format: 'state | desc' or 'clear | state'. Valid states: survival, social, stealth, investigation, travel, camping. Usage: Action: set_override_state: stealth | The Corporate compound
- disassemble_item: Breaks down an item in inventory into raw salvage components. You can invent narrative names for the resulting salvage based on the item (e.g. "Rusty Cog", "Tattered Wire", "Scrap Electronics"). Usage: Action: disassemble_item: rusty metal plate

[Query]
- query_cast: Returns the full cast of important NPCs (personality, agenda, status). Usage: Action: query_cast
- query_world_bible: Returns the full World Bible document (history, mythos, culture). Usage: Action: query_world_bible
- query_unlocked_lore: Searches the full text of all Unlocked Lore and Secrets based on a keyword or title. Usage: Action: query_unlocked_lore: Old Empire
- get_faction_details: Returns active factions and NPC databases. Usage: Action: get_faction_details
"""

    def process_turn(self, player_action: str) -> str:
        """Processes a player's action turn. Coordinates heartbeats and subagents."""
        # 1. Update turn count
        world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
        with open(world_path, "r", encoding="utf-8") as f:
            world_data = json.load(f)
        world = WorldState.from_dict(world_data)
        world.increment_turn()

        # --- TRACK RECENT PLAYER ACTIONS ---
        world.recent_player_actions.append(player_action[:150])  # Cap length
        if len(world.recent_player_actions) > 5:
            world.recent_player_actions.pop(0)
        
        # 2. Check for Heartbeat cycle
        # We store the next heartbeat target turn in world_state.json if not present
        heartbeat_target = world.next_heartbeat_turn
        if not heartbeat_target:
            heartbeat_target = world.turn_count + random.randint(5, 10)
            world.next_heartbeat_turn = heartbeat_target
            
        heartbeat_occurred = False
        heartbeat_log = ""
        critic_assessment = None
        # Run heartbeats if turn count reaches target, OR on turn 1 only for initial setup
        # to dynamically align opening story beats with player actions.
        if world.turn_count >= heartbeat_target or world.turn_count == 1:
            heartbeat_occurred = True
            if world.turn_count >= heartbeat_target:
                # Roll next target
                heartbeat_target = world.turn_count + random.randint(5, 10)
                world.next_heartbeat_turn = heartbeat_target
            
            # --- STEP 1: RUN STORY CRITIC FIRST ---
            critic_assessment = self.story_critic.evaluate(player_action)
            
            # Update beat-stall tracking
            active_beat = world.story_spine.get_active_beat() if world.story_spine else None
            current_beat_id = active_beat.id if active_beat else -1
            if current_beat_id == world.last_beat_id:
                world.turns_on_current_beat += 1
            else:
                world.turns_on_current_beat = 0
                world.last_beat_id = current_beat_id
            
            # Decrement pressure cooldown
            if world.pressure_cooldown > 0:
                world.pressure_cooldown -= 1
            
            # Apply cooldown if Critic escalated
            if critic_assessment["directive"] == "gentle_pull":
                world.pressure_cooldown = 3
            elif critic_assessment["directive"] == "force_event":
                world.pressure_cooldown = 5
            
            # --- STEP 2: FIRE SUBAGENT HEARTBEATS ---
            # Save world state first so the Critic's tracking data is available to subagents
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            
            wk_res = self.world_keeper.heartbeat(budget_mode=self.budget_mode)
            fw_res = self.faction_weaver.heartbeat(budget_mode=self.budget_mode)
            # Pass critic assessment to LoreKeeper so it doesn't conflict
            lk_res = self.lore_keeper.heartbeat(
                budget_mode=self.budget_mode, 
                critic_assessment=critic_assessment
            )
            heartbeat_log = f"\n[Heartbeat Event: {wk_res} {fw_res} {lk_res}]"
            
        # Write back world state
        with open(world_path, "w", encoding="utf-8") as f:
            json.dump(world.to_dict(), f, indent=4)
            
        # 3. Formulate query for DM ReAct loop
        self.system_instruction = self._build_dynamic_prompt()
        
        # Load character sheet to populate context snapshot
        char_path = os.path.join("saves", self.campaign_slug, "character.json")
        with open(char_path, "r", encoding="utf-8") as f:
            char_data = json.load(f)
        char = Character.from_dict(char_data)
        
        # Load turn history for narrative continuity
        history_path = os.path.join("saves", self.campaign_slug, "turn_history.json")
        turn_history_str = "None"
        if os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
                if history:
                    entries = [f"Turn {h['turn']}: Player: {h['player_action']} -> {h['dm_summary']}" for h in history]
                    turn_history_str = " | ".join(entries)
            except Exception:
                pass
        
        hp_pct = (char.hp / char.max_hp) * 100
        cond = "Healthy" if hp_pct >= 80 else "Wounded" if hp_pct >= 40 else "Near Death"
        
        eq_list = [f"{slot}: {item.name}" for slot, item in char.equipped.items()]
        inv_list = [item.name for item in char.inventory]
        tags_list = [f"{k} (+{v.modifier})" for k, v in char.abilities.tags.items()]
        
        # Load current location and adjacent paths early for relevance filtering
        current_loc = next((l for l in world.discovered_locations if l.id == getattr(world, 'current_location_id', None)), None)
        if current_loc:
            current_loc_str = f"{current_loc.name} [Type: {current_loc.type}] ({current_loc.description})"
            connected_locs = [l for l in world.discovered_locations if l.id in current_loc.connections]
            connected_str = ", ".join([l.name for l in connected_locs]) if connected_locs else "None"
            local_rumors_list = current_loc.rumors
        else:
            current_loc_str = "Unknown"
            connected_str = "None"
            local_rumors_list = []
            
        rumors_str = ", ".join(local_rumors_list) if local_rumors_list else "None"

        # Load active quests — sorted by priority (main first)
        active_quests_list = []
        main_quests = [q for q in world.active_quests if q.status == "active" and q.priority == "main"]
        side_quests = [q for q in world.active_quests if q.status == "active" and q.priority == "side"]

        for q in main_quests + side_quests:
            label = "[MAIN]" if q.priority == "main" else "[SIDE]"
            q_str = f"{label} {q.name} ({q.description})"
            if q.positive_consequence or q.negative_consequence:
                q_str += f" [Reward: {q.positive_consequence}] [Failure: {q.negative_consequence}]"
            if q.notes:
                notes_str = "; ".join(q.notes[-3:])  # Only last 3 notes to cap size
                q_str += f" [Clues: {notes_str}]"
            active_quests_list.append(q_str)
        quests_str = " || ".join(active_quests_list) if active_quests_list else "None"

        relevance_text = f"{current_loc_str} {rumors_str} {quests_str}".lower()
        
        # Load factions to populate context snapshot
        factions_path = os.path.join("saves", self.campaign_slug, "factions.json")
        factions_summary = "None"
        clocks_summary = "None"
        recent_events_summary = "None"
        if os.path.exists(factions_path):
            try:
                with open(factions_path, "r", encoding="utf-8") as f:
                    f_data = json.load(f)
                factions_list = []
                clocks_list = []
                for f_id, f_info in f_data.get("factions", {}).items():
                    f_name = f_info.get("name", f_id)
                    # Political Pruning: only inject if relevant
                    if f_name.lower() in relevance_text or f_id.lower() in relevance_text:
                        npc_names = list(f_info.get("npcs", {}).keys())
                        npc_str = f" (NPCs: {', '.join(npc_names)})" if npc_names else ""
                        factions_list.append(f"{f_name} [Rep: {f_info.get('reputation', 0)}]{npc_str}")
                        
                        # Read clocks
                        for clock in f_info.get("clocks", []):
                            clocks_list.append(f"{f_name}: {clock['name']} ({clock['turns_remaining']} turns remaining)")
                        
                if factions_list:
                    factions_summary = " | ".join(factions_list)
                if clocks_list:
                    clocks_summary = " | ".join(clocks_list)
                    
                # Read last 3 events
                events = f_data.get("faction_events", [])
                if events:
                    recent_events = events[-3:]
                    events_list = [f"[{e.get('faction_id')}] {e.get('event')}" for e in recent_events]
                    recent_events_summary = " | ".join(events_list)
            except Exception:
                pass
                
        # Load relationships to populate context snapshot
        rel_list = [f"{name} ({rel})" for name, rel in char.relationships.items()]
        rel_str = ", ".join(rel_list) if rel_list else "None"
        
        # Load active world aspects
        aspect_list = []
        for aspect in world.world_aspects:
            aspect_list.append(f"{aspect.name} ({aspect.type}): {aspect.description} [Intensity: {aspect.intensity}]")
        aspects_str = " | ".join(aspect_list) if aspect_list else "None"

        # Load unlocked lore & secrets
        lore_path = os.path.join("saves", self.campaign_slug, "lore.json")
        lore_titles = []
        secrets_list = []
        if os.path.exists(lore_path):
            try:
                with open(lore_path, "r", encoding="utf-8") as f:
                    lore_data = json.load(f)
                lore_titles = [entry.get("title") for entry in lore_data.get("unlocked_lore", [])]
                raw_secrets = lore_data.get("secrets", [])
                secrets_list = [s[:50] + "..." if len(s) > 50 else s for s in raw_secrets]
            except Exception:
                pass
        lore_str = ", ".join(lore_titles) if lore_titles else "None"
        secrets_str = ", ".join(secrets_list) if secrets_list else "None"

        hunger_labels = ["Full", "Hungry", "Starving"]
        fatigue_labels = ["Rested", "Tired", "Exhausted"]
        
        # Build the Director's Brief line
        directors_brief = world.next_story_beat if world.next_story_beat else "Continue the current narrative naturally."

        # Load story spine info
        spine_str = "None"
        if world.story_spine and world.story_spine.beats:
            active_beat = world.story_spine.get_active_beat()
            if active_beat:
                spine_str = f"Beat {active_beat.id} — '{active_beat.name}': {active_beat.dramatic_question} (Tone: {active_beat.tonal_direction})"
            else:
                spine_str = "All beats resolved — story approaching conclusion"

        # Load cast summary
        cast_summary = "None"
        cast_path = os.path.join("saves", self.campaign_slug, "cast.json")
        if os.path.exists(cast_path):
            try:
                with open(cast_path, "r", encoding="utf-8") as f:
                    cast_data = json.load(f)
                cast_entries = []
                for section in ["spine_characters", "promoted_npcs"]:
                    for cid, cinfo in cast_data.get(section, {}).items():
                        cast_entries.append(f"{cinfo['name']} ({cinfo['role']}, {cinfo['status']})")
                if cast_entries:
                    cast_summary = ", ".join(cast_entries)
            except Exception:
                pass

        context_str = (
            f"DIRECTOR'S BRIEF: {directors_brief}\n"
            f"Recent Events: {turn_history_str}\n"
            f"Character Status: {cond} | "
            f"Currency: {char.currency} | "
            f"Equipped: {', '.join(eq_list) if eq_list else 'None'} | "
            f"Inventory: {', '.join(inv_list) if inv_list else 'Empty'} | "
            f"Skills: {', '.join(tags_list)} | "
            f"Hunger: {hunger_labels[world.hunger]} | "
            f"Fatigue: {fatigue_labels[world.fatigue]} | "
            f"Weather: {world.weather if world.weather else 'Clear'} | "
            f"Relationships: {rel_str} | "
            f"Factions: {factions_summary} | "
            f"Faction Clocks: {clocks_summary} | "
            f"Faction Events: {recent_events_summary} | "
            f"Active Quests: {quests_str} | "
            f"Story Beat: {spine_str} | "
            f"Key Cast: {cast_summary} | "
            f"Campaign Arc: {world.campaign_arc} | "
            f"Current Location: {current_loc_str} | "
            f"Adjacent Paths: {connected_str} | "
            f"Local Rumors: {rumors_str} | "
            f"Active World Aspects: {aspects_str} | "
            f"Unlocked Lore: {lore_str} | "
            f"Secrets: {secrets_str}\n"
            f"World Bible Summary: {world.world_bible_summary}"
        )

        # --- COMBAT ENFORCEMENT ---
        # Mechanically check if an active encounter exists on disk.
        # If so, override the player's action with a combat-locked prompt so the DM
        # CANNOT ignore the fight regardless of what the player chose to do.
        enc_path = os.path.join("saves", self.campaign_slug, "encounters.json")
        active_enemy_str = None
        if os.path.exists(enc_path):
            try:
                with open(enc_path, "r", encoding="utf-8") as f:
                    enc_data = json.load(f)
                ae = enc_data.get("active_encounter")
                if ae and ae.get("enemies"):
                    enemy_strs = []
                    for idx, e in enumerate(ae["enemies"]):
                        if e.get("hp", 0) <= 0:
                            enemy_strs.append(f"[{idx}] {e.get('name')} (DEAD)")
                        else:
                            hp_pct = (e.get("hp", 1) / max(e.get("max_hp", 1), 1)) * 100
                            cond = "Healthy" if hp_pct >= 70 else "Wounded" if hp_pct >= 30 else "Near Death"
                            enemy_strs.append(f"[{idx}] {e.get('name')} (Threat: {e.get('threat_level', 1)} | HP: {e.get('hp')}/{e.get('max_hp')} — {cond})")
                    active_enemy_str = " | ".join(enemy_strs)
            except Exception:
                pass

        if active_enemy_str:
            # Hard-inject combat override: player's chosen action becomes a combat action context
            query = (
                f"⚠️ ACTIVE COMBAT — COMBAT OVERRIDE IS MANDATORY. "
                f"Active Enemies: {active_enemy_str}. "
                f"The player attempted: '{player_action}'. "
                f"Interpret this action in the context of the ongoing fight (e.g., if they tried to use an item, narrate it as a mid-combat action and still resolve the enemies' attacks). "
                f"You MUST call 'apply_combat_turn' using the integer target index (e.g. 0 or 1) to resolve this round mechanically. "
                f"When generating the 3-4 player choices, you MUST explicitly indicate which enemy they are targeting if there are multiple (e.g., 'Attack [0] Goblin A with your sword'). "
                f"You MUST NOT exit combat or present non-combat options until 'get_active_encounter' returns no active enemies.\n"
                f"Context: {context_str}"
            )
        elif world.survival_situation:
            # Survival override — player is in immediate mortal danger
            query = (
                f"⚠️ SURVIVAL SITUATION — SURVIVAL OVERRIDE IS MANDATORY. "
                f"Threat: {world.survival_situation}. "
                f"The player attempted: '{player_action}'. "
                f"ALL options MUST be frantic survival actions focused on escaping this immediate threat. "
                f"When the threat is resolved, you MUST call 'set_override_state: clear | survival' to end this lock.\n"
                f"Context: {context_str}"
            )
        elif world.stealth_mission:
            # Stealth override — player is sneaking
            query = (
                f"⚠️ STEALTH MISSION — STEALTH OVERRIDE IS MANDATORY. "
                f"Target: {world.stealth_mission}. "
                f"The player attempted: '{player_action}'. "
                f"ALL options MUST be restricted to quiet movement, finding cover, observing patrols, or silent takedowns. Do not offer casual exploration options. "
                f"If the player is caught or successfully escapes the area, you MUST call 'set_override_state: clear | stealth' to end this lock.\n"
                f"Context: {context_str}"
            )
        elif world.social_encounter:
            # Social override — player is locked in a conversation/negotiation
            query = (
                f"⚠️ SOCIAL ENCOUNTER — SOCIAL OVERRIDE IS MANDATORY. "
                f"Scene: {world.social_encounter}. "
                f"The player attempted: '{player_action}'. "
                f"ALL options MUST be dialogue responses, persuasion tactics, or social maneuvers within this conversation. "
                f"When the conversation concludes (resolution, escape, or breakdown), you MUST call 'set_override_state: clear | social' to end this lock.\n"
                f"NOTE: If the player attempts a custom action that intentionally breaks this context (e.g., drawing a weapon), naturally transition the scene, clear this state, and trigger the appropriate tools.\n"
                f"Context: {context_str}"
            )
        elif world.investigation_focus:
            # Investigation override — player is solving a puzzle or examining a scene
            query = (
                f"⚠️ INVESTIGATION OVERRIDE IS MANDATORY. "
                f"Focus: {world.investigation_focus}. "
                f"The player attempted: '{player_action}'. "
                f"ALL options MUST be focused intellectual actions regarding this puzzle/scene. "
                f"When the puzzle is solved, or if the player abandons the task, you MUST call 'set_override_state: clear | investigation' to end this lock.\n"
                f"NOTE: If the player attempts a custom action that intentionally breaks this context, transition the scene and clear this state.\n"
                f"Context: {context_str}"
            )
        elif world.travel_journey:
            # Travel override — player is on a road trip between locations
            query = (
                f"⚠️ TRAVEL JOURNEY — TRAVEL OVERRIDE IS MANDATORY. "
                f"Route: {world.travel_journey}. "
                f"The player attempted: '{player_action}'. "
                f"ALL options MUST be focused on the journey (foraging, making camp, dealing with roadside events/hazards). Do not offer full location exploration until they arrive. "
                f"When the player finally arrives at the destination, you MUST call 'set_override_state: clear | travel' to end this lock.\n"
                f"NOTE: If the player attempts a custom action to abandon the journey and turn back, transition the scene and clear this state.\n"
                f"Context: {context_str}"
            )
        elif world.is_camping:
            # Camping override — player is at a campfire/rest site
            query = (
                f"⚠️ CAMPING — CAMPING OVERRIDE IS MANDATORY. "
                f"The player attempted: '{player_action}'. "
                f"ALL options MUST be camp activities (eating, crafting, tending wounds, sleeping, or bonding). "
                f"Current Hunger: {['Full','Hungry','Starving'][world.hunger]}. Current Fatigue: {['Rested','Tired','Exhausted'][world.fatigue]}. "
                f"When the player is done resting and breaks camp, you MUST call 'set_override_state: clear | camping' to end this lock.\n"
                f"NOTE: If the player attempts a custom action that intentionally breaks camp abruptly, transition the scene and clear this state.\n"
                f"Context: {context_str}"
            )
        else:
            query = f"Player Action: {player_action}.\nContext: {context_str}"

        if heartbeat_occurred:
            query += f" Note: A world heartbeat just triggered: {heartbeat_log}."
            
        # --- INJECT CRITIC WARNING ---
        if critic_assessment and critic_assessment.get("is_repeating"):
            critic_warning = (
                f"⚠️ [CRITIC WARNING — REPETITION DETECTED]: {critic_assessment['critic_note']}\n"
                f"You MUST introduce a NEW scene, NEW NPC interaction, or a dramatic event. "
                f"Do NOT describe the same scene or offer the same choices as last turn.\n"
            )
            query = critic_warning + query

        dm_response = self.run(query, max_turns=12, verbose=self.verbose, agent_name="DM")
        
        # Save turn history (last 3 turns)
        history_path = os.path.join("saves", self.campaign_slug, "turn_history.json")
        history = []
        if os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        # Extract a 1-sentence summary from the DM response (first sentence or first 150 chars)
        summary = dm_response.strip().split(".")[0] + "." if dm_response else "No response."
        if len(summary) > 200:
            summary = summary[:200] + "..."

        history.append({
            "turn": world.turn_count,
            "player_action": player_action[:100],  # Cap to prevent bloat
            "dm_summary": summary
        })

        # Keep only last 3
        history = history[-3:]

        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
            
        return dm_response
