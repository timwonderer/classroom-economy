from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    result = db.session.execute(text("SELECT column_name, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'insurance_policies'"))
    for row in result:
        print(row)
