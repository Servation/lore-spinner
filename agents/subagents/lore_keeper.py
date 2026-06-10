import os
import json
from typing import Dict, Callable
from agents.base_agent import BaseAgent
from game_engine.world import WorldState, StorySpine

class LoreKeeper(BaseAgent):
    def __init__(self, llm_client, campaign_slug: str):
        self.campaign_slug = campaign_slug
        self.tools = self._get_tools()
        
        sys_instruction = """You are the Lore Keeper. You manage quest progressions, hidden secrets, unlocked lore/codex entries, and the Cast of characters.
Your job is to track narrative milestones, unlock historical or technological lore, and manage quests.
You also manage the Story Spine — a 5-beat adaptive narrative arc. You track which beat is active and advance the spine when the current beat's dramatic question has been answered through player actions.
You do NOT interact with the player directly. Your task is to maintain the overarching narrative logic of the world. You run in a background ReAct loop.
You read the DM log and the current 'Campaign Arc' and 'Active Quests'. 

The 5 beats are:
1. The Hook — the personal inciting incident
2. The Deepening — the problem is bigger than it seemed
3. The Betrayal/Reversal — something trusted flips
4. The Crisis — the player's deepest fear is tested
5. The Reckoning — the final confrontation

When deciding to advance a beat, consider: Has the current beat's dramatic question been meaningfully answered by player actions? Don't advance prematurely — each beat should feel earned.

If the player completes major tasks, update the quests. If they discover something new, unlock lore entries.
If the player acts recklessly, angers NPCs, or suffers massive defeat, you MUST spawn new 'World Aspects' (like 'Nemesis', 'Doom Clock', 'Heat', or 'Trauma') to impose lasting consequences on them.

You also manage the Cast (important NPCs). Use 'modify_cast_member' to update their status, location, or relationships as the story evolves. Use 'promote_npc' when a recurring NPC deserves full characterization.

Your tools are:
- add_quest: Spawns a new quest. Format: 'id | name | desc | [pos_conseq] | [neg_conseq] | [priority]'. Priority is 'main' or 'side' (default: side). Usage: Action: add_quest: main_shard | Find the Data Shard | Locate the encrypted shard. | Access to archives | Corporate wipe | main
- update_quest: Updates a quest status. Format: 'quest_id | status'. Status options: 'completed', 'failed'. Usage: Action: update_quest: main_shard | completed
- unlock_lore: Unlocks a codex/lore entry. Format: 'title | content'. Usage: Action: unlock_lore: The Great Freeze | A historical recount of the disaster.
- plant_secret: Registers a secret clue. Format: 'secret_description'. Usage: Action: plant_secret: Jax is planning a double cross.
- update_campaign_arc: Replaces the core campaign arc. Format: 'new arc'. Usage: Action: update_campaign_arc: The player must stop the AI before it ascends.
- update_story_beat: Sets a specific narrative directive telling the DM what should happen next. This should be a concrete, actionable 1-2 sentence instruction (e.g., "Have an NPC reveal the smuggler's betrayal" or "The player should discover the hidden lab entrance behind the waterfall"). Usage: Action: update_story_beat: The resistance contact should approach the player with urgent news about a traitor.
- add_world_aspect: Adds a new World Aspect constraint (Nemesis, Doom Clock, Heat, Trauma). Format: 'name | type | desc | [intensity]'. Usage: Action: add_world_aspect: Kael | Nemesis | A rival bounty hunter tracking you. | 3
- remove_world_aspect: Removes an aspect. Format: 'name'. Usage: Action: remove_world_aspect: Kael
- store_story_spine: Stores the generated story spine structure. Format: JSON string. Usage: Action: store_story_spine: {"theme": "...", "beats": [...]}
- store_cast_member: Stores a spine character in the cast. Format: 'character_id | name | role | appearance | personality | hidden_agenda | relationship_to_player | dramatic_function'. Usage: Action: store_cast_member: anchor_01 | Aldric | anchor | ...
- advance_spine_beat: Resolves current active beat and activates the next. Format: 'resolution_notes'. Usage: Action: advance_spine_beat: Player discovered the truth about Aldric.
- modify_cast_member: Updates a cast member's field. Format: 'character_id | field | value'. Usage: Action: modify_cast_member: anchor_01 | status | dead
- promote_npc: Promotes a lightweight NPC to the full cast. Format: 'npc_name | role | appearance | personality | hidden_agenda | relationship_to_player | dramatic_function'. Usage: Action: promote_npc: Sera | promoted | ...
"""
        super().__init__(llm_client, self.tools, sys_instruction)

    def _get_tools(self) -> Dict[str, Callable[[str], str]]:
        def add_quest(args: str) -> str:
            parts = args.split("|")
            if len(parts) < 3:
                return "Error: Format must be 'quest_id | quest_name | description | [pos_conseq] | [neg_conseq] | [priority]'"
            qid = parts[0].strip()
            name = parts[1].strip()
            desc = parts[2].strip()
            pos = parts[3].strip() if len(parts) > 3 else ""
            neg = parts[4].strip() if len(parts) > 4 else ""
            priority = parts[5].strip() if len(parts) > 5 else "side"
            if priority not in ("main", "side"):
                priority = "side"
            
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(world_path):
                return "Error: World state not found."
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.add_quest(qid, name, desc, pos_conseq=pos, neg_conseq=neg, priority=priority)
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

        def update_story_beat(beat: str) -> str:
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(world_path):
                return "Error: World state not found."
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.next_story_beat = beat
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            return f"Director's Brief updated: {beat}"

        def store_story_spine(args: str) -> str:
            """Format: JSON string of the story spine object.
            Example: {"theme": "Redemption through sacrifice", "beats": [{"id": 1, "name": "The Hook", "dramatic_question": "...", "tonal_direction": "...", "status": "active", "pressure_mechanism": "..."}, ...]}
            Usage: Action: store_story_spine: {"theme": "...", "beats": [...]}"""
            try:
                spine_data = json.loads(args.strip())
            except json.JSONDecodeError:
                return "Error: Invalid JSON. Must be a valid story spine object."

            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(world_path):
                return "Error: World state not found."
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)
            world.story_spine = StorySpine.from_dict(spine_data)
            world.campaign_arc = spine_data.get("theme", "")
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            return "Story Spine stored successfully."

        def store_cast_member(args: str) -> str:
            """Format: 'character_id | name | role | appearance | personality | hidden_agenda | relationship_to_player | dramatic_function'.
            Roles: 'anchor', 'catalyst', 'adversary'.
            Usage: Action: store_cast_member: anchor_01 | Master Aldric | anchor | Weathered man with ink-stained hands | Patient but secretive | Hiding a forbidden artifact | Former mentor | Emotional anchor for Beat 1"""
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 4:
                return "Error: Need at least 'id | name | role | appearance'."

            char_id = parts[0]
            entry = {
                "name": parts[1],
                "role": parts[2],
                "appearance": parts[3] if len(parts) > 3 else "",
                "personality": parts[4] if len(parts) > 4 else "",
                "hidden_agenda": parts[5] if len(parts) > 5 else "",
                "relationship_to_player": parts[6] if len(parts) > 6 else "",
                "dramatic_function": parts[7] if len(parts) > 7 else "",
                "status": "alive",
                "current_location": ""
            }

            cast_path = os.path.join("saves", self.campaign_slug, "cast.json")
            if not os.path.exists(cast_path):
                cast = {"spine_characters": {}, "promoted_npcs": {}}
            else:
                with open(cast_path, "r", encoding="utf-8") as f:
                    cast = json.load(f)

            cast.setdefault("spine_characters", {})[char_id] = entry
            with open(cast_path, "w", encoding="utf-8") as f:
                json.dump(cast, f, indent=4)
            return f"Spine Character '{parts[1]}' (role: {parts[2]}) stored in cast."

        def advance_spine_beat(args: str) -> str:
            """Format: 'resolution_notes'. Resolves the current active story beat and activates the next.
            Usage: Action: advance_spine_beat: The player discovered the mentor was taken by the Collector."""
            world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
            if not os.path.exists(world_path):
                return "Error: World state not found."
            with open(world_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            world = WorldState.from_dict(data)

            if not world.story_spine.beats:
                return "Error: No story spine exists."

            next_beat = world.story_spine.advance_beat(args.strip())
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)

            if next_beat:
                return f"Beat resolved. Now active: Beat {next_beat.id} — '{next_beat.name}': {next_beat.dramatic_question}"
            return "Story spine complete — all beats resolved. The story has reached its conclusion."

        def modify_cast_member(args: str) -> str:
            """Format: 'character_id | field | value'. Updates a field on a cast member.
            Valid fields: status, current_location, relationship_to_player, hidden_agenda, personality, dramatic_function.
            Usage: Action: modify_cast_member: anchor_01 | status | dead"""
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 3:
                return "Error: Format must be 'character_id | field | value'"
            char_id, field_name, value = parts[0], parts[1], parts[2]

            cast_path = os.path.join("saves", self.campaign_slug, "cast.json")
            if not os.path.exists(cast_path):
                return "Error: Cast file not found."
            with open(cast_path, "r", encoding="utf-8") as f:
                cast = json.load(f)

            target = None
            for section in ["spine_characters", "promoted_npcs"]:
                if char_id in cast.get(section, {}):
                    target = cast[section][char_id]
                    break

            if not target:
                return f"Error: Cast member '{char_id}' not found."

            valid_fields = ["status", "current_location", "relationship_to_player", "hidden_agenda", "personality", "dramatic_function"]
            if field_name not in valid_fields:
                return f"Error: Invalid field. Valid fields: {', '.join(valid_fields)}"

            target[field_name] = value
            with open(cast_path, "w", encoding="utf-8") as f:
                json.dump(cast, f, indent=4)
            return f"Updated cast member '{char_id}': {field_name} = {value}"

        def promote_npc(args: str) -> str:
            """Format: 'npc_name | role | appearance | personality | hidden_agenda | relationship_to_player | dramatic_function'.
            Promotes a lightweight NPC to a full cast member in cast.json.
            Usage: Action: promote_npc: Sera | promoted | Tall woman with a scar | Calculating but loyal | Secretly working for the Collector | Trusted informant | Provides intel that drives Beat 3"""
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 1:
                return "Error: Format must be 'npc_name | [role] | [appearance] | [personality] | [hidden_agenda] | [relationship_to_player] | [dramatic_function]'"
            
            import uuid
            npc_id = f"promoted_{uuid.uuid4().hex[:8]}"
            name = parts[0]
            role = parts[1] if len(parts) > 1 else "promoted"
            appearance = parts[2] if len(parts) > 2 else ""
            personality = parts[3] if len(parts) > 3 else ""
            hidden_agenda = parts[4] if len(parts) > 4 else ""
            rel = parts[5] if len(parts) > 5 else ""
            dramatic_func = parts[6] if len(parts) > 6 else ""

            cast_path = os.path.join("saves", self.campaign_slug, "cast.json")
            if not os.path.exists(cast_path):
                cast = {"spine_characters": {}, "promoted_npcs": {}}
            else:
                with open(cast_path, "r", encoding="utf-8") as f:
                    cast = json.load(f)

            cast.setdefault("promoted_npcs", {})[npc_id] = {
                "name": name,
                "role": role,
                "appearance": appearance,
                "personality": personality,
                "hidden_agenda": hidden_agenda,
                "relationship_to_player": rel,
                "dramatic_function": dramatic_func,
                "status": "alive",
                "current_location": ""
            }
            with open(cast_path, "w", encoding="utf-8") as f:
                json.dump(cast, f, indent=4)
            return f"NPC '{name}' promoted to cast (ID: {npc_id})."

        return {
            "add_quest": add_quest,
            "update_quest": update_quest,
            "unlock_lore": unlock_lore,
            "plant_secret": plant_secret,
            "update_campaign_arc": update_campaign_arc,
            "update_story_beat": update_story_beat,
            "add_world_aspect": add_world_aspect,
            "remove_world_aspect": remove_world_aspect,
            "store_story_spine": store_story_spine,
            "store_cast_member": store_cast_member,
            "advance_spine_beat": advance_spine_beat,
            "modify_cast_member": modify_cast_member,
            "promote_npc": promote_npc
        }

    def check_lore(self, action: str, location: str) -> str:
        """Called by DM to check if any lore is unlocked by this action/location."""
        query = f"Location: {location}. Action: {action}. Determine if any secrets are unlocked or quests advanced."
        return self.run(query, max_turns=3, verbose=False, agent_name="LoreKeeper")

    def heartbeat(self, budget_mode: bool = False, critic_assessment: dict = None, context_map = None) -> str:
        if budget_mode:
            return "LoreKeeper heartbeat skipped (Budget Mode)."
            
        world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
        if not os.path.exists(world_path):
            return ""
            
        with open(world_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        world = WorldState.from_dict(data)
        
        heartbeat_logs = []
 
        # Read DM log if it exists to provide context of recent events
        dm_log_content = "No log found."
        dm_log_path = os.path.join("saves", self.campaign_slug, "dm_log.md")
        if os.path.exists(dm_log_path):
            with open(dm_log_path, "r", encoding="utf-8") as f:
                dm_log_content = f.read()
 
        # Format quest status context
        quests_list = []
        for q in world.active_quests:
            quests_list.append(f"- Quest Name: {q.name} (ID: {q.id}), Status: {q.status}, Description: {q.description}")
        quests_str = "\n".join(quests_list) if quests_list else "No active quests."
 
        if world.escalated_rumors:
            rumors_str = ", ".join(world.escalated_rumors)
            arc_str = world.campaign_arc if world.campaign_arc else "None (Create one now based on these rumors)"
            
            query = (
                f"HEARTBEAT: The following rumors were escalated by the DM: [{rumors_str}]. "
                f"The current Campaign Arc is: [{arc_str}]. \n\n"
                f"Here is the DM log of recent events for context:\n"
                f"\"\"\"\n{dm_log_content}\n\"\"\"\n\n"
            )
            if context_map:
                query += f"Context Map Summary: {context_map.summary()}\n\n"
            query += (
                f"Weave these escalated rumors into a new Narrative Thread (Quest) and add it. "
                f"If there is no Campaign Arc, use 'update_campaign_arc' to create one now. "
                f"IMPORTANT: You MUST also call 'update_story_beat' with a specific, actionable 1-2 sentence directive telling the DM what the next narrative moment should be, adapted to the player's immediate context."
            )
            
            res = self.run(query, max_turns=4, verbose=False, agent_name="LoreKeeper")
            
            failed_keywords = ["Failed to arrive", "Error", "turn limit"]
            if not any(kw in res for kw in failed_keywords):
                with open(world_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                world = WorldState.from_dict(data)
                world.escalated_rumors.clear()
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                heartbeat_logs.append("Processed escalated rumors into Narrative Threads.")
            else:
                heartbeat_logs.append(f"LoreKeeper failed to process rumors; queue preserved. ({res})")
 
        # Reload world state to check spine progression pressure
        with open(world_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        world = WorldState.from_dict(data)
 
        if world.story_spine and world.story_spine.beats:
            active_beat = world.story_spine.get_active_beat()
            if active_beat:
                # Build critic context string
                critic_context = ""
                if critic_assessment:
                    critic_context = (
                        f"\n\nSTORY CRITIC ASSESSMENT:\n"
                        f"- Player Mode: {critic_assessment.get('player_mode', 'quest')}\n"
                        f"- Repetition Detected: {critic_assessment.get('is_repeating', False)}\n"
                        f"- Recommended Directive: {critic_assessment.get('directive', 'organic')}\n"
                        f"- Critic Note: {critic_assessment.get('critic_note', 'N/A')}\n"
                    )
 
                spine_query = (
                    f"SPINE CHECK: The current story beat is Beat {active_beat.id} — '{active_beat.name}'. "
                    f"Dramatic question: '{active_beat.dramatic_question}'. "
                    f"Pressure mechanism if stalling: '{active_beat.pressure_mechanism}'. \n\n"
                    f"Here is the DM log of recent events:\n"
                    f"\"\"\"\n{dm_log_content}\n\"\"\"\n\n"
                    f"Here are the active quests:\n{quests_str}\n"
                    f"{critic_context}\n"
                )
                if context_map:
                    spine_query += f"Context Map Summary: {context_map.summary()}\n\n"
                spine_query += (
                    f"Your instructions:\n"
                    f"1. Determine if the active story beat's dramatic question has been resolved by checking the DM log and quest statuses. "
                    f"If the dramatic question has been answered, call 'advance_spine_beat' with resolution notes.\n"
                    f"2. CHECK THE STORY CRITIC ASSESSMENT ABOVE before deciding whether to pressure.\n"
                    f"   - If the Critic's directive is 'organic': Do NOT activate pressure. The player is engaged in their own activity. Instead, update the Director's Brief to weave a SUBTLE quest hook into whatever the player is currently doing (e.g., if they're shopping, the merchant could mention a rumor related to the quest).\n"
                    f"   - If the Critic's directive is 'gentle_pull': Update the Director's Brief with an environmental hook that naturally connects the player's current situation to the main quest. Do NOT use World Aspects or faction events yet.\n"
                    f"   - If the Critic's directive is 'force_event': The story has been stuck too long. Activate the pressure mechanism aggressively — spawn a World Aspect, trigger a faction event, or have an NPC burst in with urgent news. Make it unavoidable.\n"
                    f"3. Update the Director's Brief (`next_story_beat`) using 'update_story_beat' to provide the DM with a specific, actionable 1-2 sentence directive for the next turn. Adapt it to the player's current location, immediate actions, and choices in the DM log so the narrative flows naturally."
                )
                self.run(spine_query, max_turns=4, verbose=False, agent_name="LoreKeeper")
                heartbeat_logs.append(f"Checked story spine progression for Beat {active_beat.id}.")
 
        return " | ".join(heartbeat_logs) if heartbeat_logs else "No activities."

    def generate_story_spine(self, char_data: dict) -> None:
        """Generates the full 5-beat Story Spine, Spine Characters, and opening quest."""
        world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
        if not os.path.exists(world_path):
            return

        with open(world_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        world = WorldState.from_dict(data)

        # Extract character backstory fields
        fear = char_data.get("fear", char_data.get("backstory", ""))
        childhood = char_data.get("childhood_event", "")
        past_life = char_data.get("past_life", "")
        sentimental_item = char_data.get("sentimental_item_story", "")
        char_name = char_data.get("name", "the player")

        query = (
            f"INITIALIZATION — GENERATE STORY SPINE.\n"
            f"Genre: '{world.setting_genre}'.\n"
            f"Setting: '{world.setting_description}'.\n"
            f"World Bible Summary: '{world.world_bible_summary}'.\n\n"
            f"Character Name: '{char_name}'.\n"
            f"Character's Defining Childhood Event: '{childhood}'.\n"
            f"Character's Past Life / Occupation: '{past_life}'.\n"
            f"Character's Deepest Fear (concrete scenario + emotional wound): '{fear}'.\n"
            f"Character's Sentimental Item: '{sentimental_item}'.\n\n"
            f"YOUR TASKS (complete ALL of them using tools):\n"
            f"1. Design a 5-beat Story Spine. Each beat needs: a dramatic_question, tonal_direction, and pressure_mechanism. "
            f"The story must be personally meaningful to THIS character — 'world-changing to the player' not necessarily world-scale. "
            f"Beat 1 (The Hook) must intersect a world event with the character's backstory. "
            f"Beat 4 (The Crisis) MUST directly weaponize the character's fear: '{fear}'. "
            f"Output the spine as a JSON object and use 'store_story_spine' to store it.\n"
            f"2. Generate 3 Spine Characters and store them using tools:\n"
            f"   - The Anchor: emotionally tied to the character's childhood or past life. The reason the player cares.\n"
            f"   - The Catalyst: someone who appears helpful but has hidden knowledge or a hidden agenda. Drives Beats 2-3. Give them a highly unique, nuanced agenda (e.g., motivated by saving their family, seeking penance, or a tragic duty rather than a cliché double-cross).\n"
            f"   - The Adversary: a personal rival whose goals directly conflict with the player's. Persistent across multiple beats.\n"
            f"   CRITICAL CHARACTER RULES:\n"
            f"   - Do NOT use cliché names. Specifically, do NOT use the names: Elara, Kaelen, Lyra, Sera, Jax, Finn, Zephyr, Orion, Cora, or Gideon.\n"
            f"   - Ensure each character has distinct, contrasting personalities and agendas.\n"
            f"   Use 'store_cast_member' for each character.\n"
            f"3. Create the Inciting Incident (Beat 1 quest) using 'add_quest' with priority 'main'. "
            f"It MUST have explicit positive and negative consequences and be personal to the character.\n"
            f"4. Call 'update_story_beat' with a specific directive for the DM's opening scene that introduces the Anchor character.\n"
        )
        self.run(query, max_turns=6, verbose=False, agent_name="LoreKeeper")
