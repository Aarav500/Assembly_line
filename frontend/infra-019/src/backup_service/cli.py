from __future__ import annotations
import argparse
import json
import sys

from backup_service.backup_runner import run_backup
from backup_service.restore_runner import (
    restore_ebs_snapshot,
    attach_restored_volume,
    restore_rds_from_snapshot,
)


def main():
    p = argparse.ArgumentParser(prog="backup-service", description="Backup and restore service with automated snapshots, retention, and DR")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_backup = sub.add_parser("backup", help="Run backup and retention across configured services")
    p_backup.add_argument("--config", dest="config", help="Path to YAML config", default=None)

    p_rebs = sub.add_parser("restore-ebs", help="Restore an EBS volume from a snapshot")
    p_rebs.add_argument("--snapshot-id", required=True)
    p_rebs.add_argument("--az", required=True, help="Availability Zone for the new volume")
    p_rebs.add_argument("--volume-type", default="gp3")
    p_rebs.add_argument("--iops", type=int)
    p_rebs.add_argument("--throughput", type=int)
    p_rebs.add_argument("--kms-key-id")
    p_rebs.add_argument("--name", dest="tag_name")
    p_rebs.add_argument("--config", dest="config", default=None)
    p_rebs.add_argument("--dry-run", action="store_true")

    p_attach = sub.add_parser("attach-ebs", help="Attach a volume to an EC2 instance")
    p_attach.add_argument("--volume-id", required=True)
    p_attach.add_argument("--instance-id", required=True)
    p_attach.add_argument("--device", required=True, help="Device name, e.g., /dev/sdf")
    p_attach.add_argument("--config", dest="config", default=None)
    p_attach.add_argument("--dry-run", action="store_true")

    p_rrds = sub.add_parser("restore-rds", help="Restore an RDS instance from a snapshot")
    p_rrds.add_argument("--snapshot-id", required=True)
    p_rrds.add_argument("--target-db-id", required=True)
    p_rrds.add_argument("--db-class")
    p_rrds.add_argument("--subnet-group")
    p_rrds.add_argument("--public", action="store_true")
    p_rrds.add_argument("--multi-az", action="store_true")
    p_rrds.add_argument("--config", dest="config", default=None)
    p_rrds.add_argument("--dry-run", action="store_true")

    args = p.parse_args()

    if args.cmd == "backup":
        run_backup(args.config)
        return

    if args.cmd == "restore-ebs":
        resp = restore_ebs_snapshot(
            snapshot_id=args.snapshot_id,
            availability_zone=args.az,
            volume_type=args.volume_type,
            iops=args.iops,
            throughput=args.throughput,
            kms_key_id=args.kms_key_id,
            tag_name=args.tag_name,
            config_path=args.config,
            dry_run=args.dry_run,
        )
        print(json.dumps(resp, default=str))
        return

    if args.cmd == "attach-ebs":
        resp = attach_restored_volume(
            volume_id=args.volume_id,
            instance_id=args.instance_id,
            device_name=args.device,
            config_path=args.config,
            dry_run=args.dry_run,
        )
        print(json.dumps(resp, default=str))
        return

    if args.cmd == "restore-rds":
        resp = restore_rds_from_snapshot(
            snapshot_identifier=args.snapshot_id,
            target_db_instance_identifier=args.target_db_id,
            db_instance_class=args.db_class,
            subnet_group_name=args.subnet_group,
            publicly_accessible=args.public,
            multi_az=args.multi_az,
            config_path=args.config,
            dry_run=args.dry_run,
        )
        print(json.dumps(resp, default=str))
        return


if __name__ == "__main__":
    main()

