#!/usr/bin/env python3
"""
Cloud Run Workspace Manager for OnMemOS v3
==========================================
Replaces Docker-based workspace management with Cloud Run services
"""

import os
import logging
import subprocess
import time
import json
from typing import Dict, List, Optional, Any
from google.cloud import run_v2
from google.cloud import storage
from google.cloud import compute_v1

logger = logging.getLogger(__name__)

class CloudRunWorkspaceManager:
    """Manages workspaces using Cloud Run with GCS volume mounts"""
    
    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID", "ai-engine-448418")
        self.region = os.getenv("REGION", "us-central1")
        self.client = run_v2.ServicesClient()
        self.storage_client = storage.Client(project=self.project_id)
        self.compute_client = compute_v1.DisksClient()
        
    def create_workspace(self, template: str, namespace: str, user: str, 
                        ttl_minutes: int = 180, storage_options: Dict = None) -> Dict[str, Any]:
        """Create a Cloud Run workspace with GCS and Filestore mounts"""
        try:
            workspace_id = f"ws-{namespace}-{user}-{int(time.time())}"
            
            # Create GCS bucket for workspace
            bucket_name = f"onmemos-{namespace}-{user}-{int(time.time())}"
            bucket = self.storage_client.bucket(bucket_name)
            bucket.create(location=self.region)
            
            # Get or create Filestore instance for persistent storage
            filestore_instance = self._get_or_create_filestore_instance(namespace)
            
            # Create Cloud Run service
            service_name = f"onmemos-{workspace_id}"
            service_url = self._deploy_cloud_run_service(
                service_name=service_name,
                template=template,
                bucket_name=bucket_name,
                filestore_instance=filestore_instance,
                namespace=namespace,
                user=user
            )
            
            workspace = {
                "id": workspace_id,
                "template": template,
                "namespace": namespace,
                "user": user,
                "service_name": service_name,
                "service_url": service_url,
                "bucket_name": bucket_name,
                "filestore_instance": filestore_instance["name"],
                "created_at": time.time(),
                "ttl_minutes": ttl_minutes,
                "status": "running"
            }
            
            logger.info(f"✅ Created Cloud Run workspace {workspace_id}")
            return workspace
            
        except Exception as e:
            logger.error(f"Failed to create workspace: {e}")
            raise
    
    def _get_or_create_filestore_instance(self, namespace: str) -> Dict[str, Any]:
        """Get or create a Filestore instance for the namespace"""
        try:
            from google.cloud import filestore_v1
            
            filestore_client = filestore_v1.CloudFilestoreManagerClient()
            instance_name = f"onmemos-filestore-{namespace}"
            
            # Check if instance exists
            parent = f"projects/{self.project_id}/locations/{self.region}"
            instance_path = f"{parent}/instances/{instance_name}"
            
            try:
                instance = filestore_client.get_instance(name=instance_path)
                logger.info(f"✅ Using existing Filestore instance: {instance_name}")
                return {
                    "name": instance_name,
                    "ip_address": instance.networks[0].ip_addresses[0],
                    "share_name": instance.file_shares[0].name
                }
            except Exception:
                # Create new instance
                logger.info(f"🔄 Creating new Filestore instance: {instance_name}")
                
                instance = filestore_v1.Instance()
                instance.name = instance_name
                instance.tier = filestore_v1.Instance.Tier.BASIC_HDD
                instance.file_shares.add(name="workspace", capacity_gb=1024)
                instance.networks.add(
                    name="default",
                    modes=[filestore_v1.NetworkConfig.Mode.MODE_IPV4]
                )
                
                operation = filestore_client.create_instance(
                    parent=parent,
                    instance_id=instance_name,
                    instance=instance
                )
                
                # Wait for operation to complete
                result = operation.result()
                
                return {
                    "name": instance_name,
                    "ip_address": result.networks[0].ip_addresses[0],
                    "share_name": result.file_shares[0].name
                }
                
        except Exception as e:
            logger.warning(f"Failed to create Filestore instance: {e}")
            # Fallback to in-memory storage
            return {
                "name": "in-memory",
                "ip_address": None,
                "share_name": None
            }
    
    def _deploy_cloud_run_service(self, service_name: str, template: str, 
                                 bucket_name: str, filestore_instance: Dict,
                                 namespace: str, user: str) -> str:
        """Deploy a Cloud Run service with GCS and Filestore volume mounts"""
        try:
            # Build and push container image
            image_name = f"gcr.io/{self.project_id}/{service_name}:latest"
            self._build_and_push_image(image_name, template)
            
            # Base Cloud Run deploy command
            cmd = [
                "gcloud", "run", "deploy", service_name,
                "--image", image_name,
                "--region", self.region,
                "--platform", "managed",
                "--allow-unauthenticated",
                "--memory", "2Gi",
                "--cpu", "1",
                "--timeout", "3600",
                "--concurrency", "1",
                "--max-instances", "1",
                "--set-env-vars", f"WORKSPACE_ID={service_name},NAMESPACE={namespace},USER={user}",
                "--service-account", f"agent-gcs-accessor@{self.project_id}.iam.gserviceaccount.com"
            ]
            
            # Add GCS volume mount
            cmd.extend([
                "--add-volume", f"name=gcs-{bucket_name},type=cloud-storage,bucket={bucket_name}",
                "--add-volume-mount", f"volume=gcs-{bucket_name},mount-path=/workspace/buckets/{namespace}/{user}"
            ])
            
            # Add Filestore volume mount if available
            if filestore_instance["ip_address"]:
                cmd.extend([
                    "--add-volume", f"name=filestore-{namespace},type=nfs,location={filestore_instance['ip_address']}:/{filestore_instance['share_name']}",
                    "--add-volume-mount", f"volume=filestore-{namespace},mount-path=/workspace/persist/{namespace}/{user}"
                ])
            else:
                # Fallback to in-memory volume
                cmd.extend([
                    "--add-volume", f"name=tmp-{namespace},type=in-memory,size-limit=1Gi",
                    "--add-volume-mount", f"volume=tmp-{namespace},mount-path=/workspace/persist/{namespace}/{user}"
                ])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Extract service URL from output
            for line in result.stdout.split('\n'):
                if 'Service URL:' in line:
                    service_url = line.split('Service URL:')[1].strip()
                    return service_url
            
            raise Exception("Could not extract service URL from deployment")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to deploy Cloud Run service: {e.stderr}")
            raise Exception(f"Cloud Run deployment failed: {e.stderr}")
    
    def _build_and_push_image(self, image_name: str, template: str):
        """Build and push Docker image to GCR"""
        try:
            # Create Dockerfile for the template
            dockerfile_content = self._get_dockerfile_for_template(template)
            
            # Write Dockerfile
            with open("Dockerfile", "w") as f:
                f.write(dockerfile_content)
            
            # Build and push
            subprocess.run([
                "gcloud", "builds", "submit", "--tag", image_name, "."
            ], check=True)
            
            # Cleanup
            os.remove("Dockerfile")
            
        except Exception as e:
            logger.error(f"Failed to build and push image: {e}")
            raise
    
    def _get_dockerfile_for_template(self, template: str) -> str:
        """Get Dockerfile content for template"""
        if template == "python":
            return """
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    vim \
    nano \
    htop \
    tree \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --upgrade pip
RUN pip install google-cloud-storage google-cloud-compute

# Create workspace directories
RUN mkdir -p /workspace/work /workspace/tmp /workspace/buckets

# Set working directory
WORKDIR /workspace/work

# Start interactive shell
CMD ["/bin/bash"]
"""
        else:
            raise Exception(f"Template {template} not supported")
    
    def execute_in_workspace(self, workspace_id: str, command: str, 
                           timeout: int = 30) -> Dict[str, Any]:
        """Execute command in Cloud Run workspace"""
        try:
            # Get workspace info
            workspace = self.get_workspace(workspace_id)
            if not workspace:
                raise Exception(f"Workspace {workspace_id} not found")
            
            # Execute command via Cloud Run exec
            cmd = [
                "gcloud", "run", "jobs", "execute", "command",
                "--region", self.region,
                "--command", command,
                workspace["service_name"]
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
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
    
    def delete_workspace(self, workspace_id: str) -> bool:
        """Delete Cloud Run workspace and cleanup resources"""
        try:
            workspace = self.get_workspace(workspace_id)
            if not workspace:
                return False
            
            # Delete Cloud Run service
            subprocess.run([
                "gcloud", "run", "services", "delete", workspace["service_name"],
                "--region", self.region,
                "--quiet"
            ], check=False)
            
            # Delete GCS bucket
            bucket = self.storage_client.bucket(workspace["bucket_name"])
            bucket.delete(force=True)
            
            logger.info(f"✅ Deleted Cloud Run workspace {workspace_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete workspace {workspace_id}: {e}")
            return False
    
    def list_workspaces(self, namespace: Optional[str] = None, 
                       user: Optional[str] = None) -> List[Dict[str, Any]]:
        """List Cloud Run workspaces"""
        try:
            # List Cloud Run services
            parent = f"projects/{self.project_id}/locations/{self.region}"
            request = run_v2.ListServicesRequest(parent=parent)
            
            workspaces = []
            for service in self.client.list_services(request):
                if service.metadata.name.startswith("onmemos-ws-"):
                    # Parse workspace info from service name
                    parts = service.metadata.name.replace("onmemos-", "").split("-")
                    if len(parts) >= 3:
                        ws_namespace = parts[1]
                        ws_user = parts[2]
                        
                        if namespace and ws_namespace != namespace:
                            continue
                        if user and ws_user != user:
                            continue
                        
                        workspaces.append({
                            "id": service.metadata.name,
                            "namespace": ws_namespace,
                            "user": ws_user,
                            "service_name": service.metadata.name,
                            "service_url": service.status.url,
                            "status": "running" if service.status.conditions else "unknown"
                        })
            
            return workspaces
            
        except Exception as e:
            logger.error(f"Failed to list workspaces: {e}")
            return []
    
    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get workspace information"""
        workspaces = self.list_workspaces()
        for workspace in workspaces:
            if workspace["id"] == workspace_id:
                return workspace
        return None

# Global Cloud Run workspace manager instance
cloudrun_workspace_manager = CloudRunWorkspaceManager()
