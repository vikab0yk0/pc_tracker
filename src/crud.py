from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload

from src.models import (
    User, UserRole, Category, ComponentModel, ModelStatus,
    StoreVariant, ShopType, PriceHistory, Build, BuildItem
)


def create_user(db: Session, email: str, hashed_pw: str, role: UserRole = UserRole.USER) -> User:
    user = User(email=email, hashed_password=hashed_pw, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    stmt = select(User).where(User.email == email)
    return db.scalar(stmt)

def touch_user_login(db: Session, user_id: int):
    """Обновление last_login_at (защита от неактивности)"""
    user = db.get(User, user_id)
    if user:
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()


def create_category(db: Session, name: str, slug: str) -> Category:
    category = Category(name=name, slug=slug)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

def create_component_model(
    db: Session, 
    category_id: int, 
    name: str, 
    brand: str, 
    specs: dict, 
    author_id: Optional[int] = None,
    is_admin: bool = False
) -> ComponentModel:
    """Создание модели: если создает админ — сразу APPROVED, если пользователь — PENDING_REVIEW"""
    status = ModelStatus.APPROVED if is_admin else ModelStatus.PENDING_REVIEW
    model = ComponentModel(
        category_id=category_id,
        created_by_user_id=author_id,
        name=name,
        brand=brand,
        specs=specs,
        status=status
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model

def approve_model_by_admin(db: Session, model_id: int, updated_specs: Optional[dict] = None) -> ComponentModel:
    """Админская модерация: утверждение модели в глобальный каталог"""
    model = db.get(ComponentModel, model_id)
    if not model:
        raise ValueError(f"Модель с ID {model_id} не найдена")
    model.status = ModelStatus.APPROVED
    if updated_specs:
        model.specs = updated_specs
    db.commit()
    db.refresh(model)
    return model


def add_store_variant(
    db: Session,
    user_id: int,
    model_id: int,
    custom_name: str,
    shop_type: ShopType,
    url: str,
    price: Decimal,
    delivery_info: Optional[str] = None,
    comment: Optional[str] = None,
    track: bool = False
) -> StoreVariant:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("Пользователь не найден")

    if track and user.role == UserRole.USER:
        tracked_count_stmt = select(func.count(StoreVariant.id)).where(
            StoreVariant.created_by_user_id == user_id,
            StoreVariant.is_tracked == True
        )
        current_tracked = db.scalar(tracked_count_stmt) or 0
        if current_tracked >= 12:
            raise PermissionError("Превышен лимит (12 товаров) для базового тарифа. Перейдите на Premium.")

    variant = StoreVariant(
        component_model_id=model_id,
        created_by_user_id=user_id,
        custom_name=custom_name,
        shop_type=shop_type,
        url=url,
        current_price=price,
        delivery_info=delivery_info,
        comment=comment,
        is_tracked=track,
        last_checked_at=datetime.now(timezone.utc)
    )
    db.add(variant)
    db.flush()

    history = PriceHistory(variant_id=variant.id, price=price)
    db.add(history)
    db.commit()
    db.refresh(variant)
    return variant

def update_variant_price(db: Session, variant_id: int, new_price: Decimal, in_stock: bool = True) -> StoreVariant:
    """Обновление цены воркером с записью в PriceHistory"""
    variant = db.get(StoreVariant, variant_id)
    if not variant:
        raise ValueError("Вариант не найден")

    if variant.current_price != new_price:
        variant.current_price = new_price
        history = PriceHistory(variant_id=variant.id, price=new_price)
        db.add(history)

    variant.is_in_stock = in_stock
    variant.last_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(variant)
    return variant

def get_active_tracked_variants(db: Session) -> List[StoreVariant]:
    """
    Получение вариантов для парсера с учетом:
    1) is_tracked == True
    2) is_in_stock == True
    3) Пользователь заходил в систему не позже 30 дней назад
    """
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    stmt = (
        select(StoreVariant)
        .join(User, StoreVariant.created_by_user_id == User.id)
        .where(
            StoreVariant.is_tracked == True,
            StoreVariant.is_in_stock == True,
            or_(
            User.role == UserRole.PREMIUM,
            User.last_login_at >= thirty_days_ago
        )
        )
    )
    return list(db.scalars(stmt))



def create_build(db: Session, user_id: int, name: str, description: Optional[str] = None) -> Build:
    build = Build(user_id=user_id, name=name, description=description)
    db.add(build)
    db.commit()
    db.refresh(build)
    return build

def add_component_to_build(
    db: Session,
    build_id: int,
    model_id: int,
    category_id: int,
    quantity: int = 1,
    is_active: bool = True,
    selected_variant_id: Optional[int] = None
) -> BuildItem:
    item = BuildItem(
        build_id=build_id,
        component_model_id=model_id,
        category_id=category_id,
        quantity=quantity,
        is_active_variant=is_active,
        selected_variant_id=selected_variant_id
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def clone_build(db: Session, build_id: int, new_name: Optional[str] = None) -> Build:
    """Клонирование существующей сборки вместе со всеми слотами и привязками"""
    stmt = (
        select(Build)
        .options(selectinload(Build.items))
        .where(Build.id == build_id)
    )
    original_build = db.scalar(stmt)
    if not original_build:
        raise ValueError("Сборка не найдена")

    cloned_name = new_name or f"{original_build.name} (Копия)"
    cloned_build = Build(
        user_id=original_build.user_id,
        name=cloned_name,
        description=original_build.description
    )
    db.add(cloned_build)
    db.flush()

    for item in original_build.items:
        cloned_item = BuildItem(
            build_id=cloned_build.id,
            component_model_id=item.component_model_id,
            category_id=item.category_id,
            quantity=item.quantity,
            is_active_variant=item.is_active_variant,
            selected_variant_id=item.selected_variant_id
        )
        db.add(cloned_item)

    db.commit()
    db.refresh(cloned_build)
    return cloned_build

def calculate_build_total_price(db: Session, build_id: int) -> Decimal:
    """Подсчет суммарной стоимости активных компонентов сборки с учетом quantity"""
    stmt = (
        select(BuildItem)
        .options(selectinload(BuildItem.selected_variant))
        .where(
            BuildItem.build_id == build_id,
            BuildItem.is_active_variant == True
        )
    )
    items = db.scalars(stmt).all()
    total = Decimal("0.00")
    for item in items:
        if item.selected_variant and item.selected_variant.is_in_stock:
            total += item.selected_variant.current_price * item.quantity
    return total