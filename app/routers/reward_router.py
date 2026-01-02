from fastapi import APIRouter, HTTPException, status
from app.models.request import RewardRequest
from app.models.response import RewardResponse
from app.services.reward_engine import calculate_reward

router = APIRouter()


@router.post("/reward/decide", response_model=RewardResponse, status_code=status.HTTP_200_OK)
async def decide_reward(req: RewardRequest) -> RewardResponse:
    """
    Decide reward for a transaction.
    
    Phase 1: Fully async endpoint with optimized cache operations.
    
    Args:
        req: RewardRequest containing transaction details
        
    Returns:
        RewardResponse with reward decision
        
    Raises:
        HTTPException: If request validation or processing fails
    """
    try:
        return await calculate_reward(req)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )
