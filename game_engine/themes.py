from dataclasses import dataclass
from questionary import Style

@dataclass
class UITheme:
    name: str
    color_dm: str
    color_ooc: str
    color_system: str
    color_title: str
    color_error: str
    q_style: Style

def _create_style(primary: str, secondary: str) -> Style:
    return Style([
        ('qmark', f'fg:{primary} bold'),
        ('question', 'bold'),
        ('answer', f'fg:{secondary} bold'),
        ('pointer', f'fg:{primary} bold'),
        ('highlighted', f'fg:{secondary} bold'),
        ('selected', f'fg:{secondary}'),
        ('separator', 'fg:#555555'),
        ('instruction', 'fg:#888888 italic')
    ])

# Pre-defined palettes
THEMES = {
    "default": UITheme(
        name="default",
        color_dm="\033[96m",      # Cyan
        color_ooc="\033[93m",     # Yellow
        color_system="\033[90m",  # Gray
        color_title="\033[95m",   # Magenta
        color_error="\033[91m",   # Red
        q_style=_create_style('#ff00ff', '#00ffff') # Magenta/Cyan
    ),
    "fire": UITheme(
        name="fire",
        color_dm="\033[91m",      # Red
        color_ooc="\033[93m",     # Yellow
        color_system="\033[90m",  # Gray
        color_title="\033[91m",   # Red
        color_error="\033[91m",   # Red
        q_style=_create_style('#ff0000', '#ff8800') # Red/Orange
    ),
    "forest": UITheme(
        name="forest",
        color_dm="\033[92m",      # Green
        color_ooc="\033[93m",     # Yellow
        color_system="\033[90m",  # Gray
        color_title="\033[92m",   # Green
        color_error="\033[91m",   # Red
        q_style=_create_style('#00ff00', '#aaaa00') # Green/Olive
    ),
    "ice": UITheme(
        name="ice",
        color_dm="\033[96m",      # Cyan
        color_ooc="\033[97m",     # White
        color_system="\033[90m",  # Gray
        color_title="\033[94m",   # Blue
        color_error="\033[91m",   # Red
        q_style=_create_style('#00ffff', '#ffffff') # Cyan/White
    ),
    "dark": UITheme(
        name="dark",
        color_dm="\033[35m",      # Purple
        color_ooc="\033[90m",     # Gray
        color_system="\033[30m",  # Dark Gray
        color_title="\033[35m",   # Purple
        color_error="\033[91m",   # Red
        q_style=_create_style('#880088', '#555555') # Purple/Gray
    ),
    "royal": UITheme(
        name="royal",
        color_dm="\033[93m",      # Gold
        color_ooc="\033[97m",     # White
        color_system="\033[90m",  # Gray
        color_title="\033[93m",   # Gold
        color_error="\033[91m",   # Red
        q_style=_create_style('#ffcc00', '#ffffff') # Gold/White
    ),
    "cyberpunk": UITheme(
        name="cyberpunk",
        color_dm="\033[95m",      # Pink
        color_ooc="\033[96m",     # Cyan
        color_system="\033[90m",  # Gray
        color_title="\033[96m",   # Cyan
        color_error="\033[91m",   # Red
        q_style=_create_style('#ff00ff', '#00ffff') # Neon Pink/Cyan
    ),
    "desert": UITheme(
        name="desert",
        color_dm="\033[33m",      # Yellow
        color_ooc="\033[93m",     # Bright Yellow
        color_system="\033[90m",  # Gray
        color_title="\033[33m",   # Yellow
        color_error="\033[91m",   # Red
        q_style=_create_style('#ddaa00', '#ffcc00') # Sand/Gold
    ),
    "water": UITheme(
        name="water",
        color_dm="\033[94m",      # Light Blue
        color_ooc="\033[96m",     # Cyan
        color_system="\033[90m",  # Gray
        color_title="\033[94m",   # Light Blue
        color_error="\033[91m",   # Red
        q_style=_create_style('#0088ff', '#00ffff') # Blue/Cyan
    ),
    "holy": UITheme(
        name="holy",
        color_dm="\033[97m",      # Bright White
        color_ooc="\033[93m",     # Gold
        color_system="\033[90m",  # Gray
        color_title="\033[97m",   # Bright White
        color_error="\033[91m",   # Red
        q_style=_create_style('#ffffff', '#ffcc00') # White/Gold
    )
}

VALID_THEMES_LIST = list(THEMES.keys())

def get_theme(name: str) -> UITheme:
    return THEMES.get(name.lower(), THEMES["default"])
