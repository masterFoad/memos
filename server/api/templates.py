"""
Session Templates API - Template management endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from pydantic import BaseModel

from server.core.logging import get_api_logger
from server.core.security import require_api_key
from server.models.session_templates import (
    SessionTemplate, TemplateCategory, template_manager, TemplateManager
)
from server.models.users import UserType

logger = get_api_logger()
router = APIRouter(prefix="/v1/templates", tags=["templates"])


class CreateTemplateRequest(BaseModel):
    """Request model for creating a new template"""
    template_id: str
    name: str
    description: str
    category: TemplateCategory
    resource_tier: str = "small"
    image_type: str = "alpine_basic"
    storage_type: str = "ephemeral"
    storage_size_gb: int = 0
    env_vars: dict = {}
    pre_install_commands: List[str] = []
    tags: List[str] = []
    estimated_cost_per_hour: float = 0.05


class UpdateTemplateRequest(BaseModel):
    """Request model for updating a template"""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[TemplateCategory] = None
    resource_tier: Optional[str] = None
    image_type: Optional[str] = None
    storage_type: Optional[str] = None
    storage_size_gb: Optional[int] = None
    env_vars: Optional[dict] = None
    pre_install_commands: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    estimated_cost_per_hour: Optional[float] = None


@router.get("/")
async def list_templates(
    category: Optional[TemplateCategory] = Query(None, description="Filter by category"),
    user_type: Optional[str] = Query(None, description="Filter by user type"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    popular: bool = Query(False, description="Get popular templates only"),
    limit: int = Query(10, description="Maximum number of templates to return")
):
    """List available session templates with optional filtering"""
    try:
        # Parse user type if provided
        parsed_user_type = None
        if user_type:
            try:
                parsed_user_type = UserType(user_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid user type: {user_type}")
        
        # Parse tags if provided
        parsed_tags = None
        if tags:
            parsed_tags = [tag.strip() for tag in tags.split(",")]
        
        # Get templates based on filters
        if popular:
            templates = template_manager.get_popular_templates(limit)
        else:
            templates = template_manager.list_templates(
                category=category,
                user_type=parsed_user_type,
                tags=parsed_tags
            )
            templates = templates[:limit]
        
        return {
            "templates": [template.dict() for template in templates],
            "total": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list templates")


@router.get("/{template_id}")
async def get_template(template_id: str):
    """Get a specific template by ID"""
    try:
        template = template_manager.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
        
        return template.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get template")


@router.post("/")
async def create_template(
    request: CreateTemplateRequest,
    user_info: dict = Depends(require_api_key)
):
    """Create a new session template"""
    try:
        # Check if template already exists
        if template_manager.get_template(request.template_id):
            raise HTTPException(status_code=409, detail=f"Template {request.template_id} already exists")
        
        # Create template object
        template = SessionTemplate(
            template_id=request.template_id,
            name=request.name,
            description=request.description,
            category=request.category,
            resource_tier=request.resource_tier,
            image_type=request.image_type,
            storage_type=request.storage_type,
            storage_size_gb=request.storage_size_gb,
            env_vars=request.env_vars,
            pre_install_commands=request.pre_install_commands,
            tags=request.tags,
            estimated_cost_per_hour=request.estimated_cost_per_hour,
            created_by=user_info.get("user_id")
        )
        
        # Add template
        success = template_manager.create_template(template)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create template")
        
        logger.info(f"Created template {request.template_id} by user {user_info.get('user_id')}")
        return template.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail="Failed to create template")


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    user_info: dict = Depends(require_api_key)
):
    """Update an existing template"""
    try:
        # Get existing template
        template = template_manager.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
        
        # Check if user can modify this template
        if template.created_by and template.created_by != user_info.get("user_id"):
            raise HTTPException(status_code=403, detail="Not authorized to modify this template")
        
        # Update fields
        update_data = request.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)
        
        # Save updated template
        success = template_manager.update_template(template)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update template")
        
        logger.info(f"Updated template {template_id} by user {user_info.get('user_id')}")
        return template.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update template")


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user_info: dict = Depends(require_api_key)
):
    """Delete a template"""
    try:
        # Get existing template
        template = template_manager.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
        
        # Check if user can delete this template
        if template.created_by and template.created_by != user_info.get("user_id"):
            raise HTTPException(status_code=403, detail="Not authorized to delete this template")
        
        # Delete template
        success = template_manager.delete_template(template_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete template")
        
        logger.info(f"Deleted template {template_id} by user {user_info.get('user_id')}")
        return {"message": f"Template {template_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete template")


@router.get("/categories/list")
async def list_categories():
    """List all available template categories"""
    return {
        "categories": [
            {"id": cat.value, "name": cat.value.replace("_", " ").title()}
            for cat in TemplateCategory
        ]
    }


@router.get("/popular/{limit}")
async def get_popular_templates(limit: int = 5):
    """Get most popular templates by usage count"""
    try:
        templates = template_manager.get_popular_templates(limit)
        return {
            "templates": [template.dict() for template in templates],
            "total": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Error getting popular templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to get popular templates")
