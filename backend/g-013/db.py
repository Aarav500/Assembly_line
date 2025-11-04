from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db():
    from models import Dataset, CodeVersion, Environment, Run, RunDataset, Artifact, Bundle
    db.create_all()

