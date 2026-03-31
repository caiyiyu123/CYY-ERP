"""Create initial admin user."""
from app.database import SessionLocal, Base, engine
from app.models.user import User
from app.utils.security import hash_password
import app.models  # noqa: F401

Base.metadata.create_all(bind=engine)

db = SessionLocal()
if not db.query(User).filter(User.username == "admin").first():
    admin = User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True)
    db.add(admin)
    db.commit()
    print("Admin user created: admin / admin123")
else:
    print("Admin user already exists")
db.close()
