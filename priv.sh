REGION=us-central1

for CL in imru-cluster onmemos-autopilot; do
  gcloud container clusters update "$CL" --region "$REGION" \
    --update-addons=GcsFuseCsiDriver=ENABLED,GcpFilestoreCsiDriver=ENABLED
done

# verify after a minute:
kubectl get csidrivers | grep -E 'gcsfuse|filestore'