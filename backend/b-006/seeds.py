from app import create_app
from app.models import db, Taxonomy, Term


def seed():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        tech = Taxonomy(name='Technology', description='Tech related topics', default_threshold=0.8)
        db.session.add(tech)
        db.session.flush()

        terms = [
            Term(
                name='Python', taxonomy_id=tech.id, weight=1.2, threshold=0.7,
                keywords=[
                    {'pattern': 'python', 'weight': 1.0},
                    {'pattern': 'py3', 'weight': 0.8},
                    {'pattern': 're:py(thon)?\s+\d+(\.\d+)?', 'weight': 0.9},
                ]
            ),
            Term(
                name='Flask', taxonomy_id=tech.id, weight=1.3, threshold=0.7,
                keywords=[
                    {'pattern': 'flask', 'weight': 1.0},
                    {'pattern': 'werkzeug', 'weight': 0.6},
                    {'pattern': 'jinja', 'weight': 0.6},
                ]
            ),
            Term(
                name='Machine Learning', taxonomy_id=tech.id, weight=1.0, threshold=1.0,
                keywords=[
                    {'pattern': 'machine learning', 'weight': 1.0},
                    {'pattern': 'ml', 'weight': 0.6},
                    {'pattern': 'model training', 'weight': 0.8},
                    {'pattern': 'neural network', 'weight': 1.1},
                ]
            ),
        ]
        db.session.add_all(terms)

        biz = Taxonomy(name='Business', description='Business and marketing', default_threshold=1.0)
        db.session.add(biz)
        db.session.flush()

        db.session.add_all([
            Term(
                name='Marketing', taxonomy_id=biz.id, weight=1.0,
                keywords=[{'pattern': 'marketing'}, {'pattern': 'seo', 'weight': 0.9}, {'pattern': 'campaign'}]
            ),
            Term(
                name='Finance', taxonomy_id=biz.id, weight=1.0,
                keywords=[{'pattern': 'finance'}, {'pattern': 'accounting'}, {'pattern': 'budget'}]
            ),
        ])

        db.session.commit()
        print('Seeded example taxonomies and terms.')


if __name__ == '__main__':
    seed()

