import os
import io
import zipfile
import hashlib
from datetime import datetime
from werkzeug.datastructures import FileStorage
from models import Artifact

try:
    import requests
except ImportError:
    requests = None


def ensure_storage(base_dir: str):
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'artifacts'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'bundles'), exist_ok=True)


def save_uploaded_file(storage: FileStorage, base_dir: str):
    artifacts_dir = os.path.join(base_dir, 'artifacts')
    filename = storage.filename
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S-%f')
    safe_name = f"{timestamp}-{filename}"
    path = os.path.join(artifacts_dir, safe_name)
    storage.save(path)
    size = os.path.getsize(path)
    return path, size


def compute_checksum(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha.update(chunk)
    return sha.hexdigest()


def create_bundle_zip(bundle, artifacts, base_dir: str) -> str:
    bundles_dir = os.path.join(base_dir, 'bundles')
    os.makedirs(bundles_dir, exist_ok=True)
    zip_name = f"bundle-{bundle.id}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.zip"
    zip_path = os.path.join(bundles_dir, zip_name)
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        base_folder = f"{bundle.name.replace(' ', '_')}/"
        for art in artifacts:
            arcname = base_folder + os.path.basename(art.filename)
            if os.path.isfile(art.path):
                zf.write(art.path, arcname=arcname)
    return zip_path


def fetch_url_to_artifact(url: str, base_dir: str) -> Artifact:
    if requests is None:
        raise RuntimeError('requests library is required for URL fetching. Add requests to requirements.')
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    content_disposition = resp.headers.get('content-disposition', '')
    filename = None
    if 'filename=' in content_disposition:
        filename = content_disposition.split('filename=')[-1].strip('"')
    if not filename:
        filename = url.split('/')[-1] or 'downloaded.bin'
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S-%f')
    artifacts_dir = os.path.join(base_dir, 'artifacts')
    safe_name = f"{timestamp}-{filename}"
    path = os.path.join(artifacts_dir, safe_name)
    with open(path, 'wb') as f:
        f.write(resp.content)
    size = os.path.getsize(path)
    checksum = compute_checksum(path)
    return Artifact(filename=filename, path=path, size=size, checksum=checksum)

