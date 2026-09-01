from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import SessionLocal
from app.models.user import User
from app.models.technician import Technician
from app.models.customer import Customer
from app.core.security import hash_password, verify_password, create_access_token
from app.core.auth import get_current_user, require_admin

router = APIRouter(
    prefix="/auth",
    tags=["Authentication & RBAC"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def serialize_user(user: User, db: Session) -> Dict[str, Any]:
    """Serialize user safely without exposing password hashes."""
    team = None
    if user.technician_id:
        tech = db.query(Technician).filter(Technician.id == user.technician_id).first()
        if tech:
            team = tech.team

    company = None
    if user.customer_id:
        cust = db.query(Customer).filter(Customer.id == user.customer_id).first()
        if cust:
            company = cust.company

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "technician_id": user.technician_id,
        "customer_id": user.customer_id,
        "team": team,
        "company": company,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email and password, returning signed JWT token."""
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact your system administrator."
        )

    token_data = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "name": user.name,
        "technician_id": user.technician_id,
        "customer_id": user.customer_id
    }
    token = create_access_token(token_data)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user, db),
        "message": "Login successful"
    }


@router.post("/logout")
def logout():
    """Logout endpoint."""
    return {"message": "Logged out successfully"}


@router.get("/me")
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return profile and permissions for currently authenticated user."""
    return {
        "user": serialize_user(current_user, db),
        "permissions": {
            "is_admin": current_user.role == "admin",
            "is_manager": current_user.role in ["admin", "manager"],
            "is_technician": current_user.role in ["admin", "manager", "technician"],
            "is_customer": current_user.role == "customer"
        }
    }


# -----------------------------------------------------------------------------
# USER MANAGEMENT (ADMIN ONLY)
# -----------------------------------------------------------------------------

@router.get("/users")
def list_users(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all registered users in the system."""
    users = db.query(User).order_by(User.id.asc()).all()
    return {
        "count": len(users),
        "users": [serialize_user(u, db) for u in users]
    }


class UserCreateRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str
    technician_id: Optional[int] = None
    customer_id: Optional[int] = None


@router.post("/users")
def create_user(
    payload: UserCreateRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new user account (Admin only)."""
    email_clean = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{email_clean}' already exists."
        )

    role_clean = payload.role.strip().lower()
    if role_clean not in ["admin", "manager", "technician", "customer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be one of: 'admin', 'manager', 'technician', 'customer'."
        )

    if not payload.password or len(payload.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )

    new_user = User(
        name=payload.name.strip(),
        email=email_clean,
        password_hash=hash_password(payload.password),
        role=role_clean,
        technician_id=payload.technician_id,
        customer_id=payload.customer_id,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": f"User '{new_user.name}' created successfully.",
        "user": serialize_user(new_user, db)
    }


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    technician_id: Optional[int] = None
    customer_id: Optional[int] = None


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a user's details, role, active status, or reset password (Admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.name is not None and payload.name.strip():
        user.name = payload.name.strip()

    if payload.role is not None:
        role_clean = payload.role.strip().lower()
        if role_clean in ["admin", "manager", "technician", "customer"]:
            user.role = role_clean

    if payload.is_active is not None:
        user.is_active = payload.is_active

    if payload.password and len(payload.password) >= 6:
        user.password_hash = hash_password(payload.password)

    if payload.technician_id is not None:
        user.technician_id = payload.technician_id if payload.technician_id > 0 else None

    if payload.customer_id is not None:
        user.customer_id = payload.customer_id if payload.customer_id > 0 else None

    db.commit()
    db.refresh(user)

    return {
        "message": "User updated successfully.",
        "user": serialize_user(user, db)
    }
