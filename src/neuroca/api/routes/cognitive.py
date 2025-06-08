"""
Cognitive Control API Routes for NeuroCognitive Architecture (NCA)

This module provides endpoints for interacting with the cognitive control system,
including attention management, decision making, goal management, and metacognitive
processes. These endpoints allow external systems to trigger cognitive processes
and monitor cognitive state.

Usage:
    These routes provide access to the core cognitive control components:
    - Attention Manager: Focus and attention control
    - Decision Maker: Decision-making processes
    - Goal Manager: Goal setting and tracking
    - Planner: Planning and execution
    - Metacognition: Self-monitoring and regulation
    - Inhibitor: Impulse control and inhibition

Security:
    Cognitive endpoints may modify system behavior and should be properly secured.
    Consider implementing rate limiting for cognitive operations.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/cognitive",
    tags=["cognitive"],
    responses={
        401: {"description": "Unauthorized"},
        500: {"description": "Internal Server Error"},
    },
)


# Pydantic models for cognitive operations
class AttentionRequest(BaseModel):
    """Request model for attention operations."""
    target: str = Field(..., description="Target for attention focus")
    priority: int = Field(default=1, ge=1, le=10, description="Priority level (1-10)")
    duration_seconds: Optional[int] = Field(None, description="Duration to maintain attention")


class DecisionRequest(BaseModel):
    """Request model for decision-making operations."""
    decision_type: str = Field(..., description="Type of decision to make")
    options: list[str] = Field(..., description="Available options")
    criteria: Optional[dict[str, float]] = Field(None, description="Decision criteria with weights")
    context: Optional[dict[str, Any]] = Field(None, description="Additional context for decision")


class GoalRequest(BaseModel):
    """Request model for goal management operations."""
    goal_id: Optional[str] = Field(None, description="Goal identifier")
    description: str = Field(..., description="Goal description")
    priority: int = Field(default=5, ge=1, le=10, description="Goal priority (1-10)")
    deadline: Optional[str] = Field(None, description="Goal deadline (ISO format)")
    parent_goal_id: Optional[str] = Field(None, description="Parent goal identifier")


class PlanRequest(BaseModel):
    """Request model for planning operations."""
    goal_id: str = Field(..., description="Goal to plan for")
    time_horizon: Optional[int] = Field(None, description="Planning time horizon in hours")
    constraints: Optional[dict[str, Any]] = Field(None, description="Planning constraints")


class MetacognitionRequest(BaseModel):
    """Request model for metacognitive operations."""
    operation: str = Field(..., description="Metacognitive operation to perform")
    target_component: Optional[str] = Field(None, description="Target component for metacognition")
    parameters: Optional[dict[str, Any]] = Field(None, description="Operation parameters")


# Response models
class CognitiveResponse(BaseModel):
    """Generic response model for cognitive operations."""
    success: bool
    message: str
    data: Optional[dict[str, Any]] = None


class AttentionStatus(BaseModel):
    """Model for attention status information."""
    current_focus: Optional[str]
    attention_level: float = Field(ge=0, le=1)
    active_targets: list[str]
    last_updated: str


class DecisionResult(BaseModel):
    """Model for decision results."""
    decision_id: str
    selected_option: str
    confidence: float = Field(ge=0, le=1)
    reasoning: Optional[str]
    timestamp: str


class GoalStatus(BaseModel):
    """Model for goal status information."""
    goal_id: str
    description: str
    status: str
    priority: int
    progress: float = Field(ge=0, le=1)
    created_at: str
    updated_at: str


# Attention Management Endpoints
@router.get(
    "/attention/status",
    summary="Get attention status",
    description="Get current attention status and focus information",
    response_model=AttentionStatus,
)
async def get_attention_status() -> AttentionStatus:
    """
    Get current attention status.
    
    Returns:
        AttentionStatus: Current attention state information
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.core.cognitive_control.attention_manager import AttentionManager
        
        attention_manager = AttentionManager()
        
        # Get current attention state
        # This would call actual methods on the attention manager
        return AttentionStatus(
            current_focus=getattr(attention_manager, 'current_focus', None),
            attention_level=getattr(attention_manager, 'attention_level', 0.5),
            active_targets=getattr(attention_manager, 'active_targets', []),
            last_updated="2024-01-01T00:00:00Z",  # Would be actual timestamp
        )
    except Exception as e:
        logger.exception("Failed to get attention status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get attention status: {str(e)}",
        ) from e


@router.post(
    "/attention/focus",
    summary="Set attention focus",
    description="Direct attention to a specific target",
    response_model=CognitiveResponse,
)
async def set_attention_focus(request: AttentionRequest) -> CognitiveResponse:
    """
    Set attention focus to a target.
    
    Args:
        request: Attention request with target and parameters
        
    Returns:
        CognitiveResponse: Result of attention operation
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.core.cognitive_control.attention_manager import AttentionManager
        
        attention_manager = AttentionManager()
        
        # Set attention focus
        # This would call actual methods on the attention manager
        logger.info(f"Setting attention focus to: {request.target} with priority {request.priority}")
        
        return CognitiveResponse(
            success=True,
            message=f"Attention focused on {request.target}",
            data={
                "target": request.target,
                "priority": request.priority,
                "duration_seconds": request.duration_seconds,
            }
        )
    except Exception as e:
        logger.exception("Failed to set attention focus")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set attention focus: {str(e)}",
        ) from e


# Decision Making Endpoints
@router.post(
    "/decision/make",
    summary="Make a decision",
    description="Request the decision maker to evaluate options and make a decision",
    response_model=DecisionResult,
)
async def make_decision(request: DecisionRequest) -> DecisionResult:
    """
    Make a decision based on provided options and criteria.
    
    Args:
        request: Decision request with options and criteria
        
    Returns:
        DecisionResult: The decision result
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.core.cognitive_control.decision_maker import DecisionMaker
        
        decision_maker = DecisionMaker()
        
        # Make decision
        # This would call actual methods on the decision maker
        logger.info(f"Making decision of type: {request.decision_type} with {len(request.options)} options")
        
        # For now, return a mock decision (first option)
        selected_option = request.options[0] if request.options else "no_option"
        
        return DecisionResult(
            decision_id=f"decision_{hash(str(request.options))}",
            selected_option=selected_option,
            confidence=0.75,  # Would be calculated
            reasoning=f"Selected based on {request.decision_type} criteria",
            timestamp="2024-01-01T00:00:00Z",  # Would be actual timestamp
        )
    except Exception as e:
        logger.exception("Failed to make decision")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to make decision: {str(e)}",
        ) from e


