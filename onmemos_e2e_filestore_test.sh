#!/usr/bin/env bash
set -euo pipefail

# End-to-end Filestore mount test (PVC) with diagnostics and polling
# - Ensures namespace/KSA/GSA/Workload Identity
# - Resolves Filestore IP (from instance+zone or direct IP)
# - Creates PV (NFS) + PVC and mounts in a test pod
# - Waits for PodScheduled and Ready; prints describe/events on failure
# - Optional cleanup
#
# Usage examples:
#   ./onmemos_e2e_filestore_test.sh \
#     --project ai-engine-448418 --region us-central1 --cluster onmemos-autopilot \
#     --workspace-id ws-user-XXXXXX-YYYYYY \
#     --fs-instance fs-onmemos-dev --fs-zone us-central1-a \
#     --export-path /share1/ws-user-XXXXXX-YYYYYY \
#     --cleanup
#
#   ./onmemos_e2e_filestore_test.sh \
#     --project ai-engine-448418 --region us-central1 --cluster onmemos-autopilot \
#     --workspace-id ws-user-XXXXXX-YYYYYY \
#     --fs-ip 10.0.0.5 --export-path /share1/ws-user-XXXXXX-YYYYYY \
#     --cleanup

log() { printf "%s %s\n" "[$(date +'%H:%M:%S')]" "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1"; }
need gcloud
need kubectl
need sha1sum

PROJECT=""; REGION=""; CLUSTER=""; WORKSPACE_ID=""; NS_PREFIX="onmemos"; KSA_NAME="ws-sa";
FS_INSTANCE=""; FS_ZONE=""; FS_IP=""; EXPORT_PATH=""; PVC_SIZE="100Gi"; WAIT_S=600; CLEANUP=false
# Optional GCS bucket to mount alongside Filestore
BUCKET=""; LOCATION="us-central1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2;;
    --project=*) PROJECT="${1#*=}"; shift;;
    --region) REGION="$2"; shift 2;;
    --region=*) REGION="${1#*=}"; shift;;
    --cluster) CLUSTER="$2"; shift 2;;
    --cluster=*) CLUSTER="${1#*=}"; shift;;
    --workspace-id) WORKSPACE_ID="$2"; shift 2;;
    --workspace-id=*) WORKSPACE_ID="${1#*=}"; shift;;
    --ns-prefix) NS_PREFIX="$2"; shift 2;;
    --ns-prefix=*) NS_PREFIX="${1#*=}"; shift;;
    --ksa) KSA_NAME="$2"; shift 2;;
    --ksa=*) KSA_NAME="${1#*=}"; shift;;
    --fs-instance) FS_INSTANCE="$2"; shift 2;;
    --fs-instance=*) FS_INSTANCE="${1#*=}"; shift;;
    --fs-zone) FS_ZONE="$2"; shift 2;;
    --fs-zone=*) FS_ZONE="${1#*=}"; shift;;
    --fs-ip) FS_IP="$2"; shift 2;;
    --fs-ip=*) FS_IP="${1#*=}"; shift;;
    --export-path) EXPORT_PATH="$2"; shift 2;;
    --export-path=*) EXPORT_PATH="${1#*=}"; shift;;
    --pvc-size) PVC_SIZE="$2"; shift 2;;
    --pvc-size=*) PVC_SIZE="${1#*=}"; shift;;
    --wait-seconds) WAIT_S="$2"; shift 2;;
    --wait-seconds=*) WAIT_S="${1#*=}"; shift;;
    --bucket) BUCKET="$2"; shift 2;;
    --bucket=*) BUCKET="${1#*=}"; shift;;
    --location) LOCATION="$2"; shift 2;;
    --location=*) LOCATION="${1#*=}"; shift;;
    --cleanup) CLEANUP=true; shift;;
    -h|--help)
      cat <<EOF
Usage:
  $0 --project <id> --region <region> --cluster <name> --workspace-id <id> \
     (--fs-instance <name> --fs-zone <zone> | --fs-ip <ip>) --export-path </export/path> \
     [--bucket <name>] [--location us-central1] \
     [--ns-prefix onmemos] [--ksa ws-sa] [--pvc-size 100Gi] [--wait-seconds 600] [--cleanup]
EOF
      exit 0;;
    *) die "unknown flag: $1";;
  esac
done

[[ -n "$PROJECT" && -n "$REGION" && -n "$CLUSTER" && -n "$WORKSPACE_ID" ]] || die "missing required flags"
[[ -n "$EXPORT_PATH" ]] || die "--export-path required (e.g., /share1/$WORKSPACE_ID)"

NS="${NS_PREFIX}-${WORKSPACE_ID}"

log "Cluster credentials → $CLUSTER ($REGION)"
gcloud container clusters get-credentials "$CLUSTER" --region "$REGION" --project "$PROJECT"

log "Ensure namespace $NS"
kubectl get ns "$NS" >/dev/null 2>&1 || kubectl create ns "$NS"

