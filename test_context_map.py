import unittest
from game_engine.context_map import (
    ContextMap,
    NODE_TYPE_CHARACTER,
    NODE_TYPE_LOCATION,
    NODE_TYPE_EVENT
)

class TestContextMap(unittest.TestCase):
    def setUp(self):
        self.context_map = ContextMap()
        
        # Standard mock data reflecting the actual schemas
        self.mock_json = {
            "character": {
                "name": "Sock",
                "position": "loc_1",
                "relationships": {
                    "Jax": "allied_with",
                    "Boss Maroni": "HOSTILE_TO",
                    "Sergeant Vance": "OWES_MONEY_TO"  # should fallback to KNOWS
                }
            },
            "world_state": {
                "current_location_id": "loc_1",
                "discovered_locations": [
                    {
                        "id": "loc_1",
                        "name": "Bio-Scrap Alley",
                        "type": "city",
                        "description": "A smelly alleyway.",
                        "connections": ["loc_2"],
                        "scope": "node",
                        "theme": "cyberpunk"
                    },
                    {
                        "id": "loc_2",
                        "name": "Neon Plaza",
                        "type": "plaza",
                        "description": "A bright square.",
                        "connections": ["loc_1", "loc_3"],
                        "scope": "node",
                        "theme": "cyberpunk"
                    },
                    {
                        "id": "loc_3",
                        "name": "Corpo HQ",
                        "type": "tower",
                        "description": "Huge tower.",
                        "connections": ["loc_2"],
                        "scope": "node",
                        "theme": "cyberpunk"
                    }
                ],
                "active_quests": [
                    {
                        "id": "quest_sunken_echo",
                        "name": "The Sunken Echo",
                        "status": "active",
                        "priority": "main"
                    }
                ]
            },
            "factions": {
                "factions": {
                    "factions:thieves_guild": {
                        "name": "Thieves Guild",
                        "reputation": -5,
                        "npcs": {
                            "Jax": "A quick-handed smuggler.",
                            "Miri": "A stealth expert."
                        }
                    }
                }
            },
            "encounters": {
                "active_encounter": {
                    "enemy": {
                        "name": "Bio-Scrap Lurker",
                        "hp": 11
                    },
                    "description": "A slimy creature jumps out of the heap!"
                }
            },
            "cast": {
                "spine_characters": {
                    "cast:aldric": {
                        "name": "Aldric",
                        "role": "Anchor",
                        "status": "active"
                    }
                },
                "promoted_npcs": {
                    "cast:sera": {
                        "name": "Sera",
                        "role": "Catalyst",
                        "status": "active"
                    }
                }
            }
        }

    def test_rebuild_creates_correct_node_types(self):
        self.context_map.rebuild(self.mock_json)
        
        characters = self.context_map.get_nodes_by_type(NODE_TYPE_CHARACTER)
        locations = self.context_map.get_nodes_by_type(NODE_TYPE_LOCATION)
        events = self.context_map.get_nodes_by_type(NODE_TYPE_EVENT)
        
        # Characters: Player ("player"), thieves_guild, Jax, Miri, Aldric, Sera, Lurker, Boss Maroni, Sergeant Vance (since Vance & Maroni are created from Player's relationships)
        char_ids = {c["node_id"] for c in characters}
        self.assertIn("player", char_ids)
        self.assertIn("factions:thieves_guild", char_ids)
        self.assertIn("factions:thieves_guild:Jax", char_ids)
        self.assertIn("factions:thieves_guild:Miri", char_ids)
        self.assertIn("cast:aldric", char_ids)
        self.assertIn("cast:sera", char_ids)
        self.assertIn("encounter:enemy", char_ids)
        self.assertIn("Boss Maroni", char_ids)
        self.assertIn("Sergeant Vance", char_ids)
        
        # Locations: loc_1, loc_2, loc_3
        loc_ids = {l["node_id"] for l in locations}
        self.assertEqual(loc_ids, {"loc_1", "loc_2", "loc_3"})
        
        # Events: quest_sunken_echo, active_encounter
        event_ids = {e["node_id"] for e in events}
        self.assertEqual(event_ids, {"quest_sunken_echo", "active_encounter"})

    def test_rebuild_handles_missing_cast(self):
        # Remove cast from json
        json_copy = self.mock_json.copy()
        json_copy["cast"] = None
        
        self.context_map.rebuild(json_copy)
        
        characters = self.context_map.get_nodes_by_type(NODE_TYPE_CHARACTER)
        char_ids = {c["node_id"] for c in characters}
        
        # Aldric and Sera shouldn't be there (unless referenced elsewhere)
        self.assertNotIn("cast:aldric", char_ids)
        self.assertNotIn("cast:sera", char_ids)
        self.assertIn("player", char_ids)

    def test_edge_schema_fallback(self):
        self.context_map.rebuild(self.mock_json)
        
        # Jax relationship was "allied_with" -> ALLIED_WITH
        jax_node_id = "factions:thieves_guild:Jax"
        self.assertTrue(self.context_map.graph.has_edge("player", jax_node_id))
        self.assertEqual(self.context_map.graph["player"][jax_node_id]["relation"], "ALLIED_WITH")
        
        # Boss Maroni was "HOSTILE_TO" -> HOSTILE_TO
        self.assertTrue(self.context_map.graph.has_edge("player", "Boss Maroni"))
        self.assertEqual(self.context_map.graph["player"]["Boss Maroni"]["relation"], "HOSTILE_TO")
        
        # Sergeant Vance was "OWES_MONEY_TO" -> fallback to KNOWS
        self.assertTrue(self.context_map.graph.has_edge("player", "Sergeant Vance"))
        self.assertEqual(self.context_map.graph["player"]["Sergeant Vance"]["relation"], "KNOWS")

    def test_location_connections(self):
        self.context_map.rebuild(self.mock_json)
        
        # loc_1 connects to loc_2, loc_2 connects to loc_1
        related_to_loc1 = self.context_map.get_related("loc_1", edge_type="CONNECTED_TO", direction="both")
        related_ids = {r["node_id"] for r in related_to_loc1}
        self.assertIn("loc_2", related_ids)
        
        # Check bidirectional retrieval
        related_to_loc2 = self.context_map.get_related("loc_2", edge_type="CONNECTED_TO", direction="both")
        loc2_ids = {r["node_id"] for r in related_to_loc2}
        self.assertIn("loc_1", loc2_ids)
        self.assertIn("loc_3", loc2_ids)

    def test_faction_member_edges(self):
        self.context_map.rebuild(self.mock_json)
        
        members = self.context_map.get_faction_members("factions:thieves_guild")
        member_names = {m["name"] for m in members}
        self.assertEqual(member_names, {"Jax", "Miri"})

    def test_player_located_in(self):
        self.context_map.rebuild(self.mock_json)
        
        related = self.context_map.get_related("player", edge_type="LOCATED_IN", direction="out")
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["node_id"], "loc_1")

    def test_get_characters_at_location(self):
        self.context_map.rebuild(self.mock_json)
        
        # Player and active enemy should be located at loc_1
        chars = self.context_map.get_characters_at_location("loc_1")
        char_ids = {c["node_id"] for c in chars}
        self.assertIn("player", char_ids)
        self.assertIn("encounter:enemy", char_ids)

    def test_find_path(self):
        self.context_map.rebuild(self.mock_json)
        
        # Path from loc_1 to loc_3
        path = self.context_map.find_path("loc_1", "loc_3")
        self.assertEqual(path, ["loc_1", "loc_2", "loc_3"])
        
        # Path to non-existent node
        path = self.context_map.find_path("loc_1", "nonexistent")
        self.assertIsNone(path)

    def test_summary_output(self):
        self.context_map.rebuild(self.mock_json)
        summary = self.context_map.summary()
        
        self.assertIn("Nodes", summary)
        self.assertIn("Edges", summary)
        self.assertIn("Character", summary)
        self.assertIn("Location", summary)
        self.assertIn("Event", summary)

    def test_summary_empty(self):
        """Test summary output for an empty context map."""
        summary = self.context_map.summary()
        self.assertEqual(summary, "Nodes: 0. Edges: 0.")

    def test_summary_exact_counts(self):
        """Test summary with a small, manually constructed map."""
        # Add some nodes
        self.context_map.graph.add_node("char1", type=NODE_TYPE_CHARACTER)
        self.context_map.graph.add_node("char2", type=NODE_TYPE_CHARACTER)
        self.context_map.graph.add_node("loc1", type=NODE_TYPE_LOCATION)

        # Add some edges
        self.context_map.graph.add_edge("char1", "char2", relation="KNOWS")
        self.context_map.graph.add_edge("char1", "loc1", relation="LOCATED_IN")
        self.context_map.graph.add_edge("char2", "loc1", relation="LOCATED_IN")

        summary = self.context_map.summary()
        # Nodes: 2 Character, 1 Location
        # Edges: 1 KNOWS, 2 LOCATED_IN
        expected = "Nodes: 2 Character, 1 Location. Edges: 1 KNOWS, 2 LOCATED_IN."
        self.assertEqual(summary, expected)

    def test_summary_unknown_types(self):
        """Test summary handles missing type/relation attributes gracefully."""
        self.context_map.graph.add_node("node1") # Missing 'type'
        self.context_map.graph.add_node("node2") # Missing 'type'

        self.context_map.graph.add_edge("node1", "node2") # Missing 'relation'

        summary = self.context_map.summary()
        self.assertEqual(summary, "Nodes: 2 Unknown. Edges: 1 Unknown.")


if __name__ == "__main__":
    unittest.main()
