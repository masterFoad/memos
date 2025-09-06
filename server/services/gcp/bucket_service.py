"""
Real GCS Bucket Service for OnMemOS v3
"""
import os
import subprocess
from typing import Dict, List, Optional, Any

from google.cloud import storage
from google.cloud.exceptions import NotFound, Conflict
from google.api_core.exceptions import GoogleAPIError

from server.core.logging import get_storage_logger

logger = get_storage_logger()


class GCSBucketService:
    """Real GCS bucket service using google-cloud-storage"""

    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID", "ai-engine-448418")
        self.region = os.getenv("REGION", "us-central1")

        # Production-ready authentication strategy (no interface changes)
        self.client: storage.Client
        last_err: Optional[Exception] = None

        # 1) Service Account Key (VMs/local dev with key file)
        try:
            key_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./service-account-key.json")
            if key_file and os.path.exists(key_file):
                self.client = storage.Client.from_service_account_json(key_file, project=self.project_id)
                logger.info(f"✅ Using Service Account Key File: {key_file}")
            else:
                raise FileNotFoundError("No service account key file found")
            return
        except Exception as e:
            last_err = e
            logger.warning(f"Service Account Key failed: {e}")

        # 2) Workload Identity / Metadata (GKE/GCE)
        try:
            from google.auth import default
            credentials, project = default()
            self.client = storage.Client(credentials=credentials, project=project or self.project_id)
            logger.info("✅ Using Workload Identity / Metadata Server authentication")
            return
        except Exception as e2:
            last_err = e2
            logger.warning(f"Workload Identity / Metadata auth failed: {e2}")

        # 3) gcloud CLI ADC (developer machines)
        try:
            result = subprocess.run(
                ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
                capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                service_account = result.stdout.strip()
                logger.info(f"✅ Using gcloud CLI ADC: {service_account}")
                # Clear any stale file creds to force ADC
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""
                from google.auth import default
                credentials, project = default()
                self.client = storage.Client(credentials=credentials, project=project or self.project_id)
                return
            raise RuntimeError("No active gcloud account")
        except Exception as e3:
            last_err = e3
            logger.error(f"gcloud ADC auth failed: {e3}")

        # 4) Basic client as last resort (likely to fail on first operation, but clearer error)
        logger.error(f"All authentication methods failed; falling back to default client. Last error: {last_err}")
        self.client = storage.Client(project=self.project_id)

    # ------------------------------- CRUD ------------------------------- #

    def create_bucket(self, bucket_name: str, namespace: str, user: str) -> Dict[str, Any]:
        """Create a real GCS bucket"""
        try:
            bucket = self.client.bucket(bucket_name)
            bucket.create(location=self.region)

            # Enable uniform bucket-level access and attach labels (labels are additive/helpful, no IO change)
            try:
                bucket.iam_configuration.uniform_bucket_level_access_enabled = True  # type: ignore[attr-defined]
                # Attach lightweight labels for easier ops
                labels = bucket.labels or {}
                labels.update({"onmemos": "true", "namespace": namespace, "user": user})
                bucket.labels = labels
                bucket.patch()
            except GoogleAPIError as e:
                logger.warning(f"Could not set UBLA/labels on bucket {bucket_name}: {e}")

            # Create namespace/user prefix structure marker
            prefix = f"{namespace}/{user}/"
            marker = bucket.blob(f"{prefix}.metadata")
            marker.upload_from_string(f"Created for namespace={namespace}, user={user}")

            logger.info(f"✅ Created real GCS bucket: {bucket_name}")

            return {
                "bucket_name": bucket_name,
                "namespace": namespace,
                "user": user,
                "prefix": prefix,
                "location": self.region,
                "url": f"gs://{bucket_name}",
                "mount_path": f"/buckets/{namespace}/{user}",
            }

        except Conflict:
            logger.warning(f"Bucket {bucket_name} already exists")
            return self.get_bucket_info(bucket_name, namespace, user)
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            raise

    def get_bucket_info(self, bucket_name: str, namespace: str, user: str) -> Dict[str, Any]:
        """Get bucket information"""
        try:
            bucket = self.client.bucket(bucket_name)
            bucket.reload()

            prefix = f"{namespace}/{user}/"
            return {
                "bucket_name": bucket_name,
                "namespace": namespace,
                "user": user,
                "prefix": prefix,
                "location": bucket.location,
                "url": f"gs://{bucket_name}",
                "mount_path": f"/buckets/{namespace}/{user}",
                "created": bucket.time_created.isoformat() if bucket.time_created else None,
            }
        except NotFound:
            raise Exception(f"Bucket {bucket_name} not found")
        except Exception as e:
            logger.error(f"Failed to get bucket info for {bucket_name}: {e}")
            raise

    def list_buckets_in_namespace(self, namespace: str) -> List[Dict[str, Any]]:
        """List buckets for a namespace (heuristic: presence of any object under {namespace}/)"""
        try:
            buckets: List[Dict[str, Any]] = []
            for bucket in self.client.list_buckets():
                try:
                    # Efficient check: look for *any* blob with the namespace prefix
                    # (original code looked for `{namespace}/.metadata`, but creation uses `{namespace}/{user}/.metadata`)
                    iterator = bucket.list_blobs(prefix=f"{namespace}/", max_results=1)
                    has_namespace = any(True for _ in iterator)
                    if has_namespace:
                        buckets.append({
                            "bucket_name": bucket.name,
                            "namespace": namespace,
                            "location": bucket.location,
                            "url": f"gs://{bucket.name}",
                            "created": bucket.time_created.isoformat() if bucket.time_created else None,
                        })
                except Exception:
                    continue
            return buckets
        except Exception as e:
            logger.error(f"Failed to list buckets for namespace {namespace}: {e}")
            return []

    def delete_bucket(self, bucket_name: str) -> bool:
        """Delete a GCS bucket (handles non-empty buckets safely)"""
        try:
            bucket = self.client.bucket(bucket_name)

            # Try fast path: force-delete (if available in installed client)
            try:
                bucket.delete(force=True)  # type: ignore[call-arg]
                logger.info(f"✅ Deleted GCS bucket: {bucket_name}")
                return True
            except TypeError:
                # Older client without `force` param; fall through to manual delete
                pass
            except GoogleAPIError:
                # Some servers reject force: continue with manual cleanup
                pass

            # Manual deletion of all object versions, then bucket
            try:
                # Delete current versions
                for blob in bucket.list_blobs():
                    blob.delete()

                # Delete archived versions if versioning had been enabled
                for blob in bucket.list_blobs(versions=True):
                    try:
                        blob.delete()
                    except Exception:
                        # Best effort on versions; continue
                        continue

                bucket.delete()
                logger.info(f"✅ Deleted GCS bucket: {bucket_name}")
                return True
            except NotFound:
                logger.warning(f"Bucket {bucket_name} not found for deletion")
                return True
        except Exception as e:
            logger.error(f"Failed to delete bucket {bucket_name}: {e}")
            return False

    def clone_bucket(self, source_bucket: str, new_bucket: str, namespace: str, user: str) -> Dict[str, Any]:
        """Clone a bucket by copying all objects (supports multi-chunk rewrite)"""
        try:
            # Create destination bucket
            new_bucket_info = self.create_bucket(new_bucket, namespace, user)

            src = self.client.bucket(source_bucket)
            dst = self.client.bucket(new_bucket)

            for blob in src.list_blobs():
                new_blob = dst.blob(blob.name)
                token: Optional[str] = None
                # rewrite() may require multiple calls for large objects
                while True:
                    token, _bytes_rewritten, _total_bytes = new_blob.rewrite(blob, token=token)
                    if token is None:
                        break

            logger.info(f"✅ Cloned bucket {source_bucket} -> {new_bucket}")
            return new_bucket_info

        except Exception as e:
            logger.error(f"Failed to clone bucket {source_bucket}: {e}")
            raise

    def mount_bucket_in_container(self, bucket_name: str, namespace: str, user: str, container_id: str) -> str:
        """Mount GCS bucket in container using gcsfuse (best-effort, distro-aware)"""
        mount_path = f"/buckets/{namespace}/{user}"
        try:
            # Ensure mount directory exists
            subprocess.run(
                ["docker", "exec", container_id, "sh", "-c", f"mkdir -p {mount_path}"],
                check=True
            )

            # Ensure gcsfuse present (try common distros)
            install_cmds = [
                "which gcsfuse || (apt-get update && apt-get install -y gcsfuse)",          # Debian/Ubuntu
                "which gcsfuse || (apk add --no-cache gcsfuse || true)",                    # Alpine (if package repo has it)
                "which gcsfuse || (yum install -y gcsfuse || dnf install -y gcsfuse || true)",  # RHEL/CentOS/Fedora
            ]
            for cmd in install_cmds:
                subprocess.run(["docker", "exec", container_id, "sh", "-c", cmd], check=False)

            # Attempt mount (implicit dirs, mount only the namespace/user prefix)
            mount_cmd = (
                f"gcsfuse --implicit-dirs --only-dir {namespace}/{user} {bucket_name} {mount_path}"
            )
            res = subprocess.run(["docker", "exec", container_id, "sh", "-c", mount_cmd], capture_output=True, text=True)

            if res.returncode != 0:
                logger.error(f"gcsfuse mount failed: {res.stderr.strip()}")
                raise Exception(res.stderr.strip())

            logger.info(f"✅ Mounted GCS bucket {bucket_name} at {mount_path} in container {container_id}")
            return mount_path

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to mount bucket {bucket_name}: {e}")
            raise Exception(f"Failed to mount GCS bucket: {e}")
        except Exception as e:
            logger.error(f"Failed to mount bucket {bucket_name}: {e}")
            raise


# Global instance
bucket_service = GCSBucketService()
