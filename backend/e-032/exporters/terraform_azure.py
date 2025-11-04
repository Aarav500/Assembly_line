from utils.naming import slugify


def _vm_size_from(vcpu: int, ram_gb: float) -> str:
    if vcpu <= 2 and ram_gb <= 4:
        return "Standard_B2s"
    if vcpu <= 4 and ram_gb <= 16:
        return "Standard_D4s_v5"
    if vcpu <= 8 and ram_gb <= 32:
        return "Standard_D8s_v5"
    return "Standard_D16s_v5"


def provider_tf(location):
    return f'''terraform {{
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = ">= 3.100.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
}}
'''


def variables_tf(default_location, project):
    rg_name = slugify(f"{project}-rg")
    return f'''variable "azure_location" {{
  type        = string
  description = "Azure location"
  default     = "{default_location}"
}}

variable "project" {{
  type        = string
  default     = "{project}"
}}

variable "resource_group_name" {{
  type        = string
  default     = "{rg_name}"
}}

variable "db_admin_login" {{
  type    = string
  default = "pgadmin"
}}

variable "db_admin_password" {{
  type      = string
  sensitive = true
  default   = "ChangeMeStrongP@ssw0rd"
}}
'''


def rg_tf():
    return '''resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.azure_location
}
'''


def compute_tf(project, item):
    r = item["inputs"]
    name = slugify(f"{project}-{item['resourceId']}-vm")
    vcpu = int(r.get("vcpu", 2))
    ram = float(r.get("ram_gb", 4))
    size = _vm_size_from(vcpu, ram)
    return f'''resource "azurerm_virtual_network" "{item['resourceId']}_vnet" {{
  name                = "{name}-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = var.azure_location
  resource_group_name = azurerm_resource_group.rg.name
}}

resource "azurerm_subnet" "{item['resourceId']}_subnet" {{
  name                 = "default"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.{item['resourceId']}_vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}}

resource "azurerm_network_interface" "{item['resourceId']}_nic" {{
  name                = "{name}-nic"
  location            = var.azure_location
  resource_group_name = azurerm_resource_group.rg.name

  ip_configuration {{
    name                          = "internal"
    subnet_id                     = azurerm_subnet.{item['resourceId']}_subnet.id
    private_ip_address_allocation = "Dynamic"
  }}
}}

resource "azurerm_linux_virtual_machine" "{item['resourceId']}" {{
  name                = "{name}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.azure_location
  size                = "{size}"
  admin_username      = "azureuser"
  network_interface_ids = [
    azurerm_network_interface.{item['resourceId']}_nic.id
  ]
  disable_password_authentication = false
  admin_password = "Azure1234!Strong"

  os_disk {{
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }}

  source_image_reference {{
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts"
    version   = "latest"
  }}
}}
'''


def db_tf(project, item):
    r = item["inputs"]
    name = slugify(f"{project}-{item['resourceId']}-pg")
    storage = int(r.get("storage_gb", 32))
    return f'''resource "azurerm_postgresql_flexible_server" "{item['resourceId']}" {{
  name                   = "{name}"
  resource_group_name    = azurerm_resource_group.rg.name
  location               = var.azure_location
  version                = "14"
  administrator_login    = var.db_admin_login
  administrator_password = var.db_admin_password
  storage_mb             = {storage * 1024}
  sku_name               = "Standard_D2s_v3"
  public_network_access_enabled = true
}}
'''


def storage_tf(project, item):
    acc = slugify(f"{project}{item['resourceId']}sa")[:22]
    return f'''resource "azurerm_storage_account" "{item['resourceId']}" {{
  name                     = "{acc}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = var.azure_location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}}

resource "azurerm_storage_container" "{item['resourceId']}" {{
  name                  = "data"
  storage_account_name  = azurerm_storage_account.{item['resourceId']}.name
  container_access_type = "private"
}}
'''


def outputs_tf():
    return '''output "azure_location" {
  value = var.azure_location
}
'''


def terraform_for_azure(project, items):
    if not items:
        return []
    default_location = items[0]["cloudRegion"]
    main_parts = [provider_tf(default_location), rg_tf()]

    for it in items:
        if it["type"] == "compute":
            main_parts.append(compute_tf(project, it))
        elif it["type"] == "database":
            main_parts.append(db_tf(project, it))
        elif it["type"] == "storage":
            main_parts.append(storage_tf(project, it))

    files = []
    base = "iac/terraform/azure"
    files.append({"path": f"{base}/main.tf", "content": "\n".join(main_parts)})
    files.append({"path": f"{base}/variables.tf", "content": variables_tf(default_location, project)})
    files.append({"path": f"{base}/outputs.tf", "content": outputs_tf()})
    return files

