from __future__ import annotations
from typing import Dict

from backup_service.config import load_config
from backup_service.logger import get_logger
from backup_service.aws.session import get_session
from backup_service.aws import ebs as ebs_mod
from backup_service.aws import rds as rds_mod

log = get_logger("backup_service.runner")


def run_backup(config_path: str | None = None):
    cfg = load_config(config_path)
    g = cfg.get("global", {})
    primary_region = g.get("primary_region")
    dr_region = g.get("dr_region")
    profile = g.get("profile_name")
    role_arn = g.get("role_arn")
    external_id = g.get("external_id")
    kms_key_id = g.get("kms_key_id")
    dry_run = bool(g.get("dry_run", False))

    primary_sess = get_session(primary_region, profile_name=profile, role_arn=role_arn, external_id=external_id)
    dr_sess = get_session(dr_region, profile_name=profile, role_arn=role_arn, external_id=external_id) if dr_region else None

    # EBS
    ebs_cfg: Dict = cfg.get("ebs", {})
    if ebs_cfg.get("enabled", True):
        vols = ebs_mod.find_volumes(primary_sess, ebs_cfg.get("tag_filters") or None)
        log.info("Found EBS volumes", extra={"extra": {"count": len(vols), "region": primary_region}})
        ebs_snaps = ebs_mod.create_snapshots(
            primary_sess,
            primary_region,
            vols,
            retention_days=int(ebs_cfg.get("retention_days", 14)),
            wait=bool(ebs_cfg.get("wait_for_completion", False)),
            kms_key_id=kms_key_id,
            dry_run=dry_run,
        )
        if ebs_cfg.get("copy_to_dr", False) and dr_sess and dr_region:
            ebs_mod.copy_snapshots_to_dr(
                primary_sess,
                primary_region,
                dr_sess,
                dr_region,
                ebs_snaps,
                kms_key_id=kms_key_id,
                wait=bool(ebs_cfg.get("wait_for_completion", False)),
                dry_run=dry_run,
            )
        # enforce retention in both regions
        ebs_mod.enforce_retention(primary_sess, primary_region, int(ebs_cfg.get("retention_days", 14)), dry_run=dry_run)
        if dr_sess and dr_region:
            ebs_mod.enforce_retention(dr_sess, dr_region, int(ebs_cfg.get("retention_days", 14)), dry_run=dry_run)

    # RDS
    rds_cfg: Dict = cfg.get("rds", {})
    if rds_cfg.get("enabled", True):
        all_instances = rds_mod.list_instances(primary_sess, primary_region)
        candidates = all_instances
        ids = rds_cfg.get("instance_identifiers") or []
        if ids:
            idset = set(ids)
            candidates = [db for db in all_instances if db.get("DBInstanceIdentifier") in idset]
        tag_filters = rds_cfg.get("tag_filters") or []
        if tag_filters:
            candidates = rds_mod.filter_instances_by_tags(primary_sess, primary_region, candidates, tag_filters)
        log.info("Found RDS instances for backup", extra={"extra": {"count": len(candidates), "region": primary_region}})
        rds_snaps = rds_mod.create_db_snapshots(
            primary_sess,
            primary_region,
            candidates,
            retention_days=int(rds_cfg.get("retention_days", 7)),
            wait=bool(rds_cfg.get("wait_for_completion", False)),
            dry_run=dry_run,
        )
        if rds_cfg.get("copy_to_dr", False) and dr_sess and dr_region:
            rds_mod.copy_db_snapshots_to_dr(
                primary_sess,
                primary_region,
                dr_sess,
                dr_region,
                rds_snaps,
                kms_key_id=kms_key_id,
                wait=bool(rds_cfg.get("wait_for_completion", False)),
                dry_run=dry_run,
            )
        # enforce retention in both regions
        rds_mod.enforce_retention(primary_sess, primary_region, int(rds_cfg.get("retention_days", 7)), dry_run=dry_run)
        if dr_sess and dr_region:
            rds_mod.enforce_retention(dr_sess, dr_region, int(rds_cfg.get("retention_days", 7)), dry_run=dry_run)

    log.info("Backup run complete", extra={"extra": {"primary_region": primary_region, "dr_region": dr_region}})

