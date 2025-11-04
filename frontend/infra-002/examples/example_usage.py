import os
from s3_backblaze.config import S3Config
from s3_backblaze.storage_service import StorageService, StorageInitOptions
from s3_backblaze.lifecycle import (
    apply_lifecycle_rules,
    build_abort_incomplete_multipart_rule,
    build_expiration_rule,
)

# Ensure env variables are set or pass explicitly.
# For Backblaze, set S3_ENDPOINT_URL (e.g., https://s3.us-west-004.backblazeb2.com)

cfg = S3Config.from_env()
opts = StorageInitOptions(
    bucket_name=cfg.bucket_name,
    region_name=cfg.region_name,
    endpoint_url=cfg.endpoint_url,
    access_key=cfg.access_key,
    secret_key=cfg.secret_key,
    session_token=cfg.session_token,
)
svc = StorageService(opts)

# Ensure bucket exists (create if missing)
svc.ensure_bucket(create_if_missing=True)

# Upload a file
svc.upload_file("./README.md", "docs/README.md", content_type="text/markdown")

# Download it back
svc.download_file("docs/README.md", "./_tmp_readme.md")

# Generate signed GET URL
url_get = svc.generate_presigned_url_get("docs/README.md", expires_in=600)
print("GET URL:", url_get)

# Generate signed PUT URL
url_put = svc.generate_presigned_url_put("uploads/newfile.txt", expires_in=600, content_type="text/plain")
print("PUT URL:", url_put)

# Apply lifecycle: expire files in logs/ after 30 days; abort incomplete multiparts after 7 days
rules = [
    build_expiration_rule("expire-logs-30d", True, days=30, prefix="logs/"),
    build_abort_incomplete_multipart_rule("abort-mpu-7d", True, days_after_initiation=7),
]
apply_lifecycle_rules(svc.client, cfg.bucket_name, rules)
print("Lifecycle applied")

