from app import create_app
from todo_extractor import scan_and_update_backlog

app = create_app()

if __name__ == '__main__':
    # Convenience CLI: python manage.py scan
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'scan':
        result = scan_and_update_backlog(app)
        print(result)
    else:
        app.run()

