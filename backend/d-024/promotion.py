import json
import tempfile
import time
from typing import Dict, Any, Tuple, Set
from registry import RegistryClient, RegistryError

class PromotionError(Exception):
    def __init__(self, message: str, http_code: int = 400, details: Any = None):
        super().__init__(message)
        self.http_code = http_code
        self.details = details

class PromotionService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.staging = RegistryClient(
            base_url=config['STAGING_REGISTRY'],
            username=config.get('STAGING_USERNAME'),
            password=config.get('STAGING_PASSWORD'),
            verify_tls=config.get('STAGING_VERIFY_TLS', True),
            timeout=config.get('HTTP_TIMEOUT', 30),
            extra_headers=config.get('STAGING_EXTRA_HEADERS', {})
        )
        self.prod = RegistryClient(
            base_url=config['PROD_REGISTRY'],
            username=config.get('PROD_USERNAME'),
            password=config.get('PROD_PASSWORD'),
            verify_tls=config.get('PROD_VERIFY_TLS', True),
            timeout=config.get('HTTP_TIMEOUT', 30),
            extra_headers=config.get('PROD_EXTRA_HEADERS', {})
        )

    def promote(self, repository: str, source_ref: str, dest_ref: str, dry_run: bool = False, force: bool = False) -> Dict[str, Any]:
        start = time.time()
        stats = {
            'repository': repository,
            'source': source_ref,
            'destination': dest_ref,
            'dry_run': dry_run,
            'force': force,
            'manifests_pushed': 0,
            'manifests_skipped': 0,
            'blobs_copied': 0,
            'blobs_skipped': 0,
            'bytes_copied': 0,
            'manifest_type': None,
        }
        try:
            # Check destination existence
            if not force and self.prod.manifest_exists(repository, dest_ref):
                stats['manifests_skipped'] += 1
                stats['manifest_type'] = 'unknown'
                return {
                    **stats,
                    'message': 'Destination reference already exists in prod. Use force=true to overwrite.'
                }

            # Fetch source manifest from staging
            manifest_bytes, manifest_content_type, manifest_digest = self.staging.get_manifest(repository, source_ref)
            stats['manifest_type'] = manifest_content_type

            if dry_run:
                return {**stats, 'message': 'Dry run: no changes applied.'}

            copied_digests: Set[str] = set()

            if manifest_content_type in (
                'application/vnd.docker.distribution.manifest.list.v2+json',
                'application/vnd.oci.image.index.v1+json'
            ):
                # Multi-arch index: ensure all referenced manifests and blobs exist, then push index
                idx = json.loads(manifest_bytes)
                manifests = idx.get('manifests', [])
                for desc in manifests:
                    child_digest = desc.get('digest')
                    if not child_digest:
                        raise PromotionError('Invalid manifest index: missing child digest', 502)

                    # Fetch child manifest by digest
                    child_bytes, child_ct, _ = self.staging.get_manifest(repository, child_digest)
                    # Ensure blobs for child manifest exist in prod
                    cstats = self._ensure_child_manifest_blobs(repository, child_bytes)
                    stats['blobs_copied'] += cstats['blobs_copied']
                    stats['blobs_skipped'] += cstats['blobs_skipped']
                    stats['bytes_copied'] += cstats['bytes_copied']

                    # Push child manifest to prod
                    self.prod.put_manifest(repository, child_digest, child_bytes, child_ct)
                    stats['manifests_pushed'] += 1

                # Push index manifest to prod under destination ref
                self.prod.put_manifest(repository, dest_ref, manifest_bytes, manifest_content_type)
                stats['manifests_pushed'] += 1

            elif manifest_content_type in (
                'application/vnd.docker.distribution.manifest.v2+json',
                'application/vnd.oci.image.manifest.v1+json'
            ):
                # Single-arch manifest
                cstats = self._ensure_child_manifest_blobs(repository, manifest_bytes)
                stats['blobs_copied'] += cstats['blobs_copied']
                stats['blobs_skipped'] += cstats['blobs_skipped']
                stats['bytes_copied'] += cstats['bytes_copied']
                self.prod.put_manifest(repository, dest_ref, manifest_bytes, manifest_content_type)
                stats['manifests_pushed'] += 1

            else:
                raise PromotionError(f'Unsupported manifest mediaType: {manifest_content_type}', 415)

            stats['elapsed_seconds'] = round(time.time() - start, 3)
            return stats

        except RegistryError as re:
            raise PromotionError(f'Registry error: {re}', http_code=502, details=getattr(re, 'details', None))

    def _ensure_child_manifest_blobs(self, repository: str, manifest_bytes: bytes) -> Dict[str, int]:
        data = json.loads(manifest_bytes)
        blobs = []
        # Docker & OCI manifests share these fields
        cfg = data.get('config')
        if cfg and cfg.get('digest'):
            blobs.append(cfg['digest'])
        for layer in data.get('layers', []) or []:
            if layer.get('digest'):
                blobs.append(layer['digest'])

        blobs_copied = 0
        blobs_skipped = 0
        bytes_copied = 0

        for digest in blobs:
            if self.prod.blob_exists(repository, digest):
                blobs_skipped += 1
                continue
            # Download from staging to temp file (to know Content-Length for upload)
            with tempfile.NamedTemporaryFile(prefix='promote-', suffix='.blob', delete=False) as tf:
                temp_path = tf.name
            size = self.staging.download_blob_to_file(repository, digest, temp_path)
            # Upload to prod
            self.prod.upload_blob(repository, digest, temp_path, size)
            blobs_copied += 1
            bytes_copied += size
        return {
            'blobs_copied': blobs_copied,
            'blobs_skipped': blobs_skipped,
            'bytes_copied': bytes_copied,
        }

