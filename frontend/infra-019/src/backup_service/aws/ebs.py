from __future__ import annotations
import datetime as dt
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from backup_service.logger import get_logger

log = get_logger("backup_service.ebs")

BACKUP_TAG = "BackupService"
CREATED_BY_VALUE = "Managed"
CREATED_BY_KEY = "CreatedBy"
SOURCE_KEY = "Source"
SOURCE_VALUE = "EBS"
RETENTION_KEY = "RetentionDays"
ORIGIN_REGION_KEY = "OriginalRegion"
DR_COPIED_KEY = "DRCopied"
NAME_TAG = "Name"


def _build_tag_spec(additional: Optional[Dict[str, str]] = None):
    tags = [
        {"Key": BACKUP_TAG, "Value": CREATED_BY_VALUE},
        {"Key": CREATED_BY_KEY, "Value": "backup-service"},
        {"Key": SOURCE_KEY, "Value": SOURCE_VALUE},
    ]
    if additional:
        for k, v in additional.items():
            tags.append({"Key": str(k), "Value": str(v)})
    return [{"ResourceType": "snapshot", "Tags": tags}]


def _format_desc(volume_id: str, instance_id: Optional[str], name: Optional[str]) -> str:
    parts = [f"Automated backup of {volume_id}"]
    if instance_id:
        parts.append(f"instance {instance_id}")
    if name:
        parts.append(f"({name})")
    parts.append(dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    return " - ".join(parts)


def find_volumes(session: boto3.session.Session, tag_filters: List[Dict[str, List[str]]] | None = None) -> List[dict]:
    ec2 = session.client("ec2")
    filters = []
    if tag_filters:
        for f in tag_filters:
            if "Key" in f and "Values" in f:
                filters.append({"Name": f"tag:{f['Key']}", "Values": f["Values"]})
    paginator = ec2.get_paginator("describe_volumes")
    vols = []
    for page in paginator.paginate(Filters=filters or None):
        for v in page.get("Volumes", []):
            vols.append(v)
    return vols


def create_snapshots(
    session: boto3.session.Session,
    region: str,
    volumes: List[dict],
    retention_days: int,
    wait: bool = False,
    kms_key_id: Optional[str] = None,
    dry_run: bool = False,
) -> List[dict]:
    ec2 = session.client("ec2", region_name=region)
    created = []
    for v in volumes:
        vol_id = v["VolumeId"]
        instance_id = None
        name_tag = None
        for att in v.get("Attachments", []):
            if att.get("InstanceId"):
                instance_id = att.get("InstanceId")
                break
        for t in v.get("Tags", []) or []:
            if t.get("Key") == NAME_TAG:
                name_tag = t.get("Value")
                break
        desc = _format_desc(vol_id, instance_id, name_tag)
        additional = {
            RETENTION_KEY: str(retention_days),
            ORIGIN_REGION_KEY: region,
            NAME_TAG: name_tag or vol_id,
        }
        try:
            params = {
                "VolumeId": vol_id,
                "Description": desc,
                "TagSpecifications": _build_tag_spec(additional),
                "DryRun": dry_run,
            }
            if kms_key_id:
                params["OutpostArn"] = None  # placeholder to allow future outpost support
            snap = ec2.create_snapshot(**{k: v for k, v in params.items() if v is not None})
            snap_id = snap["SnapshotId"]
            created.append(snap)
            log.info("EBS snapshot created", extra={"extra": {"snapshot_id": snap_id, "volume_id": vol_id}})
            if wait and not dry_run:
                waiter = ec2.get_waiter("snapshot_completed")
                waiter.wait(SnapshotIds=[snap_id])
                log.info("EBS snapshot completed", extra={"extra": {"snapshot_id": snap_id}})
        except ClientError as e:
            if e.response["Error"].get("Code") == "DryRunOperation" and dry_run:
                log.info("Dry run: would create snapshot", extra={"extra": {"volume_id": vol_id}})
            else:
                log.error("Failed to create snapshot", extra={"extra": {"volume_id": vol_id, "error": str(e)}})
    return created


def copy_snapshots_to_dr(
    source_session: boto3.session.Session,
    source_region: str,
    target_session: boto3.session.Session,
    target_region: str,
    snapshots: List[dict],
    kms_key_id: Optional[str] = None,
    wait: bool = False,
    dry_run: bool = False,
) -> List[dict]:
    if not target_region:
        return []
    src_ec2 = source_session.client("ec2", region_name=source_region)
    dst_ec2 = target_session.client("ec2", region_name=target_region)
    copied = []
    for s in snapshots:
        snap_id = s.get("SnapshotId")
        name = None
        for t in (s.get("Tags") or []):
            if t.get("Key") == NAME_TAG:
                name = t.get("Value")
                break
        add_tags = {DR_COPIED_KEY: "true", NAME_TAG: name or snap_id, ORIGIN_REGION_KEY: source_region}
        try:
            params = {
                "SourceRegion": source_region,
                "SourceSnapshotId": snap_id,
                "Description": f"DR copy of {snap_id} from {source_region}",
                "TagSpecifications": _build_tag_spec(add_tags),
                "DryRun": dry_run,
            }
            if kms_key_id:
                params.update({"Encrypted": True, "KmsKeyId": kms_key_id})
            copied_snap = dst_ec2.copy_snapshot(**params)
            copied.append(copied_snap)
            log.info("EBS snapshot copied to DR", extra={"extra": {"source_snapshot": snap_id, "dr_snapshot": copied_snap.get("SnapshotId"), "target_region": target_region}})
            if wait and not dry_run:
                waiter = dst_ec2.get_waiter("snapshot_completed")
                waiter.wait(SnapshotIds=[copied_snap["SnapshotId"]])
        except ClientError as e:
            if e.response["Error"].get("Code") == "DryRunOperation" and dry_run:
                log.info("Dry run: would copy snapshot to DR", extra={"extra": {"snapshot_id": snap_id, "target_region": target_region}})
            else:
                log.error("Failed to copy snapshot to DR", extra={"extra": {"snapshot_id": snap_id, "error": str(e)}})
    return copied


def _list_managed_snapshots(ec2, owned_only: bool = True) -> List[dict]:
    owner = ["self"] if owned_only else None
    paginator = ec2.get_paginator("describe_snapshots")
    filters = [{"Name": f"tag:{BACKUP_TAG}", "Values": [CREATED_BY_VALUE]}, {"Name": f"tag:{SOURCE_KEY}", "Values": [SOURCE_VALUE]}]
    snaps = []
    for page in paginator.paginate(OwnerIds=owner, Filters=filters):
        snaps.extend(page.get("Snapshots", []))
    return snaps


def enforce_retention(session: boto3.session.Session, region: str, retention_days_default: int, dry_run: bool = False) -> Tuple[int, int]:
    ec2 = session.client("ec2", region_name=region)
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    to_delete: List[str] = []
    for s in _list_managed_snapshots(ec2):
        tags = {t["Key"]: t["Value"] for t in (s.get("Tags") or [])}
        rdays = int(tags.get(RETENTION_KEY, retention_days_default))
        cutoff = now - dt.timedelta(days=rdays)
        st: dt.datetime = s.get("StartTime")
        if st and st < cutoff:
            to_delete.append(s.get("SnapshotId"))
    deleted = 0
    for sid in to_delete:
        try:
            ec2.delete_snapshot(SnapshotId=sid, DryRun=dry_run)
            deleted += 1
            log.info("Deleted EBS snapshot by retention", extra={"extra": {"snapshot_id": sid, "region": region}})
        except ClientError as e:
            if e.response["Error"].get("Code") == "DryRunOperation" and dry_run:
                log.info("Dry run: would delete snapshot", extra={"extra": {"snapshot_id": sid}})
            else:
                log.error("Failed to delete snapshot", extra={"extra": {"snapshot_id": sid, "error": str(e)}})
    return len(to_delete), deleted


def restore_volume_from_snapshot(
    session: boto3.session.Session,
    region: str,
    snapshot_id: str,
    availability_zone: str,
    volume_type: str = "gp3",
    iops: Optional[int] = None,
    throughput: Optional[int] = None,
    kms_key_id: Optional[str] = None,
    tag_name: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    ec2 = session.client("ec2", region_name=region)
    params = {
        "SnapshotId": snapshot_id,
        "AvailabilityZone": availability_zone,
        "VolumeType": volume_type,
        "DryRun": dry_run,
        "TagSpecifications": [
            {
                "ResourceType": "volume",
                "Tags": [
                    {"Key": BACKUP_TAG, "Value": CREATED_BY_VALUE},
                    {"Key": CREATED_BY_KEY, "Value": "backup-service"},
                    {"Key": SOURCE_KEY, "Value": SOURCE_VALUE},
                    {"Key": NAME_TAG, "Value": tag_name or f"restored-from-{snapshot_id}"},
                ],
            }
        ],
    }
    if iops is not None:
        params["Iops"] = iops
    if throughput is not None:
        params["Throughput"] = throughput
    if kms_key_id:
        params["KmsKeyId"] = kms_key_id
        params["Encrypted"] = True
    vol = ec2.create_volume(**params)
    log.info("Created volume from snapshot", extra={"extra": {"snapshot_id": snapshot_id, "volume_id": vol.get("VolumeId")}})
    return vol


def attach_volume(
    session: boto3.session.Session,
    region: str,
    volume_id: str,
    instance_id: str,
    device_name: str,
    dry_run: bool = False,
) -> dict:
    ec2 = session.client("ec2", region_name=region)
    resp = ec2.attach_volume(VolumeId=volume_id, InstanceId=instance_id, Device=device_name, DryRun=dry_run)
    log.info("Attached volume", extra={"extra": {"volume_id": volume_id, "instance_id": instance_id, "device": device_name}})
    return resp