log "Ensure KSA $NS/$KSA_NAME"
kubectl -n "$NS" get sa "$KSA_NAME" >/dev/null 2>&1 || kubectl -n "$NS" create sa "$KSA_NAME"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
WORKLOAD_POOL="$PROJECT.svc.id.goog"
NS_HASH=$(printf "%s" "$NS" | sha1sum | awk '{print $1}' | cut -c1-10)
GSA_ID="gsa-${NS_HASH}-sa"
GSA_EMAIL="$GSA_ID@$PROJECT.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$GSA_EMAIL" --project "$PROJECT" >/dev/null 2>&1; then
  log "Create GSA $GSA_EMAIL"
  gcloud iam service-accounts create "$GSA_ID" --display-name="GSA for $NS" --project "$PROJECT"
else
  log "GSA $GSA_EMAIL exists"
fi

log "Bind Workload Identity"
gcloud iam service-accounts add-iam-policy-binding "$GSA_EMAIL" \
  --role roles/iam.workloadIdentityUser \
  --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_POOL}/subject/ns/${NS}/sa/${KSA_NAME}" \
  --project "$PROJECT"

log "Annotate KSA"
kubectl -n "$NS" annotate sa "$KSA_NAME" iam.gke.io/gcp-service-account="$GSA_EMAIL" --overwrite

# Resolve Filestore IP
if [[ -z "$FS_IP" ]]; then
  [[ -n "$FS_INSTANCE" && -n "$FS_ZONE" ]] || die "provide --fs-ip or (--fs-instance and --fs-zone)"
  log "Resolve Filestore IP from instance $FS_INSTANCE ($FS_ZONE)"
  FS_IP=$(gcloud filestore instances describe "$FS_INSTANCE" --zone "$FS_ZONE" --format="value(networks[0].ipAddresses[0])")
fi
[[ -n "$FS_IP" ]] || die "unable to resolve Filestore IP"

PV_NAME="pv-$WORKSPACE_ID"
PVC_NAME="pvc-$WORKSPACE_ID"
POD_NAME="test-dual-$WORKSPACE_ID-$(date +%s)"

# Optionally ensure a GCS bucket and grant IAM so we can mount both
if [[ -z "$BUCKET" ]]; then
  BUCKET="onmemos-$WORKSPACE_ID-$(date +%s)"
  log "Create bucket gs://$BUCKET in $LOCATION"
  gcloud storage buckets create "gs://$BUCKET" --location "$LOCATION" --project "$PROJECT"
else
  log "Using bucket gs://$BUCKET"
fi

log "Grant bucket IAM to $GSA_EMAIL"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member "serviceAccount:$GSA_EMAIL" \
  --role roles/storage.objectAdmin \
  --project "$PROJECT"

log "Wait 60s for IAM propagation"
sleep 60

log "Create PV + PVC (NFS: $FS_IP:$EXPORT_PATH, size $PVC_SIZE)"
cat <<YAML | kubectl -n "$NS" apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
  name: $PV_NAME
spec:
  capacity:
    storage: $PVC_SIZE
  accessModes:
  - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  nfs:
    server: $FS_IP
    path: $EXPORT_PATH
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: $PVC_NAME
spec:
  accessModes:
  - ReadWriteMany
  resources:
    requests:
      storage: $PVC_SIZE
  volumeName: $PV_NAME
YAML

log "Apply test pod mounting both PVC and GCS Fuse"
cat <<YAML | kubectl -n "$NS" apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: $POD_NAME
spec:
  serviceAccountName: $KSA_NAME
  restartPolicy: Never
  containers:
  - name: main
    image: alpine:latest
    command: ["/bin/sh","-c","echo hello > /data/hello.txt && ls -la /data && ls -la /workspace && sleep 3600"]
    volumeMounts:
    - name: filestore
      mountPath: /data
    - name: gcs-fuse
      mountPath: /workspace
  volumes:
  - name: filestore
    persistentVolumeClaim:
      claimName: $PVC_NAME
  - name: gcs-fuse
    csi:
      driver: gcsfuse.csi.storage.gke.io
      readOnly: false
      volumeAttributes:
        bucketName: "$BUCKET"
        mountOptions: "implicit-dirs,only-dir=workspace/,file-mode=0644,dir-mode=0755"
YAML

log "Wait for PodScheduled (timeout ${WAIT_S}s)"
kubectl -n "$NS" wait --for=condition=PodScheduled --timeout=${WAIT_S}s pod "$POD_NAME" || {
  kubectl -n "$NS" describe pod "$POD_NAME" || true
  kubectl -n "$NS" get events --sort-by=.lastTimestamp | tail -n 100 || true
  exit 2
}

log "Wait for Ready (timeout ${WAIT_S}s)"
kubectl -n "$NS" wait --for=condition=Ready --timeout=${WAIT_S}s pod "$POD_NAME" || {
  kubectl -n "$NS" describe pod "$POD_NAME" || true
  kubectl -n "$NS" get events --sort-by=.lastTimestamp | tail -n 100 || true
  exit 3
}

log "SUCCESS: Pod is Ready; Filestore mounted at /data and GCS Fuse mounted at /workspace"

if $CLEANUP; then
  log "Cleanup: delete pod (PV/PVC retained)"
  kubectl -n "$NS" delete pod "$POD_NAME" --ignore-not-found
fi


