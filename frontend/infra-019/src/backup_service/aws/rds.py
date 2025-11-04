from __future__ import annotations
import datetime as dt
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from backup_service.logger import get_logger

log = get_logger("backup_service.rds")

BACKUP_TAG = "BackupService"
CREATED_BY_VALUE = "Managed"
CREATED_BY_KEY = "CreatedBy"
SOURCE_KEY = "Source"
SOURCE_VALUE = "RDS"
RETENTION_KEY = "RetentionDays"
ORIGIN_REGION_KEY = "OriginalRegion"
DR_COPIED_KEY = "DRCopied"
NAME_TAG = "Name"


def _tags_list_to_dict(tags: List[Dict[str, str]]) -> Dict[str, str]:
    return {t.get("Key"): t.get("Value") for t in (tags or [])}


def _snapshot_tags(retention_days: int, region: str, name: str | None = None):
    tags = [
        {"Key": BACKUP_TAG, "Value": CREATED_BY_VALUE},
        {"Key": CREATED_BY_KEY, "Value": "backup-service"},
        {"Key": SOURCE_KEY, "Value": SOURCE_VALUE},
        {"Key": RETENTION_KEY, "Value": str(retention_days)},
        {"Key": ORIGIN_REGION_KEY, "Value": region},
    ]
    if name:
        tags.append({"Key": NAME_TAG, "Value": name})
    return tags


def list_instances(session: boto3.session.Session, region: str) -> List[dict]:
    rds = session.client("rds", region_name=region)
    paginator = rds.get_paginator("describe_db_instances")
    inst = []
    for page in paginator.paginate():
        inst.extend(page.get("DBInstances", []))
    return inst


def filter_instances_by_tags(session: boto3.session.Session, region: str, instances: List[dict], tag_filters: List[Dict]) -> List[dict]:
    if not tag_filters:
        return instances
    rds = session.client("rds", region_name=region)
    matched = []
    for db in instances:
        arn = db.get("DBInstanceArn")
        try:
            tags = rds.list_tags_for_resource(ResourceName=arn).get("TagList", [])
            tag_map = _tags_list_to_dict(tags)
            ok = False
            for f in tag_filters:
                k = f.get("Key")
                vals = set(map(str, f.get("Values", [])))
                if k and k in tag_map and (not vals or tag_map[k] in vals):
                    ok = True
                    break
            if ok:
                matched.append(db)
        except ClientError as e:
            log.error("Failed to list RDS tags", extra={"extra": {"db_instance": db.get("DBInstanceIdentifier"), "error": str(e)}})
    return matched


def create_db_snapshots(
    session: boto3.session.Session,
    region: str,
    instances: List[dict],
    retention_days: int,
    wait: bool = False,
    dry_run: bool = False,
) -> List[dict]:
    rds = session.client("rds", region_name=region)
    created = []
    now = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    for db in instances:
        dbid = db.get("DBInstanceIdentifier")
        name = f"auto-{dbid}-{now}"
        params = {"DBInstanceIdentifier": dbid, "DBSnapshotIdentifier": name, "Tags": _snapshot_tags(retention_days, region, name)}
        try:
            if dry_run:
                log.info("Dry run: would create RDS snapshot", extra={"extra": {"db_instance": dbid, "snapshot": name}})
                continue
            snap = rds.create_db_snapshot(**params)["DBSnapshot"]
            created.append(snap)
            log.info("Created RDS snapshot", extra={"extra": {"db_instance": dbid, "snapshot": name}})
            if wait:
                waiter = rds.get_waiter("db_snapshot_completed")
                waiter.wait(DBSnapshotIdentifier=name)
        except ClientError as e:
            log.error("Failed to create RDS snapshot", extra={"extra": {"db_instance": dbid, "error": str(e)}})
    return created


