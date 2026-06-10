from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class JourneyNode:
    id: str
    type: str  # "Combat", "Hazard", "Event", "Camp", "Merchant", "Start", "Destination"
    name: str
    description: str
    connections: List[str] = field(default_factory=list)
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "connections": self.connections,
            "resolved": self.resolved
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JourneyNode":
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "Event"),
            name=data.get("name", "Unknown Node"),
            description=data.get("description", ""),
            connections=data.get("connections", []),
            resolved=data.get("resolved", False)
        )

@dataclass
class JourneyMap:
    destination_location_id: str
    destination_name: str
    nodes: Dict[str, JourneyNode] = field(default_factory=dict)
    layers: List[List[str]] = field(default_factory=list)
    current_node_id: str = ""

    def to_dict(self) -> dict:
        return {
            "destination_location_id": self.destination_location_id,
            "destination_name": self.destination_name,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "layers": self.layers,
            "current_node_id": self.current_node_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JourneyMap":
        if not data:
            return None
        j = cls(
            destination_location_id=data.get("destination_location_id", ""),
            destination_name=data.get("destination_name", ""),
            layers=data.get("layers", []),
            current_node_id=data.get("current_node_id", "")
        )
        nodes_data = data.get("nodes", {})
        for nid, ndata in nodes_data.items():
            j.nodes[nid] = JourneyNode.from_dict(ndata)
        return j

    def get_current_node(self) -> Optional[JourneyNode]:
        if not self.current_node_id:
            return None
        return self.nodes.get(self.current_node_id)

def generate_journey_map(llm_client, current_name: str, dest_id: str, dest_name: str, genre: str, active_quests: list = None) -> Optional[JourneyMap]:
    import json
    
    quest_str = ""
    if active_quests:
        quest_str = "\nActive Quests:\n" + "\n".join([f"- {q.name}: {q.description}" for q in active_quests])
        quest_str += "\n\nCRITICAL: Weave themes, encounters, or hazards directly related to these quests into the node names and descriptions!\n"

    prompt = f"""The player is at '{current_name}' and is embarking on a journey to '{dest_name}'.
Based on the '{genre}' genre, generate a branching 'Slay the Spire' style pointcrawl node map for this journey.{quest_str}
The map must have exactly 3 layers (depths) of intermediate nodes between the start and the destination.
The player will start by choosing one of the nodes in Layer 1.

Valid node types: Combat, Hazard, Event, Camp, Merchant.

Output ONLY a valid JSON object in this exact format:
{{
  "layers": [["node1", "node2"], ["node3", "node4", "node5"], ["node6", "node7"]],
  "nodes": {{
    "node1": {{"name": "Whispering Woods", "type": "Event", "description": "A dark, eerie forest.", "connections": ["node3", "node4"]}},
    "node3": {{"name": "Bandit Toll", "type": "Combat", "description": "A blocked road.", "connections": ["node6"]}}
  }}
}}
Make sure every node in layer N has connections to at least one node in layer N+1.
Layer 3 nodes should NOT have connections (they will inherently connect to the final destination).
"""
    try:
        res = llm_client.generate(prompt)
        clean = res.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        
        jmap = JourneyMap(destination_location_id=dest_id, destination_name=dest_name)
        
        # Parse layers
        layer_ids = data.get("layers", [])
        jmap.layers = layer_ids
        
        # Parse nodes
        nodes_data = data.get("nodes", {})
        for nid, ndata in nodes_data.items():
            jmap.nodes[nid] = JourneyNode(
                id=nid,
                type=ndata.get("type", "Event"),
                name=ndata.get("name", "Unknown Node"),
                description=ndata.get("description", ""),
                connections=ndata.get("connections", []),
                resolved=False
            )
            
        return jmap
    except Exception as e:
        print(f"Failed to generate journey map: {e}")
        return None

def render_journey_map(jmap: JourneyMap, theme):
    print(f"\n--- JOURNEY TO {jmap.destination_name.upper()} ---")
    
    current_layer_idx = -1
    if jmap.current_node_id:
        for i, layer in enumerate(jmap.layers):
            if jmap.current_node_id in layer:
                current_layer_idx = i
                break
                
    for i, layer in enumerate(jmap.layers):
        layer_str = f"Depth {i+1}: "
        node_strs = []
        for nid in layer:
            n = jmap.nodes.get(nid)
            if not n: continue
            
            marker = " "
            if nid == jmap.current_node_id:
                marker = "*"
            elif n.resolved:
                marker = "x"
                
            node_strs.append(f"[{marker}] {n.name} ({n.type})")
            
        print(layer_str + " | ".join(node_strs))
        if i < len(jmap.layers) - 1:
            print("         |")
            
    print(f"Destination: {jmap.destination_name}\n")
