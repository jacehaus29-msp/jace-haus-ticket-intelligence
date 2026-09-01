from typing import Optional, List, Callable
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.core.security import decode_access_token


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token")
) -> User:
    """
    Authenticate request via JWT Bearer token or X-Auth-Token header.
    Returns the authenticated active User instance.
    """
    token = None
    if isinstance(authorization, str) and authorization.strip():
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]
    elif isinstance(x_auth_token, str) and x_auth_token.strip():
        token = x_auth_token.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or corrupted authentication token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists in system."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Please contact your system administrator."
        )

    return user


def get_optional_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token")
) -> Optional[User]:
    """
    Optional user extractor for endpoints that can adapt behavior for authenticated vs anonymous calls.
    """
    token = None
    if isinstance(authorization, str) and authorization.strip():
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]
    elif isinstance(x_auth_token, str) and x_auth_token.strip():
        token = x_auth_token.strip()

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    user_id = payload.get("sub")
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def require_roles(allowed_roles: List[str]) -> Callable:
    """
    FastAPI dependency factory enforcing that the authenticated user possesses one of the allowed roles.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = (current_user.role or "").strip().lower()
        normalized_allowed = [r.strip().lower() for r in allowed_roles]

        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Role '{current_user.role}' does not have permission to access this resource. Required role(s): {', '.join(allowed_roles)}."
            )
        return current_user

    return role_checker


# Role shortcut dependencies
require_admin = require_roles(["admin"])
require_manager_or_admin = require_roles(["admin", "manager"])
require_internal = require_roles(["admin", "manager", "technician"])
require_customer = require_roles(["customer"])
