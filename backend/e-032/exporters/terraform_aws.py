from utils.naming import slugify


def _instance_type_from(vcpu: int, ram_gb: float) -> str:
    # crude mapping
    if vcpu <= 2 and ram_gb <= 4:
        return "t3.small"
    if vcpu <= 2 and ram_gb <= 8:
        return "t3.large"
    if vcpu <= 4 and ram_gb <= 16:
        return "t3.xlarge"
    if vcpu <= 8 and ram_gb <= 32:
        return "m5.2xlarge"
    return "m5.4xlarge"


def _db_instance_class_from(vcpu: int, ram_gb: float) -> str:
    if vcpu <= 2 and ram_gb <= 8:
        return "db.t3.medium"
    if vcpu <= 4 and ram_gb <= 16:
        return "db.m5.large"
    if vcpu <= 8 and ram_gb <= 32:
        return "db.m5.2xlarge"
    return "db.m5.4xlarge"


def provider_tf(region):
    return f'''terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }}
  }}
}}

provider "aws" {{
  region = var.aws_region
}}
'''


def variables_tf(default_region):
    return f'''variable "aws_region" {{
  type        = string
  description = "AWS region"
  default     = "{default_region}"
}}

variable "project" {{
  type        = string
  description = "Project name"
}}

variable "db_username" {{
  type        = string
  default     = "admin"
}}

variable "db_password" {{
  type        = string
  sensitive   = true
  default     = "ChangeMeStrongP@ssw0rd"
}}
'''


def compute_tf(project, item):
    r = item["inputs"]
    name = slugify(f"{project}-{item['resourceId']}-vm")
    vcpu = int(r.get("vcpu", 2))
    ram = float(r.get("ram_gb", 4))
    itype = _instance_type_from(vcpu, ram)
    return f'''data "aws_ami" "ubuntu_{item['resourceId']}" {{
  most_recent = true
  owners      = ["099720109477"]
  filter {{
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }}
}}

resource "aws_instance" "{item['resourceId']}" {{
  ami           = data.aws_ami.ubuntu_{item['resourceId']}.id
  instance_type = "{itype}"
  tags = {{
    Name    = "{name}"
    Project = var.project
  }}
}}
'''


def db_tf(project, item):
    r = item["inputs"]
    name = slugify(f"{project}-{item['resourceId']}-db")
    vcpu = int(r.get("vcpu", 2))
    ram = float(r.get("ram_gb", 4))
    storage = int(r.get("storage_gb", 20))
    cls = _db_instance_class_from(vcpu, ram)
    return f'''resource "aws_db_instance" "{item['resourceId']}" {{
  allocated_storage    = {storage}
  engine               = "postgres"
  engine_version       = "14"
  instance_class       = "{cls}"
  username             = var.db_username
  password             = var.db_password
  skip_final_snapshot  = true
  publicly_accessible  = true
  identifier           = "{name}"
  tags = {{
    Project = var.project
  }}
}}
'''


def storage_tf(project, item):
    bucket = slugify(f"{project}-{item['resourceId']}-bucket")[:60]
    return f'''resource "aws_s3_bucket" "{item['resourceId']}" {{
  bucket = "{bucket}"
  tags = {{
    Project = var.project
  }}
}}
'''


def outputs_tf():
    return '''output "aws_region" {
  value = var.aws_region
}
'''


def terraform_for_aws(project, items):
    if not items:
        return []
    # choose first item's region for provider default
    default_region = items[0]["cloudRegion"]

    main_parts = [provider_tf(default_region)]
    for it in items:
        if it["type"] == "compute":
            main_parts.append(compute_tf(project, it))
        elif it["type"] == "database":
            main_parts.append(db_tf(project, it))
        elif it["type"] == "storage":
            main_parts.append(storage_tf(project, it))

    files = []
    base = "iac/terraform/aws"
    files.append({"path": f"{base}/main.tf", "content": "\n".join(main_parts)})
    files.append({"path": f"{base}/variables.tf", "content": variables_tf(default_region)})
    files.append({"path": f"{base}/outputs.tf", "content": outputs_tf()})
    return files

