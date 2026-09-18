"""Auth service."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError
from app.core.exceptions import ForbiddenError
from app.core.exceptions import NotFoundError
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token
from app.core.security import hash_password
from app.core.security import verify_password
from app.features.auth.model import User
from app.features.auth.schema import RegisterRequest
from app.features.auth.schema import UserUpdate


class AuthService:
    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        stmt = select(User).where(User.email == AuthService.normalize_email(email))
        return db.scalar(stmt)

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> User:
        user = db.get(User, user_id)

        if user is None:
            raise NotFoundError("User not found")

        return user

    @staticmethod
    def get_active_user(db: Session, user_id: int) -> User:
        """Used by the auth dependency — raises 401/403 rather than 404."""

        user = db.get(User, user_id)

        if user is None:
            raise UnauthorizedError("This account no longer exists.")

        if not user.is_active:
            raise ForbiddenError("This account is disabled.")

        return user

    @staticmethod
    def register(db: Session, payload: RegisterRequest) -> User:
        email = AuthService.normalize_email(payload.email)

        if AuthService.get_by_email(db, email) is not None:
            raise ConflictError("An account with that email already exists.")

        user = User(
            email=email,
            hashed_password=hash_password(payload.password),
            full_name=(payload.full_name or "").strip() or None,
            company_name=payload.company_name.strip(),
            contact_email=(
                AuthService.normalize_email(payload.contact_email)
                if payload.contact_email
                else email
            ),
            contact_phone=payload.contact_phone,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    @staticmethod
    def authenticate(db: Session, email: str, password: str) -> User:
        user = AuthService.get_by_email(db, email)

        # Deliberately the same error for "no such user" and "wrong password", so
        # the endpoint cannot be used to enumerate accounts.
        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password.")

        if not user.is_active:
            raise ForbiddenError("This account is disabled.")

        return user

    @staticmethod
    def issue_token(user: User) -> tuple[str, int]:
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        token = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email},
        )

        return token, expires_in

    @staticmethod
    def update(db: Session, user: User, payload: UserUpdate) -> User:
        data = payload.model_dump(exclude_unset=True)

        if "contact_email" in data and data["contact_email"]:
            data["contact_email"] = AuthService.normalize_email(data["contact_email"])

        for key, value in data.items():
            setattr(user, key, value)

        db.commit()
        db.refresh(user)

        return user
