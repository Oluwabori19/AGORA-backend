"""Authentication endpoints for user registration, login, and token refresh.

Implements JWT-based authentication with access and refresh tokens.
Passwords are hashed with bcrypt before storage.
"""

from fastapi import APIRouter, Depends, status, HTTPException, Response
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer

from app.auth import database, utils, oauth2
from app.schemas import user_login
from app.models import user_model
from app.auth.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

# OAuth2 scheme for Bearer token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


@router.post(
    "/register", status_code=status.HTTP_201_CREATED, response_model=user_login.UserOut
)
def create_user(user: user_login.UserCreate, db: Session = Depends(database.get_db)):
    """Register a new user account.
    
    Note: Currently unrestricted. Should be updated to allow only admin users
    to create new accounts for production use.
    """
    try:
        # Hash password before storing in database
        hashed_password = utils.hash(user.password)
        user.password = hashed_password
        new_user = user_model.User(**user.model_dump())
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception as error:
        raise HTTPException(
            status_code=500, detail=f"Error while creating user {error.__cause__}"
        )


@router.post("/login", response_model=user_login.Token)
def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = (
        db.query(user_model.User)
        .filter(user_model.User.email == user_credentials.username)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Invalid user"
        )

    if not utils.verify(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Invalid password"
        )

    access_token = oauth2.create_access_token(data={"user_id": user.id})
    refresh_token = oauth2.create_refresh_token(data={"user_id": f"{user.id}_30"})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh-token", response_model=user_login.Token)
def refresh_token(
    token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # print("from function")
    # print(token)
    tokens = oauth2.verify_refresh_token(token, credentials_exception)
    # print("after")
    return tokens


"""
#Future functions
  - auth/forgot-password
  - auth/reset-password
  - auth/send-verification-email
  - auth/verify-email
"""
