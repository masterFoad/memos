"""
Workspace Manager for OnMemOS v3
"""
import os
import logging
import subprocess
import tempfile
import time
from typing import Dict, List, Optional, Any
from server.services.gcp.bucket_service import GCSBucketService
from server.services.gcp.disk_service import GCPDiskService
from server.core.config import load_settings

logger = logging.getLogger(__name__)

class WorkspaceManager:
    """Manages workspace lifecycle with real GCP integration"""
    
    def __init__(self):
        self.workspaces = {}
        self.bucket_service = GCSBucketService()
        self.disk_service = GCPDiskService()
        self.settings = load_settings()
        
    def create_workspace(self, template: str, namespace: str, user: str, 
                        ttl_minutes: int = 180, storage_options: Dict = None) -> Dict[str, Any]:
        """Create a new workspace with real GCP storage"""
        try:
            workspace_id = f"ws-{namespace}-{user}-{int(time.time())}"
            
            # Create real GCS bucket
            bucket_name = f"onmemos-{namespace}-{user}-{int(time.time())}"
            bucket_info = self.bucket_service.create_bucket(bucket_name, namespace, user)
            
            # Create real GCP persistent disk
            disk_name = f"onmemos-persist-{namespace}-{user}-{int(time.time())}"
            disk_size = storage_options.get("disk_size_gb", 10) if storage_options else 10
            disk_info = self.disk_service.create_disk(disk_name, namespace, user, disk_size)
            
            # Create Docker container with real mounts
            container_id = self._create_container_with_real_mounts(
                workspace_id, template, bucket_info, disk_info
            )
            
            workspace = {
                "id": workspace_id,
                "template": template,
                "namespace": namespace,
                "user": user,
                "container_id": container_id,
                "bucket": bucket_info,
                "disk": disk_info,
                "created_at": time.time(),
                "ttl_minutes": ttl_minutes,
                "status": "running"
            }
            
            self.workspaces[workspace_id] = workspace
            logger.info(f"✅ Created workspace {workspace_id} with real GCP storage")
            
            return workspace
            
        except Exception as e:
            logger.error(f"Failed to create workspace: {e}")
            raise
    
    def _create_container_with_real_mounts(self, workspace_id: str, template: str, 
                                         bucket_info: Dict, disk_info: Dict) -> str:
        """Create Docker container with real GCP mounts"""
        try:
            # Load template
            template_path = f"server/templates/{template}.yaml"
            if not os.path.exists(template_path):
                raise Exception(f"Template {template} not found")
            
            # Create container with real mounts
            container_name = f"onmemos-{workspace_id}"
            
            # Base Docker run command
            cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--rm",
                "--privileged",  # Needed for gcsfuse
                "--cap-add", "SYS_ADMIN",  # Needed for mounting
                "--device", "/dev/fuse",  # FUSE device
                "-e", "GOOGLE_APPLICATION_CREDENTIALS=/etc/gcp/credentials.json",
                "-v", f"{os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}:/etc/gcp/credentials.json:ro",
                "-p", "8080:8080"
            ]
            
            # Add template-specific mounts
            if template == "python":
                cmd.extend([
                    "-v", "/tmp/onmemos/work:/work:rw",
                    "-v", "/tmp/onmemos/tmp:/tmp:rw"
                ])
            
            # Add image
            cmd.extend([f"python:3.11-slim"])
            
            # Start command that sets up mounts
            cmd.extend([
                "sh", "-c", 
                f"""
                # Install gcsfuse
                apt-get update && apt-get install -y gcsfuse fuse
                
                # Create mount points
                mkdir -p {bucket_info['mount_path']} {disk_info['mount_path']}
                
                # Mount GCS bucket
                gcsfuse --implicit-dirs --only-dir {bucket_info['prefix']} {bucket_info['bucket_name']} {bucket_info['mount_path']}
                
                # For persistent disk, we'll use a local directory for now
                # In production, you'd attach the actual disk
                mkdir -p {disk_info['mount_path']}
                chmod 755 {disk_info['mount_path']}
                
                # Start interactive shell
                exec /bin/bash
                """
            ])
            
            # Run container
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            container_id = result.stdout.strip()
            
            logger.info(f"✅ Created container {container_id} with real GCP mounts")
            return container_id
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create container: {e.stderr}")
            raise Exception(f"Container creation failed: {e.stderr}")
        except Exception as e:
            logger.error(f"Failed to create container: {e}")
            raise
    
    def list_workspaces(self, namespace: Optional[str] = None, 
                       user: Optional[str] = None) -> List[Dict[str, Any]]:
        """List workspaces with optional filtering"""
        workspaces = list(self.workspaces.values())
        
        if namespace:
            workspaces = [w for w in workspaces if w["namespace"] == namespace]
        if user:
            workspaces = [w for w in workspaces if w["user"] == user]
            
        return workspaces
    
    def delete_workspace(self, workspace_id: str) -> bool:
        """Delete a workspace and cleanup GCP resources"""
        if workspace_id not in self.workspaces:
            return False
            
        workspace = self.workspaces[workspace_id]
        
        try:
            # Stop and remove container
            if workspace.get("container_id"):
                subprocess.run([
                    "docker", "stop", workspace["container_id"]
                ], check=False)
                subprocess.run([
                    "docker", "rm", workspace["container_id"]
                ], check=False)
            
            # Delete GCP resources
            if workspace.get("bucket"):
                self.bucket_service.delete_bucket(workspace["bucket"]["bucket_name"])
            
            if workspace.get("disk"):
                self.disk_service.delete_disk(workspace["disk"]["disk_name"])
            
            # Remove from local tracking
            del self.workspaces[workspace_id]
            
            logger.info(f"✅ Deleted workspace {workspace_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete workspace {workspace_id}: {e}")
            return False
    
    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get workspace information"""
        return self.workspaces.get(workspace_id)
    
    def execute_in_workspace(self, workspace_id: str, command: str, 
                           timeout: int = 30) -> Dict[str, Any]:
        """Execute command in workspace container"""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise Exception(f"Workspace {workspace_id} not found")
        
        try:
            result = subprocess.run([
                "docker", "exec", workspace["container_id"],
                "sh", "-c", command
            ], capture_output=True, text=True, timeout=timeout)
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            raise Exception(f"Command timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Failed to execute command in workspace {workspace_id}: {e}")
            raise

# Global workspace manager instance
workspace_manager = WorkspaceManager()
