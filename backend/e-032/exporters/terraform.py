from exporters.terraform_aws import terraform_for_aws
from exporters.terraform_azure import terraform_for_azure
from exporters.terraform_gcp import terraform_for_gcp


def group_by_cloud(plan: dict):
    by_cloud = {"aws": [], "azure": [], "gcp": []}
    for item in plan.get("plan", []):
        by_cloud[item["assignedCloud"]].append(item)
    return by_cloud


def generate_terraform_files(plan: dict):
    files = []
    grouped = group_by_cloud(plan)
    project = plan.get("name", "project")

    if grouped.get("aws"):
        files.extend(terraform_for_aws(project, grouped["aws"]))
    if grouped.get("azure"):
        files.extend(terraform_for_azure(project, grouped["azure"]))
    if grouped.get("gcp"):
        files.extend(terraform_for_gcp(project, grouped["gcp"]))

    return files

