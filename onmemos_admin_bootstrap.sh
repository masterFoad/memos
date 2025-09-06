#!/usr/bin/env bash
set -euo pipefail

# OnMemOS Admin Bootstrap Script
# - cluster-init: enable GCS Fuse + Filestore CSI drivers (once per cluster)
# - workspace-init: per-workspace namespace/KSA/GSA, Workload Identity bind, optional bucket IAM
#
# Examples:
#   ./onmemos_admin_bootstrap.sh cluster-init \
#     --project ai-engine-448418 --region us-central1 \
#     --clusters "imru-cluster onmemos-autopilot"
#
#   ./onmemos_admin_bootstrap.sh workspace-init \
#     --project ai-engine-448418 --region us-central1 \
#     --cluster onmemos-autopilot \
#     --workspace-id ws-user-89b18813-02d512 \
#     --bucket onmemos-ws-user-89b18813-02d512-user-89b18813-1756919708

log() { printf "%s %s\n" "[$(date +'%H:%M:%S')]" "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1"; }
need gcloud
need kubectl

usage() {
  cat <<USAGE
Usage:
  $0 cluster-init --project <id> --region <region> --clusters "CL1 CL2 ..."
  $0 workspace-init --project <id> --region <region> \
      --cluster <name> --workspace-id <id> [--bucket <name>] [--ns-prefix onmemos] [--ksa-name ws-sa]

Notes:
  - Run with an admin identity that can create service accounts and modify IAM.
  - Namespace will be <ns-prefix>-<workspace-id> (default prefix 'onmemos').
USAGE
}

# Parse flags supporting both --key=value and --key value
parse_flags() {
  # normalizes into KEY=VALUE variables in the caller's scope
  while [[ $# -gt 0 ]]; do
    case "$1" in
      cluster-init|workspace-init)
        CMD="$1"; shift;;
      --project)
        PROJECT="$2"; shift 2;;
      --project=*)
        PROJECT="${1#*=}"; shift;;
      --region)
        REGION="$2"; shift 2;;
      --region=*)
        REGION="${1#*=}"; shift;;
      --clusters)
        CLUSTERS="$2"; shift 2;;
      --clusters=*)
        CLUSTERS="${1#*=}"; shift;;
      --cluster)
        CLUSTER="$2"; shift 2;;
      --cluster=*)
        CLUSTER="${1#*=}"; shift;;
      --workspace-id)
        WORKSPACE_ID="$2"; shift 2;;
      --workspace-id=*)
        WORKSPACE_ID="${1#*=}"; shift;;
      --bucket)
        BUCKET="$2"; shift 2;;
      --bucket=*)
        BUCKET="${1#*=}"; shift;;
      --ns-prefix)
        NS_PREFIX="$2"; shift 2;;
      --ns-prefix=*)
        NS_PREFIX="${1#*=}"; shift;;
      --ksa-name)
        KSA_NAME="$2"; shift 2;;
      --ksa-name=*)
        KSA_NAME="${1#*=}"; shift;;
      -h|--help)
        usage; exit 0;;
      *)
        die "unknown flag or arg: $1";;
    esac
  done
}

CMD=""; PROJECT=""; REGION=""; CLUSTERS=""; CLUSTER=""; WORKSPACE_ID=""; BUCKET="";
NS_PREFIX="onmemos"; KSA_NAME="ws-sa"
parse_flags "$@"

[[ -n "${CMD}" ]] || { usage; die "missing command"; }
[[ -n "${PROJECT}" ]] || die "--project is required"
[[ -n "${REGION}" ]] || die "--region is required"

PROJECT_NUMBER=$(gcloud projects describe "${PROJECT}" --format='value(projectNumber)') || die "failed to resolve project number"
WORKLOAD_POOL="${PROJECT}.svc.id.goog"

cluster_init() {
  [[ -n "${CLUSTERS}" ]] || die "--clusters is required"

  log "Enabling GCS Fuse + Filestore CSI drivers on: ${CLUSTERS}"
  for CL in ${CLUSTERS}; do
    log "→ ${CL}"
    gcloud container clusters update "${CL}" --region "${REGION}" \
      --update-addons=GcsFuseCsiDriver=ENABLED,GcpFilestoreCsiDriver=ENABLED \
      --project "${PROJECT}" || die "failed to update addons for ${CL}"
  done

  # Verify on the first cluster
  FIRST=$(echo "${CLUSTERS}" | awk '{print $1}')
  gcloud container clusters get-credentials "${FIRST}" --region "${REGION}" --project "${PROJECT}"
  log "CSI drivers present:"
  kubectl get csidrivers | grep -E 'gcsfuse|filestore' || true
  log "Cluster init complete."
}

workspace_init() {
  [[ -n "${CLUSTER}" ]] || die "--cluster is required"
  [[ -n "${WORKSPACE_ID}" ]] || die "--workspace-id is required"

  local NS="${NS_PREFIX}-${WORKSPACE_ID}"
  local KSA="${KSA_NAME}"
  # GSA id must be 6-30 chars; derive a short, deterministic id from the namespace
  local NS_HASH
  NS_HASH=$(printf "%s" "${NS}" | sha1sum | awk '{print $1}' | cut -c1-10)
  local GSA="gsa-${NS_HASH}-sa"   # length <= 30, lowercase, hyphens only
  local GSA_EMAIL="${GSA}@${PROJECT}.iam.gserviceaccount.com"

  log "Fetching kube credentials for ${CLUSTER} (${REGION})"
  gcloud container clusters get-credentials "${CLUSTER}" --region "${REGION}" --project "${PROJECT}"

  log "Ensure namespace ${NS}"
  kubectl get ns "${NS}" >/dev/null 2>&1 || kubectl create ns "${NS}"

  log "Ensure KSA ${NS}/${KSA}"
  kubectl -n "${NS}" get sa "${KSA}" >/dev/null 2>&1 || kubectl -n "${NS}" create sa "${KSA}"

  if ! gcloud iam service-accounts describe "${GSA_EMAIL}" --project "${PROJECT}" >/dev/null 2>&1; then
    log "Create GSA ${GSA_EMAIL}"
    gcloud iam service-accounts create "${GSA}" --display-name="GSA for ${NS}" --project "${PROJECT}"
  else
    log "GSA ${GSA_EMAIL} exists"
  fi

  log "Bind Workload Identity (KSA -> GSA)"
  gcloud iam service-accounts add-iam-policy-binding "${GSA_EMAIL}" \
    --role roles/iam.workloadIdentityUser \
    --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_POOL}/subject/ns/${NS}/sa/${KSA}" \
    --project "${PROJECT}"

  log "Annotate KSA to use GSA"
  kubectl -n "${NS}" annotate sa "${KSA}" \
    iam.gke.io/gcp-service-account="${GSA_EMAIL}" --overwrite

  if [[ -n "${BUCKET}" ]]; then
    log "Grant bucket IAM to ${GSA_EMAIL} on gs://${BUCKET} (roles/storage.objectAdmin)"
    gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
      --member "serviceAccount:${GSA_EMAIL}" \
      --role roles/storage.objectAdmin \
      --project "${PROJECT}"
  else
    log "No --bucket provided; skipping bucket IAM"
  fi

  log "Workspace identity provisioned"
  echo "  namespace: ${NS}"
  echo "  ksa:       ${KSA}"
  echo "  gsa:       ${GSA_EMAIL}"
  [[ -n "${BUCKET}" ]] && echo "  bucket:    ${BUCKET}"
}

case "${CMD}" in
  cluster-init)   cluster_init;;
  workspace-init) workspace_init;;
  *) usage; die "unknown command: ${CMD}";;
esac


