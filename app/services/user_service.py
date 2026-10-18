from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User

# Verified against when the email doesn't exist, so "unknown email" costs the same
# time as "wrong password". Otherwise response time reveals which emails are registered.
_DUMMY_HASH = hash_password("dummy-password")


def create_user(db: Session, email: str, password: str) -> User | None:
    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # the unique constraint is the real guard against duplicates
        db.rollback()
        return None
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user