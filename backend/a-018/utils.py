import os
import zipfile
import uuid


def ensure_dirs(paths):
    for p in paths:
        os.makedirs(p, exist_ok=True)


def generate_scan_id() -> str:
    return uuid.uuid4().hex


def is_within_directory(directory: str, target: str) -> bool:
    abs_directory = os.path.abspath(directory)
    abs_target = os.path.abspath(target)
    return os.path.commonpath([abs_directory]) == os.path.commonpath([abs_directory, abs_target])


def is_zipfile_safe(zip_path: str):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.infolist():
                # Basic size check for zipbomb protection via compressed/uncompressed ratio
                if member.file_size > 1_000_000_000:  # 1GB per file cap
                    return False, "file_too_large_in_zip"
                # Path traversal protections
                extracted_path = os.path.join("/tmp", member.filename)
                if not is_within_directory("/tmp", extracted_path):
                    return False, "zip_path_traversal"
        return True, ""
    except zipfile.BadZipFile:
        return False, "bad_zip"
    except Exception as e:
        return False, str(e)


def safe_extract_zip(zip_path: str, dest_dir: str):
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            # Avoid extraction of absolute paths or parent traversal
            member_path = os.path.join(dest_dir, member.filename)
            if not is_within_directory(dest_dir, member_path):
                raise ValueError("Unsafe zip path detected")
        zf.extractall(dest_dir)

