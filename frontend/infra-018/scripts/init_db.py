from service.main import create_app
from service.db import Base, engine

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        Base.metadata.create_all(bind=engine)
        print("Database tables created")

