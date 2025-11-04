import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import io
import json
import traceback
from datetime import datetime

from flask import Flask, request, jsonify, send_file
import pandas as pd

from exporters.serializer import serialize_dataframe
from connectors.local import LocalConnector
from connectors.s3 import S3Connector
from connectors.gcs import GCSConnector
from connectors.adls import ADLSConnector
from config import settings

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


def _error(message, status=400, details=None):
    payload = {"error": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status


def _now_str():
    return datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')


def _validate_request(payload):
    if not isinstance(payload, dict):
        raise ValueError("Request JSON must be an object")

    data = payload.get("data")
    if data is None:
        raise ValueError("Field 'data' is required and must be an array of records")
    if not isinstance(data, list):
        raise ValueError("Field 'data' must be an array of objects")

    fmt = (payload.get("format") or "csv").lower()
    if fmt not in ("csv", "parquet"):
        raise ValueError("Field 'format' must be 'csv' or 'parquet'")

    destination = payload.get("destination") or {"type": "download"}
    if not isinstance(destination, dict):
        raise ValueError("Field 'destination' must be an object")

    dest_type = (destination.get("type") or "download").lower()
    if dest_type not in ("download", "local", "s3", "gcs", "adls"):
        raise ValueError("destination.type must be one of: download, local, s3, gcs, adls")

    options = payload.get("options") or {}
    if not isinstance(options, dict):
        raise ValueError("Field 'options' must be an object if provided")

    return data, fmt, destination, options


def _build_filename(base_name=None, extension="csv"):
    base = base_name or settings.DEFAULT_BASENAME
    return f"{base}-{_now_str()}.{extension}"


def _get_connector(destination: dict):
    dest_type = destination.get("type").lower()
    if dest_type == "local":
        base_dir = destination.get("base_dir") or settings.LOCAL_EXPORT_DIR
        return LocalConnector(base_dir=base_dir)

    if dest_type == "s3":
        bucket = destination.get("bucket") or settings.S3_BUCKET
        if not bucket:
            raise ValueError("destination.bucket is required for s3")
        prefix = destination.get("prefix") or settings.S3_PREFIX
        region = destination.get("region") or settings.S3_REGION
        creds = destination.get("credentials") or {}
        return S3Connector(
            bucket=bucket,
            prefix=prefix,
            region_name=region,
            aws_access_key_id=creds.get("aws_access_key_id") or settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=creds.get("aws_secret_access_key") or settings.AWS_SECRET_ACCESS_KEY,
            aws_session_token=creds.get("aws_session_token") or settings.AWS_SESSION_TOKEN,
        )

    if dest_type == "gcs":
        bucket = destination.get("bucket") or settings.GCS_BUCKET
        if not bucket:
            raise ValueError("destination.bucket is required for gcs")
        prefix = destination.get("prefix") or settings.GCS_PREFIX
        project = destination.get("project") or settings.GCP_PROJECT
        creds = destination.get("credentials") or settings.GCP_SERVICE_ACCOUNT_JSON
        return GCSConnector(bucket=bucket, prefix=prefix, project=project, credentials=creds)

    if dest_type == "adls":
        container = destination.get("container") or settings.AZURE_BLOB_CONTAINER
        if not container:
            raise ValueError("destination.container is required for adls")
        path_prefix = destination.get("prefix") or settings.AZURE_BLOB_PREFIX
        creds = destination.get("credentials") or {}
        # Supports either connection_string or account_name/account_key
        connection_string = creds.get("connection_string") or settings.AZURE_STORAGE_CONNECTION_STRING
        account_name = creds.get("account_name") or settings.AZURE_STORAGE_ACCOUNT_NAME
        account_key = creds.get("account_key") or settings.AZURE_STORAGE_ACCOUNT_KEY
        return ADLSConnector(
            container=container,
            prefix=path_prefix,
            connection_string=connection_string,
            account_name=account_name,
            account_key=account_key,
        )

    if dest_type == "download":
        return None

    raise ValueError(f"Unsupported destination type: {dest_type}")


@app.route('/export', methods=['POST'])
def export_data():
    try:
        payload = request.get_json(silent=True)
        if payload is None:
            return _error("Invalid or missing JSON body", 400)

        data, fmt, destination, options = _validate_request(payload)

        # Convert data to DataFrame
        try:
            df = pd.DataFrame(data)
        except Exception as e:
            return _error("Failed to construct DataFrame from 'data'", 400, str(e))

        # Serialize to target format
        content_bytes, content_type, extension = serialize_dataframe(df, fmt=fmt, options=options)

        # File naming
        filename = destination.get("filename") or _build_filename(base_name=destination.get("base_name"), extension=extension)

        # Handle destination
        dest_type = destination.get("type").lower()
        if dest_type == "download":
            return send_file(
                io.BytesIO(content_bytes),
                mimetype=content_type,
                as_attachment=True,
                download_name=filename,
            )

        connector = _get_connector(destination)
        if connector is None:
            return _error("Connector resolution failed", 400)

        # Path/key per destination
        path = destination.get("path") or filename

        # Write to destination
        location = connector.write(content_bytes, path, content_type=content_type)

        return jsonify({
            "status": "success",
            "location": location,
            "content_type": content_type,
            "bytes": len(content_bytes),
        })

    except ValueError as ve:
        return _error(str(ve), 400)
    except Exception:
        if settings.DEBUG:
            return _error("Internal server error", 500, traceback.format_exc())
        return _error("Internal server error", 500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '8080'))) 



def create_app():
    return app


@app.route('/export/csv', methods=['POST'])
def _auto_stub_export_csv():
    return 'Auto-generated stub for /export/csv', 200


@app.route('/export/parquet', methods=['POST'])
def _auto_stub_export_parquet():
    return 'Auto-generated stub for /export/parquet', 200


@app.route('/connector/info', methods=['GET'])
def _auto_stub_connector_info():
    return 'Auto-generated stub for /connector/info', 200
