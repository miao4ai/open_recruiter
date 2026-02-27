"""Auth routes — register, login, me."""

import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app import database as db
from app.auth import create_token, get_current_user, hash_password, verify_password
from app.models import User, UserLogin, UserRegister

router = APIRouter()


@router.post("/register")
async def register(req: UserRegister):
    # Check if this exact email+role combo already exists
    existing = db.get_user_by_email_and_role(req.email, req.role.value)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email already registered as {req.role.value}",
        )

    user = User(email=req.email, name=req.name, role=req.role.value)
    user_dict = user.model_dump()
    user_dict["password_hash"] = hash_password(req.password)

    # Retry with a fresh ID on the unlikely chance of a primary-key collision
    for attempt in range(3):
        try:
            db.insert_user(user_dict)
            break
        except sqlite3.IntegrityError as exc:
            err_msg = str(exc).lower()
            if "email" in err_msg or "unique" in err_msg:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email already registered as {req.role.value}",
                )
            # Likely a primary-key collision — regenerate ID
            user_dict["id"] = uuid.uuid4().hex[:8]
            user.id = user_dict["id"]
            if attempt == 2:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Registration failed — please try again",
                )

    token = create_token(user.id, user.email)
    return {"token": token, "user": user.model_dump()}


@router.post("/login")
async def login(req: UserLogin):
    row = db.get_user_by_email_and_role(req.email, req.role.value)
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user = User(id=row["id"], email=row["email"], name=row["name"], role=row.get("role", "recruiter"), created_at=row["created_at"])
    token = create_token(user.id, user.email)
    return {"token": token, "user": user.model_dump()}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "name": current_user["name"],
        "role": current_user.get("role", "recruiter"),
        "created_at": current_user["created_at"],
    }


@router.delete("/account")
async def delete_account(
    delete_records: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Delete the current user's account.

    Query params:
        delete_records: if true, also removes all business data (jobs, candidates, emails, etc.)
    """
    db.delete_user(current_user["id"], delete_records=delete_records)
    return {"status": "ok"}
