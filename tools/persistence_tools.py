# persistence_tools.py - Shared persistence tools
from persistence.save_manager import SaveManager
from persistence.log_manager import write_dm_log, read_dm_log

def save_campaign_state(campaign_name: str, character_data: dict, world_data: dict, faction_data: dict, encounter_data: dict, lore_data: dict) -> None:
    """Wrapper to save the entire campaign state via SaveManager."""
    SaveManager.save_game(campaign_name, character_data, world_data, faction_data, encounter_data, lore_data)

def load_campaign_state(campaign_slug: str) -> dict:
    """Wrapper to load the entire campaign state via SaveManager."""
    return SaveManager.load_game(campaign_slug)

def write_log(campaign_slug: str, text: str, llm_client) -> str:
    """Wrapper to write a DM log entry via LogManager."""
    return write_dm_log(campaign_slug, text, llm_client)

def read_log(campaign_slug: str, limit: int = 10) -> str:
    """Wrapper to read DM log entries via LogManager."""
    return read_dm_log(campaign_slug, limit)
