import os
import json
import re
import shutil
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

# Root saves directory
SAVES_DIR = "saves"

def generate_slug(name: str) -> str:
    """Generates a URL-safe lowercase slug from a campaign name."""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s-]+", "-", s)
    return s.strip("-")

class SaveManager:
    @staticmethod
    def _get_campaign_path(campaign_slug: str) -> str:
        return os.path.join(SAVES_DIR, campaign_slug)

    @staticmethod
    def save_game(
        campaign_name: str, 
        character_data: dict, 
        world_state_data: dict, 
        factions_data: dict, 
        encounters_data: dict, 
        lore_data: dict
    ) -> str:
        """Saves all game components into the campaign folder under saves/slug/.
        
        Creates/updates meta.json for listing and searching saves.
        Returns the campaign_slug.
        """
        slug = generate_slug(campaign_name)
        campaign_path = SaveManager._get_campaign_path(slug)
        os.makedirs(campaign_path, exist_ok=True)
        
        # Save game state files
        with open(os.path.join(campaign_path, "character.json"), "w", encoding="utf-8") as f:
            json.dump(character_data, f, indent=4)
            
        with open(os.path.join(campaign_path, "world_state.json"), "w", encoding="utf-8") as f:
            json.dump(world_state_data, f, indent=4)
            
        with open(os.path.join(campaign_path, "factions.json"), "w", encoding="utf-8") as f:
            json.dump(factions_data, f, indent=4)
            
        with open(os.path.join(campaign_path, "encounters.json"), "w", encoding="utf-8") as f:
            json.dump(encounters_data, f, indent=4)
            
        with open(os.path.join(campaign_path, "lore.json"), "w", encoding="utf-8") as f:
            json.dump(lore_data, f, indent=4)
            
        # Create metadata
        meta = {
            "campaign_name": campaign_name,
            "campaign_slug": slug,
            "character_name": character_data.get("name", "Unknown"),
            "genre": world_state_data.get("setting_genre", "Fantasy"),
            "turn_count": world_state_data.get("turn_count", 0),
            "last_played": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(os.path.join(campaign_path, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=4)
            
        # Update centralized index
        index = SaveManager._load_index()
        # Remove existing entry if it exists
        index = [s for s in index if s.get("campaign_slug") != slug]
        index.append(meta)
        SaveManager._save_index(index)

        return slug

    @staticmethod
    def load_game(campaign_slug: str) -> Optional[Tuple[dict, dict, dict, dict, dict]]:
        """Loads all game components from the campaign folder.
        
        Returns a tuple of (character, world_state, factions, encounters, lore) or None if path doesn't exist.
        """
        campaign_path = SaveManager._get_campaign_path(campaign_slug)
        if not os.path.exists(campaign_path):
            return None
            
        try:
            with open(os.path.join(campaign_path, "character.json"), "r", encoding="utf-8") as f:
                char_data = json.load(f)
            with open(os.path.join(campaign_path, "world_state.json"), "r", encoding="utf-8") as f:
                world_data = json.load(f)
            with open(os.path.join(campaign_path, "factions.json"), "r", encoding="utf-8") as f:
                factions_data = json.load(f)
            with open(os.path.join(campaign_path, "encounters.json"), "r", encoding="utf-8") as f:
                encounters_data = json.load(f)
            with open(os.path.join(campaign_path, "lore.json"), "r", encoding="utf-8") as f:
                lore_data = json.load(f)
                
            return char_data, world_data, factions_data, encounters_data, lore_data
        except Exception:
            return None


    @staticmethod
    def _get_index_path() -> str:
        return os.path.join(SAVES_DIR, "saves_index.json")

    @staticmethod
    def _load_index() -> List[dict]:
        index_path = SaveManager._get_index_path()
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    @staticmethod
    def _save_index(index_data: List[dict]) -> None:
        if not os.path.exists(SAVES_DIR):
            os.makedirs(SAVES_DIR, exist_ok=True)
        index_path = SaveManager._get_index_path()
        try:
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=4)
        except Exception:
            pass

    @staticmethod
    def _rebuild_index() -> List[dict]:
        if not os.path.exists(SAVES_DIR):
            return []
            
        saves = []
        for slug in os.listdir(SAVES_DIR):
            if slug == "saves_index.json":
                continue
            campaign_path = SaveManager._get_campaign_path(slug)
            meta_path = os.path.join(campaign_path, "meta.json")
            if os.path.isdir(campaign_path) and os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    saves.append(meta)
                except Exception:
                    pass
                    
        SaveManager._save_index(saves)
        return saves

    @staticmethod
    def list_saves() -> List[dict]:
        """Lists metadata of all available campaign saves."""
        if not os.path.exists(SAVES_DIR):
            return []

        index_path = SaveManager._get_index_path()

        # If no index, rebuild it
        if not os.path.exists(index_path):
            saves = SaveManager._rebuild_index()
        else:
            # For O(1) directory validation, we can check the modification time of SAVES_DIR
            # If the directory was modified (e.g. folder added/removed), we rebuild.
            # We also check the mtime of the index file itself. If index is older than SAVES_DIR, it's stale.
            saves_dir_mtime = os.stat(SAVES_DIR).st_mtime
            index_mtime = os.stat(index_path).st_mtime

            # Additional check: If index_mtime is older than the mtime of ANY meta.json
            # it means a save was updated but the index wasn't (e.g. manual file edit)
            # To avoid an O(N) loop here, we rely on the fact that save_game() updates the index.
            # We will trust the index unless the SAVES_DIR structure changes (detected above).

            if saves_dir_mtime > index_mtime:
                saves = SaveManager._rebuild_index()
            else:
                saves = SaveManager._load_index()

        # Sort by last played date descending
        saves.sort(key=lambda x: x.get("last_played", ""), reverse=True)
        return saves
    @staticmethod
    def search_saves(query: str) -> List[dict]:
        """Searches campaign saves by campaign name, character name, or genre (case-insensitive)."""
        all_saves = SaveManager.list_saves()
        q = query.strip().lower()
        if not q:
            return all_saves
            
        results = []
        for save in all_saves:
            name = save.get("campaign_name", "").lower()
            char = save.get("character_name", "").lower()
            genre = save.get("genre", "").lower()
            
            if q in name or q in char or q in genre or q in save.get("campaign_slug", ""):
                results.append(save)
        return results

    @staticmethod
    def delete_save(campaign_slug: str) -> bool:
        """Deletes the campaign folder."""
        campaign_path = SaveManager._get_campaign_path(campaign_slug)
        if os.path.exists(campaign_path):
            try:
                shutil.rmtree(campaign_path)

                # Update centralized index
                index = SaveManager._load_index()
                index = [s for s in index if s.get("campaign_slug") != campaign_slug]
                SaveManager._save_index(index)

                return True
            except Exception:
                return False
        return False
