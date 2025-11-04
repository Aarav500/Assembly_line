import argparse
import json
import os
import sys
from typing import Optional

from s3_backblaze.config import S3Config
from s3_backblaze.lifecycle import (
    apply_lifecycle_rules,
    build_abort_incomplete_multipart_rule,
    build_expiration_rule,
    build_noncurrent_version_expiration_rule,
    delete_lifecycle_rules,
    get_lifecycle_rules,
)
from s3_backblaze.storage_service import StorageInitOptions, StorageService


def _build_service(cfg: S3Config) -> StorageService:
    cfg.ensure_valid()
    opts = StorageInitOptions(
        bucket_name=cfg.bucket_name,
        region_name=cfg.region_name,
        endpoint_url=cfg.endpoint_url,
        access_key=cfg.access_key,
        secret_key=cfg.secret_key,
        session_token=cfg.session_token,
        use_ssl=cfg.use_ssl,
        verify_ssl=cfg.verify_ssl,
        signature_version=cfg.signature_version,
        addressing_style=cfg.addressing_style,
    )
    return StorageService(opts)


def cmd_upload(args):
    cfg = S3Config.from_env()
    if args.bucket:
        cfg.bucket_name = args.bucket
    svc = _build_service(cfg)
    extra_args = {}
    if args.sse:
        extra_args["ServerSideEncryption"] = args.sse
    if args.ssekms_key_id:
        extra_args["SSEKMSKeyId"] = args.ssekms_key_id
    svc.upload_file(
        file_path=args.file,
        key=args.key,
        content_type=args.content_type,
        acl=args.acl,
        storage_class=args.storage_class,
        metadata=None,
        extra_args=extra_args or None,
    )
    print("OK")


def cmd_download(args):
    cfg = S3Config.from_env()
    if args.bucket:
        cfg.bucket_name = args.bucket
    svc = _build_service(cfg)
    svc.download_file(args.key, args.dest)
    print("OK")


def cmd_sign_get(args):
    cfg = S3Config.from_env()
    if args.bucket:
        cfg.bucket_name = args.bucket
    svc = _build_service(cfg)
    url = svc.generate_presigned_url_get(
        key=args.key,
        expires_in=args.expires,
        response_content_type=args.response_content_type,
        response_content_disposition=args.response_content_disposition,
    )
    print(url)


def cmd_sign_put(args):
    cfg = S3Config.from_env()
    if args.bucket:
        cfg.bucket_name = args.bucket
    svc = _build_service(cfg)
    url = svc.generate_presigned_url_put(
        key=args.key,
        expires_in=args.expires,
        content_type=args.content_type,
        acl=args.acl,
    )
    print(url)


def cmd_sign_post(args):
    cfg = S3Config.from_env()
    if args.bucket:
        cfg.bucket_name = args.bucket
    svc = _build_service(cfg)
    conditions = []
    fields = {}
    if args.content_type:
        conditions.append(["eq", "$Content-Type", args.content_type])
        fields["Content-Type"] = args.content_type
    policy = svc.generate_presigned_post(key=args.key, expires_in=args.expires, fields=fields or None, conditions=conditions or None)
    print(json.dumps(policy))


def cmd_lifecycle_apply(args):
    cfg = S3Config.from_env()
    if args.bucket:
        cfg.bucket_name = args.bucket
    svc = _build_service(cfg)

    rules = []
    if args.expire_days is not None:
        rules.append(
            build_expiration_rule(
                rule_id=f"expire-after-{args.expire_days}-days",
                enabled=True,
                days=args.expire_days,
                prefix=args.prefix,
            )
        )
    if args.noncurrent_days is not None:
        rules.append(
            build_noncurrent_version_expiration_rule(
                rule_id=f"noncurrent-expire-after-{args.noncurrent_days}-days",
                enabled=True,
                noncurrent_days=args.noncurrent_days,
                prefix=args.prefix,
            )
        )
    if args.abort_days is not None:
        rules.append(
            build_abort_incomplete_multipart_rule(
                rule_id=f"abort-multipart-after-{args.abort_days}-days",
                enabled=True,
                days_after_initiation=args.abort_days,
                prefix=args.prefix,
            )
        )

    if not rules:
        print("No rules specified. Use --expire-days/--noncurrent-days/--abort-days.", file=sys.stderr)
        sys.exit(2)

    apply_lifecycle_rules(svc.client, cfg.bucket_name, rules)
    print("OK")


def cmd_lifecycle_get(args):
    cfg = S3Config.from_env()
    if args.bucket:
        cfg.bucket_name = args.bucket
    svc = _build_service(cfg)
    rules = get_lifecycle_rules(svc.client, cfg.bucket_name)
    print(json.dumps(rules or [], indent=2))