def copy_db_snapshots_to_dr(
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
    dst = target_session.client("rds", region_name=target_region)
    copied = []
    for s in snapshots:
        src_id = s.get("DBSnapshotIdentifier")
        target_id = f"dr-{src_id}"
        tags = s.get("TagList") or []
        tags = tags + [{"Key": DR_COPIED_KEY, "Value": "true"}, {"Key": ORIGIN_REGION_KEY, "Value": source_region}]
        params = {
            "SourceDBSnapshotIdentifier": s.get("DBSnapshotArn"),
            "TargetDBSnapshotIdentifier": target_id,
            "CopyTags": False,
            "Tags": tags,
            "SourceRegion": source_region,
        }
        if kms_key_id:
            params["KmsKeyId"] = kms_key_id
        try:
            if dry_run:
                log.info("Dry run: would copy RDS snapshot to DR", extra={"extra": {"source_snapshot": src_id, "target": target_id, "region": target_region}})
                continue
            copied_snap = dst.copy_db_snapshot(**params)["DBSnapshot"]
            copied.append(copied_snap)
            log.info("Copied RDS snapshot to DR", extra={"extra": {"source_snapshot": src_id, "target_snapshot": target_id, "target_region": target_region}})
            if wait:
                waiter = dst.get_waiter("db_snapshot_completed")
                waiter.wait(DBSnapshotIdentifier=target_id)
        except ClientError as e:
            log.error("Failed to copy RDS snapshot to DR", extra={"extra": {"source_snapshot": src_id, "error": str(e)}})
    return copied


def enforce_retention(session: boto3.session.Session, region: str, retention_days_default: int, dry_run: bool = False) -> Tuple[int, int]:
    rds = session.client("rds", region_name=region)
    paginator = rds.get_paginator("describe_db_snapshots")
    snaps = []
    for page in paginator.paginate(SnapshotType="manual"):
        snaps.extend(page.get("DBSnapshots", []))
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    to_delete: List[str] = []
    for s in snaps:
        arn = s.get("DBSnapshotArn")
        try:
            tags = rds.list_tags_for_resource(ResourceName=arn).get("TagList", [])
        except ClientError:
            tags = []
        tmap = _tags_list_to_dict(tags)
        if tmap.get(BACKUP_TAG) != CREATED_BY_VALUE or tmap.get(SOURCE_KEY) != SOURCE_VALUE:
            continue
        rdays = int(tmap.get(RETENTION_KEY, retention_days_default))
        cutoff = now - dt.timedelta(days=rdays)
        st: dt.datetime = s.get("SnapshotCreateTime")
        if st and st < cutoff:
            to_delete.append(s.get("DBSnapshotIdentifier"))
    deleted = 0
    for sid in to_delete:
        try:
            if dry_run:
                log.info("Dry run: would delete RDS snapshot", extra={"extra": {"snapshot_id": sid}})
            else:
                rds.delete_db_snapshot(DBSnapshotIdentifier=sid)
                deleted += 1
                log.info("Deleted RDS snapshot by retention", extra={"extra": {"snapshot_id": sid, "region": region}})
        except ClientError as e:
            log.error("Failed to delete RDS snapshot", extra={"extra": {"snapshot_id": sid, "error": str(e)}})
    return len(to_delete), deleted


def restore_db_from_snapshot(
    session: boto3.session.Session,
    region: str,
    snapshot_identifier: str,
    target_db_instance_identifier: str,
    db_instance_class: Optional[str] = None,
    subnet_group_name: Optional[str] = None,
    publicly_accessible: Optional[bool] = None,
    multi_az: Optional[bool] = None,
    tags: Optional[List[Dict[str, str]]] = None,
    dry_run: bool = False,
) -> dict:
    rds = session.client("rds", region_name=region)
    params = {
        "DBSnapshotIdentifier": snapshot_identifier,
        "DBInstanceIdentifier": target_db_instance_identifier,
    }
    if db_instance_class:
        params["DBInstanceClass"] = db_instance_class
    if subnet_group_name:
        params["DBSubnetGroupName"] = subnet_group_name
    if publicly_accessible is not None:
        params["PubliclyAccessible"] = publicly_accessible
    if multi_az is not None:
        params["MultiAZ"] = multi_az
    try:
        if dry_run:
            log.info("Dry run: would restore DB from snapshot", extra={"extra": {"source_snapshot": snapshot_identifier, "target": target_db_instance_identifier}})
            return {"Status": "DRY_RUN"}
        resp = rds.restore_db_instance_from_db_snapshot(**params)
        if tags:
            arn = resp["DBInstance"]["DBInstanceArn"]
            rds.add_tags_to_resource(ResourceName=arn, Tags=tags)
        log.info("Started restore of DB from snapshot", extra={"extra": {"source_snapshot": snapshot_identifier, "target": target_db_instance_identifier}})
        return resp
    except ClientError as e:
        log.error("Failed to restore DB from snapshot", extra={"extra": {"snapshot": snapshot_identifier, "error": str(e)}})
        raise

