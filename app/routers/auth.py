"""
Auth Router — /auth
====================
Handles login (student + admin), logout, and current user info.

Rate limited: 5 login attempts per IP per 15 minutes to prevent
matric number enumeration attacks.
"""

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.security import create_access_token
from app.routers.deps import CurrentUser
from app.services import identity_service

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class StudentLoginRequest(BaseModel):
    matric_number: str = Field(..., min_length=5, max_length=20)


class AdminLoginRequest(BaseModel):
    matric_number: str = Field(..., min_length=5, max_length=20)
    pin: str = Field(..., min_length=4, max_length=10)


class LoginResponse(BaseModel):
    role: str
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login/student", response_model=LoginResponse)
@limiter.limit(settings.login_rate_limit)
async def student_login(
    request: Request,
    response: Response,
    body: StudentLoginRequest,
):
    """
    Student login via matric number.
    On success, sets an httpOnly JWT cookie.
    Returns NO matric data — only role confirmation.
    """
    voter = await identity_service.get_voter(body.matric_number)
    if not voter:
        # Deliberate vague message — don't confirm whether matric exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid matric number or not eligible",
        )

    token = create_access_token(
        hashed_matric_id=voter.hashed_matric_id,
        role="student",
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.jwt_expire_hours * 3600,
    )
    return LoginResponse(role="student", message="Logged in successfully")


@router.post("/login/admin", response_model=LoginResponse)
@limiter.limit(settings.login_rate_limit)
async def admin_login(
    request: Request,
    response: Response,
    body: AdminLoginRequest,
):
    """
    Admin login via matric number + PIN.
    On success, sets an httpOnly JWT cookie with role=admin.
    """
    admin = await identity_service.authenticate_admin(body.matric_number, body.pin)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

    token = create_access_token(
        hashed_matric_id=admin.hashed_matric_id,
        role="admin",
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.jwt_expire_hours * 3600,
    )
    return LoginResponse(role="admin", message="Logged in as admin")


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me")
async def me(current_user: CurrentUser):
    """Return the current user's role. Hashed matric is not returned."""
    return {"role": current_user.get("role")}
