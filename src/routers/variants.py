from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.database import get_db
from src.models import User, StoreVariant
from src.schemas import StoreVariantCreateIn, StoreVariantUpdateIn, StoreVariantOut
from src.dependencies import get_current_user
import src.crud as crud


router = APIRouter(prefix="/variants", tags=["Варианты покупки (Маркетплейсы)"])


@router.post("/", response_model=StoreVariantOut, status_code=status.HTTP_201_CREATED)
def add_variant(
    var_in: StoreVariantCreateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    try:
        return crud.add_store_variant(
            db=db,
            user_id=current_user.id,
            model_id=var_in.component_model_id,
            custom_name=var_in.custom_name,
            shop_type=var_in.shop_type,
            url=var_in.url,
            price=var_in.current_price,
            delivery_info=var_in.delivery_info,
            comment=var_in.comment,
            track=var_in.is_tracked
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.get("/my", response_model=List[StoreVariantOut])
def get_my_variants(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    stmt = select(StoreVariant).where(StoreVariant.created_by_user_id == current_user.id)
    return db.scalars(stmt).all()

@router.patch("/{variant_id}", response_model=StoreVariantOut)
def update_variant(
    variant_id: int,
    var_update: StoreVariantUpdateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    variant = db.get(StoreVariant, variant_id)
    if not variant or variant.created_by_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Вариант покупки не найден")

    if var_update.current_price is not None:
        crud.update_variant_price(db, variant.id, var_update.current_price, variant.is_in_stock)
    
    for field, val in var_update.model_dump(exclude_unset=True).items():
        if field != "current_price":
            setattr(variant, field, val)
            
    db.commit()
    db.refresh(variant)
    return variant

@router.delete("/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(
    variant_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    variant = db.get(StoreVariant, variant_id)
    if not variant or variant.created_by_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Вариант покупки не найден")
    db.delete(variant)
    db.commit()