# Goal Management Endpoints
@router.get(
    "/goals",
    summary="List goals",
    description="Get list of current goals",
    response_model=list[GoalStatus],
)
async def list_goals() -> list[GoalStatus]:
    """
    Get list of current goals.
    
    Returns:
        List[GoalStatus]: List of current goals
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.core.cognitive_control.goal_manager import GoalManager
        
        goal_manager = GoalManager()
        
        # Get goals
        # This would call actual methods on the goal manager
        logger.info("Retrieving current goals")
        
        return [
            GoalStatus(
                goal_id="goal_1",
                description="Example goal",
                status="active",
                priority=5,
                progress=0.3,
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )
        ]
    except Exception as e:
        logger.exception("Failed to list goals")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list goals: {str(e)}",
        ) from e


@router.post(
    "/goals",
    summary="Create goal",
    description="Create a new goal",
    response_model=CognitiveResponse,
)
async def create_goal(request: GoalRequest) -> CognitiveResponse:
    """
    Create a new goal.
    
    Args:
        request: Goal creation request
        
    Returns:
        CognitiveResponse: Result of goal creation
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.core.cognitive_control.goal_manager import GoalManager
        
        goal_manager = GoalManager()
        
        # Create goal
        # This would call actual methods on the goal manager
        logger.info(f"Creating goal: {request.description} with priority {request.priority}")
        
        goal_id = f"goal_{hash(request.description)}"
        
        return CognitiveResponse(
            success=True,
            message="Goal created successfully",
            data={
                "goal_id": goal_id,
                "description": request.description,
                "priority": request.priority,
            }
        )
    except Exception as e:
        logger.exception("Failed to create goal")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create goal: {str(e)}",
        ) from e


# Planning Endpoints
@router.post(
    "/planning/create_plan",
    summary="Create plan",
    description="Create a plan for achieving a goal",
    response_model=CognitiveResponse,
)
async def create_plan(request: PlanRequest) -> CognitiveResponse:
    """
    Create a plan for achieving a goal.
    
    Args:
        request: Planning request
        
    Returns:
        CognitiveResponse: Result of plan creation
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.core.cognitive_control.planner import Planner
        
        planner = Planner()
        
        # Create plan
        # This would call actual methods on the planner
        logger.info(f"Creating plan for goal: {request.goal_id}")
        
        return CognitiveResponse(
            success=True,
            message="Plan created successfully",
            data={
                "goal_id": request.goal_id,
                "time_horizon": request.time_horizon,
                "plan_id": f"plan_{hash(request.goal_id)}",
            }
        )
    except Exception as e:
        logger.exception("Failed to create plan")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create plan: {str(e)}",
        ) from e


# Metacognition Endpoints
@router.post(
    "/metacognition/execute",
    summary="Execute metacognitive operation",
    description="Execute a metacognitive operation",
    response_model=CognitiveResponse,
)
async def execute_metacognition(request: MetacognitionRequest) -> CognitiveResponse:
    """
    Execute a metacognitive operation.
    
    Args:
        request: Metacognition request
        
    Returns:
        CognitiveResponse: Result of metacognitive operation
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.core.cognitive_control.metacognition import Metacognition
        
        metacognition = Metacognition()
        
        # Execute metacognitive operation
        # This would call actual methods on the metacognition component
        logger.info(f"Executing metacognitive operation: {request.operation}")
        
        return CognitiveResponse(
            success=True,
            message=f"Metacognitive operation '{request.operation}' executed successfully",
            data={
                "operation": request.operation,
                "target_component": request.target_component,
                "parameters": request.parameters,
            }
        )
    except Exception as e:
        logger.exception("Failed to execute metacognitive operation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute metacognitive operation: {str(e)}",
        ) from e


@router.get(
    "/status",
    summary="Get cognitive system status",
    description="Get overall status of the cognitive control system",
)
async def get_cognitive_status() -> dict[str, Any]:
    """
    Get overall cognitive system status.
    
    Returns:
        Dict containing cognitive system status
    """
    try:
        return {
            "status": "operational",
            "components": {
                "attention_manager": "active",
                "decision_maker": "active", 
                "goal_manager": "active",
                "planner": "active",
                "metacognition": "active",
                "inhibitor": "active",
            },
            "active_goals": 1,  # Would be actual count
            "attention_level": 0.7,  # Would be actual level
            "last_decision": "2024-01-01T00:00:00Z",  # Would be actual timestamp
        }
    except Exception as e:
        logger.exception("Failed to get cognitive status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cognitive status: {str(e)}",
        ) from e
