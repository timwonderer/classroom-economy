
from app import create_app

app = create_app()
with app.app_context():
    print(app.config['SQLALCHEMY_DATABASE_URI'])
