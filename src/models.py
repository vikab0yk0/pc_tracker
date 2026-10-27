import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional


from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum as SQLEnum,
    ForeignKey, Integer, Numeric, String, Text, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship


from src.database import Base


class UserRole(str, enum.Enum):
    USER = "USER"
    PREMIUM = "PREMIUM"
    ADMIN = "ADMIN"

class ModelStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class ShopType(str, enum.Enum):
    OZON = "OZON"
    WILDBERRIES = "WILDBERRIES"
    DNS = "DNS"
    OTHER = "OTHER"



class User(Base):
    """Пользователи системы с разделением ролей и контролем неактивности"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role_enum"), 
        default=UserRole.USER, 
        nullable=False
    )
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )

    builds: Mapped[List["Build"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    custom_models: Mapped[List["ComponentModel"]] = relationship(back_populates="author")
    store_variants: Mapped[List["StoreVariant"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} email='{self.email}' role={self.role.value}>"


class Category(Base):
    """Справочник типов комплектующих (CPU, GPU, RAM, Мать и т.д.)"""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    models: Mapped[List["ComponentModel"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<Category id={self.id} name='{self.name}'>"


class ComponentModel(Base):
    """Модель детали ПК со спецификациями для gRPC и жизненным циклом модерации"""
    __tablename__ = "component_models"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    
    specs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    
    status: Mapped[ModelStatus] = mapped_column(
        SQLEnum(ModelStatus, name="model_status_enum"), 
        default=ModelStatus.PENDING_REVIEW, 
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )

    category: Mapped["Category"] = relationship(back_populates="models")
    author: Mapped[Optional["User"]] = relationship(back_populates="custom_models")
    store_variants: Mapped[List["StoreVariant"]] = relationship(back_populates="component_model", cascade="all, delete-orphan")
    build_items: Mapped[List["BuildItem"]] = relationship(back_populates="component_model")

    def __repr__(self) -> str:
        return f"<ComponentModel id={self.id} name='{self.name}' status={self.status.value}>"


class StoreVariant(Base):
    """Вариант покупки товара в конкретном магазине (WB, Ozon, DNS) с трекингом цены"""
    __tablename__ = "store_variants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    component_model_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("component_models.id"), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    custom_name: Mapped[str] = mapped_column(String(255), nullable=False)
    shop_type: Mapped[ShopType] = mapped_column(
        SQLEnum(ShopType, name="shop_type_enum"), 
        nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    current_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_in_stock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_tracked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Связи
    component_model: Mapped["ComponentModel"] = relationship(back_populates="store_variants")
    user: Mapped["User"] = relationship(back_populates="store_variants")
    price_history: Mapped[List["PriceHistory"]] = relationship(back_populates="variant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<StoreVariant id={self.id} shop={self.shop_type.value} price={self.current_price} tracked={self.is_tracked}>"


class PriceHistory(Base):
    """Хронология изменения цен конкретного предложения"""
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("store_variants.id", ondelete="CASCADE"), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )

    variant: Mapped["StoreVariant"] = relationship(back_populates="price_history")

    def __repr__(self) -> str:
        return f"<PriceHistory id={self.id} variant_id={self.variant_id} price={self.price}>"


class Build(Base):
    """Сборка или проект апгрейда ПК"""
    __tablename__ = "builds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="builds")
    items: Mapped[List["BuildItem"]] = relationship(back_populates="build", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Build id={self.id} name='{self.name}' user_id={self.user_id}>"


class BuildItem(Base):
    """
    Связующая сущность Многие-ко-многим (Build <-> ComponentModel).
    Реализует: ветвление (альтернативы), учет количества (quantity) и привязку выбранного магазина.
    """
    __tablename__ = "build_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    build_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("builds.id", ondelete="CASCADE"), nullable=False)
    component_model_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("component_models.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=False)

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active_variant: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    selected_variant_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("store_variants.id"), nullable=True)

    # Связи
    build: Mapped["Build"] = relationship(back_populates="items")
    component_model: Mapped["ComponentModel"] = relationship(back_populates="build_items")
    selected_variant: Mapped[Optional["StoreVariant"]] = relationship()

    def __repr__(self) -> str:
        return (f"<BuildItem id={self.id} build_id={self.build_id} "
                f"model_id={self.component_model_id} qty={self.quantity} active={self.is_active_variant}>")