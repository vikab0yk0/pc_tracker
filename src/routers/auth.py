from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas import UserRegisterIn, UserLoginIn, TokenOut, UserOut, RoleUpdateIn
from src.security import get_password_hash, verify_password, create_access_token
from src.dependencies import get_current_user, require_admin
from src.models import User, UserRole
import src.crud as crud


router = APIRouter(prefix="/auth", tags=["Аутентификация"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegisterIn, db: Annotated[Session, Depends(get_db)]):
    existing_user = crud.get_user_by_email(db, user_in.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    
    hashed_pw = get_password_hash(user_in.password)
    user = crud.create_user(db, email=user_in.email, hashed_pw=hashed_pw, role=user_in.role)
    return user

@router.post("/login", response_model=TokenOut)
def login(login_in: UserLoginIn, db: Annotated[Session, Depends(get_db)]):
    user = crud.get_user_by_email(db, login_in.email)
    if not user or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    
    crud.touch_user_login(db, user.id)
    token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return TokenOut(access_token=token)

@router.get("/me", response_model=UserOut)
def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

@router.patch("/users/{user_id}/role", response_model=UserOut, dependencies=[Depends(require_admin)])
def update_user_role(user_id: int, role_in: RoleUpdateIn, db: Annotated[Session, Depends(get_db)]):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.role = role_in.role
    db.commit()
    db.refresh(user)
    return user

@router.post("/subscribe", response_model=UserOut)
def subscribe_premium(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    current_user.role = UserRole.PREMIUM
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/unsubscribe", response_model=UserOut)
def unsubscribe_premium(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    current_user.role = UserRole.USER
    db.commit()
    db.refresh(current_user)
    return current_user