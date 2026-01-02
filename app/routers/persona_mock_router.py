"""Router for persona mocking endpoints."""

from typing import Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.persona_service import get_persona_service
from app.models.enum import Persona

router = APIRouter(prefix="/persona", tags=["Persona Mocking"])


class SetPersonaRequest(BaseModel):
    """Request model for setting persona."""
    user_id: str
    persona: str


class PersonaResponse(BaseModel):
    """Response model for persona operations."""
    user_id: str
    persona: Optional[str]
    message: str


@router.post("/mock", response_model=PersonaResponse)
async def set_persona_mock(request: SetPersonaRequest):
    """
    Set persona for a user in in-memory map.
    
    This overrides persona calculation and JSON file entries.
    """
    service = get_persona_service()
    
    # Validate persona
    if request.persona not in [p.value for p in Persona]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid persona. Must be one of: {[p.value for p in Persona]}"
        )
    
    success = service.set_persona_in_memory(request.user_id, request.persona)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to set persona")
    
    return PersonaResponse(
        user_id=request.user_id,
        persona=request.persona,
        message=f"Persona set to {request.persona} for user {request.user_id}"
    )


@router.delete("/mock/{user_id}", response_model=PersonaResponse)
async def remove_persona_mock(user_id: str):
    """
    Remove persona mock for a user from in-memory map.
    
    After removal, persona will fall back to JSON file or cache/default.
    """
    service = get_persona_service()
    
    removed = service.remove_persona_from_memory(user_id)
    
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"No mocked persona found for user {user_id}"
        )
    
    return PersonaResponse(
        user_id=user_id,
        persona=None,
        message=f"Persona mock removed for user {user_id}"
    )


@router.get("/mock/{user_id}", response_model=PersonaResponse)
async def get_persona_mock(user_id: str):
    """Get mocked persona for a user."""
    service = get_persona_service()
    persona = await service.get_persona(user_id)
    
    if persona is None:
        raise HTTPException(
            status_code=404,
            detail=f"No mocked persona found for user {user_id}"
        )
    
    return PersonaResponse(
        user_id=user_id,
        persona=persona,
        message=f"Mocked persona: {persona}"
    )


@router.get("/mock", response_model=Dict[str, str])
async def get_all_mocked_personas():
    """Get all mocked personas (in-memory + JSON)."""
    service = get_persona_service()
    return service.get_all_mocked_personas()


@router.post("/reload-json")
async def reload_persona_json():
    """Manually reload persona JSON file."""
    service = get_persona_service()
    service.reload_json_file()
    return {"message": "Persona JSON file reloaded successfully"}

