# Deploying Contributr with Helm

## Prerequisites

- Kubernetes cluster (1.26+)
- Helm 3.x
- Traefik ingress controller installed on the cluster
- `kubectl` configured to target your cluster
- A container registry accessible from the cluster

## 1. Build and Push Images

The chart requires two custom images: **backend** and **frontend**. PostgreSQL (pgvector) and Redis are pulled from public registries.

```bash
# From the repo root
REGISTRY=your-registry.example.com

# Backend (also used by the Celery worker)
docker build -t $REGISTRY/contributr-backend:latest ./backend
docker push $REGISTRY/contributr-backend:latest

# Frontend
docker build -t $REGISTRY/contributr-frontend:latest ./frontend
docker push $REGISTRY/contributr-frontend:latest
```

## 2. Configure Values

Copy the default values and edit for your environment:

```bash
cp helm/contributr/values.yaml helm/contributr/values-production.yaml
```

At minimum, update these fields in your production values file:

| Value | What to set |
|---|---|
| `global.imageRegistry` | Your container registry (e.g. `your-registry.example.com`) |
| `ingress.host` | Your domain (e.g. `your.fqdn.com`) |
| `ingress.tls.secretName` | Name of the TLS secret (see [TLS Setup](#4-tls-setup)) |
| `postgresql.auth.password` | A strong, unique password |
| `backend.secretKey` | Random 64-char hex string for encryption |
| `backend.jwtSecret` | Random string for JWT signing |
| `backend.image.repository` | `contributr-backend` (or full path if no `global.imageRegistry`) |
| `frontend.image.repository` | `contributr-frontend` (or full path if no `global.imageRegistry`) |

Generate secure secrets:

```bash
# Generate secretKey and jwtSecret
openssl rand -hex 32   # use for backend.secretKey
openssl rand -hex 32   # use for backend.jwtSecret

# Generate a strong postgres password
openssl rand -base64 24
```

## 3. Install the Chart

```bash
# Create namespace
kubectl create namespace contributr

# Install
helm install contributr ./helm/contributr \
  -n contributr \
  -f helm/contributr/values-production.yaml
```

Or pass overrides inline:

```bash
helm install contributr ./helm/contributr \
  -n contributr \
  --set global.imageRegistry=your-registry.example.com \
  --set ingress.host=your.fqdn.com \
  --set postgresql.auth.password="$(openssl rand -base64 24)" \
  --set backend.secretKey="$(openssl rand -hex 32)" \
  --set backend.jwtSecret="$(openssl rand -hex 32)"
```

## 4. TLS Setup

### Option A: Pre-existing TLS secret

If you already have a certificate and key:

```bash
kubectl create secret tls contributr-tls \
  -n contributr \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key
```

### Option B: cert-manager (automated Let's Encrypt)

Install cert-manager if not already present, then create a `ClusterIssuer`:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: traefik
```

Then add the annotation to your values file:

```yaml
ingress:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
```

## 5. Verify the Deployment

```bash
# Check all pods are running
kubectl get pods -n contributr

# Expected output (all Running/Ready):
#   contributr-postgresql-0        1/1  Running
#   contributr-redis-...           1/1  Running
#   contributr-backend-...         1/1  Running
#   contributr-worker-...          1/1  Running
#   contributr-frontend-...        1/1  Running

# Check the ingress was created
kubectl get ingress -n contributr

# Test the backend health endpoint
kubectl exec -n contributr deploy/contributr-backend -- \
  curl -s http://localhost:8000/api/health
```

## 6. Upgrading

After changing values or updating images:

```bash
helm upgrade contributr ./helm/contributr \
  -n contributr \
  -f helm/contributr/values-production.yaml
```

To upgrade only the image tag:

```bash
helm upgrade contributr ./helm/contributr \
  -n contributr \
  -f helm/contributr/values-production.yaml \
  --set backend.image.tag=v1.2.0 \
  --set frontend.image.tag=v1.2.0
```

## 7. Uninstalling

```bash
helm uninstall contributr -n contributr
```

> **Note:** PersistentVolumeClaims (PostgreSQL data and repos cache) are **not** deleted by `helm uninstall`. To fully clean up:
>
> ```bash
> kubectl delete pvc -n contributr -l app.kubernetes.io/part-of=contributr
> kubectl delete pvc -n contributr data-contributr-postgresql-0
> ```

## Architecture Reference

```
                     Internet
                        │
                   ┌────▼────┐
                   │ Traefik │
                   └────┬────┘
                        │
          ┌─────────────┼─────────────┐
          │ /api        │ /*          │
          ▼             │             ▼
   ┌──────────┐        │      ┌──────────┐
   │ Backend  │        │      │ Frontend │
   │ :8000    │        │      │ :3000    │
   └────┬─────┘        │      └──────────┘
        │               │
   ┌────┼──────────────┘
   │    │
   ▼    ▼
┌────┐ ┌──────────┐  ┌────────┐
│Redis│ │PostgreSQL│  │ Worker │
│:6379│ │  :5432   │  │(Celery)│
└────┘ └──────────┘  └────────┘
```

| Service | Image | Exposed |
|---|---|---|
| PostgreSQL | `pgvector/pgvector:pg18-trixie` | Internal only |
| Redis | `redis:8.6-alpine` | Internal only |
| Backend | `contributr-backend` | `/api` via ingress |
| Worker | `contributr-backend` (same image) | None (background tasks) |
| Frontend | `contributr-frontend` | `/` via ingress |

## Troubleshooting

**Pods stuck in Init:** The backend waits for PostgreSQL and Redis to be healthy before starting. The worker and frontend wait for the backend. Check upstream pod logs:

```bash
kubectl logs -n contributr contributr-postgresql-0
kubectl logs -n contributr deploy/contributr-redis
```

**Migration failures:** Check backend pod logs for Alembic errors:

```bash
kubectl logs -n contributr deploy/contributr-backend
```

**Frontend shows API errors:** Verify `NEXT_PUBLIC_API_URL` resolves correctly from a browser. It must match the external ingress URL:

```bash
kubectl get configmap -n contributr contributr-frontend -o yaml
```

**Storage issues:** If PVCs are stuck in `Pending`, check that a StorageClass is available or set `postgresql.persistence.storageClass` and `reposCache.storageClass` explicitly in your values.
