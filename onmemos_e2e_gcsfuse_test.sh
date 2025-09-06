#!/usr/bin/env bash
set -euo pipefail

# End-to-end GCS Fuse mount test with full diagnostics and polling
#
# This script:
# - Ensures per-workspace namespace and KSA
# - Creates/ensures a compact GSA and binds Workload Identity (KSA -> GSA)
# - Creates or uses a bucket and grants the GSA bucket IAM
# - Deploys a test pod using gcsfuse.csi.storage.gke.io with serviceAccountName: ws-sa
# - Waits for PodScheduled and Ready, printing detailed diagnostics on failure
# - Optional cleanup
#
# Usage example:
#   ./onmemos_e2e_gcsfuse_test.sh \
#     --project ai-engine-448418 --region us-central1 --cluster onmemos-autopilot \
#     --workspace-id ws-user-XXXXXX-YYYYYY \
#     --location us-central1 \
#     --cleanup

log() { printf "%s %s\n" "[$(date +'%H:%M:%S')]" "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1"; }
need gcloud
need kubectl
need sha1sum

CMD_PROJECT=""; CMD_REGION=""; CMD_CLUSTER=""; CMD_WORKSPACE_ID=""; CMD_BUCKET=""; CMD_NS_PREFIX="onmemos"; CMD_KSA="ws-sa"; CMD_LOCATION="us-central1"; CMD_WAIT_S="600"; CMD_CLEANUP="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)        CMD_PROJECT="$2"; shift 2;;
    --project=*)      CMD_PROJECT="${1#*=}"; shift;;
    --region)         CMD_REGION="$2"; shift 2;;
    --region=*)       CMD_REGION="${1#*=}"; shift;;
    --cluster)        CMD_CLUSTER="$2"; shift 2;;
    --cluster=*)      CMD_CLUSTER="${1#*=}"; shift;;
    --workspace-id)   CMD_WORKSPACE_ID="$2"; shift 2;;
    --workspace-id=*) CMD_WORKSPACE_ID="${1#*=}"; shift;;
    --bucket)         CMD_BUCKET="$2"; shift 2;;
    --bucket=*)       CMD_BUCKET="${1#*=}"; shift;;
    --ns-prefix)      CMD_NS_PREFIX="$2"; shift 2;;
    --ns-prefix=*)    CMD_NS_PREFIX="${1#*=}"; shift;;
    --ksa)            CMD_KSA="$2"; shift 2;;
    --ksa=*)          CMD_KSA="${1#*=}"; shift;;
    --location)       CMD_LOCATION="$2"; shift 2;;
    --location=*)     CMD_LOCATION="${1#*=}"; shift;;
    --wait-seconds)   CMD_WAIT_S="$2"; shift 2;;
    --wait-seconds=*) CMD_WAIT_S="${1#*=}"; shift;;
    --cleanup)        CMD_CLEANUP="true"; shift;;
    -h|--help)
      cat <<EOF
Usage:
  $0 --project <id> --region <region> --cluster <name> \
     --workspace-id <id> [--bucket <name>] [--ns-prefix onmemos] [--ksa ws-sa] \
     [--location us-central1] [--wait-seconds 600] [--cleanup]
EOF
      exit 0;;
    *) die "unknown flag: $1";;
  esac
done

[[ -n "${CMD_PROJECT}" ]] || die "--project required"
[[ -n "${CMD_REGION}" ]] || die "--region required"
[[ -n "${CMD_CLUSTER}" ]] || die "--cluster required"
[[ -n "${CMD_WORKSPACE_ID}" ]] || die "--workspace-id required"

PROJECT="${CMD_PROJECT}"
REGION="${CMD_REGION}"
CLUSTER="${CMD_CLUSTER}"
WORKSPACE_ID="${CMD_WORKSPACE_ID}"
NS_PREFIX="${CMD_NS_PREFIX}"
KSA_NAME="${CMD_KSA}"
LOCATION="${CMD_LOCATION}"
WAIT_S="${CMD_WAIT_S}"
NS="${NS_PREFIX}-${WORKSPACE_ID}"
POD=""

PROJECT_NUMBER=$(gcloud projects describe "${PROJECT}" --format='value(projectNumber)') || die "failed to resolve project number"
WORKLOAD_POOL="${PROJECT}.svc.id.goog"

log "Cluster credentials → ${CLUSTER} (${REGION})"
gcloud container clusters get-credentials "${CLUSTER}" --region "${REGION}" --project "${PROJECT}"

log "Verify CSI drivers present"
kubectl get csidrivers | grep -E 'gcsfuse|filestore' || die "CSI drivers not found; enable GcsFuseCsiDriver and GcpFilestoreCsiDriver"

log "Ensure namespace ${NS}"
kubectl get ns "${NS}" >/dev/null 2>&1 || kubectl create ns "${NS}"

log "Ensure KSA ${NS}/${KSA_NAME}"
kubectl -n "${NS}" get sa "${KSA_NAME}" >/dev/null 2>&1 || kubectl -n "${NS}" create sa "${KSA_NAME}"

