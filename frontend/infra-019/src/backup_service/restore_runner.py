from __future__ import annotations
from typing import Optional

from backup_service.config import load_config
from backup_service.logger import get_logger
from backup_service.aws.session import get_session
from backup_service.aws import ebs as ebs_mod
from backup_service.aws import rds as rds_mod

log = get_logger("backup_service.restore")


def restore_ebs_snapshot(
    snapshot_id: str,
    availability_zone: str,
    volume_type: str = "gp3",
    iops: Optional[int] = None,
    throughput: Optional[int] = None,
    kms_key_id: Optional[str] = None,
    tag_name: Optional[str] = None,
    config_path: str | None = None,
    dry_run: bool = False,
):
    cfg = load_config(config_path)
    g = cfg.get("global", {})
    region = g.get("primary_region")
    sess = get_session(region, profile_name=g.get("profile_name"), role_arn=g.get("role_arn"), external_id=g.get("external_id"))
    return ebs_mod.restore_volume_from_snapshot(
        sess,
        region,
        snapshot_id,
        availability_zone,
        volume_type=volume_type,
        iops=iops,
        throughput=throughput,
        kms_key_id=kms_key_id or g.get("kms_key_id"),
        tag_name=tag_name,
        dry_run=dry_run or g.get("dry_run", False),
    )


def attach_restored_volume(volume_id: str, instance_id: str, device_name: str, config_path: str | None = None, dry_run: bool = False):
    cfg = load_config(config_path)
    g = cfg.get("global", {})
    region = g.get("primary_region")
    sess = get_session(region, profile_name=g.get("profile_name"), role_arn=g.get("role_arn"), external_id=g.get("external_id"))
    return ebs_mod.attach_volume(sess, region, volume_id, instance_id, device_name, dry_run=dry_run or g.get("dry_run", False))


def restore_rds_from_snapshot(
    snapshot_identifier: str,
    target_db_instance_identifier: str,
    db_instance_class: Optional[str] = None,
    subnet_group_name: Optional[str] = None,
    publicly_accessible: Optional[bool] = None,
    multi_az: Optional[bool] = None,
    config_path: str | None = None,
    dry_run: bool = False,
):
    cfg = load_config(config_path)
    g = cfg.get("global", {})
    region = g.get("primary_region")
    sess = get_session(region, profile_name=g.get("profile_name"), role_arn=g.get("role_arn"), external_id=g.get("external_id"))
    tags = [
        {"Key": "RestoredBy", "Value": "backup-service"},
    ]
    return rds_mod.restore_db_from_snapshot(
        sess,
        region,
        snapshot_identifier,
        target_db_instance_identifier,
        db_instance_class=db_instance_class,
        subnet_group_name=subnet_group_name,
        publicly_accessible=publicly_accessible,
        multi_az=multi_az,
        tags=tags,
        dry_run=dry_run or g.get("dry_run", False),
    )

