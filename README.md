# DocEmbed

DocEmbed is a scalable document embedding system designed to process, store, and query document embeddings using Qdrant as a vector database. It leverages Kubernetes (EKS) for deployment, RabbitMQ for task queuing, and Celery for distributed task processing. The system includes a UI, a query service, and workers to handle PDF processing and embedding generation.

The web UI is available at [this link](http://acc92feef718c478e8e67a3daa5083f8-729555859.us-east-2.elb.amazonaws.com).
![Web UI Screenshot](docs/sc.jpg)

# Design Overview

The system starts with file ingestion via the s3_ingestor, which uploads incoming files to an Amazon S3 bucket. A scalable Kubernetes (K8s) cluster, deployed on EKS and backed by EC2 instances, provides both horizontal and vertical scaling capabilities to support dynamic workloads.

#### File Processing Pipeline:
Scheduled Celery workers continuously poll the S3 bucket for new files.
Upon detection, each file is broken down into paragraph-level chunks.
Each chunk is assigned a unique identifier and then published to a persistent RabbitMQ message broker for downstream processing.

#### Embedding and Storage:
Celery consumers subscribe to RabbitMQ, retrieving the chunks.
Each chunk is passed through a language embedding model to generate a high-dimensional vector representation.
The resulting embedding, along with metadata (file ID, chunk ID, and raw text), is stored in a scalable vector database (Qdrant), which is backed by persistent storage.

#### Query Processing:
When a user query is received through the Application Load Balancer (ALB), a worker:
Converts the query into an embedding using the same language model.
Performs a cosine similarity search against the vector database.
Returns the most relevant chunks as results.

#### Scalability & Cost Efficiency:
All core components—including Celery workers, RabbitMQ, and Qdrant—are containerized and scale independently to handle varying loads efficiently.
The architecture is highly cost-efficient, leveraging a cloud-agnostic stack that minimizes vendor lock-in and optimizes resource usage. This flexibility is a major advantage for both portability and long-term cost control.

#### TODO
 - Refactor and clean the codebase; eliminate all hardcoded configuration values.
 - Integrate system monitoring using Prometheus and Grafana for better observability and operational insight.

## Table of Contents

- Prerequisites
- Architecture Overview
- Setup and Deployment
  - Create EKS Cluster
  - Deploy Qdrant with Persistent Storage
  - Test Persistent Storage
  - Deploy RabbitMQ
  - Deploy Celery Workers
  - Deploy Query Service
  - Deploy UI Service
  - Run Scheduler
- Building and Pushing Docker Images
  - Qdrant Client
  - Celery PDF Worker
  - Celery Embed Worker
  - Query Service
  - UI Service
- Debugging Commands
- Usage
- License

## Prerequisites

- AWS CLI configured with appropriate credentials
- `eksctl` for managing EKS clusters
- `kubectl` for interacting with Kubernetes
- `helm` for deploying RabbitMQ and Qdrant
- Docker installed for building and pushing images
- AWS ECR access for container registry

## Architecture Overview

- **Qdrant**: Vector database for storing and querying document embeddings.
- **RabbitMQ**: Message broker for task queuing.
- **Celery Workers**: Handle PDF processing and embedding generation.
- **Query Service**: API for querying embeddings.
- **UI Service**: Web interface for interacting with the system.
- **EKS**: Kubernetes cluster for orchestration.
- **EBS**: Persistent storage for Qdrant and RabbitMQ.

## Setup and Deployment

### Create EKS Cluster

Create an EKS cluster using the provided configuration file:

```bash
eksctl create cluster -f eks-cluster.yaml
```

Verify the cluster:

```bash
eksctl get cluster --region us-east-2
kubectl get nodes
```

### Deploy Qdrant with Persistent Storage

Add the Qdrant Helm repository and deploy Qdrant with persistent storage:

```bash
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo update
kubectl apply -f ebs-storageclass.yaml
helm install qdrant qdrant/qdrant -f qdrant-values.yaml --namespace qdrant --create-namespace
```

Test Qdrant connectivity:

```bash
kubectl port-forward svc/qdrant -n qdrant 6333:6333
curl http://localhost:6333/collections
```

### Test Persistent Storage

Verify that data persists across pod restarts:

1. Restart the Qdrant pod:

   ```bash
   kubectl delete pod -n qdrant -l app.kubernetes.io/name=qdrant
   ```

2. Wait for the pod to restart:

   ```bash
   kubectl get pods -n qdrant
   ```

3. Verify data persistence:

   ```bash
   curl http://localhost:6333/collections/test_collection
   ```

   The collection and its points (e.g., ID 1 with payload `{"color": "red"}`) should still exist.

### Deploy RabbitMQ

Deploy RabbitMQ with persistent storage:

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm install rabbitmq bitnami/rabbitmq -f rabbitmq-values.yaml --namespace qdrant
```

Access RabbitMQ management UI:

```bash
kubectl port-forward svc/rabbitmq -n qdrant 15672:15672
```

RabbitMQ is accessible at `rabbitmq.qdrant.svc.cluster.local:5672`.

### Deploy Celery Workers

1. **Create IAM Service Account** for Celery PDF worker:

   ```bash
   eksctl create iamserviceaccount \
     --cluster doc-embed \
     --namespace qdrant \
     --name celery-pdf-worker \
     --attach-policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly \
     --attach-policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess \
     --approve \
     --region us-east-2
   ```

2. **Deploy Celery PDF Worker**:

   ```bash
   kubectl apply -f celery-pdf-worker-deployment.yaml
   ```

3. **Deploy Celery Embed Worker**:

   ```bash
   kubectl apply -f celery-embed-worker-deployment.yaml
   ```

4. **Check Worker Status**:

   ```bash
   kubectl get deployments -n qdrant
   kubectl get pods -n qdrant -l app=celery-pdf-worker
   kubectl get pods -n qdrant -l app=celery-embed-worker
   kubectl logs -n qdrant -l app=celery-pdf-worker --tail=100
   kubectl logs -n qdrant -l app=celery-embed-worker --tail=100
   ```

### Deploy Query Service

Deploy the query service and its associated Kubernetes service:

```bash
kubectl apply -f query-service-deployment.yaml
kubectl apply -f query-service-service.yaml
```

Check status:

```bash
kubectl get deployments -n qdrant -l app=query-service
kubectl get services -n qdrant -l app=query-service
kubectl describe svc query-service -n qdrant
```

### Deploy UI Service

Deploy the UI service and its associated Kubernetes service:

```bash
kubectl apply -f ui-service-deployment.yaml
kubectl apply -f ui-service-service.yaml
```

Check status and get the external URL:

```bash
kubectl get deployments -n qdrant -l app=ui-service
kubectl get services -n qdrant -l app=ui-service
kubectl get svc ui-service -n qdrant -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
kubectl describe svc ui-service -n qdrant
```

Inspect the UI container:

```bash
docker run -it 705926388196.dkr.ecr.us-east-2.amazonaws.com/ui-service:latest sh
ls -R /usr/share/nginx/html
cat /etc/nginx/conf.d/default.conf
```

### Run Scheduler

Deploy a CronJob to trigger periodic tasks:

```bash
kubectl apply -f celery-pdf-trigger-cronjob.yaml
```

Check status:

```bash
kubectl get cronjobs -n qdrant
kubectl get jobs -n qdrant
kubectl logs -n qdrant -l job-name=celery-pdf-trigger
```

## Building and Pushing Docker Images

### Qdrant Client

```bash
docker build --no-cache -t qdrant-client:latest .
aws ecr create-repository --repository-name qdrant-client --region us-east-2
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 705926388196.dkr.ecr.us-east-2.amazonaws.com
docker tag qdrant-client:latest 705926388196.dkr.ecr.us-east-2.amazonaws.com/qdrant-client:latest
docker push 705926388196.dkr.ecr.us-east-2.amazonaws.com/qdrant-client:latest
kubectl apply -f qdrant-client-deployment.yaml
```

Check status:

```bash
kubectl get deployments -n qdrant
kubectl get pods -n qdrant
kubectl logs -n qdrant -l app=qdrant-test-app
kubectl get pods -n qdrant -l app=qdrant-test-app --field-selector=status.phase!=Running
```

### Celery PDF Worker

```bash
aws ecr create-repository --repository-name celery-pdf-worker --region us-east-2
docker build -t celery-pdf-worker .
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 705926388196.dkr.ecr.us-east-2.amazonaws.com
docker tag celery-pdf-worker:latest 705926388196.dkr.ecr.us-east-2.amazonaws.com/celery-pdf-worker:latest
docker push 705926388196.dkr.ecr.us-east-2.amazonaws.com/celery-pdf-worker:latest
```

### Celery Embed Worker

```bash
aws ecr create-repository --repository-name celery-embed-worker --region us-east-2
docker build --no-cache -t celery-embed-worker -f Dockerfile .
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 705926388196.dkr.ecr.us-east-2.amazonaws.com
docker tag celery-embed-worker:latest 705926388196.dkr.ecr.us-east-2.amazonaws.com/celery-embed-worker:latest
docker push 705926388196.dkr.ecr.us-east-2.amazonaws.com/celery-embed-worker:latest
```

### Query Service

```bash
docker build --no-cache -t query-service -f Dockerfile .
aws ecr create-repository --repository-name query-service --region us-east-2
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 705926388196.dkr.ecr.us-east-2.amazonaws.com
docker tag query-service:latest 705926388196.dkr.ecr.us-east-2.amazonaws.com/query-service:latest
docker push 705926388196.dkr.ecr.us-east-2.amazonaws.com/query-service:latest
```

### UI Service

```bash
docker build --no-cache -t ui-service -f Dockerfile .
aws ecr create-repository --repository-name ui-service --region us-east-2
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 705926388196.dkr.ecr.us-east-2.amazonaws.com
docker tag ui-service:latest 705926388196.dkr.ecr.us-east-2.amazonaws.com/ui-service:latest
docker push 705926388196.dkr.ecr.us-east-2.amazonaws.com/ui-service:latest
```

Debugging Commands

- Delete EKS cluster:

  eksctl delete cluster --name doc-embed --region us-east-2

- Check Qdrant data:

  kubectl port-forward svc/qdrant -n qdrant 6333:6333\\

  curl http://localhost:6333/collections/test_collection/points?filter={"must":\[{"key":"doc_id","match":{"value":"test_file"}}\]}\
  curl -X POST http://localhost:6333/collections/test_collection/points/scroll -H 'Content-Type: application/json' -d '{"limit": 100, "with_payload": true}'

- Check deployment and pod status:

  kubectl get deployments -n qdrant\\

  kubectl get pods -n qdrant\
  kubectl describe deployment celery-pdf-worker -n qdrant

Usage

1. Upload PDF documents via the UI or trigger the CronJob to process files from an S3 bucket.
2. The Celery PDF worker processes PDFs and sends tasks to the embed worker.
3. The embed worker generates embeddings and stores them in Qdrant.
4. Query embeddings using the query service API or UI.
5. Use the UI to visualize results or interact with the system.

