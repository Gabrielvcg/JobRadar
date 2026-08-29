# AWS Deployment Preparation

The MVP works locally and does not create cloud resources. A reasonable AWS deployment would use:

- ECR for the Docker image.
- ECS/Fargate for the FastAPI web container.
- A separate ECS task definition for `python -m app.cli ingest`.
- EventBridge Scheduler to run the ingestion task.
- RDS PostgreSQL for persistence.
- Secrets Manager or SSM Parameter Store for `DATABASE_URL` and future credentials.
- CloudWatch Logs for API and ingestion logs.

Cost-bearing components include ECS/Fargate task runtime, RDS instance/storage/backups, NAT gateways if private subnets need outbound internet, CloudWatch log retention, ECR storage, and data transfer.

Destruction plan:

1. Disable EventBridge schedules.
2. Stop ECS services and one-off tasks.
3. Remove ECS services, task definitions, and ECR images.
4. Snapshot or delete RDS depending on data retention needs.
5. Delete secrets/parameters only after confirming they are no longer referenced.
6. Remove networking resources if they were created specifically for JobRadar.

`infra/terraform/` is intentionally left as a placeholder until concrete AWS account, network, domain, and cost constraints are known. Terraform should not be run from this repository until those decisions are explicit.

