import os
import zipfile
import shutil


def extract_zip_to(zip_path, dest_dir):
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(dest_dir)


def make_zip_from_dir(src_dir, out_zip_path):
    base_dir = os.path.abspath(src_dir)
    with zipfile.ZipFile(out_zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, base_dir)
                z.write(full, rel)


def copytree(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

