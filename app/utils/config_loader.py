import yaml
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

_config_file_path: Optional[str] = None
_config_last_modified: float = 0
_config_cache: Optional[Dict[str, Any]] = None

def load_config(config_path: str = None, force_reload: bool = False) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file. If None, tries default locations.
        force_reload: If True, reload even if file hasn't changed
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """
    global _config_file_path, _config_last_modified, _config_cache
    
    if config_path is None and _config_file_path is not None:
        
        config_path = _config_file_path
    elif config_path is None:
        
        possible_paths = [
            "app/config.yaml",
            os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
            Path(__file__).parent.parent / "config.yaml"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                _config_file_path = path  
                break
        
        if config_path is None:
            raise FileNotFoundError(
                "Config file not found. Tried: " + ", ".join([str(p) for p in possible_paths])
            )
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    # Checking if file has been modified 
    current_mtime = os.path.getmtime(config_path)
    if not force_reload and current_mtime <= _config_last_modified and _config_cache is not None:
        # File hasn't changed, return cached config (avoids re-reading and re-parsing)
        return _config_cache
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            if config is None:
                raise ValueError("Config file is empty or invalid")
            _config_last_modified = current_mtime
            _config_cache = config  # Cache the loaded config
            return config
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error loading config file: {str(e)}")


try:
    CONFIG = load_config()
except Exception as e:
    # Fallback config file 
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
    print(f"Warning: Failed to load config file, using defaults: {e}")


def reload_config() -> Dict[str, Any]:
    """
    Reload configuration from file (for hot-reload).
    
    Returns:
        Updated configuration dictionary
    """
    global CONFIG
    try:
        new_config = load_config(force_reload=True)
        CONFIG = new_config
        print(f"Configuration reloaded successfully at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        return CONFIG
    except Exception as e:
        print(f"Failed to reload config: {e}. Keeping existing configuration.")
        return CONFIG


def has_config_changed() -> bool:
    """
    Check if config file has been modified since last load.
    
    Returns:
        True if config file has changed
    """
    global _config_file_path, _config_last_modified
    if _config_file_path is None or not os.path.exists(_config_file_path):
        return False
    
    try:
        current_mtime = os.path.getmtime(_config_file_path)
        return current_mtime > _config_last_modified
    except Exception:
        return False