NS_HASH=$(printf "%s" "${NS}" | sha1sum | awk '{print $1}' | cut -c1-10)
GSA_ID="gsa-${NS_HASH}-sa"
GSA_EMAIL="${GSA_ID}@${PROJECT}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "${GSA_EMAIL}" --project "${PROJECT}" >/dev/null 2>&1; then
  log "Create GSA ${GSA_EMAIL}"
  gcloud iam service-accounts create "${GSA_ID}" --display-name="GSA for ${NS}" --project "${PROJECT}"
else
  log "GSA ${GSA_EMAIL} exists"
fi

log "Bind Workload Identity: ${NS}/${KSA_NAME} -> ${GSA_EMAIL}"
gcloud iam service-accounts add-iam-policy-binding "${GSA_EMAIL}" \
  --role roles/iam.workloadIdentityUser \
  --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_POOL}/subject/ns/${NS}/sa/${KSA_NAME}" \
  --project "${PROJECT}"

log "Annotate KSA"
kubectl -n "${NS}" annotate sa "${KSA_NAME}" iam.gke.io/gcp-service-account="${GSA_EMAIL}" --overwrite

if [[ -z "${CMD_BUCKET}" ]]; then
  # create a new bucket
  BUCKET="onmemos-${WORKSPACE_ID}-$(date +%s)"
  log "Create bucket gs://${BUCKET} in ${LOCATION}"
  gcloud storage buckets create "gs://${BUCKET}" --location "${LOCATION}" --project "${PROJECT}"
else
  BUCKET="${CMD_BUCKET}"
  log "Using bucket gs://${BUCKET}"
fi

log "Grant bucket IAM to ${GSA_EMAIL}"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member "serviceAccount:${GSA_EMAIL}" \
  --role roles/storage.objectAdmin \
  --project "${PROJECT}"

log "Wait 60s for IAM propagation"
sleep 60

POD_NAME="onmemos-${WORKSPACE_ID}-$(date +%s)"
K8S_NS="${NS_PREFIX}-${WORKSPACE_ID}"

log "Apply test pod manifest (gcsfuse CSI)"
cat <<YAML | kubectl -n "${K8S_NS}" apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: ${POD_NAME}
  namespace: ${K8S_NS}
  annotations:
    gke-gcsfuse/volumes: "true"
  labels:
    onmemos_workspace_id: ${WORKSPACE_ID}
    namespace: ${WORKSPACE_ID}
spec:
  serviceAccountName: ${KSA_NAME}
  restartPolicy: Never
  securityContext:
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: main
    image: alpine:latest
    imagePullPolicy: IfNotPresent
    command: ["/bin/sh", "-c", "ls -la /workspace && sleep 3600"]
    env:
    - name: BUCKET_NAME
      value: "${BUCKET}"
    volumeMounts:
    - name: gcs-fuse
      mountPath: /workspace
    resources:
      requests: { cpu: "250m", memory: "512Mi" }
      limits:   { cpu: "500m", memory: "1Gi" }
  volumes:
  - name: gcs-fuse
    csi:
      driver: gcsfuse.csi.storage.gke.io
      readOnly: false
      volumeAttributes:
        bucketName: "${BUCKET}"
        mountOptions: "implicit-dirs,only-dir=workspace/,file-mode=0644,dir-mode=0755"
YAML

log "Wait for PodScheduled (timeout ${WAIT_S}s)"
if ! kubectl -n "${K8S_NS}" wait --for=condition=PodScheduled --timeout=${WAIT_S}s pod "${POD_NAME}"; then
  log "Pod failed to schedule; describe and events:"
  kubectl -n "${K8S_NS}" describe pod "${POD_NAME}" || true
  kubectl -n "${K8S_NS}" get events --sort-by=.lastTimestamp | tail -n 100 || true
  exit 2
fi

log "Wait for Ready (timeout ${WAIT_S}s)"
if ! kubectl -n "${K8S_NS}" wait --for=condition=Ready --timeout=${WAIT_S}s pod "${POD_NAME}"; then
  log "Pod failed to become Ready; diagnostics:"
  kubectl -n "${K8S_NS}" describe pod "${POD_NAME}" || true
  kubectl -n "${K8S_NS}" get events --sort-by=.lastTimestamp | tail -n 100 || true
  echo "Suggested checks:"
  echo "- KSA annotation: kubectl -n ${K8S_NS} get sa ${KSA_NAME} -o jsonpath=\"{.metadata.annotations['iam.gke.io/gcp-service-account']}\""
  echo "- Bucket IAM for ${GSA_EMAIL}: gcloud storage buckets get-iam-policy gs://${BUCKET} --project ${PROJECT}"
  exit 3
fi

log "SUCCESS: Pod is Ready and GCS Fuse is mounted at /workspace"

if [[ "${CMD_CLEANUP}" == "true" ]]; then
  log "Cleanup: delete pod"
  kubectl -n "${K8S_NS}" delete pod "${POD_NAME}" --ignore-not-found
fi


