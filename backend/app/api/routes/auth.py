from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.rate_limit import auth_rate_limit
from app.core.security import (
    create_access_token,
    hash_password,
    verify_google_credential,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    AuthUser,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=AuthUser.model_validate(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    dependencies=[Depends(auth_rate_limit)],
)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Try logging in.",
        )

    user = User(
        email=data.email,
        name=(data.name or "").strip() or None,
        password_hash=hash_password(data.password),
        email_verified=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return _token_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(auth_rate_limit)],
)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    if user is None:
        # Spend the same time as a real check so response timing
        # doesn't reveal which emails are registered.
        hash_password(data.password)
        valid = False
    else:
        valid = verify_password(data.password, user.password_hash)

    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
        )

    return _token_response(user)


@router.post(
    "/google",
    response_model=TokenResponse,
    dependencies=[Depends(auth_rate_limit)],
)
def google_login(data: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        info = verify_google_credential(data.credential)
    except Exception as error:
        logger.warning("Google sign-in rejected: %s", error)
        raise HTTPException(
            status_code=401,
            detail="Google sign-in failed. Please try again.",
        )

    google_sub = info["sub"]
    email = info["email"].strip().lower()
    name = info.get("name")
    picture = info.get("picture")

    user = db.query(User).filter(User.google_sub == google_sub).first()

    if user is None:
        user = db.query(User).filter(User.email == email).first()

        if user is not None:
            # Link Google to the existing account. If that account was
            # created with an unverified email + password, drop the
            # password: someone else could have registered this email
            # first, and Google has now proven who really owns it.
            user.google_sub = google_sub

            if not user.email_verified:
                user.password_hash = None
                user.email_verified = True
        else:
            user = User(
                email=email,
                name=name,
                google_sub=google_sub,
                email_verified=True,
            )
            db.add(user)

    if not user.name and name:
        user.name = name

    # Use the Google photo unless the user has set their own.
    if not user.avatar_url and picture:
        user.avatar_url = picture

    db.commit()
    db.refresh(user)

    return _token_response(user)


@router.get("/me", response_model=AuthUser)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=AuthUser)
def update_me(
    data: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.name is not None:
        current_user.name = data.name.strip() or None

    if data.avatar is not None:
        current_user.avatar_url = data.avatar or None

    db.commit()
    db.refresh(current_user)

    return current_user
