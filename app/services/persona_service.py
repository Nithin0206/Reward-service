"""Persona service with support for mocking via JSON file, in-memory map, and API endpoint."""

import json
import os
from typing import Optional, Dict
from app.models.enum import Persona
from app.utils.config_loader import CONFIG


class PersonaService:
    """Service for managing user personas with mocking support."""
    
    def __init__(self):
        self._in_memory_map: Dict[str, str] = {}
        self._json_file_path: Optional[str] = None
        self._json_cache: Optional[Dict[str, str]] = None
        self._enabled = False
        self._load_config()
    
    def _load_config(self):
        """Load persona mocking configuration."""
        persona_config = CONFIG.get("persona_mocking", {})
        self._enabled = persona_config.get("enabled", False)
        
        if self._enabled:
            # Load JSON file path
            json_path = persona_config.get("json_file_path")
            if json_path:
                self._json_file_path = json_path
                self._load_json_file()
            
            # Load in-memory map from config
            in_memory = persona_config.get("in_memory_map", {})
            if in_memory:
                self._in_memory_map.update(in_memory)
    
    def _load_json_file(self):
        """Load persona mappings from JSON file."""
        if not self._json_file_path or not os.path.exists(self._json_file_path):
            self._json_cache = {}
            return
        
        try:
            with open(self._json_file_path, 'r') as f:
                self._json_cache = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading persona JSON file: {str(e)}")
            self._json_cache = {}
    
    def _reload_json_file(self):
        """Reload JSON file (useful when file is updated)."""
        self._load_json_file()
    
    async def get_persona(self, user_id: str) -> Optional[str]:
        """
        Get persona for a user with priority:
        1. In-memory map (highest priority)
        2. JSON file
        3. None (fallback to cache/default)
        
        Args:
            user_id: User identifier
            
        Returns:
            Persona string or None if not found in mocks
        """
        if not self._enabled:
            return None
        
        # Priority 1: In-memory map
        if user_id in self._in_memory_map:
            persona = self._in_memory_map[user_id]
            if persona in [p.value for p in Persona]:
                return persona
        
        # Priority 2: JSON file
        if self._json_cache and user_id in self._json_cache:
            persona = self._json_cache[user_id]
            if persona in [p.value for p in Persona]:
                return persona
        
        return None
    
    def set_persona_in_memory(self, user_id: str, persona: str) -> bool:
        """
        Set persona in in-memory map.
        
        Args:
            user_id: User identifier
            persona: Persona value (NEW, RETURNING, POWER)
            
        Returns:
            True if successful, False otherwise
        """
        if persona not in [p.value for p in Persona]:
            return False
        
        self._in_memory_map[user_id] = persona
        return True
    
    def remove_persona_from_memory(self, user_id: str) -> bool:
        """
        Remove persona from in-memory map.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if removed, False if not found
        """
        if user_id in self._in_memory_map:
            del self._in_memory_map[user_id]
            return True
        return False
    
    def get_all_mocked_personas(self) -> Dict[str, str]:
        """
        Get all mocked personas (in-memory + JSON).
        
        Returns:
            Dictionary of user_id -> persona
        """
        result = {}
        
        # Add in-memory personas
        result.update(self._in_memory_map)
        
        # Add JSON personas (in-memory takes precedence)
        if self._json_cache:
            for user_id, persona in self._json_cache.items():
                if user_id not in result:
                    result[user_id] = persona
        
        return result
    
    def reload_json_file(self):
        """Manually reload JSON file."""
        self._reload_json_file()


# Global instance
_persona_service: Optional[PersonaService] = None


def get_persona_service() -> PersonaService:
    """Get or create persona service instance."""
    global _persona_service
    if _persona_service is None:
        _persona_service = PersonaService()
    return _persona_service

