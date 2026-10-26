import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src import crud
from src.models import (
    User, UserRole, Category, ComponentModel, ModelStatus,
    StoreVariant, ShopType, Build, BuildItem
)


class TestDatabaseConstraints:
    """Тестирование целостности реляционной схемы и ограничений СУБД."""

    def test_user_email_unique_constraint(self, db_session: Session):
        # Arrange
        duplicate_email = f"uniq_{uuid.uuid4().hex[:8]}@example.com"
        user1 = User(email=duplicate_email, hashed_password="hash_password_1", role=UserRole.USER)
        user2 = User(email=duplicate_email, hashed_password="hash_password_2", role=UserRole.USER)

        db_session.add(user1)
        db_session.commit()

        # Act & Assert
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_category_slug_unique_constraint(self, db_session: Session):
        # Arrange
        slug = f"slug-{uuid.uuid4().hex[:6]}"
        cat1 = Category(name=f"Cat 1 {slug}", slug=slug)
        cat2 = Category(name=f"Cat 2 {slug}", slug=slug)

        db_session.add(cat1)
        db_session.commit()

        # Act & Assert
        db_session.add(cat2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestDataLayerBusinessLogic:
    """Тестирование CRUD-операций и бизнес-логики слоя доступа к данным."""

    def test_create_component_model_with_jsonb_specs(self, db_session: Session):
        # Arrange
        cat = crud.create_category(db_session, name=f"GPU-{uuid.uuid4().hex[:6]}", slug=f"gpu-{uuid.uuid4().hex[:6]}")
        specs_data = {
            "length_mm": 304,
            "tdp": 285,
            "power_connectors": "16-pin 12VHPWR"
        }

        # Act
        model = crud.create_component_model(
            db=db_session,
            category_id=cat.id,
            name="GeForce RTX 4070 Ti Super",
            brand="ASUS",
            specs=specs_data,
            is_admin=True
        )

        # Assert
        assert model.id is not None
        assert model.status == ModelStatus.APPROVED
        assert model.specs["length_mm"] == 304
        assert model.specs["tdp"] == 285

    def test_cascade_delete_build_removes_build_items(self, db_session: Session):
        # Arrange: Создаем пользователя, категорию, модель и сборку со слотом
        user = crud.create_user(db_session, email=f"cascade_{uuid.uuid4().hex[:6]}@test.com", hashed_pw="pwd")
        cat = crud.create_category(db_session, name=f"Cat-{uuid.uuid4().hex[:6]}", slug=f"cat-{uuid.uuid4().hex[:6]}")
        model = crud.create_component_model(
            db_session, category_id=cat.id, name="Test Part", brand="Test", specs={}, is_admin=True
        )

        build = crud.create_build(db_session, user_id=user.id, name="Temp Build")
        crud.add_component_to_build(db_session, build_id=build.id, model_id=model.id, category_id=cat.id, quantity=1)

        # Act: Удаляем родительскую сборку
        db_session.delete(build)
        db_session.commit()

        # Assert: Связанные BuildItem должны быть каскадно удалены
        remaining_items = db_session.query(BuildItem).filter(BuildItem.build_id == build.id).all()
        assert len(remaining_items) == 0

    def test_calculate_build_total_price_with_multipliers(self, db_session: Session):
        # Arrange: Настройка сборки с модулями памяти и видеокартой
        user = crud.create_user(db_session, email=f"calc_{uuid.uuid4().hex[:6]}@test.com", hashed_pw="pwd")
        cat = crud.create_category(db_session, name=f"RAM-{uuid.uuid4().hex[:6]}", slug=f"ram-{uuid.uuid4().hex[:6]}")
        model = crud.create_component_model(
            db_session, category_id=cat.id, name="RAM Stick", brand="Corsair", specs={}, is_admin=True
        )

        unit_price = Decimal("3200.00")
        variant = crud.add_store_variant(
            db=db_session,
            user_id=user.id,
            model_id=model.id,
            custom_name="DNS Retail",
            shop_type=ShopType.DNS,
            url="https://dns.ru/ram",
            price=unit_price,
            track=False
        )

        build = crud.create_build(db_session, user_id=user.id, name="Budget Setup")
        quantity = 4  # 4 планки памяти

        crud.add_component_to_build(
            db=db_session,
            build_id=build.id,
            model_id=model.id,
            category_id=cat.id,
            quantity=quantity,
            is_active=True,
            selected_variant_id=variant.id
        )

        # Act
        total_calculated = crud.calculate_build_total_price(db_session, build.id)

        # Assert
        assert total_calculated == unit_price * quantity

    def test_inactive_user_tracking_filter(self, db_session: Session):
        # Arrange: Пользователь, не заходивший 35 дней (неактивный базовый аккаунт)
        inactive_user = crud.create_user(
            db_session, email=f"old_{uuid.uuid4().hex[:6]}@test.com", hashed_pw="pwd", role=UserRole.USER
        )
        inactive_user.last_login_at = datetime.now(timezone.utc) - timedelta(days=35)
        db_session.commit()

        cat = crud.create_category(db_session, name=f"CPU-{uuid.uuid4().hex[:6]}", slug=f"cpu-{uuid.uuid4().hex[:6]}")
        model = crud.create_component_model(
            db_session, category_id=cat.id, name="Old CPU", brand="Intel", specs={}, is_admin=True
        )

        variant = crud.add_store_variant(
            db=db_session,
            user_id=inactive_user.id,
            model_id=model.id,
            custom_name="Tracked Variant",
            shop_type=ShopType.OZON,
            url="https://ozon.ru/item",
            price=Decimal("15000.00"),
            track=True
        )

        # Act: Сбор вариантов для фонового воркера
        active_variants = crud.get_active_tracked_variants(db_session)
        active_variant_ids = [v.id for v in active_variants]

        # Assert: Неактивный базовый пользователь исключается из выборки воркера
        assert variant.id not in active_variant_ids
