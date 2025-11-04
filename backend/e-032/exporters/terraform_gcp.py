from utils.naming import slugify


def _machine_type_from(vcpu: int, ram_gb: float) -> str:
    # Use e2 machine family for general purpose
    if vcpu <= 2 and ram_gb <= 4:
        return "e2-standard-2"
    if vcpu <= 4 and ram_gb <= 16:
        return "e2-standard-4"
    if vcpu <= 8 and ram_gb <= 32:
        return "e2-standard-8"
    return "e2-standard-16"


def provider_tf(region):
    return f'''terraform {{
  required_providers {{
    google = {{
      source  = "hashicorp/google"
      version = ">= 5.0"
    }}
  }}
}}

provider "google" {{
  project = var.gcp_project_id
  region  = var.gcp_region
}}
'''


def variables_tf(default_region):
    return f'''variable "gcp_project_id" {{
  type        = string
  description = "GCP Project ID"
  default     = "change-me-project"
}}

variable "gcp_region" {{
  type        = string
  description = "GCP region"
  default     = "{default_region}"
}}

variable "project" {{
  type        = string
  description = "Project name"
}}
'''


def compute_tf(project, item):
    r = item["inputs"]
    name = slugify(f"{project}-{item['resourceId']}-vm")
    vcpu = int(r.get("vcpu", 2))
    ram = float(r.get("ram_gb", 4))
    mtype = _machine_type_from(vcpu, ram)
    zone = f"${{var.gcp_region}}-a"
    return f'''resource "google_compute_network" "{item['resourceId']}_vpc" {{
  name = "{name}-vpc"
}}

resource "google_compute_subnetwork" "{item['resourceId']}_subnet" {{
  name          = "{name}-subnet"
  ip_cidr_range = "10.10.0.0/24"
  region        = var.gcp_region
  network       = google_compute_network.{item['resourceId']}_vpc.id
}}

resource "google_compute_instance" "{item['resourceId']}" {{
  name         = "{name}"
  machine_type = "{mtype}"
  zone         = "{zone}"

  boot_disk {{
    initialize_params {{
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
    }}
  }}

  network_interface {{
    subnetwork = google_compute_subnetwork.{item['resourceId']}_subnet.id
    access_config {{}}
  }}
}}
'''


def db_tf(project, item):
    r = item["inputs"]
    name = slugify(f"{project}-{item['resourceId']}-pg")
    vcpu = int(r.get("vcpu", 2))
    ram_gb = float(r.get("ram_gb", 4))
    mem_mb = int(ram_gb * 1024)
    storage = int(r.get("storage_gb", 20))
    tier = f"db-custom-{vcpu}-{mem_mb}"
    return f'''resource "google_sql_database_instance" "{item['resourceId']}" {{
  name             = "{name}"
  database_version = "POSTGRES_14"
  region           = var.gcp_region

  settings {{
    tier            = "{tier}"
    availability_type = "ZONAL"
    disk_size       = {storage}
    ip_configuration {{
      ipv4_enabled = true
    }}
  }}
}}
'''


def storage_tf(project, item):
    name = slugify(f"{project}-{item['resourceId']}-bucket")
    return f'''resource "google_storage_bucket" "{item['resourceId']}" {{
  name     = "{name}"
  location = var.gcp_region
  uniform_bucket_level_access = true
}}
'''


def outputs_tf():
    return '''output "gcp_region" {
  value = var.gcp_region
}
'''


def terraform_for_gcp(project, items):
    if not items:
        return []
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
    base = "iac/terraform/gcp"
    files.append({"path": f"{base}/main.tf", "content": "\n".join(main_parts)})
    files.append({"path": f"{base}/variables.tf", "content": variables_tf(default_region)})
    files.append({"path": f"{base}/outputs.tf", "content": outputs_tf()})
    return files