def cmd_lifecycle_delete(args):
    cfg = S3Config.from_env()
    if args.bucket:
        cfg.bucket_name = args.bucket
    svc = _build_service(cfg)
    delete_lifecycle_rules(svc.client, cfg.bucket_name)
    print("OK")


def cmd_bucket_ensure(args):
    cfg = S3Config.from_env()
    if args.bucket:
        cfg.bucket_name = args.bucket
    svc = _build_service(cfg)
    ok = svc.ensure_bucket(create_if_missing=args.create, acl=args.acl)
    print("exists" if ok else "missing")


def cmd_bucket_versioning(args):
    cfg = S3Config.from_env()
    if args.bucket:
        cfg.bucket_name = args.bucket
    svc = _build_service(cfg)
    svc.set_bucket_versioning(enabled=args.enable)
    print("OK")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="S3/Backblaze S3-compatible storage CLI")
    sub = p.add_subparsers(dest="cmd")

    common_bucket = [
        dict(flags=["--bucket"], kwargs=dict(help="Bucket name (overrides BUCKET_NAME)", default=None)),
    ]

    up = sub.add_parser("upload", help="Upload file")
    up.add_argument("file", help="Local file path")
    up.add_argument("key", help="Object key")
    up.add_argument("--content-type", default=None)
    up.add_argument("--acl", default=None)
    up.add_argument("--storage-class", default=None)
    up.add_argument("--sse", default=None, help="Server-side encryption (e.g., AES256, aws:kms)")
    up.add_argument("--ssekms-key-id", default=None)
    for c in common_bucket:
        up.add_argument(*c["flags"], **c["kwargs"]) 
    up.set_defaults(func=cmd_upload)

    dl = sub.add_parser("download", help="Download file")
    dl.add_argument("key")
    dl.add_argument("dest")
    for c in common_bucket:
        dl.add_argument(*c["flags"], **c["kwargs"]) 
    dl.set_defaults(func=cmd_download)

    sg = sub.add_parser("sign-get", help="Generate presigned GET URL")
    sg.add_argument("key")
    sg.add_argument("--expires", type=int, default=3600)
    sg.add_argument("--response-content-type", default=None)
    sg.add_argument("--response-content-disposition", default=None)
    for c in common_bucket:
        sg.add_argument(*c["flags"], **c["kwargs"]) 
    sg.set_defaults(func=cmd_sign_get)

    sp = sub.add_parser("sign-put", help="Generate presigned PUT URL")
    sp.add_argument("key")
    sp.add_argument("--expires", type=int, default=3600)
    sp.add_argument("--content-type", default=None)
    sp.add_argument("--acl", default=None)
    for c in common_bucket:
        sp.add_argument(*c["flags"], **c["kwargs"]) 
    sp.set_defaults(func=cmd_sign_put)

    spost = sub.add_parser("sign-post", help="Generate presigned POST policy")
    spost.add_argument("key")
    spost.add_argument("--expires", type=int, default=3600)
    spost.add_argument("--content-type", default=None)
    for c in common_bucket:
        spost.add_argument(*c["flags"], **c["kwargs"]) 
    spost.set_defaults(func=cmd_sign_post)

    lc = sub.add_parser("lifecycle-apply", help="Apply lifecycle rules")
    lc.add_argument("--prefix", default=None, help="Optional prefix filter")
    lc.add_argument("--expire-days", type=int, default=None)
    lc.add_argument("--noncurrent-days", type=int, default=None)
    lc.add_argument("--abort-days", type=int, default=None)
    for c in common_bucket:
        lc.add_argument(*c["flags"], **c["kwargs"]) 
    lc.set_defaults(func=cmd_lifecycle_apply)

    lcg = sub.add_parser("lifecycle-get", help="Get lifecycle rules")
    for c in common_bucket:
        lcg.add_argument(*c["flags"], **c["kwargs"]) 
    lcg.set_defaults(func=cmd_lifecycle_get)

    lcd = sub.add_parser("lifecycle-delete", help="Delete lifecycle rules")
    for c in common_bucket:
        lcd.add_argument(*c["flags"], **c["kwargs"]) 
    lcd.set_defaults(func=cmd_lifecycle_delete)

    be = sub.add_parser("bucket-ensure", help="Ensure bucket exists (optionally create)")
    be.add_argument("--create", action="store_true")
    be.add_argument("--acl", default=None)
    for c in common_bucket:
        be.add_argument(*c["flags"], **c["kwargs"]) 
    be.set_defaults(func=cmd_bucket_ensure)

    bv = sub.add_parser("bucket-versioning", help="Enable/disable bucket versioning")
    bv.add_argument("--enable", action="store_true")
    for c in common_bucket:
        bv.add_argument(*c["flags"], **c["kwargs"]) 
    bv.set_defaults(func=cmd_bucket_versioning)

    return p


def main(argv: Optional[list] = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

