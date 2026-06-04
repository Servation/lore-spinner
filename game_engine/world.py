from dataclasses import dataclass, field
from typing import List, Dict, Any
from game_engine.ability_system import AbilityTag

@dataclass
class Quest:
    id: str
    name: str
    description: str
    status: str = "active"  # "active", "completed", "failed"
    positive_consequence: str = ""
    negative_consequence: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "positive_consequence": self.positive_consequence,
            "negative_consequence": self.negative_consequence,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Quest":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Unknown Quest"),
            description=data.get("description", ""),
            status=data.get("status", "active"),
            positive_consequence=data.get("positive_consequence", ""),
            negative_consequence=data.get("negative_consequence", ""),
            notes=data.get("notes", [])
        )

@dataclass
class Location:
    id: str
    name: str
    description: str
    type: str # 'city', 'dungeon', 'landmark'
    discovered_turn: int
    connections: List[str] = field(default_factory=list)
    scope: str = "node" # 'node', 'region'
    parent_region_id: str = ""
    theme: str = "default"
    rumors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "discovered_turn": self.discovered_turn,
            "connections": self.connections,
            "scope": self.scope,
            "parent_region_id": self.parent_region_id,
            "theme": self.theme,
            "rumors": self.rumors
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Location':
        import uuid
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            description=data["description"],
            type=data["type"],
            discovered_turn=data["discovered_turn"],
            connections=data.get("connections", []),
            scope=data.get("scope", "node"),
            parent_region_id=data.get("parent_region_id", ""),
            theme=data.get("theme", "default"),
            rumors=data.get("rumors", [])
        )

@dataclass
class WorldAspect:
    name: str
    type: str  # "Nemesis", "Doom Clock", "Heat", "Trauma", "Rule"
    description: str
    intensity: int = 1

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "intensity": self.intensity
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldAspect":
        return cls(
            name=data.get("name", "Unknown Aspect"),
            type=data.get("type", "Rule"),
            description=data.get("description", ""),
            intensity=data.get("intensity", 1)
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
    campaign_arc: str = ""
    escalated_rumors: List[str] = field(default_factory=list)
    world_aspects: List[WorldAspect] = field(default_factory=list)
    world_bible_summary: str = ""
    current_location_id: str = ""
    weather: str = ""        # Descriptive weather string, e.g. "Heavy Rain"
    hunger: int = 0           # 0=Full, 1=Hungry, 2=Starving
    fatigue: int = 0          # 0=Rested, 1=Tired, 2=Exhausted
    # --- Situational Override States ---
    # These are set/cleared mechanically by DM tools so overrides cannot be forgotten
    survival_situation: str = ""   # Non-empty = Survival Override active; describes the threat
    social_encounter: str = ""     # Non-empty = Social Override active; describes who and the stakes
    is_camping: bool = False        # True = Camping Override active

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

    def add_quest(self, quest_id: str, name: str, description: str, pos_conseq: str = "", neg_conseq: str = "") -> None:
        # Check if already exists
        for q in self.active_quests:
            if q.id == quest_id:
                return
        self.active_quests.append(Quest(id=quest_id, name=name, description=description, positive_consequence=pos_conseq, negative_consequence=neg_conseq))

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

    def add_aspect(self, name: str, a_type: str, description: str, intensity: int = 1) -> None:
        clean_name = name.strip().lower()
        for aspect in self.world_aspects:
            if aspect.name.lower() == clean_name:
                aspect.intensity = intensity
                aspect.description = description
                return
        self.world_aspects.append(WorldAspect(name=name, type=a_type, description=description, intensity=intensity))

    def remove_aspect(self, name: str) -> bool:
        clean_name = name.strip().lower()
        initial_len = len(self.world_aspects)
        self.world_aspects = [a for a in self.world_aspects if a.name.lower() != clean_name]
        return len(self.world_aspects) < initial_len

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
            "discovered_locations": [l.to_dict() for l in self.discovered_locations],
            "campaign_arc": self.campaign_arc,
            "escalated_rumors": self.escalated_rumors,
            "world_aspects": [a.to_dict() for a in self.world_aspects],
            "world_bible_summary": self.world_bible_summary,
            "current_location_id": self.current_location_id,
            "weather": self.weather,
            "hunger": self.hunger,
            "fatigue": self.fatigue,
            "survival_situation": self.survival_situation,
            "social_encounter": self.social_encounter,
            "is_camping": self.is_camping
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
            discovered_locations=[Location.from_dict(ld) for ld in data.get("discovered_locations", [])],
            campaign_arc=data.get("campaign_arc", ""),
            escalated_rumors=data.get("escalated_rumors", []),
            world_aspects=[WorldAspect.from_dict(ad) for ad in data.get("world_aspects", [])],
            world_bible_summary=data.get("world_bible_summary", ""),
            current_location_id=data.get("current_location_id", ""),
            weather=data.get("weather", ""),
            hunger=data.get("hunger", 0),
            fatigue=data.get("fatigue", 0),
            survival_situation=data.get("survival_situation", ""),
            social_encounter=data.get("social_encounter", ""),
            is_camping=data.get("is_camping", False)
        )
