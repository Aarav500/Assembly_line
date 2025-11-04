from __future__ import annotations
import time
from typing import Optional
import boto3
from botocore.credentials import RefreshableCredentials
from botocore.session import get_session as get_botocore_session

_assume_cache: dict[str, dict] = {}


def _assume_role(role_arn: str, session_name: str, external_id: Optional[str] = None, duration_seconds: int = 3600):
    sts = boto3.client("sts")
    params = {"RoleArn": role_arn, "RoleSessionName": session_name, "DurationSeconds": duration_seconds}
    if external_id:
        params["ExternalId"] = external_id
    return sts.assume_role(**params)["Credentials"]


def _refresh(role_arn: str, external_id: Optional[str]):
    def _do_refresh():
        creds = _assume_role(role_arn, "backup-service-session", external_id=external_id)
        return {
            "access_key": creds["AccessKeyId"],
            "secret_key": creds["SecretAccessKey"],
            "token": creds["SessionToken"],
            "expiry_time": creds["Expiration"].isoformat(),
        }
    return _do_refresh


def get_session(region: str, profile_name: Optional[str] = None, role_arn: Optional[str] = None, external_id: Optional[str] = None):
    if role_arn:
        cache_key = f"{role_arn}:{external_id or ''}:{region}"
        if cache_key not in _assume_cache:
            refresh_func = _refresh(role_arn, external_id)
            initial = refresh_func()
            refreshable = RefreshableCredentials.create_from_metadata(
                metadata=initial,
                refresh_using=refresh_func,
                method="assume-role",
            )
            bc = get_botocore_session()
            bc._credentials = refreshable
            bc.set_config_variable("region", region)
            sess = boto3.Session(botocore_session=bc, region_name=region)
            _assume_cache[cache_key] = {"session": sess, "created": time.time()}
        return _assume_cache[cache_key]["session"]
    else:
        return boto3.Session(region_name=region, profile_name=profile_name)

