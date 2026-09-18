"""Auth router — the buyer dashboard's login surface."""

from fastapi import APIRouter

from app.core.dependencies import CurrentUser
from app.core.dependencies import DBSession
from app.features.auth.model import User
from app.features.auth.schema import LoginRequest
from app.features.auth.schema import RegisterRequest
from app.features.auth.schema import TokenResponse
from app.features.auth.schema import UserResponse
from app.features.auth.schema import UserUpdate
from app.features.auth.service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


def _token_response(user: User) -> TokenResponse:
    token, expires_in = AuthService.issue_token(user)

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
)
def register(
    payload: RegisterRequest,
    db: DBSession,
):
    """Create a buyer account and return a token, so signup signs you straight in."""

    user = AuthService.register(db=db, payload=payload)

    return _token_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    payload: LoginRequest,
    db: DBSession,
):
    user = AuthService.authenticate(
        db=db,
        email=payload.email,
        password=payload.password,
    )

    return _token_response(user)


@router.get(
    "/me",
    response_model=UserResponse,
)
def me(user: CurrentUser):
    return user


@router.patch(
    "/me",
    response_model=UserResponse,
)
def update_me(
    payload: UserUpdate,
    user: CurrentUser,
    db: DBSession,
):
    return AuthService.update(db=db, user=user, payload=payload)
