from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from src.database import get_db
from src.models import User, UserRole, Category, ComponentModel, ModelStatus, StoreVariant
from src.schemas import (
    CategoryCreateIn, CategoryOut,
    ComponentModelCreateIn, ComponentModelOut, ModelApproveIn,
    StoreVariantOut
)
from src.dependencies import get_current_user, require_admin
import src.crud as crud


router = APIRouter(prefix="/catalog", tags=["Каталог и Модели"])


@router.get("/categories", response_model=List[CategoryOut])
def list_categories(db: Annotated[Session, Depends(get_db)]):
    return db.scalars(select(Category)).all()

@router.post("/categories", response_model=CategoryOut, dependencies=[Depends(require_admin)])
def create_category(cat_in: CategoryCreateIn, db: Annotated[Session, Depends(get_db)]):
    return crud.create_category(db, name=cat_in.name, slug=cat_in.slug)


@router.get("/models", response_model=List[ComponentModelOut])
def list_models(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Возвращает глобальные утвержденные модели + свои модели на модерации"""
    if current_user.role == UserRole.ADMIN:
        stmt = select(ComponentModel)
    else:
        stmt = select(ComponentModel).where(
            or_(
                ComponentModel.status == ModelStatus.APPROVED,
                ComponentModel.created_by_user_id == current_user.id
            )
        )
    return db.scalars(stmt).all()

@router.post("/models", response_model=ComponentModelOut, status_code=status.HTTP_201_CREATED)
def propose_model(
    model_in: ComponentModelCreateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    is_admin = (current_user.role == UserRole.ADMIN)
    return crud.create_component_model(
        db=db,
        category_id=model_in.category_id,
        name=model_in.name,
        brand=model_in.brand,
        specs=model_in.specs,
        author_id=current_user.id,
        is_admin=is_admin
    )

@router.patch("/models/{model_id}/approve", response_model=ComponentModelOut, dependencies=[Depends(require_admin)])
def approve_model(
    model_id: int, 
    approve_in: ModelApproveIn, 
    db: Annotated[Session, Depends(get_db)]
):
    """Админское утверждение предложенной модели"""
    try:
        return crud.approve_model_by_admin(db, model_id, approve_in.specs)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/models/{model_id}/variants", response_model=List[StoreVariantOut], dependencies=[Depends(require_admin)])
def view_all_model_variants(model_id: int, db: Annotated[Session, Depends(get_db)]):
    """Сквозной аудит для администратора: просмотр всех ссылок, прикрепленных к модели"""
    stmt = select(StoreVariant).where(StoreVariant.component_model_id == model_id)
    return db.scalars(stmt).all()