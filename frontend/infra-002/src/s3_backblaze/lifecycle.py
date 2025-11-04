from typing import Any, Dict, List, Optional

import botocore


def _build_filter(prefix: Optional[str] = None, tags: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    if prefix and tags:
        return {
            "And": {
                "Prefix": prefix,
                "Tags": [{"Key": k, "Value": v} for k, v in (tags or {}).items()],
            }
        }
    if tags and not prefix:
        return {"And": {"Tags": [{"Key": k, "Value": v} for k, v in tags.items()]}}
    if prefix:
        return {"Prefix": prefix}
    return {"Prefix": ""}


def build_expiration_rule(
    rule_id: str,
    enabled: bool,
    days: Optional[int] = None,
    prefix: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    expiration_date: Optional[str] = None,  # ISO 8601 YYYY-MM-DDThh:mm:ssZ
    expired_object_delete_marker: Optional[bool] = None,
) -> Dict[str, Any]:
    rule: Dict[str, Any] = {
        "ID": rule_id,
        "Status": "Enabled" if enabled else "Disabled",
        "Filter": _build_filter(prefix, tags),
    }

    expiration: Dict[str, Any] = {}
    if days is not None:
        expiration["Days"] = int(days)
    if expiration_date is not None:
        expiration["Date"] = expiration_date
    if expired_object_delete_marker is not None:
        expiration["ExpiredObjectDeleteMarker"] = bool(expired_object_delete_marker)

    if not expiration:
        raise ValueError("At least one expiration parameter must be provided (days, date, or expired_object_delete_marker).")

    rule["Expiration"] = expiration
    return rule


def build_noncurrent_version_expiration_rule(
    rule_id: str,
    enabled: bool,
    noncurrent_days: int,
    prefix: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    newer_noncurrent_versions: Optional[int] = None,
) -> Dict[str, Any]:
    if noncurrent_days <= 0:
        raise ValueError("noncurrent_days must be > 0")

    rule: Dict[str, Any] = {
        "ID": rule_id,
        "Status": "Enabled" if enabled else "Disabled",
        "Filter": _build_filter(prefix, tags),
        "NoncurrentVersionExpiration": {
            "NoncurrentDays": int(noncurrent_days)
        },
    }
    if newer_noncurrent_versions is not None:
        rule["NoncurrentVersionExpiration"]["NewerNoncurrentVersions"] = int(newer_noncurrent_versions)
    return rule


def build_abort_incomplete_multipart_rule(
    rule_id: str,
    enabled: bool,
    days_after_initiation: int = 7,
    prefix: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if days_after_initiation <= 0:
        raise ValueError("days_after_initiation must be > 0")

    return {
        "ID": rule_id,
        "Status": "Enabled" if enabled else "Disabled",
        "Filter": _build_filter(prefix, tags),
        "AbortIncompleteMultipartUpload": {
            "DaysAfterInitiation": int(days_after_initiation)
        },
    }


def apply_lifecycle_rules(s3_client, bucket_name: str, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    payload = {"Bucket": bucket_name, "LifecycleConfiguration": {"Rules": rules}}
    return s3_client.put_bucket_lifecycle_configuration(**payload)


def get_lifecycle_rules(s3_client, bucket_name: str) -> Optional[List[Dict[str, Any]]]:
    try:
        resp = s3_client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
        return resp.get("Rules", [])
    except s3_client.exceptions.NoSuchLifecycleConfiguration:  # type: ignore[attr-defined]
        return None
    except botocore.exceptions.ClientError as e:
        if e.response["Error"].get("Code") in {"NoSuchLifecycleConfiguration", "NoSuchBucket"}:
            return None
        raise


def delete_lifecycle_rules(s3_client, bucket_name: str) -> None:
    s3_client.delete_bucket_lifecycle(Bucket=bucket_name)

