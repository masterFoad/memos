"""
Template service for OnMemOS SDK
"""

from typing import Optional, List, Dict, Any
from ..core.http import HTTPClient
from ..models.templates import SessionTemplate, TemplateList, TemplateCategory
from ..core.exceptions import TemplateError


class TemplateService:
    """Template management service"""
    
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client
    
    async def list_templates(
        self,
        category: Optional[TemplateCategory] = None,
        user_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        popular: bool = False,
        limit: int = 10
    ) -> TemplateList:
        """List available templates"""
        try:
            params = {"limit": limit}
            if category:
                params["category"] = category.value
            if user_type:
                params["user_type"] = user_type
            if tags:
                params["tags"] = ",".join(tags)
            if popular:
                params["popular"] = "true"
            
            response = await self.http_client.get("/v1/templates", params=params)
            return TemplateList(**response)
            
        except Exception as e:
            raise TemplateError(f"Failed to list templates: {e}")
    
    async def get_template(self, template_id: str) -> SessionTemplate:
        """Get specific template"""
        try:
            response = await self.http_client.get(f"/v1/templates/{template_id}")
            return SessionTemplate(**response)
            
        except Exception as e:
            raise TemplateError(f"Failed to get template {template_id}: {e}")
    
    async def get_popular_templates(self, limit: int = 5) -> List[SessionTemplate]:
        """Get popular templates"""
        try:
            response = await self.http_client.get("/v1/templates", params={"popular": "true", "limit": limit})
            template_list = TemplateList(**response)
            return template_list.templates
            
        except Exception as e:
            raise TemplateError(f"Failed to get popular templates: {e}")
    
    async def search_templates(
        self,
        query: str,
        category: Optional[TemplateCategory] = None,
        limit: int = 10
    ) -> List[SessionTemplate]:
        """Search templates by query"""
        try:
            params = {"q": query, "limit": limit}
            if category:
                params["category"] = category.value
            
            response = await self.http_client.get("/v1/templates/search", params=params)
            template_list = TemplateList(**response)
            return template_list.templates
            
        except Exception as e:
            raise TemplateError(f"Failed to search templates: {e}")
    
    async def get_template_categories(self) -> List[Dict[str, Any]]:
        """Get available template categories"""
        try:
            response = await self.http_client.get("/v1/templates/categories")
            return response.get("categories", [])
            
        except Exception as e:
            raise TemplateError(f"Failed to get template categories: {e}")
    
    async def get_template_by_name(self, name: str) -> Optional[SessionTemplate]:
        """Get template by name (case-insensitive)"""
        try:
            templates = await self.list_templates(limit=100)
            for template in templates.templates:
                if template.name.lower() == name.lower():
                    return template
            return None
            
        except Exception as e:
            raise TemplateError(f"Failed to get template by name {name}: {e}")
    
    async def get_templates_by_category(self, category: TemplateCategory) -> List[SessionTemplate]:
        """Get all templates in a category"""
        try:
            templates = await self.list_templates(category=category, limit=100)
            return templates.templates
            
        except Exception as e:
            raise TemplateError(f"Failed to get templates by category {category}: {e}")
    
    async def get_templates_by_tags(self, tags: List[str]) -> List[SessionTemplate]:
        """Get templates matching specific tags"""
        try:
            templates = await self.list_templates(tags=tags, limit=100)
            return templates.templates
            
        except Exception as e:
            raise TemplateError(f"Failed to get templates by tags {tags}: {e}")
    
    async def get_template_usage_stats(self, template_id: str) -> Dict[str, Any]:
        """Get template usage statistics"""
        try:
            response = await self.http_client.get(f"/v1/templates/{template_id}/stats")
            return response
            
        except Exception as e:
            raise TemplateError(f"Failed to get template stats for {template_id}: {e}")
    
    async def validate_template_config(
        self,
        template_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate template configuration"""
        try:
            response = await self.http_client.post(
                f"/v1/templates/{template_id}/validate",
                json=config
            )
            return response
            
        except Exception as e:
            raise TemplateError(f"Failed to validate template config for {template_id}: {e}")
