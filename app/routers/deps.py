"""
Shared FastAPI dependencies — JWT cookie extraction and role guards.
"""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from app.core.security import decode_access_token


def _get_current_user(access_token: str | None = Cookie(default=None)) -> dict:
    """Extract and validate the JWT from the httpOnly cookie."""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_access_token(access_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


CurrentUser = Annotated[dict, Depends(_get_current_user)]


def require_student(current_user: CurrentUser) -> dict:
    if current_user.get("role") not in ("student", "admin"):  # admins can also act
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students only")
    return current_user


def require_admin(current_user: CurrentUser) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return current_user


StudentDep = Annotated[dict, Depends(require_student)]
AdminDep = Annotated[dict, Depends(require_admin)]
