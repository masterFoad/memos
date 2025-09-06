#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./onmemos_provision.sh cluster-init \
#     --project ai-engine-448418 --region us-central1 \
#     --clusters "imru-cluster onmemos-autopilot"
#
#   ./onmemos_provision.sh workspace-init \
#     --project ai-engine-448418 --region us-central1 --cluster onmemos-autopilot \
#     --workspace-id ws-EXAMPLE123 \
#     --bucket onmemos-ws-EXAMPLE123-<suffix>   # optional; if set, grants IAM

log() { printf "%s %s\n" "[$(date +'%H:%M:%S')]" "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1"; }
need gcloud
need kubectl
need sed
need grep

parse_kv() {
  local key="$1"; shift
  local def="${1:-}"; shift || true
  local v="${def}"
  for a in "$@"; do
    case "$a" in
      --${key}) die "flag --${key} requires a value";;
      --${key}=*) v="${a#*=}";;
      --${key}) shift; v="${1:-}";;
    esac
  done
  echo "${v}"
}

cmd="${1:-}"; shift || true
[ -n "${cmd}" ] || die "missing command: cluster-init | workspace-init"

PROJECT="$(parse_kv project "" "$@")"
REGION="$(parse_kv region "" "$@")"

[ -n "${PROJECT}" ] || die "--project is required"
[ -n "${REGION}" ] || die "--region is required"

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT}" --format='value(projectNumber)')"
[ -n "${PROJECT_NUMBER}" ] || die "failed to resolve PROJECT_NUMBER for ${PROJECT}"
WORKLOAD_POOL="${PROJECT}.svc.id.goog"

cluster_init() {
  local clusters
  clusters="$(parse_kv clusters "" "$@")"
  [ -n "${clusters}" ] || die "--clusters \"CL1 CL2 ...\" is required"

  log "Enabling CSI drivers on clusters: ${clusters}"
  for CL in ${clusters}; do
    log "→ ${CL}"
    gcloud container clusters update "${CL}" --region "${REGION}" \
      --update-addons=GcsFuseCsiDriver=ENABLED,GcpFilestoreCsiDriver=ENABLED \
      --project "${PROJECT}"
  done

  log "Getting credentials for first cluster for verification"
  gcloud container clusters get-credentials "$(echo "${clusters}" | awk '{print $1}')" --region "${REGION}" --project "${PROJECT}"

  log "Verifying CSI drivers"
  kubectl get csidrivers | grep -E 'gcsfuse|filestore' || true
  log "Done."
}

workspace_init() {
  local CLUSTER WORKSPACE_ID BUCKET
  CLUSTER="$(parse_kv cluster "" "$@")"
  WORKSPACE_ID="$(parse_kv workspace-id "" "$@")"
  BUCKET="$(parse_kv bucket "" "$@")"
  [ -n "${CLUSTER}" ] || die "--cluster is required"
  [ -n "${WORKSPACE_ID}" ] || die "--workspace-id is required"

  local NS="ws-${WORKSPACE_ID}"
  local KSA="ws-sa"
  local GSA="ws-${WORKSPACE_ID}-sa"
  local GSA_EMAIL="${GSA}@${PROJECT}.iam.gserviceaccount.com"

  log "Kube context → ${CLUSTER}"
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

  log "Bind Workload Identity (KSA → GSA)"
  gcloud iam service-accounts add-iam-policy-binding "${GSA_EMAIL}" \
    --role roles/iam.workloadIdentityUser \
    --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_POOL}/subject/ns/${NS}/sa/${KSA}" \
    --project "${PROJECT}"

  log "Annotate KSA to use GSA"
  kubectl -n "${NS}" annotate sa "${KSA}" \
    iam.gke.io/gcp-service-account="${GSA_EMAIL}" --overwrite

  if [ -n "${BUCKET}" ]; then
    log "Grant bucket IAM (roles/storage.objectAdmin) to ${GSA_EMAIL} on gs://${BUCKET}"
    gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
      --member "serviceAccount:${GSA_EMAIL}" \
      --role roles/storage.objectAdmin \
      --project "${PROJECT}"
  else
    log "No --bucket provided; skipping bucket IAM grant"
  fi

  log "Workspace identity provisioned:"
  echo "  namespace: ${NS}"
  echo "  ksa:       ${KSA}"
  echo "  gsa:       ${GSA_EMAIL}"
  [ -n "${BUCKET}" ] && echo "  bucket:    ${BUCKET}"
  log "Done."
}

case "${cmd}" in
  cluster-init)   cluster_init   "$@";;
  workspace-init) workspace_init "$@";;
  *) die "unknown command: ${cmd}";;
esac