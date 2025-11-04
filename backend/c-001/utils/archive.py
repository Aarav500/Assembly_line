from pathlib import Path
import zipfile


def zip_directory(source_dir: Path, zip_path: Path) -> None:
    source_dir = Path(source_dir).resolve()
    zip_path = Path(zip_path).resolve()
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for p in source_dir.rglob('*'):
            if p.is_file():
                zf.write(p, arcname=p.relative_to(source_dir))

