import yaml
import os
from pathlib import Path
from typing import Dict, Any

def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file. If None, tries default locations.
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """
    if config_path is None:
        # Try multiple possible locations
        possible_paths = [
            "app/config.yaml",
            os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
            Path(__file__).parent.parent / "config.yaml"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if config_path is None:
            raise FileNotFoundError(
                "Config file not found. Tried: " + ", ".join(possible_paths)
            )
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            if config is None:
                raise ValueError("Config file is empty or invalid")
            return config
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error loading config file: {str(e)}")

# Load config at module level
try:
    CONFIG = load_config()
except Exception as e:
    # Fallback to minimal config if loading fails
    CONFIG = {
        "xp_per_rupee": 1,
        "max_xp_per_txn": 500,
        "persona_multipliers": {
            "NEW": 1.5,
            "RETURNING": 1.2,
            "POWER": 1.0
        },
        "daily_cac_limit": {
            "NEW": 200,
            "RETURNING": 150,
            "POWER": 100
        },
        "gold_reward_value": 50,
        "feature_flags": {
            "prefer_xp": True,
            "prefer_gold": False,
            "cooldown_enabled": True
        },
        "policy_version": "v1"
    }
    # In production, you might want to log this error
    print(f"Warning: Failed to load config file, using defaults: {e}")