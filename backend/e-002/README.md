Packer Image Pipelines for Golden Images & AMIs

Stack: Python + Flask + Packer (HCL2)

Features:
- Define pipelines in YAML (pipelines/*.yaml)
- Trigger AMI builds via REST API using Packer
- Centralized build logs and status tracking
- Automatically resolve created AMI ID via boto3 using AMI name

API Endpoints:
- GET /health
- GET /pipelines
- GET /pipelines/{name}
- POST /pipelines/{name}/run
  - Body (JSON): { "overrides": { ...optional Packer vars... }, "ami_suffix": "optional-suffix" }
- GET /builds
- GET /builds/{id}
- GET /builds/{id}/logs

Quickstart:
1) Ensure AWS credentials are available (env, shared config, or instance profile). Set AWS_REGION if needed.
2) Install packer (or use the provided Dockerfile).
3) pip install -r requirements.txt
4) Update pipelines/* with your VPC and Subnet IDs.
5) Start: python app.py

Trigger a build:
- curl -X POST http://localhost:8000/pipelines/ubuntu-22/run -H 'Content-Type: application/json' -d '{"overrides": {"subnet_id": "subnet-abc", "vpc_id": "vpc-abc"}}'

Notes:
- The server generates an ami_name at runtime and injects it into the Packer build.
- After a successful build, the AMI ID is resolved via describe_images by name.
- Ensure IAM permissions allow: ec2:CreateImage, ec2:DescribeImages, and all operations Packer needs (launch instances, create snapshots, tagging, etc.).

