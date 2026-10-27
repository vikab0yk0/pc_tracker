from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.database import get_db
from src.models import User, Build, BuildItem
from src.schemas import (
    BuildCreateIn, BuildCloneIn, BuildDetailOut,
    BuildItemAddIn, BuildItemUpdateIn, BuildItemOut,
    CompatibilityReportOut
)
from src.dependencies import get_current_user
import src.crud as crud
import grpc
from src.grpc_services.client import CompatibilityGrpcClient


router = APIRouter(prefix="/builds", tags=["Сборки ПК"])
grpc_client = CompatibilityGrpcClient()


@router.post("/", response_model=BuildDetailOut, status_code=status.HTTP_201_CREATED)
def create_build(
    b_in: BuildCreateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    build = crud.create_build(db, user_id=current_user.id, name=b_in.name, description=b_in.description)
    return BuildDetailOut(
        id=build.id,
        user_id=build.user_id,
        name=build.name,
        description=build.description,
        total_price=crud.calculate_build_total_price(db, build.id),
        items=[],
        created_at=build.created_at,
        updated_at=build.updated_at
    )

@router.get("/", response_model=List[BuildDetailOut])
def get_user_builds(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    stmt = select(Build).where(Build.user_id == current_user.id)
    builds = db.scalars(stmt).all()
    res = []
    for b in builds:
        res.append(BuildDetailOut(
            id=b.id,
            user_id=b.user_id,
            name=b.name,
            description=b.description,
            total_price=crud.calculate_build_total_price(db, b.id),
            items=[BuildItemOut.model_validate(it) for it in b.items],
            created_at=b.created_at,
            updated_at=b.updated_at
        ))
    return res

@router.get("/{build_id}", response_model=BuildDetailOut)
def get_build_details(
    build_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    build = db.get(Build, build_id)
    if not build or build.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Сборка не найдена")
    return BuildDetailOut(
        id=build.id,
        user_id=build.user_id,
        name=build.name,
        description=build.description,
        total_price=crud.calculate_build_total_price(db, build.id),
        items=[BuildItemOut.model_validate(it) for it in build.items],
        created_at=build.created_at,
        updated_at=build.updated_at
    )

@router.post("/{build_id}/clone", response_model=BuildDetailOut, status_code=status.HTTP_201_CREATED)
def clone_existing_build(
    build_id: int,
    clone_in: BuildCloneIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    build = db.get(Build, build_id)
    if not build or build.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Сборка не найдена")
    
    cloned = crud.clone_build(db, build_id=build.id, new_name=clone_in.new_name)
    return BuildDetailOut(
        id=cloned.id,
        user_id=cloned.user_id,
        name=cloned.name,
        description=cloned.description,
        total_price=crud.calculate_build_total_price(db, cloned.id),
        items=[BuildItemOut.model_validate(it) for it in cloned.items],
        created_at=cloned.created_at,
        updated_at=cloned.updated_at
    )



@router.post("/{build_id}/items", response_model=BuildItemOut)
def add_slot_item(
    build_id: int,
    item_in: BuildItemAddIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    build = db.get(Build, build_id)
    if not build or build.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Сборка не найдена")

    return crud.add_component_to_build(
        db=db,
        build_id=build.id,
        model_id=item_in.component_model_id,
        category_id=item_in.category_id,
        quantity=item_in.quantity,
        is_active=item_in.is_active_variant,
        selected_variant_id=item_in.selected_variant_id
    )

@router.patch("/{build_id}/items/{item_id}", response_model=BuildItemOut)
def update_slot_item(
    build_id: int,
    item_id: int,
    upd_in: BuildItemUpdateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Позволяет переключать активную альтернативу (ветвление) и менять количество"""
    build = db.get(Build, build_id)
    if not build or build.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Сборка не найдена")

    item = db.get(BuildItem, item_id)
    if not item or item.build_id != build.id:
        raise HTTPException(status_code=404, detail="Элемент сборки не найден")

    for f, v in upd_in.model_dump(exclude_unset=True).items():
        setattr(item, f, v)

    db.commit()
    db.refresh(item)
    return item



@router.get("/{build_id}/compatibility", response_model=CompatibilityReportOut)
def check_build_compatibility(
    build_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Запрашивает проверку совместимости компонентов сборки у отдельного gRPC-сервиса."""
    build = db.get(Build, build_id)
    if not build or build.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Сборка не найдена")

    components_payload = []
    for item in build.items:
        if item.is_active_variant:
            components_payload.append({
                "category_slug": item.component_model.category.slug,
                "model_name": item.component_model.name,
                "quantity": item.quantity,
                "specs": item.component_model.specs
            })

    try:
        report = grpc_client.check_build(build_id=build.id, components_data=components_payload)
        report["build_id"] = build.id
        return report
    except grpc.RpcError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Микросервис совместимости временно недоступен: {e.details() if hasattr(e, 'details') else str(e)}"
        )
