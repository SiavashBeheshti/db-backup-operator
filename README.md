# 🗄️ Database Backup Operator

A Kubernetes operator that automates database backup operations by managing `DatabaseBackup` custom resources. Define your backup strategy declaratively, and the operator handles scheduling, execution, and retention—all as native Kubernetes resources.

## ✨ Features

- **Multi-Database Support** — PostgreSQL, MySQL, and MongoDB
- **Cloud Storage Integration** — AWS S3, Google Cloud Storage, and Azure Blob Storage
- **Declarative Configuration** — Define backups as Kubernetes custom resources
- **Automated Scheduling** — Cron-based backup scheduling via CronJobs
- **Retention Management** — Automatic cleanup of old backups
- **Status Tracking** — Monitor backup status directly from the CR
- **Owner References** — Automatic cleanup when resources are deleted

## 📋 Prerequisites

- Kubernetes cluster (v1.20+)
- `kubectl` configured for your cluster
- Access to a container registry (for custom builds)
- Database credentials stored in Kubernetes Secrets
- Cloud storage credentials stored in Kubernetes Secrets

## 🚀 Quick Start

### 1. Install the CRD

```bash
kubectl apply -f manifests/crd.yaml
```

### 2. Set up RBAC

```bash
kubectl apply -f manifests/rbac.yaml
```

### 3. Deploy the Operator

First, build and push the operator image:

```bash
docker build -t your-registry/db-backup-operator:latest .
docker push your-registry/db-backup-operator:latest
```

Then update the image in `manifests/deployment.yaml` and deploy:

```bash
kubectl apply -f manifests/deployment.yaml
```

### 4. Create Your First Backup

Create secrets for database and storage credentials:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgres-creds
type: Opaque
stringData:
  username: postgres
  password: your-password
---
apiVersion: v1
kind: Secret
metadata:
  name: s3-creds
type: Opaque
stringData:
  access-key: YOUR_ACCESS_KEY
  secret-key: YOUR_SECRET_KEY
```

Create a `DatabaseBackup` resource:

```yaml
apiVersion: backup.example.com/v1
kind: DatabaseBackup
metadata:
  name: production-db-backup
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  database:
    type: postgres
    host: postgres.default.svc.cluster.local
    port: 5432
    name: production
    credentialsSecret: postgres-creds
  storage:
    type: s3
    bucket: my-backup-bucket
    region: us-east-1
    credentialsSecret: s3-creds
  retention:
    keepLast: 7
```

```bash
kubectl apply -f your-backup.yaml
```

## 📖 Configuration

### DatabaseBackup Spec

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schedule` | string | Yes | Cron expression for backup schedule |
| `database.type` | string | Yes | Database type: `postgres`, `mysql`, or `mongodb` |
| `database.host` | string | Yes | Database hostname |
| `database.port` | integer | No | Database port (uses default if not specified) |
| `database.name` | string | Yes | Database name to backup |
| `database.credentialsSecret` | string | No | Secret name containing `username` and `password` |
| `storage.type` | string | Yes | Storage type: `s3`, `gcs`, or `azure` |
| `storage.bucket` | string | Yes | Storage bucket name |
| `storage.region` | string | No | Storage region (uses default if not specified) |
| `storage.credentialsSecret` | string | No | Secret name containing `access-key` and `secret-key` |
| `retention.keepLast` | integer | No | Number of backups to retain (default: 7) |

### Environment Variables

The operator supports the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPERATOR_NAMESPACE` | Namespace to watch (empty = all namespaces) | All namespaces |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENABLE_WEBHOOKS` | Enable admission webhooks | `false` |
| `ENABLE_METRICS` | Enable Prometheus metrics | `false` |
| `DEFAULT_BACKUP_SCHEDULE` | Default cron schedule | `0 2 * * *` |
| `DEFAULT_RETENTION_DAYS` | Default retention period | `7` |

### Default Ports

| Database | Default Port |
|----------|--------------|
| PostgreSQL | 5432 |
| MySQL | 3306 |
| MongoDB | 27017 |

### Resource Limits

The backup jobs are created with the following default resource limits:

| Resource | Request | Limit |
|----------|---------|-------|
| Memory | 256Mi | 512Mi |
| CPU | 100m | 500m |
| Temp Storage | 10Gi | - |

## 📊 Checking Backup Status

The operator updates the status of each `DatabaseBackup` resource:

```bash
kubectl get databasebackups
kubectl describe databasebackup production-db-backup
```

Status fields include:

- `lastBackup`: Timestamp of the last successful backup
- `phase`: Current state (`Pending`, `Active`, or `Error`)
- `activeJobs`: Number of currently running backup jobs

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                           │
│  ┌──────────────────┐     ┌───────────────────┐                    │
│  │  DatabaseBackup  │────▶│  Backup Operator  │                    │
│  │   Custom Resource│     │                   │                    │
│  └──────────────────┘     └─────────┬─────────┘                    │
│                                     │                               │
│                                     ▼                               │
│                           ┌─────────────────┐                       │
│                           │    CronJob      │                       │
│                           │  (Auto-created) │                       │
│                           └────────┬────────┘                       │
│                                    │                                │
│          ┌─────────────────────────┼─────────────────────────┐     │
│          ▼                         ▼                         ▼     │
│  ┌───────────────┐       ┌─────────────────┐       ┌─────────────┐ │
│  │   PostgreSQL  │       │      MySQL      │       │   MongoDB   │ │
│  └───────────────┘       └─────────────────┘       └─────────────┘ │
│                                    │                                │
│                                    ▼                                │
│                          ┌─────────────────┐                        │
│                          │  Cloud Storage  │                        │
│                          │ (S3/GCS/Azure)  │                        │
│                          └─────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

## 🛠️ Development

### Local Development

```bash
# Clone the repository
git clone https://github.com/your-username/db-backup-operator.git
cd db-backup-operator

# Install dependencies
pip install -r requirements.txt

# Run the operator locally (requires kubeconfig)
kopf run operator/handlers.py --verbose
```

### Project Structure

```
db-backup-operator/
├── Dockerfile
├── README.md
├── requirements.txt
├── operator/
│   ├── __init__.py        # Package exports
│   ├── config.py          # Configuration management
│   ├── handlers.py        # Kopf event handlers
│   └── templates.py       # Kubernetes manifest templates
└── manifests/
    ├── crd.yaml           # CustomResourceDefinition
    ├── deployment.yaml    # Operator deployment
    ├── rbac.yaml          # ServiceAccount, ClusterRole, ClusterRoleBinding
    └── examples/
        └── sample-backup.yaml  # Example DatabaseBackup
```

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-cov

# Run tests
pytest
```

## 🔒 Security Considerations

- Database and storage credentials should be stored in Kubernetes Secrets
- Use RBAC to limit which namespaces can create `DatabaseBackup` resources
- Consider using a service mesh for encrypted communication
- Review and customize resource limits based on your database sizes

## 📝 License

This project is open source. See the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

