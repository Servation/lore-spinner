from dataclasses import dataclass, field
from typing import List, Dict, Any
from game_engine.ability_system import AbilityTag

@dataclass
class Quest:
    id: str
    name: str
    description: str
    status: str = "active"  # "active", "completed", "failed"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Quest":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Unknown Quest"),
            description=data.get("description", ""),
            status=data.get("status", "active"),
            notes=data.get("notes", [])
        )

@dataclass
class Location:
    name: str
    description: str
    type: str  # "city", "natural wonder", "point of interest", "dungeon", etc.
    discovered_turn: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "discovered_turn": self.discovered_turn
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Location":
        return cls(
            name=data.get("name", "Unknown Location"),
            description=data.get("description", ""),
            type=data.get("type", "point of interest"),
            discovered_turn=data.get("discovered_turn", 0)
        )

@dataclass
class WorldState:
    setting_genre: str = "Fantasy"
    setting_description: str = ""
    current_location: str = "Start"
    time_of_day: str = "Morning"  # Morning, Noon, Afternoon, Dusk, Night, Midnight
    turn_count: int = 0
    dm_traits: List[str] = field(default_factory=list)
    active_quests: List[Quest] = field(default_factory=list)
    environmental_modifiers: List[AbilityTag] = field(default_factory=list)
    next_heartbeat_turn: int = 0
    last_narrative: str = ""
    discovered_locations: List[Location] = field(default_factory=list)

    TIMES_OF_DAY = ["Morning", "Noon", "Afternoon", "Dusk", "Night", "Midnight"]

    def advance_time(self) -> str:
        """Advances the time of day to the next phase and returns it."""
        try:
            curr_idx = self.TIMES_OF_DAY.index(self.time_of_day)
            next_idx = (curr_idx + 1) % len(self.TIMES_OF_DAY)
            self.time_of_day = self.TIMES_OF_DAY[next_idx]
        except ValueError:
            self.time_of_day = "Morning"
        return self.time_of_day

    def increment_turn(self) -> int:
        self.turn_count += 1
        return self.turn_count

    def add_environmental_modifier(self, name: str, modifier: int) -> None:
        clean_name = name.strip().lower()
        # Remove existing if any
        self.environmental_modifiers = [t for t in self.environmental_modifiers if t.name != clean_name]
        self.environmental_modifiers.append(AbilityTag(name=clean_name, modifier=modifier, source="environment"))

    def remove_environmental_modifier(self, name: str) -> None:
        clean_name = name.strip().lower()
        self.environmental_modifiers = [t for t in self.environmental_modifiers if t.name != clean_name]

    def add_quest(self, quest_id: str, name: str, description: str) -> None:
        # Check if already exists
        for q in self.active_quests:
            if q.id == quest_id:
                return
        self.active_quests.append(Quest(id=quest_id, name=name, description=description))

    def update_quest_status(self, quest_id: str, status: str) -> bool:
        for q in self.active_quests:
            if q.id == quest_id:
                q.status = status
                return True
        return False

    def add_quest_note(self, quest_id: str, note: str) -> bool:
        for q in self.active_quests:
            if q.id == quest_id:
                q.notes.append(note)
                return True
        return False

    def to_dict(self) -> dict:
        return {
            "setting_genre": self.setting_genre,
            "setting_description": self.setting_description,
            "current_location": self.current_location,
            "time_of_day": self.time_of_day,
            "turn_count": self.turn_count,
            "dm_traits": self.dm_traits,
            "active_quests": [q.to_dict() for q in self.active_quests],
            "environmental_modifiers": [
                {
                    "name": t.name,
                    "modifier": t.modifier,
                    "usage_count": t.usage_count,
                    "source": t.source
                }
                for t in self.environmental_modifiers
            ],
            "next_heartbeat_turn": self.next_heartbeat_turn,
            "last_narrative": self.last_narrative,
            "discovered_locations": [l.to_dict() for l in self.discovered_locations]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldState":
        if not data:
            return cls()
            
        quests_data = data.get("active_quests", [])
        env_mods_data = data.get("environmental_modifiers", [])
        
        env_mods = []
        for em in env_mods_data:
            env_mods.append(AbilityTag(
                name=em.get("name", ""),
                modifier=em.get("modifier", 0),
                usage_count=em.get("usage_count", 0),
                source=em.get("source", "environment")
            ))
            
        return cls(
            setting_genre=data.get("setting_genre", "Fantasy"),
            setting_description=data.get("setting_description", ""),
            current_location=data.get("current_location", "Start"),
            time_of_day=data.get("time_of_day", "Morning"),
            turn_count=data.get("turn_count", 0),
            dm_traits=data.get("dm_traits", []),
            active_quests=[Quest.from_dict(qd) for qd in quests_data],
            environmental_modifiers=env_mods,
            next_heartbeat_turn=data.get("next_heartbeat_turn", 0),
            last_narrative=data.get("last_narrative", ""),
            discovered_locations=[Location.from_dict(ld) for ld in data.get("discovered_locations", [])]
        )
