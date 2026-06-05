import networkx as nx
from typing import List, Dict, Any, Optional, Set

# --- Strict Edge Schema ---
ALLOWED_EDGE_TYPES: Set[str] = {
    "KNOWS",
    "HOSTILE_TO",
    "ALLIED_WITH",
    "LOCATED_IN",
    "MEMBER_OF",
    "CONNECTED_TO",   # Location ↔ Location connections
}
FALLBACK_EDGE_TYPE: str = "KNOWS"

# --- Node Types ---
NODE_TYPE_CHARACTER = "Character"
NODE_TYPE_LOCATION  = "Location"
NODE_TYPE_EVENT     = "Event"


class ContextMap:
    def __init__(self) -> None:
        """Initialize an empty NetworkX Directed Graph."""
        self.graph = nx.DiGraph()
        self.current_location_id: Optional[str] = None

    def _normalize_edge_type(self, relation: str) -> str:
        """Normalize edge type to uppercase, strip whitespace, and check against ALLOWED_EDGE_TYPES.
        
        If not allowed, falls back to FALLBACK_EDGE_TYPE.
        """
        if not relation:
            return FALLBACK_EDGE_TYPE
        normalized = relation.strip().upper()
        if normalized in ALLOWED_EDGE_TYPES:
            return normalized
        
        # Check for common keywords in free-form descriptions
        if "HOSTILE" in normalized or "ENEMY" in normalized:
            return "HOSTILE_TO"
        if "ALLY" in normalized or "ALLIED" in normalized or "FRIEND" in normalized:
            return "ALLIED_WITH"
        if "MEMBER" in normalized or "BELONGS TO" in normalized:
            return "MEMBER_OF"
        if "CONNECTED" in normalized:
            return "CONNECTED_TO"
        if "LOCATED" in normalized:
            return "LOCATED_IN"
            
        return FALLBACK_EDGE_TYPE

    def _find_node_by_name(self, name: str) -> Optional[str]:
        """Look up character node ID by name."""
        if not name:
            return None
        name_lower = name.lower()
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("type") == NODE_TYPE_CHARACTER and attrs.get("name", "").lower() == name_lower:
                return node_id
        return None

    def rebuild(self, json_data: Dict[str, Any]) -> None:
        """Clear the existing graph and rebuild it from the provided JSON data dictionary."""
        self.graph.clear()
        self.current_location_id = None
        
        # Safe extraction of components
        world_state = json_data.get("world_state") or {}
        character_data = json_data.get("character") or {}
        factions_data = json_data.get("factions") or {}
        encounters_data = json_data.get("encounters") or {}
        cast_data = json_data.get("cast")  # could be None
        
        # Capture current location ID
        self.current_location_id = world_state.get("current_location_id") or character_data.get("position")
        
        # Build components in dependency order
        self._build_locations(world_state)
        self._build_factions(factions_data)
        if cast_data:
            self._build_cast(cast_data)
        self._build_player(character_data)
        self._build_quests(world_state)
        self._build_encounter(encounters_data)

    def _build_locations(self, world_state: Dict[str, Any]) -> None:
        """Build Location nodes and CONNECTED_TO edges."""
        locations = world_state.get("discovered_locations", [])
        if not isinstance(locations, list):
            return
            
        for loc in locations:
            if not isinstance(loc, dict) or "id" not in loc:
                continue
            loc_id = loc["id"]
            self.graph.add_node(
                loc_id,
                type=NODE_TYPE_LOCATION,
                name=loc.get("name"),
                description=loc.get("description"),
                location_type=loc.get("type"),
                scope=loc.get("scope"),
                theme=loc.get("theme")
            )
            
        # Add connections after all location nodes are created
        for loc in locations:
            if not isinstance(loc, dict) or "id" not in loc:
                continue
            loc_id = loc["id"]
            connections = loc.get("connections", [])
            if isinstance(connections, list):
                for target_id in connections:
                    if target_id in self.graph:
                        self.graph.add_edge(loc_id, target_id, relation="CONNECTED_TO")

    def _build_factions(self, factions_data: Dict[str, Any]) -> None:
        """Build Faction character nodes and Faction NPC character nodes with MEMBER_OF edges."""
        factions = factions_data.get("factions", {})
        if not isinstance(factions, dict):
            return
            
        for faction_id, info in factions.items():
            if not isinstance(info, dict):
                continue
            # Add Faction node as a Character node
            self.graph.add_node(
                faction_id,
                type=NODE_TYPE_CHARACTER,
                name=info.get("name"),
                reputation=info.get("reputation"),
                is_faction=True,
                is_cast=False,
                is_player=False
            )
            
            # Add Faction NPCs
            npcs = info.get("npcs", {})
            if isinstance(npcs, dict):
                for npc_name, npc_desc in npcs.items():
                    npc_node_id = f"{faction_id}:{npc_name}"
                    self.graph.add_node(
                        npc_node_id,
                        type=NODE_TYPE_CHARACTER,
                        name=npc_name,
                        description=npc_desc,
                        is_faction=False,
                        is_cast=False,
                        is_player=False
                    )
                    self.graph.add_edge(npc_node_id, faction_id, relation="MEMBER_OF")

    def _build_cast(self, cast_data: Dict[str, Any]) -> None:
        """Build cast Character nodes."""
        if not isinstance(cast_data, dict):
            return
            
        for category in ["spine_characters", "promoted_npcs"]:
            chars = cast_data.get(category, {})
            if not isinstance(chars, dict):
                continue
            for char_id, info in chars.items():
                if not isinstance(info, dict):
                    continue
                
                # Check if a character node already exists with this ID or matches by name
                node_id = char_id
                name = info.get("name")
                
                # If name matches an existing faction NPC or other node, merge them or use the same ID
                existing_id = self._find_node_by_name(name)
                if existing_id:
                    node_id = existing_id
                
                if node_id in self.graph:
                    # Update existing node
                    self.graph.nodes[node_id].update({
                        "is_cast": True,
                        "role": info.get("role", self.graph.nodes[node_id].get("role")),
                        "status": info.get("status", self.graph.nodes[node_id].get("status"))
                    })
                else:
                    # Create new character node
                    self.graph.add_node(
                        node_id,
                        type=NODE_TYPE_CHARACTER,
                        name=name,
                        role=info.get("role"),
                        status=info.get("status"),
                        is_cast=True,
                        is_faction=False,
                        is_player=False
                    )

    def _build_player(self, character_data: Dict[str, Any]) -> None:
        """Build player Character node, LOCATED_IN edge, and relationship edges."""
        if not isinstance(character_data, dict):
            return
            
        player_name = character_data.get("name", "Player")
        # Add or update player node
        self.graph.add_node(
            "player",
            type=NODE_TYPE_CHARACTER,
            name=player_name,
            is_player=True,
            is_cast=False,
            is_faction=False
        )
        
        # Link player to current location
        position = character_data.get("position")
        if position:
            # Check if position exists in the graph, if not, check self.current_location_id
            loc_id = position if position in self.graph else self.current_location_id
            if loc_id and loc_id in self.graph:
                self.graph.add_edge("player", loc_id, relation="LOCATED_IN")
            elif position:
                # Fallback: create a temporary location node if not present
                self.graph.add_node(position, type=NODE_TYPE_LOCATION, name=position)
                self.graph.add_edge("player", position, relation="LOCATED_IN")
        elif self.current_location_id and self.current_location_id in self.graph:
            self.graph.add_edge("player", self.current_location_id, relation="LOCATED_IN")
            
        # Parse relationships
        relationships = character_data.get("relationships", {})
        if isinstance(relationships, dict):
            for npc_name, rel_desc in relationships.items():
                if not npc_name:
                    continue
                # Resolve the NPC name to a node ID
                npc_node_id = self._find_node_by_name(npc_name)
                if not npc_node_id:
                    # If NPC doesn't exist yet in the graph, create a basic Character node
                    npc_node_id = npc_name
                    self.graph.add_node(
                        npc_node_id,
                        type=NODE_TYPE_CHARACTER,
                        name=npc_name,
                        is_player=False,
                        is_cast=False,
                        is_faction=False
                    )
                
                # Parse relation type from description
                relation_type = self._normalize_edge_type(rel_desc)
                self.graph.add_edge("player", npc_node_id, relation=relation_type)

    def _build_quests(self, world_state: Dict[str, Any]) -> None:
        """Build Event nodes from active quests."""
        quests = world_state.get("active_quests", [])
        if not isinstance(quests, list):
            return
            
        for quest in quests:
            if not isinstance(quest, dict) or "id" not in quest:
                continue
            quest_id = quest["id"]
            self.graph.add_node(
                quest_id,
                type=NODE_TYPE_EVENT,
                name=quest.get("name"),
                status=quest.get("status"),
                event_type="Quest"
            )
            # If the current location is known, link the quest to the location
            if self.current_location_id and self.current_location_id in self.graph:
                self.graph.add_edge(quest_id, self.current_location_id, relation="LOCATED_IN")

    def _build_encounter(self, encounters_data: Dict[str, Any]) -> None:
        """Build Character node for enemy and Event node for active encounter."""
        if not isinstance(encounters_data, dict):
            return
            
        active_encounter = encounters_data.get("active_encounter")
        if not isinstance(active_encounter, dict) or not active_encounter:
            return
            
        # Create encounter event node
        self.graph.add_node(
            "active_encounter",
            type=NODE_TYPE_EVENT,
            description=active_encounter.get("description"),
            event_type="Encounter"
        )
        
        # Link encounter to current location
        if self.current_location_id and self.current_location_id in self.graph:
            self.graph.add_edge("active_encounter", self.current_location_id, relation="LOCATED_IN")
            
        enemy = active_encounter.get("enemy")
        if isinstance(enemy, dict) and "name" in enemy:
            enemy_name = enemy["name"]
            self.graph.add_node(
                "encounter:enemy",
                type=NODE_TYPE_CHARACTER,
                name=enemy_name,
                hp=enemy.get("hp"),
                is_encounter_enemy=True,
                is_player=False,
                is_cast=False,
                is_faction=False
            )
            # Link enemy to active encounter
            self.graph.add_edge("encounter:enemy", "active_encounter", relation="LOCATED_IN")
            # Link enemy to current location
            if self.current_location_id and self.current_location_id in self.graph:
                self.graph.add_edge("encounter:enemy", self.current_location_id, relation="LOCATED_IN")
            # Link enemy to player as HOSTILE_TO
            self.graph.add_edge("encounter:enemy", "player", relation="HOSTILE_TO")

    # --- Query Methods ---

    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """Return all nodes of the specified type with their properties and node_id."""
        result = []
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("type") == node_type:
                result.append({"node_id": node_id, **attrs})
        return result

    def get_related(self, node_id: str, edge_type: Optional[str] = None, direction: str = "both") -> List[Dict[str, Any]]:
        """Return neighboring nodes, optionally filtered by edge type and direction ('in', 'out', 'both')."""
        if node_id not in self.graph:
            return []
            
        neighbor_ids = set()
        
        if direction in ("out", "both"):
            for _, target, edge_data in self.graph.out_edges(node_id, data=True):
                if edge_type is None or edge_data.get("relation") == edge_type:
                    neighbor_ids.add(target)
                    
        if direction in ("in", "both"):
            for source, _, edge_data in self.graph.in_edges(node_id, data=True):
                if edge_type is None or edge_data.get("relation") == edge_type:
                    neighbor_ids.add(source)
                    
        result = []
        for nid in neighbor_ids:
            if nid in self.graph:
                result.append({"node_id": nid, **self.graph.nodes[nid]})
        return result

    def get_characters_at_location(self, location_id: str) -> List[Dict[str, Any]]:
        """Return all Character nodes located at the given location."""
        # Query incoming LOCATED_IN edges to the location node
        candidates = self.get_related(location_id, edge_type="LOCATED_IN", direction="in")
        return [node for node in candidates if node.get("type") == NODE_TYPE_CHARACTER]

    def get_faction_members(self, faction_node_id: str) -> List[Dict[str, Any]]:
        """Return all Character nodes that are members of the given faction."""
        # Query incoming MEMBER_OF edges to the faction node
        candidates = self.get_related(faction_node_id, edge_type="MEMBER_OF", direction="in")
        return [node for node in candidates if node.get("type") == NODE_TYPE_CHARACTER]

    def find_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """Find the shortest path as a list of node IDs from source to target, or None."""
        if source_id not in self.graph or target_id not in self.graph:
            return None
        try:
            return nx.shortest_path(self.graph, source_id, target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_hostile_to(self, node_id: str) -> List[Dict[str, Any]]:
        """Return all nodes connected via HOSTILE_TO to or from the given node."""
        return self.get_related(node_id, edge_type="HOSTILE_TO", direction="both")

    def get_allies_of(self, node_id: str) -> List[Dict[str, Any]]:
        """Return all nodes connected via ALLIED_WITH to or from the given node."""
        return self.get_related(node_id, edge_type="ALLIED_WITH", direction="both")

    def summary(self) -> str:
        """Return a human-readable summary of the node and edge counts in the graph."""
        node_counts = {}
        for _, attrs in self.graph.nodes(data=True):
            ntype = attrs.get("type", "Unknown")
            node_counts[ntype] = node_counts.get(ntype, 0) + 1
            
        edge_counts = {}
        for _, _, edge_data in self.graph.edges(data=True):
            etype = edge_data.get("relation", "Unknown")
            edge_counts[etype] = edge_counts.get(etype, 0) + 1
            
        nodes_str = ", ".join(f"{count} {ntype}" for ntype, count in sorted(node_counts.items()))
        edges_str = ", ".join(f"{count} {etype}" for etype, count in sorted(edge_counts.items()))
        
        return f"Nodes: {nodes_str or '0'}. Edges: {edges_str or '0'}."
