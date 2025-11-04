import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def main():
    """Main function."""
    pass
