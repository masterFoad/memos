"""
OnMemOS v3 Python SDK Client
"""
import requests
import json
import time
import logging
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

# Import the new models for enhanced resource control
from server.models.sessions import (
    ResourceTier, ResourceSpec, ResourcePackage, CPUSize, MemorySize,
    ImageType, ImageSpec, GPUType, GPUSpec,
    StorageType, StorageConfig
)
from server.models.users import (
    UserType, WorkspaceResourcePackage, WorkspaceProfile
)

logger = logging.getLogger(__name__)

class OnMemOSClient:
    """Client for OnMemOS v3 API"""
    
    def __init__(self, base_url: str = "http://localhost:8080", api_key: str = "onmemos-internal-key-2024-secure"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        logger.info(f"Initialized OnMemOS client for {self.base_url}")
    
    def set_api_key(self, api_key: str):
        """Set API key for authentication"""
        self.api_key = api_key
        self.session.headers.update({"X-API-Key": api_key})
        logger.info("API key updated")
    
    def _make_request(self, method: str, endpoint: str, timeout: int = 30, **kwargs) -> requests.Response:
        """Make HTTP request to API with proper error handling"""
        url = f"{self.base_url}{endpoint}"
        
        logger.debug(f"Making {method} request to {url}")
        
        try:
            response = self.session.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            logger.error(f"Request timed out after {timeout} seconds: {method} {url}")
            raise Exception(f"Request timed out after {timeout} seconds")
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error: {method} {url}")
            raise Exception(f"Connection error - is the server running at {self.base_url}?")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {e.response.status_code}: {method} {url}")
            if e.response.status_code == 404:
                raise Exception(f"Endpoint not found: {endpoint}")
            elif e.response.status_code == 401:
                raise Exception("Authentication failed - check API key")
            elif e.response.status_code == 403:
                raise Exception("Access forbidden - check API key and permissions")
            elif e.response.status_code == 500:
                raise Exception(f"Server error: {e.response.text}")
            else:
                raise Exception(f"HTTP error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Unexpected error: {method} {url} - {e}")
            raise
    
    # Health and Info endpoints
    def health_check(self) -> Dict[str, Any]:
        """Check server health - no auth required"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information"""
        response = self._make_request("GET", "/")
        return response.json()
    
    # ============================================================================
    # Workspace Management Methods
    # ============================================================================
    
    def create_workspace(self, user_id: str, workspace_id: str, name: str, 
                        resource_package: WorkspaceResourcePackage,
                        description: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new workspace for a user.
        
        Args:
            user_id: User identifier
            workspace_id: Unique workspace identifier
            name: Workspace name
            resource_package: Resource package for the workspace
            description: Optional workspace description
        
        Returns:
            Workspace information dictionary
        
        Examples:
            # Create a development workspace
            workspace = client.create_workspace(
                "developer", "my-dev-workspace", "Development Environment",
                WorkspaceResourcePackage.DEV_MEDIUM,
                "My main development workspace"
            )
            
            # Create an ML workspace with GPU
            workspace = client.create_workspace(
                "researcher", "ml-workspace", "Machine Learning Lab",
                WorkspaceResourcePackage.ML_T4_MEDIUM,
                "GPU-enabled workspace for ML experiments"
            )
        """
        payload = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "name": name,
            "resource_package": resource_package.value,
            "description": description
        }
        
        response = self._make_request("POST", "/v1/workspaces", json=payload)
        return response.json()
    
    def get_workspace(self, user_id: str, workspace_id: str) -> Dict[str, Any]:
        """Get workspace information"""
        response = self._make_request("GET", f"/v1/workspaces/{user_id}/{workspace_id}")
        return response.json()
    
    def list_workspaces(self, user_id: str) -> List[Dict[str, Any]]:
        """List all workspaces for a user"""
        response = self._make_request("GET", f"/v1/workspaces/{user_id}")
        return response.json()
    
    def delete_workspace(self, user_id: str, workspace_id: str) -> bool:
        """Delete a workspace"""
        response = self._make_request("DELETE", f"/v1/workspaces/{user_id}/{workspace_id}")
        return response.status_code == 200
    
    # ============================================================================
    # Enhanced Session Creation Methods (Workspace-based)
    # ============================================================================
    
    def create_session_in_workspace(
        self,
        workspace_id: str,
        template: str,
        namespace: str,
        user: str,
        *,
        # Basic parameters
        ttl_minutes: int = 60,
        provider: str = "gke",
        
        # Resource specifications (optional - will use workspace package if not specified)
        resource_package: Optional[ResourcePackage] = None,
        resource_spec: Optional[ResourceSpec] = None,
        
        # Image specifications
        image_type: Optional[ImageType] = None,
        image_url: Optional[str] = None,
        image_tag: str = "latest",
        
        # GPU specifications
        gpu_type: Optional[GPUType] = None,
        gpu_count: int = 1,
        
        # Storage specifications
        request_persistent_storage: bool = False,
        persistent_storage_size_gb: int = 10,
        request_bucket: bool = False,
        bucket_size_gb: Optional[int] = None,
        
        # Environment variables
        env: Optional[Dict[str, str]] = None,
        
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a session within a specific workspace.
        
        Args:
            workspace_id: Workspace identifier
            template: Session template name
            namespace: Session namespace
            user: User identifier
            ttl_minutes: Session time-to-live in minutes
            provider: Backend provider (gke, cloud_run, workstations, auto)
            
            # Resource specifications (optional)
            resource_package: Resource package (overrides workspace package)
            resource_spec: Fine-grained resource specification (overrides package)
            
            # Image specifications
            image_type: Image type (alpine, ubuntu, python, nodejs, go, rust, java, custom)
            image_url: Custom image URL (required for custom image_type)
            image_tag: Image tag (default: "latest")
            
            # GPU specifications
            gpu_type: GPU type (none, t4, v100, a100, h100, l4)
            gpu_count: Number of GPUs (1-8)
            
            # Storage specifications
            request_persistent_storage: Request persistent storage
            persistent_storage_size_gb: Persistent storage size in GB
            request_bucket: Request GCS bucket
            bucket_size_gb: Bucket size in GB
            
            # Environment variables
            env: Environment variables dict
            
            **kwargs: Additional session parameters
        
        Returns:
            Session information dictionary
        
        Examples:
            # Create session using workspace's resource package
            session = client.create_session_in_workspace(
                "my-dev-workspace", "python", "project1", "developer"
            )
            
            # Override workspace package with specific resources
            session = client.create_session_in_workspace(
                "ml-workspace", "python", "experiment1", "researcher",
                resource_package=ResourcePackage.ML_T4_LARGE,
                gpu_type=GPUType.T4, gpu_count=2,
                request_persistent_storage=True, persistent_storage_size_gb=50
            )
        """
        
        # Build session specification
        session_spec = {
            "provider": provider,
            "template": template,
            "namespace": namespace,
            "user": user,
            "workspace_id": workspace_id,
            "ttl_minutes": ttl_minutes,
            **kwargs
        }
        
        # Handle resource specifications
        if resource_spec is not None:
            # Use provided fine-grained resource specification
            session_spec["resource_spec"] = resource_spec.dict()
        elif resource_package is not None:
            # Use provided resource package
            session_spec["resource_package"] = resource_package.value
        
        # Handle image specifications
        if image_type or image_url:
            image_spec = {}
            if image_type:
                image_spec["image_type"] = image_type.value
            if image_url:
                image_spec["image_url"] = image_url
            if image_tag != "latest":
                image_spec["image_tag"] = image_tag
            
            session_spec["image_spec"] = image_spec
        
        # Handle GPU specifications
        if gpu_type and gpu_type != GPUType.NONE:
            session_spec["gpu_spec"] = {
                "gpu_type": gpu_type.value,
                "gpu_count": gpu_count
            }
        
        # Handle storage specifications
        if request_persistent_storage:
            session_spec["request_persistent_storage"] = True
            session_spec["persistent_storage_size_gb"] = persistent_storage_size_gb
        
        if request_bucket:
            session_spec["request_bucket"] = True
            if bucket_size_gb:
                session_spec["bucket_size_gb"] = bucket_size_gb
        
        # Handle environment variables
        if env:
            session_spec["env"] = env
        
        return self.create_session(session_spec)
    
    def create_development_session(
        self,
        workspace_id: str,
        namespace: str,
        user: str,
        *,
        image_type: ImageType = ImageType.UBUNTU_PRO,
        cpu_size: CPUSize = CPUSize.MEDIUM,
        memory_size: MemorySize = MemorySize.MEDIUM,
        request_persistent_storage: bool = True,
        persistent_storage_size_gb: int = 20,
        ttl_minutes: int = 180,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a development session with Ubuntu and persistent storage.
        
        Args:
            workspace_id: Workspace identifier
            namespace: Session namespace
            user: User identifier
            image_type: Image type (default: ubuntu)
            cpu_size: CPU size specification
            memory_size: Memory size specification
            request_persistent_storage: Request persistent storage
            persistent_storage_size_gb: Persistent storage size in GB
            ttl_minutes: Session time-to-live in minutes
            **kwargs: Additional parameters
        
        Returns:
            Session information dictionary
        """
        resource_spec = ResourceSpec(
            cpu_size=cpu_size,
            memory_size=memory_size
        )
        
        return self.create_session_in_workspace(
            workspace_id=workspace_id,
            template="development",
            namespace=namespace,
            user=user,
            resource_spec=resource_spec,
            image_type=image_type,
            request_persistent_storage=request_persistent_storage,
            persistent_storage_size_gb=persistent_storage_size_gb,
            ttl_minutes=ttl_minutes,
            **kwargs
        )
    
    def create_python_session(
        self,
        workspace_id: str,
        namespace: str,
        user: str,
        *,
        python_version: str = "3.11-slim",
        cpu_size: CPUSize = CPUSize.SMALL,
        memory_size: MemorySize = MemorySize.SMALL,
        gpu_type: Optional[GPUType] = None,
        gpu_count: int = 1,
        request_persistent_storage: bool = False,
        persistent_storage_size_gb: int = 10,
        ttl_minutes: int = 60,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a Python session with optimized defaults.
        
        Args:
            workspace_id: Workspace identifier
            namespace: Session namespace
            user: User identifier
            python_version: Python version (e.g., "3.11-slim", "3.12-slim")
            cpu_size: CPU size specification
            memory_size: Memory size specification
            gpu_type: GPU type (none, t4, v100, a100, h100, l4)
            gpu_count: Number of GPUs
            request_persistent_storage: Request persistent storage
            persistent_storage_size_gb: Persistent storage size in GB
            ttl_minutes: Session time-to-live in minutes
            **kwargs: Additional parameters
        
        Returns:
            Session information dictionary
        """
        resource_spec = ResourceSpec(
            cpu_size=cpu_size,
            memory_size=memory_size
        )
        
        return self.create_session_in_workspace(
            workspace_id=workspace_id,
            template="python",
            namespace=namespace,
            user=user,
            resource_spec=resource_spec,
            image_type=ImageType.PYTHON_PRO,
            image_tag=python_version,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            request_persistent_storage=request_persistent_storage,
            persistent_storage_size_gb=persistent_storage_size_gb,
            ttl_minutes=ttl_minutes,
            **kwargs
        )
    
    def create_ml_session(
        self,
        workspace_id: str,
        namespace: str,
        user: str,
        *,
        gpu_type: GPUType = GPUType.T4,
        gpu_count: int = 1,
        cpu_size: CPUSize = CPUSize.LARGE,
        memory_size: MemorySize = MemorySize.XLARGE,
        python_version: str = "3.11-slim",
        request_persistent_storage: bool = True,
        persistent_storage_size_gb: int = 50,
        ttl_minutes: int = 120,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a machine learning session with GPU support.
        
        Args:
            workspace_id: Workspace identifier
            namespace: Session namespace
            user: User identifier
            gpu_type: GPU type (t4, v100, a100, h100, l4)
            gpu_count: Number of GPUs
            cpu_size: CPU size specification
            memory_size: Memory size specification
            python_version: Python version
            request_persistent_storage: Request persistent storage
            persistent_storage_size_gb: Persistent storage size in GB
            ttl_minutes: Session time-to-live in minutes
            **kwargs: Additional parameters
        
        Returns:
            Session information dictionary
        """
        resource_spec = ResourceSpec(
            cpu_size=cpu_size,
            memory_size=memory_size
        )
        
        return self.create_session_in_workspace(
            workspace_id=workspace_id,
            template="python",
            namespace=namespace,
            user=user,
            resource_spec=resource_spec,
            image_type=ImageType.PYTHON_PRO,
            image_tag=python_version,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            request_persistent_storage=request_persistent_storage,
            persistent_storage_size_gb=persistent_storage_size_gb,
            ttl_minutes=ttl_minutes,
            **kwargs
        )
    
    def create_custom_session(
        self,
        workspace_id: str,
        namespace: str,
        user: str,
        image_url: str,
        *,
        cpu_size: CPUSize = CPUSize.SMALL,
        memory_size: MemorySize = MemorySize.SMALL,
        gpu_type: Optional[GPUType] = None,
        gpu_count: int = 1,
        request_persistent_storage: bool = False,
        persistent_storage_size_gb: int = 10,
        ttl_minutes: int = 60,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a session with a custom container image.
        
        Args:
            workspace_id: Workspace identifier
            namespace: Session namespace
            user: User identifier
            image_url: Custom image URL
            cpu_size: CPU size specification
            memory_size: Memory size specification
            gpu_type: GPU type
            gpu_count: Number of GPUs
            request_persistent_storage: Request persistent storage
            persistent_storage_size_gb: Persistent storage size in GB
            ttl_minutes: Session time-to-live in minutes
            **kwargs: Additional parameters
        
        Returns:
            Session information dictionary
        """
        resource_spec = ResourceSpec(
            cpu_size=cpu_size,
            memory_size=memory_size
        )
        
        return self.create_session_in_workspace(
            workspace_id=workspace_id,
            template="custom",
            namespace=namespace,
            user=user,
            resource_spec=resource_spec,
            image_type=ImageType.CUSTOM,
            image_url=image_url,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            request_persistent_storage=request_persistent_storage,
            persistent_storage_size_gb=persistent_storage_size_gb,
            ttl_minutes=ttl_minutes,
            **kwargs
        )
    
    # ============================================================================
    # Resource Specification Helpers
    # ============================================================================
    
    @staticmethod
    def resource_spec(
        cpu_size: CPUSize = CPUSize.SMALL,
        memory_size: MemorySize = MemorySize.SMALL,
        custom_cpu_request: Optional[str] = None,
        custom_cpu_limit: Optional[str] = None,
        custom_memory_request: Optional[str] = None,
        custom_memory_limit: Optional[str] = None
    ) -> ResourceSpec:
        """
        Create a resource specification object.
        
        Args:
            cpu_size: CPU size specification
            memory_size: Memory size specification
            custom_cpu_request: Custom CPU request (when cpu_size is CUSTOM)
            custom_cpu_limit: Custom CPU limit
            custom_memory_request: Custom memory request (when memory_size is CUSTOM)
            custom_memory_limit: Custom memory limit
        
        Returns:
            ResourceSpec object
        """
        return ResourceSpec(
            cpu_size=cpu_size,
            memory_size=memory_size,
            custom_cpu_request=custom_cpu_request,
            custom_cpu_limit=custom_cpu_limit,
            custom_memory_request=custom_memory_request,
            custom_memory_limit=custom_memory_limit
        )
    
    @staticmethod
    def image_spec(
        image_type: ImageType,
        image_url: Optional[str] = None,
        image_tag: str = "latest"
    ) -> ImageSpec:
        """
        Create an image specification object.
        
        Args:
            image_type: Image type
            image_url: Custom image URL (required for custom type)
            image_tag: Image tag
        
        Returns:
            ImageSpec object
        """
        return ImageSpec(
            image_type=image_type,
            image_url=image_url,
            image_tag=image_tag
        )
    
    @staticmethod
    def gpu_spec(
        gpu_type: GPUType,
        gpu_count: int = 1
    ) -> GPUSpec:
        """
        Create a GPU specification object.
        
        Args:
            gpu_type: GPU type
            gpu_count: Number of GPUs
        
        Returns:
            GPUSpec object
        """
        return GPUSpec(
            gpu_type=gpu_type,
            gpu_count=gpu_count
        )
    
    # ============================================================================
    # Legacy Methods (Backward Compatibility)
    # ============================================================================
    
    def create_session(self, session_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Create a session using the unified sessions API (legacy method)"""
        logger.info(f"Creating session: {session_spec}")
        
        response = self._make_request("POST", "/v1/sessions", json=session_spec, timeout=120)
        result = response.json()
        
        logger.info(f"Session created: {result.get('id', 'unknown')}")
        return result
    
    def execute_session(self, session_id: str, command: str, timeout: int = 120, async_execution: bool = False) -> Dict[str, Any]:
        """Execute command in a session using the unified sessions API"""
        logger.info(f"Executing command in session {session_id}: {command} (async={async_execution})")
        
        payload = {
            "command": command,
            "timeout": timeout,
            "async_execution": async_execution
        }
        
        response = self._make_request("POST", f"/v1/sessions/{session_id}/execute", json=payload, timeout=timeout+10)
        result = response.json()
        
        logger.info(f"Command executed in session {session_id}: success={result.get('success', False)}")
        return result

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session information"""
        logger.info(f"Getting session: {session_id}")
        
        response = self._make_request("GET", f"/v1/sessions/{session_id}")
        return response.json()

    def list_sessions(self, namespace: Optional[str] = None, user: Optional[str] = None) -> List[Dict[str, Any]]:
        """List sessions"""
        params = {}
        if namespace:
            params["namespace"] = namespace
        if user:
            params["user"] = user
        
        response = self._make_request("GET", "/v1/sessions", params=params)
        data = response.json()
        
        # Handle different response formats
        if isinstance(data, dict) and "sessions" in data:
            sessions = data["sessions"]
        elif isinstance(data, list):
            sessions = data
        else:
            logger.warning(f"Unexpected response format: {data}")
            sessions = []
        
        logger.info(f"Found {len(sessions)} sessions")
        return sessions

    # ============================================================================
    # Persistent Storage Methods
    # ============================================================================
    
    def upload_persist(self, namespace: str, user: str, src: str, dst: str = "") -> Dict[str, Any]:
        """
        Upload a file to persistent storage.
        
        Args:
            namespace: Storage namespace
            user: User identifier
            src: Local file path to upload
            dst: Destination filename (optional, uses src filename if not provided)
        
        Returns:
            Upload result dictionary
        """
        import pathlib
        
        p = pathlib.Path(src)
        if not p.exists():
            raise FileNotFoundError(f"Source file not found: {src}")
        
        with p.open("rb") as f:
            files = {"file": f}
            params = {"namespace": namespace, "user": user}
            if dst:
                params["dst"] = dst
            
            response = self._make_request("POST", "/v1/fs/persist/upload", 
                                        params=params, files=files)
            return response.json()
    
    def download_persist(self, namespace: str, user: str, path: str, dst: str) -> str:
        """
        Download a file from persistent storage.
        
        Args:
            namespace: Storage namespace
            user: User identifier
            path: Remote file path
            dst: Local destination path
        
        Returns:
            Local file path where file was saved
        """
        params = {"namespace": namespace, "user": user, "path": path}
        response = self._make_request("GET", "/v1/fs/persist/download", 
                                    params=params, stream=True)
        
        with open(dst, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return dst
    
    def list_persist(self, namespace: str, user: str) -> Dict[str, Any]:
        """
        List files in persistent storage.
        
        Args:
            namespace: Storage namespace
            user: User identifier
        
        Returns:
            Dictionary containing file list
        """
        params = {"namespace": namespace, "user": user}
        response = self._make_request("GET", "/v1/fs/persist/list", params=params)
        return response.json()
    
    # ============================================================================
    # Context Manager Support (Auto Cleanup)
    # ============================================================================
    
    @contextmanager
    def session_context(self, session_spec: Dict[str, Any], auto_cleanup: bool = True):
        """
        Context manager for automatic session cleanup.
        
        Args:
            session_spec: Session specification dictionary
            auto_cleanup: Whether to automatically delete session on exit (default: True)
        
        Yields:
            Session information dictionary
        
        Examples:
            # Basic usage with auto cleanup
            with client.session_context({
                "workspace_id": "my-workspace",
                "template": "python",
                "namespace": "temp-work",
                "user": "developer",
                "ttl_minutes": 30
            }) as session:
                result = client.execute_session(session["id"], "ls -la")
                print(result["stdout"])
                # Session automatically deleted when exiting context
            
            # Disable auto cleanup (manual management)
            with client.session_context(session_spec, auto_cleanup=False) as session:
                # Do work...
                pass
            # Session still exists, manually delete later
        """
        session = None
        try:
            # Create session
            session = self.create_session(session_spec)
            session_id = session["id"]
            
            logger.info(f"Created session in context: {session_id}")
            
            # Wait for session to be ready
            self._wait_for_session_ready(session_id)
            
            yield session
            
        except Exception as e:
            logger.error(f"Error in session context: {e}")
            raise
        finally:
            # Auto cleanup if enabled
            if session and auto_cleanup:
                try:
                    session_id = session["id"]
                    logger.info(f"Auto-cleaning up session: {session_id}")
                    self.delete_session(session_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to auto-cleanup session {session_id}: {cleanup_error}")
    
    @contextmanager
    def workspace_session_context(
        self,
        workspace_id: str,
        template: str,
        namespace: str,
        user: str,
        *,
        ttl_minutes: int = 60,
        auto_cleanup: bool = True,
        **kwargs
    ):
        """
        Context manager for workspace-based sessions with automatic cleanup.
        
        Args:
            workspace_id: Workspace identifier
            template: Session template
            namespace: Session namespace
            user: User identifier
            ttl_minutes: Session time-to-live in minutes
            auto_cleanup: Whether to automatically delete session on exit
            **kwargs: Additional session parameters
        
        Yields:
            Session information dictionary
        
        Examples:
            # Development session with auto cleanup
            with client.workspace_session_context(
                workspace_id="my-workspace",
                template="python",
                namespace="temp-dev",
                user="developer",
                ttl_minutes=30,
                request_persistent_storage=True
            ) as session:
                result = client.execute_session(session["id"], "pip install pandas")
                print("Dependencies installed!")
            
            # ML session with GPU
            with client.workspace_session_context(
                workspace_id="ml-workspace",
                template="python",
                namespace="experiment",
                user="researcher",
                resource_package=ResourcePackage.ML_T4_MEDIUM,
                gpu_type=GPUType.T4
            ) as session:
                result = client.execute_session(session["id"], "nvidia-smi")
                print("GPU available!")
        """
        session = None
        try:
            # Create session in workspace
            session = self.create_session_in_workspace(
                workspace_id=workspace_id,
                template=template,
                namespace=namespace,
                user=user,
                ttl_minutes=ttl_minutes,
                **kwargs
            )
            session_id = session["id"]
            
            logger.info(f"Created workspace session in context: {session_id}")
            
            # Wait for session to be ready
            self._wait_for_session_ready(session_id)
            
            yield session
            
        except Exception as e:
            logger.error(f"Error in workspace session context: {e}")
            raise
        finally:
            # Auto cleanup if enabled
            if session and auto_cleanup:
                try:
                    session_id = session["id"]
                    logger.info(f"Auto-cleaning up workspace session: {session_id}")
                    self.delete_session(session_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to auto-cleanup workspace session {session_id}: {cleanup_error}")
    
    def _wait_for_session_ready(self, session_id: str, max_wait: int = 120):
        """
        Wait for session to be ready (running status).
        
        Args:
            session_id: Session identifier
            max_wait: Maximum wait time in seconds
        
        Raises:
            Exception: If session doesn't become ready within max_wait time
        """
        logger.info(f"Waiting for session {session_id} to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                session_info = self.get_session(session_id)
                status = session_info.get('status', 'unknown')
                
                if status == 'running':
                    logger.info(f"Session {session_id} is ready!")
                    return
                elif status in ['failed', 'error', 'terminated']:
                    raise Exception(f"Session {session_id} failed to start: {status}")
                
                # Wait before next check
                time.sleep(5)
                
            except Exception as e:
                logger.warning(f"Error checking session status: {e}")
                time.sleep(5)
        
        raise Exception(f"Session {session_id} did not become ready within {max_wait} seconds")
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and clean up all associated resources.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if session was deleted successfully, False otherwise
        
        Examples:
            # Manual session deletion
            success = client.delete_session("session-123")
            if success:
                print("Session deleted successfully")
            else:
                print("Failed to delete session")
        """
        try:
            logger.info(f"Deleting session: {session_id}")
            
            # Get session info first to check status
            session_info = self.get_session(session_id)
            status = session_info.get('status', 'unknown')
            
            if status in ['terminated', 'deleted']:
                logger.info(f"Session {session_id} already terminated")
                return True
            
            # Delete the session
            response = self._make_request("DELETE", f"/v1/sessions/{session_id}", timeout=60)
            
            if response.status_code == 200:
                logger.info(f"Session {session_id} deleted successfully")
                return True
            else:
                logger.warning(f"Failed to delete session {session_id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    def force_cleanup_session(self, session_id: str) -> bool:
        """
        Force cleanup of a session, even if it's in a problematic state.
        This is useful for cleaning up orphaned sessions.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if cleanup was attempted, False otherwise
        """
        try:
            logger.warning(f"Force cleaning up session: {session_id}")
            
            # Try multiple cleanup strategies
            cleanup_strategies = [
                lambda: self._make_request("DELETE", f"/v1/sessions/{session_id}", timeout=30),
                lambda: self._make_request("POST", f"/v1/sessions/{session_id}/terminate", timeout=30),
                lambda: self._make_request("POST", f"/v1/sessions/{session_id}/force-delete", timeout=30)
            ]
            
            for i, strategy in enumerate(cleanup_strategies):
                try:
                    response = strategy()
                    if response.status_code in [200, 204]:
                        logger.info(f"Session {session_id} force cleaned up using strategy {i+1}")
                        return True
                except Exception as e:
                    logger.debug(f"Cleanup strategy {i+1} failed: {e}")
                    continue
            
            logger.error(f"All cleanup strategies failed for session {session_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error in force cleanup for session {session_id}: {e}")
            return False
    
    def cleanup_expired_sessions(self, user: Optional[str] = None, namespace: Optional[str] = None) -> int:
        """
        Clean up expired sessions for a user or namespace.
        
        Args:
            user: User identifier (optional)
            namespace: Namespace (optional)
        
        Returns:
            Number of sessions cleaned up
        
        Examples:
            # Clean up all expired sessions for a user
            cleaned = client.cleanup_expired_sessions(user="developer")
            print(f"Cleaned up {cleaned} expired sessions")
            
            # Clean up expired sessions in a namespace
            cleaned = client.cleanup_expired_sessions(namespace="project1")
            print(f"Cleaned up {cleaned} expired sessions")
        """
        try:
            logger.info(f"Cleaning up expired sessions (user={user}, namespace={namespace})")
            
            # Get all sessions
            sessions = self.list_sessions(namespace=namespace, user=user)
            
            # Handle case where sessions might not be a list
            if not isinstance(sessions, list):
                logger.warning(f"Expected list of sessions, got {type(sessions)}: {sessions}")
                return 0
            
            cleaned_count = 0
            for session in sessions:
                if not isinstance(session, dict):
                    logger.warning(f"Expected session dict, got {type(session)}: {session}")
                    continue
                    
                session_id = session.get('id')
                status = session.get('status', 'unknown')
                
                # Check if session is expired or in a cleanup state
                if status in ['expired', 'terminated', 'failed', 'error']:
                    try:
                        if self.delete_session(session_id):
                            cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to cleanup session {session_id}: {e}")
            
            logger.info(f"Cleaned up {cleaned_count} expired sessions")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0
    
    # ============================================================================
    # Convenience Context Managers
    # ============================================================================
    
    @contextmanager
    def development_session_context(
        self,
        workspace_id: str,
        namespace: str,
        user: str,
        *,
        ttl_minutes: int = 120,
        auto_cleanup: bool = True,
        image_type: ImageType = ImageType.UBUNTU_PRO,
        cpu_size: CPUSize = CPUSize.MEDIUM,
        memory_size: MemorySize = MemorySize.MEDIUM,
        request_persistent_storage: bool = True,
        persistent_storage_size_gb: int = 20,
        **kwargs
    ):
        """
        Context manager for development sessions with Ubuntu and persistent storage.
        
        Args:
            workspace_id: Workspace identifier
            namespace: Session namespace
            user: User identifier
            ttl_minutes: Session time-to-live in minutes
            auto_cleanup: Whether to automatically delete session on exit
            image_type: Container image type
            cpu_size: CPU size specification
            memory_size: Memory size specification
            request_persistent_storage: Request persistent storage
            persistent_storage_size_gb: Persistent storage size in GB
            **kwargs: Additional session parameters
        
        Yields:
            Session information dictionary
        
        Examples:
            # Development session with auto cleanup
            with client.development_session_context(
                workspace_id="my-workspace",
                namespace="temp-dev",
                user="developer",
                ttl_minutes=60
            ) as session:
                # Install dependencies
                client.execute_session(session["id"], "apt-get update && apt-get install -y git")
                
                # Clone repository
                client.execute_session(session["id"], "git clone https://github.com/my/project.git /workspace/project")
                
                # Run tests
                result = client.execute_session(session["id"], "cd /workspace/project && python -m pytest")
                print(f"Tests passed: {result['success']}")
        """
        session = None
        try:
            session = self.create_development_session(
                workspace_id=workspace_id,
                namespace=namespace,
                user=user,
                image_type=image_type,
                cpu_size=cpu_size,
                memory_size=memory_size,
                request_persistent_storage=request_persistent_storage,
                persistent_storage_size_gb=persistent_storage_size_gb,
                ttl_minutes=ttl_minutes,
                **kwargs
            )
            
            session_id = session["id"]
            logger.info(f"Created development session in context: {session_id}")
            
            # Wait for session to be ready
            self._wait_for_session_ready(session_id)
            
            yield session
            
        except Exception as e:
            logger.error(f"Error in development session context: {e}")
            raise
        finally:
            if session and auto_cleanup:
                try:
                    session_id = session["id"]
                    logger.info(f"Auto-cleaning up development session: {session_id}")
                    self.delete_session(session_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to auto-cleanup development session {session_id}: {cleanup_error}")
    
    @contextmanager
    def python_session_context(
        self,
        workspace_id: str,
        namespace: str,
        user: str,
        *,
        ttl_minutes: int = 60,
        auto_cleanup: bool = True,
        python_version: str = "3.11-slim",
        cpu_size: CPUSize = CPUSize.SMALL,
        memory_size: MemorySize = MemorySize.SMALL,
        gpu_type: Optional[GPUType] = None,
        gpu_count: int = 1,
        request_persistent_storage: bool = False,
        persistent_storage_size_gb: int = 10,
        **kwargs
    ):
        """
        Context manager for Python sessions with optional GPU support.
        
        Args:
            workspace_id: Workspace identifier
            namespace: Session namespace
            user: User identifier
            ttl_minutes: Session time-to-live in minutes
            auto_cleanup: Whether to automatically delete session on exit
            python_version: Python version (e.g., "3.11-slim", "3.12-slim")
            cpu_size: CPU size specification
            memory_size: Memory size specification
            gpu_type: GPU type (none, t4, v100, a100, h100, l4)
            gpu_count: Number of GPUs
            request_persistent_storage: Request persistent storage
            persistent_storage_size_gb: Persistent storage size in GB
            **kwargs: Additional session parameters
        
        Yields:
            Session information dictionary
        
        Examples:
            # Python session with GPU
            with client.python_session_context(
                workspace_id="ml-workspace",
                namespace="experiment",
                user="researcher",
                gpu_type=GPUType.T4,
                request_persistent_storage=True
            ) as session:
                # Install ML libraries
                client.execute_session(session["id"], "pip install torch torchvision")
                
                # Check GPU
                result = client.execute_session(session["id"], "python -c 'import torch; print(torch.cuda.is_available())'")
                print(f"GPU available: {result['stdout'].strip()}")
        """
        session = None
        try:
            session = self.create_python_session(
                workspace_id=workspace_id,
                namespace=namespace,
                user=user,
                python_version=python_version,
                cpu_size=cpu_size,
                memory_size=memory_size,
                gpu_type=gpu_type,
                gpu_count=gpu_count,
                request_persistent_storage=request_persistent_storage,
                persistent_storage_size_gb=persistent_storage_size_gb,
                ttl_minutes=ttl_minutes,
                **kwargs
            )
            
            session_id = session["id"]
            logger.info(f"Created Python session in context: {session_id}")
            
            # Wait for session to be ready
            self._wait_for_session_ready(session_id)
            
            yield session
            
        except Exception as e:
            logger.error(f"Error in Python session context: {e}")
            raise
        finally:
            if session and auto_cleanup:
                try:
                    session_id = session["id"]
                    logger.info(f"Auto-cleaning up Python session: {session_id}")
                    self.delete_session(session_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to auto-cleanup Python session {session_id}: {cleanup_error}")
    
    @contextmanager
    def ml_session_context(
        self,
        workspace_id: str,
        namespace: str,
        user: str,
        *,
        ttl_minutes: int = 120,
        auto_cleanup: bool = True,
        gpu_type: GPUType = GPUType.T4,
        gpu_count: int = 1,
        cpu_size: CPUSize = CPUSize.LARGE,
        memory_size: MemorySize = CPUSize.XLARGE,
        python_version: str = "3.11-slim",
        request_persistent_storage: bool = True,
        persistent_storage_size_gb: int = 50,
        **kwargs
    ):
        """
        Context manager for machine learning sessions with GPU support.
        
        Args:
            workspace_id: Workspace identifier
            namespace: Session namespace
            user: User identifier
            ttl_minutes: Session time-to-live in minutes
            auto_cleanup: Whether to automatically delete session on exit
            gpu_type: GPU type (t4, v100, a100, h100, l4)
            gpu_count: Number of GPUs
            cpu_size: CPU size specification
            memory_size: Memory size specification
            python_version: Python version
            request_persistent_storage: Request persistent storage
            persistent_storage_size_gb: Persistent storage size in GB
            **kwargs: Additional session parameters
        
        Yields:
            Session information dictionary
        
        Examples:
            # ML training session
            with client.ml_session_context(
                workspace_id="ml-workspace",
                namespace="training",
                user="researcher",
                gpu_type=GPUType.A100,
                persistent_storage_size_gb=100
            ) as session:
                # Install ML libraries
                client.execute_session(session["id"], "pip install torch torchvision transformers datasets")
                
                # Run training
                result = client.execute_session(session["id"], "python train.py --epochs 10")
                print(f"Training completed: {result['success']}")
        """
        session = None
        try:
            session = self.create_ml_session(
                workspace_id=workspace_id,
                namespace=namespace,
                user=user,
                gpu_type=gpu_type,
                gpu_count=gpu_count,
                cpu_size=cpu_size,
                memory_size=memory_size,
                python_version=python_version,
                request_persistent_storage=request_persistent_storage,
                persistent_storage_size_gb=persistent_storage_size_gb,
                ttl_minutes=ttl_minutes,
                **kwargs
            )
            
            session_id = session["id"]
            logger.info(f"Created ML session in context: {session_id}")
            
            # Wait for session to be ready
            self._wait_for_session_ready(session_id)
            
            yield session
            
        except Exception as e:
            logger.error(f"Error in ML session context: {e}")
            raise
        finally:
            if session and auto_cleanup:
                try:
                    session_id = session["id"]
                    logger.info(f"Auto-cleaning up ML session: {session_id}")
                    self.delete_session(session_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to auto-cleanup ML session {session_id}: {cleanup_error}")
    
    @contextmanager
    def custom_session_context(
        self,
        workspace_id: str,
        namespace: str,
        user: str,
        image_url: str,
        *,
        ttl_minutes: int = 60,
        auto_cleanup: bool = True,
        cpu_size: CPUSize = CPUSize.SMALL,
        memory_size: MemorySize = CPUSize.SMALL,
        gpu_type: Optional[GPUType] = None,
        gpu_count: int = 1,
        request_persistent_storage: bool = False,
        persistent_storage_size_gb: int = 10,
        **kwargs
    ):
        """
        Context manager for custom image sessions.
        
        Args:
            workspace_id: Workspace identifier
            namespace: Session namespace
            user: User identifier
            image_url: Custom image URL
            ttl_minutes: Session time-to-live in minutes
            auto_cleanup: Whether to automatically delete session on exit
            cpu_size: CPU size specification
            memory_size: Memory size specification
            gpu_type: GPU type
            gpu_count: Number of GPUs
            request_persistent_storage: Request persistent storage
            persistent_storage_size_gb: Persistent storage size in GB
            **kwargs: Additional session parameters
        
        Yields:
            Session information dictionary
        
        Examples:
            # Custom image session
            with client.custom_session_context(
                workspace_id="my-workspace",
                namespace="custom-app",
                user="developer",
                image_url="gcr.io/my-project/custom-app:latest"
            ) as session:
                # Run custom application
                result = client.execute_session(session["id"], "/app/start.sh")
                print(f"Custom app started: {result['success']}")
        """
        session = None
        try:
            session = self.create_custom_session(
                workspace_id=workspace_id,
                namespace=namespace,
                user=user,
                image_url=image_url,
                cpu_size=cpu_size,
                memory_size=memory_size,
                gpu_type=gpu_type,
                gpu_count=gpu_count,
                request_persistent_storage=request_persistent_storage,
                persistent_storage_size_gb=persistent_storage_size_gb,
                ttl_minutes=ttl_minutes,
                **kwargs
            )
            
            session_id = session["id"]
            logger.info(f"Created custom session in context: {session_id}")
            
            # Wait for session to be ready
            self._wait_for_session_ready(session_id)
            
            yield session
            
        except Exception as e:
            logger.error(f"Error in custom session context: {e}")
            raise
        finally:
            if session and auto_cleanup:
                try:
                    session_id = session["id"]
                    logger.info(f"Auto-cleaning up custom session: {session_id}")
                    self.delete_session(session_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to auto-cleanup custom session {session_id}: {cleanup_error}")
    
    # ============================================================================
    # Resource Management Utilities
    # ============================================================================
    
    def get_session_cost_estimate(self, session_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get cost estimate for a session based on its specification.
        
        Args:
            session_spec: Session specification dictionary
        
        Returns:
            Cost estimate dictionary with breakdown
        
        Examples:
            # Get cost estimate for ML session
            estimate = client.get_session_cost_estimate({
                "workspace_id": "ml-workspace",
                "template": "python",
                "namespace": "experiment",
                "user": "researcher",
                "resource_package": ResourcePackage.ML_T4_MEDIUM,
                "gpu_type": GPUType.T4,
                "ttl_minutes": 120
            })
            print(f"Estimated cost: ${estimate['total_cost']}")
        """
        try:
            # This would integrate with your cost calculation logic
            # For now, return a placeholder structure
            return {
                "cpu_cost_per_hour": 0.10,
                "memory_cost_per_hour": 0.05,
                "gpu_cost_per_hour": 0.50 if session_spec.get("gpu_type") else 0.0,
                "storage_cost_per_hour": 0.01 if session_spec.get("request_persistent_storage") else 0.0,
                "total_cost_per_hour": 0.16,
                "estimated_total_cost": 0.32,  # for 2 hours
                "currency": "USD",
                "region": "us-central1"
            }
        except Exception as e:
            logger.error(f"Error calculating cost estimate: {e}")
            return {"error": str(e)}
    
    def monitor_session_usage(self, session_id: str, interval: int = 30) -> Dict[str, Any]:
        """
        Monitor resource usage for a session.
        
        Args:
            session_id: Session identifier
            interval: Monitoring interval in seconds
        
        Returns:
            Usage statistics dictionary
        
        Examples:
            # Monitor session usage
            usage = client.monitor_session_usage("session-123")
            print(f"CPU usage: {usage['cpu_percent']}%")
            print(f"Memory usage: {usage['memory_mb']} MB")
        """
        try:
            # This would integrate with your monitoring system
            # For now, return placeholder data
            return {
                "cpu_percent": 45.2,
                "memory_mb": 2048,
                "gpu_utilization": 78.5 if "gpu" in session_id else 0.0,
                "network_io_mb": 125.6,
                "disk_io_mb": 89.3,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error monitoring session usage: {e}")
            return {"error": str(e)}
