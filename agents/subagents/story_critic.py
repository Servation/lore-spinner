import os
import json
from game_engine.world import WorldState


class StoryCritic:
    """Lightweight critic agent that analyzes player intent and detects narrative loops.
    
    Runs a single LLM call (no ReAct loop, no tools) and returns a structured
    assessment that is fed into the LoreKeeper and DM Agent to prevent
    story/location locking.
    """
    
    def __init__(self, llm_client, campaign_slug: str):
        self.llm_client = llm_client
        self.campaign_slug = campaign_slug

    def evaluate(self, current_player_action: str) -> dict:
        """Runs the critic evaluation. Returns a dict with:
        - player_mode: str ("quest" | "exploring" | "shopping" | "socializing")
        - is_repeating: bool
        - directive: str ("organic" | "gentle_pull" | "force_event")
        - critic_note: str (free-text advice for the LoreKeeper and DM)
        """
        # Load world state
        world_path = os.path.join("saves", self.campaign_slug, "world_state.json")
        if not os.path.exists(world_path):
            return self._default_assessment()
        
        try:
            with open(world_path, "r", encoding="utf-8") as f:
                world = WorldState.from_dict(json.load(f))
        except Exception:
            return self._default_assessment()
        
        # Load turn history for repetition check
        history_path = os.path.join("saves", self.campaign_slug, "turn_history.json")
        turn_history = []
        if os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    turn_history = json.load(f)
            except Exception:
                pass
        
        # Get current story beat
        active_beat_str = "No active story beat."
        if world.story_spine and world.story_spine.beats:
            active_beat = world.story_spine.get_active_beat()
            if active_beat:
                active_beat_str = (
                    f"Beat {active_beat.id} — '{active_beat.name}': "
                    f"{active_beat.dramatic_question}"
                )
        
        # Get current location
        current_loc = next(
            (l for l in world.discovered_locations 
             if l.id == getattr(world, 'current_location_id', None)), 
            None
        )
        loc_str = f"{current_loc.name} ({current_loc.type})" if current_loc else "Unknown"
        
        # Build the recent actions context
        recent_actions = world.recent_player_actions[-5:] if world.recent_player_actions else []
        actions_str = "\n".join(
            [f"  {i+1}. \"{a}\"" for i, a in enumerate(recent_actions)]
        ) if recent_actions else "  (none yet)"
        
        # Build the recent DM responses context
        dm_summaries = "\n".join(
            [f"  Turn {h['turn']}: {h['dm_summary']}" for h in turn_history]
        ) if turn_history else "  (none yet)"
        
        prompt = f"""You are the Story Critic for a text-based RPG. Your ONLY job is to analyze 
the current game state and output a structured assessment. You do NOT write narrative.

CURRENT STATE:
- Current Location: {loc_str}
- Active Story Beat: {active_beat_str}
- Turns on current beat: {world.turns_on_current_beat}
- Pressure cooldown remaining: {world.pressure_cooldown} turns
- Current player action this turn: "{current_player_action}"

RECENT PLAYER ACTIONS (oldest to newest):
{actions_str}

RECENT DM RESPONSES:
{dm_summaries}

INSTRUCTIONS:
Analyze the above and respond with EXACTLY these 4 lines (no other text):

PLAYER_MODE: [quest|exploring|shopping|socializing]
IS_REPEATING: [true|false]
DIRECTIVE: [organic|gentle_pull|force_event]
CRITIC_NOTE: [Your 1-2 sentence advice for the story system]

RULES FOR YOUR ASSESSMENT:
- PLAYER_MODE: What is the player currently trying to do? 
  "quest" = actively pursuing the main story. 
  "exploring" = wandering, investigating, looking around. 
  "shopping" = buying, selling, trading, browsing merchants. 
  "socializing" = talking to NPCs for fun, not quest-related.

- IS_REPEATING: Are the last 3+ DM responses describing essentially the same scene, 
  mentioning the same NPCs, or offering the same choices? If yes, true.

- DIRECTIVE: How should the story system respond?
  "organic" = Player is engaged. Leave them alone. Let the story flow naturally.
  "gentle_pull" = Player has been off the main quest for a while (4+ turns on same beat) 
    AND is in "quest" mode (not deliberately doing something else). Suggest weaving a 
    subtle quest hook into the environment.
  "force_event" = Story has been stuck for 8+ turns on the same beat AND previous 
    gentle pulls haven't worked AND pressure_cooldown is 0. Time for a dramatic 
    interruption (ambush, urgent messenger, explosion, etc).
  
  CRITICAL: If the player's mode is "exploring", "shopping", or "socializing", 
  you should ALMOST ALWAYS output "organic" regardless of turns_on_current_beat. 
  The player is deliberately doing their own thing — respect their agency.
  Only output "force_event" if IS_REPEATING is also true (meaning the game itself 
  is stuck, not just the player ignoring the quest).

- CRITIC_NOTE: Brief advice. Examples:
  "Player is shopping — let them finish. The shopkeeper could casually mention 
   hearing strange noises from the mine."
  "DM has described the tavern entrance 3 turns in a row. Force a scene change."
  "Player is actively questing. Everything looks good, no intervention needed."
"""
        
        try:
            response = self.llm_client.generate(
                prompt, 
                system_instruction="You are a concise game analysis system. Output ONLY the 4 requested lines."
            )
            return self._parse_response(response)
        except Exception:
            return self._default_assessment()
    
    def _parse_response(self, response: str) -> dict:
        """Parse the structured LLM response into a dict."""
        result = self._default_assessment()
        
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("PLAYER_MODE:"):
                mode = line.split(":", 1)[1].strip().lower()
                if mode in ("quest", "exploring", "shopping", "socializing"):
                    result["player_mode"] = mode
            elif line.startswith("IS_REPEATING:"):
                val = line.split(":", 1)[1].strip().lower()
                result["is_repeating"] = val == "true"
            elif line.startswith("DIRECTIVE:"):
                directive = line.split(":", 1)[1].strip().lower()
                if directive in ("organic", "gentle_pull", "force_event"):
                    result["directive"] = directive
            elif line.startswith("CRITIC_NOTE:"):
                result["critic_note"] = line.split(":", 1)[1].strip()
        
        return result
    
    def _default_assessment(self) -> dict:
        """Safe default — don't pressure, don't warn."""
        return {
            "player_mode": "quest",
            "is_repeating": False,
            "directive": "organic",
            "critic_note": "No assessment available."
        }
