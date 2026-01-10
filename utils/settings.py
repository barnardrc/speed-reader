"""

"""

# utils/settings.py
import json
import os
from utils.dependents import HardwareMonitor

SETTINGS_FILE = "speed_reader_settings.json"

# Moved here from main file
PAUSE_CONFIG = {
    "period":      (2.0, "End of Sentence (. ? !):"),
    "comma":       (1.5, "Comma (, : ;):"),
    "hyphen":      (1.2, "Short Hyphen (-):"),
    "long_hyphen": (2.5, "Long Hyphen (—):"),
    "parens":      (1.5, "Parentheses ( ):"),
    "header":      (3.0, "Headers (ALL CAPS):"),
    "ellipsis":    (3.0, "Ellipsis (...):")
}

DEFAULT_SETTINGS = {
    "first_run": True,
    "tutorial_complete": False,
    "wpm": 300, 
    "opacity": 50, 
    "context_range": 20, 
    "flank_opacity": 60,
    "ai_enabled": True, 
    "ai_frequency": 1000, 
    "entity_enabled": True, 
    "entity_frequency": 300,
    "ai_backend_type": "ollama",
    "ollama_url": "http://localhost:11434",
    "ai_model": "llama3",
    "ai_timeout": 30,
    "books": {}
}

# Inject Pause Defaults into the main dictionary
for key, (val, _) in PAUSE_CONFIG.items():
    DEFAULT_SETTINGS[f"{key}_delay"] = val

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return _perform_first_run_setup()

    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            # Merge defaults to handle updates/missing keys
            for key, val in DEFAULT_SETTINGS.items():
                if key not in settings:
                    settings[key] = val
            return settings
    except (json.JSONDecodeError, IOError):
        return _perform_first_run_setup()

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except IOError as e:
        print(f"Error saving settings: {e}")

def complete_first_run():
    """
    Call this when the user finishes the tutorial or setup wizard.
    Sets 'first_run' to False and saves settings.
    """
    settings = load_settings()
    settings["first_run"] = False
    save_settings(settings)
    print("First Run Setup Complete.")

def _perform_first_run_setup():
    print("--- FIRST RUN DETECTED ---")
    settings = DEFAULT_SETTINGS.copy()
    settings["first_run"] = True
    
    # Run Hardware Check
    monitor = HardwareMonitor()
    rec = monitor.get_recommendation()
    print(rec)
    # Auto-configure model based on hardware
    if rec["can_run_70b"]:
        settings["ai_model"] = "llama3:70b"
    elif rec["can_run_13b"]:
        settings["ai_model"] = "mistral:latest"
    elif rec["can_run_7b"]:
        settings["ai_model"] = "llama3:8b"
    else:
        settings["ai_model"] = "tinyllama"
        
    save_settings(settings)
    return settings