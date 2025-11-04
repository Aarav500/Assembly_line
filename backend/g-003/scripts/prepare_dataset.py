import os
import argparse
import json
from utils.dataset_manager import DatasetManager
from config import SETTINGS


def main():
    parser = argparse.ArgumentParser(description='Create a dataset version from a JSONL or TXT file')
    parser.add_argument('--name', required=True, help='Dataset name')
    parser.add_argument('--file', required=True, help='Path to JSONL or TXT')
    parser.add_argument('--metadata', help='JSON string metadata', default='{}')
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        raise FileNotFoundError(args.file)

    with open(args.file, 'rb') as f:
        data = f.read()

    dm = DatasetManager(base_dir=SETTINGS['DATASETS_DIR'])
    meta = json.loads(args.metadata)
    info = dm.create_dataset_version(name=args.name, files=[(os.path.basename(args.file), data)], metadata=meta)
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()

