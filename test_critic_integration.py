import os
import sys
import json
import shutil
import unittest

sys.path.append(os.path.abspath("d:/agent-game"))

from game_engine.world import WorldState
from agents.subagents.story_critic import StoryCritic
from agents.dm_agent import DMAgent


class MockLLMClient:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_prompt = None
        self.last_system_instruction = None

    def generate(self, prompt: str, system_instruction: str = None) -> str:
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction
        return self.response_text


class TestStoryCriticIntegration(unittest.TestCase):
    def setUp(self):
        self.campaign_slug = "test-critic-campaign"
        self.save_dir = os.path.join("saves", self.campaign_slug)
        os.makedirs(self.save_dir, exist_ok=True)
        
        # Write initial basic world state
        self.world = WorldState()
        self.world.turn_count = 0
        with open(os.path.join(self.save_dir, "world_state.json"), "w", encoding="utf-8") as f:
            json.dump(self.world.to_dict(), f, indent=4)
            
        # Write initial empty history
        with open(os.path.join(self.save_dir, "turn_history.json"), "w", encoding="utf-8") as f:
            json.dump([], f)

    def tearDown(self):
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)

    def test_critic_parsing_and_evaluation(self):
        mock_response = (
            "PLAYER_MODE: shopping\n"
            "IS_REPEATING: true\n"
            "DIRECTIVE: organic\n"
            "CRITIC_NOTE: Player is buying some weapons and potions. Keep tavern descriptive."
        )
        llm = MockLLMClient(mock_response)
        critic = StoryCritic(llm, self.campaign_slug)
        
        assessment = critic.evaluate("I go to the merchant and look at potions.")
        
        self.assertEqual(assessment["player_mode"], "shopping")
        self.assertTrue(assessment["is_repeating"])
        self.assertEqual(assessment["directive"], "organic")
        self.assertEqual(assessment["critic_note"], "Player is buying some weapons and potions. Keep tavern descriptive.")

    def test_critic_default_fallback_on_error(self):
        # Trigger an LLM exception
        class ErrorLLM:
            def generate(self, prompt, system_instruction=None):
                raise RuntimeError("API Offline")

        critic = StoryCritic(ErrorLLM(), self.campaign_slug)
        assessment = critic.evaluate("Hello")
        
        self.assertEqual(assessment["player_mode"], "quest")
        self.assertFalse(assessment["is_repeating"])
        self.assertEqual(assessment["directive"], "organic")

    def test_dm_agent_integration_turn_tracking(self):
        mock_response = (
            "PLAYER_MODE: exploring\n"
            "IS_REPEATING: false\n"
            "DIRECTIVE: gentle_pull\n"
            "CRITIC_NOTE: Player is wandering around. Introduce environmental hook."
        )
        llm = MockLLMClient(mock_response)
        
        # Instantiate DMAgent
        # Note: We need a dummy character sheet as well for DMAgent constructor / runs
        char_path = os.path.join(self.save_dir, "character.json")
        with open(char_path, "w", encoding="utf-8") as f:
            json.dump({"name": "Tester", "hp": 20, "max_hp": 20, "inventory": [], "equipped": {}, "status_effects": [], "abilities": {"tags": {}}}, f)
            
        dm = DMAgent(llm, self.campaign_slug, verbose=False)
        
        # Mocking dm.run to prevent actual ReAct loops from firing real commands or failing on mock
        dm.run = lambda query, max_turns, verbose, agent_name: "DM Response"

        # Let's run a turn
        dm.process_turn("I search the cave entrance.")
        
        # Verify action tracking
        with open(os.path.join(self.save_dir, "world_state.json"), "r", encoding="utf-8") as f:
            updated_world = WorldState.from_dict(json.load(f))
            
        self.assertIn("I search the cave entrance.", updated_world.recent_player_actions)
        self.assertEqual(updated_world.pressure_cooldown, 3)  # Cooldown applied for gentle_pull


if __name__ == "__main__":
    unittest.main()
