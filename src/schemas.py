from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from src.models import UserRole, ModelStatus, ShopType


class UserRegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, description="Пароль не менее 6 символов")
    role: Optional[UserRole] = UserRole.USER

class UserLoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    last_login_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

class RoleUpdateIn(BaseModel):
    role: UserRole



class CategoryCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=100)

class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str

    model_config = {"from_attributes": True}



class ComponentModelCreateIn(BaseModel):
    category_id: int
    name: str = Field(min_length=2, max_length=255)
    brand: str = Field(min_length=1, max_length=100)
    specs: dict = Field(default_factory=dict, description="Характеристики (сокет, TDP, размеры)")

class ModelApproveIn(BaseModel):
    specs: Optional[dict] = None

class ComponentModelOut(BaseModel):
    id: int
    category_id: int
    created_by_user_id: Optional[int]
    name: str
    brand: str
    specs: dict
    status: ModelStatus
    created_at: datetime

    model_config = {"from_attributes": True}



class StoreVariantCreateIn(BaseModel):
    component_model_id: int
    custom_name: str = Field(min_length=2, max_length=255)
    shop_type: ShopType
    url: str
    delivery_info: Optional[str] = None
    comment: Optional[str] = None
    current_price: Decimal = Field(gt=0)
    is_tracked: bool = False

class StoreVariantUpdateIn(BaseModel):
    current_price: Optional[Decimal] = Field(None, gt=0)
    is_in_stock: Optional[bool] = None
    is_active: Optional[bool] = None
    is_tracked: Optional[bool] = None
    delivery_info: Optional[str] = None
    comment: Optional[str] = None

class StoreVariantOut(BaseModel):
    id: int
    component_model_id: int
    created_by_user_id: int
    custom_name: str
    shop_type: ShopType
    url: str
    delivery_info: Optional[str]
    comment: Optional[str]
    current_price: Decimal
    is_in_stock: bool
    is_active: bool
    is_tracked: bool
    last_checked_at: Optional[datetime]

    model_config = {"from_attributes": True}



class BuildCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None

class BuildCloneIn(BaseModel):
    new_name: Optional[str] = None

class BuildItemAddIn(BaseModel):
    component_model_id: int
    category_id: int
    quantity: int = Field(default=1, ge=1)
    is_active_variant: bool = True
    selected_variant_id: Optional[int] = None

class BuildItemUpdateIn(BaseModel):
    quantity: Optional[int] = Field(None, ge=1)
    is_active_variant: Optional[bool] = None
    selected_variant_id: Optional[int] = None

class BuildItemOut(BaseModel):
    id: int
    build_id: int
    component_model_id: int
    category_id: int
    quantity: int
    is_active_variant: bool
    selected_variant_id: Optional[int]

    model_config = {"from_attributes": True}

class BuildDetailOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str]
    total_price: Decimal
    items: List[BuildItemOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

