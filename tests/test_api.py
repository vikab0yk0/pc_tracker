import uuid
from decimal import Decimal
import pytest
import requests


class TestAuthentication:
    """Тестирование аутентификации, генерации JWT и валидации входных данных."""

    def test_user_registration_success(self, session: requests.Session, api_url: str):
        # Arrange
        unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "email": unique_email,
            "password": "StrongPassword123!",
            "role": "USER"
        }

        # Act
        response = session.post(f"{api_url}/auth/register", json=payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == unique_email
        assert data["role"] == "USER"
        assert "id" in data

    def test_duplicate_email_registration_fails(self, session: requests.Session, api_url: str):
        # Arrange
        email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
        payload = {"email": email, "password": "Password123!", "role": "USER"}
        session.post(f"{api_url}/auth/register", json=payload)

        # Act
        response = session.post(f"{api_url}/auth/register", json=payload)

        # Assert
        assert response.status_code == 400
        assert "уже существует" in response.json()["detail"].lower() or "already exists" in response.json()["detail"].lower()

    @pytest.mark.parametrize("invalid_password", ["123", "abc", ""])
    def test_registration_short_password_validation(
        self, session: requests.Session, api_url: str, invalid_password: str
    ):
        # Arrange
        payload = {
            "email": f"invalid_{uuid.uuid4().hex[:6]}@example.com",
            "password": invalid_password,
            "role": "USER"
        }

        # Act
        response = session.post(f"{api_url}/auth/register", json=payload)

        # Assert (Pydantic schema validation error)
        assert response.status_code == 422

    def test_login_invalid_credentials(self, session: requests.Session, api_url: str):
        # Arrange
        payload = {"email": "nonexistent@example.com", "password": "WrongPassword!"}

        # Act
        response = session.post(f"{api_url}/auth/login", json=payload)

        # Assert
        assert response.status_code == 401

    def test_get_current_user_unauthorized(self, session: requests.Session, api_url: str):
        # Act
        response = session.get(f"{api_url}/auth/me")

        # Assert
        assert response.status_code == 403 or response.status_code == 401


class TestAccessControlAndCatalog:
    """Тестирование разграничения прав доступа (RBAC) и модерации каталога."""

    def test_regular_user_cannot_create_category(
        self, session: requests.Session, api_url: str, user_auth: dict
    ):
        # Arrange
        payload = {"name": "Restricted Category", "slug": "restricted"}

        # Act
        response = session.post(
            f"{api_url}/catalog/categories",
            json=payload,
            headers=user_auth["headers"]
        )

        # Assert
        assert response.status_code == 403

    def test_model_proposal_and_admin_approval_workflow(
        self, session: requests.Session, api_url: str, user_auth: dict, admin_auth: dict, test_category: int
    ):
        # Arrange
        model_payload = {
            "category_id": test_category,
            "name": f"Processor-{uuid.uuid4().hex[:6]}",
            "brand": "AMD",
            "specs": {"socket": "AM5", "tdp": 105}
        }

        # Act 1: Пользователь создает модель (ожидается статус PENDING_REVIEW)
        create_resp = session.post(
            f"{api_url}/catalog/models",
            json=model_payload,
            headers=user_auth["headers"]
        )
        assert create_resp.status_code == 201
        created_model = create_resp.json()
        model_id = created_model["id"]
        assert created_model["status"] == "PENDING_REVIEW"

        # Act 2: Администратор подтверждает модель
        approve_payload = {"specs": {"socket": "AM5", "tdp": 105, "verified": True}}
        approve_resp = session.patch(
            f"{api_url}/catalog/models/{model_id}/approve",
            json=approve_payload,
            headers=admin_auth["headers"]
        )

        # Assert
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "APPROVED"
        assert approve_resp.json()["specs"]["verified"] is True


class TestStoreVariantsAndTrackingLimits:
    """Тестирование управления ценовыми предложениями и контроля лимитов тарифа."""

    def test_create_and_update_store_variant(
        self, session: requests.Session, api_url: str, user_auth: dict, admin_auth: dict, test_category: int
    ):
        # Arrange: Создаем подтвержденную модель
        model_resp = session.post(
            f"{api_url}/catalog/models",
            json={"category_id": test_category, "name": "GPU RTX 4080", "brand": "NVIDIA", "specs": {}},
            headers=admin_auth["headers"]
        )
        model_id = model_resp.json()["id"]

        variant_payload = {
            "component_model_id": model_id,
            "custom_name": "DNS Store Retail",
            "shop_type": "DNS",
            "url": "https://dns-shop.ru/product/example",
            "delivery_info": "2 days",
            "comment": "Local store warranty",
            "current_price": 95000.00,
            "is_tracked": True
        }

        # Act: Создание ценового предложения
        create_resp = session.post(
            f"{api_url}/variants/",
            json=variant_payload,
            headers=user_auth["headers"]
        )
        assert create_resp.status_code == 201
        variant_id = create_resp.json()["id"]

        # Act: Обновление цены
        update_payload = {"current_price": 91500.00, "is_in_stock": True}
        update_resp = session.patch(
            f"{api_url}/variants/{variant_id}",
            json=update_payload,
            headers=user_auth["headers"]
        )

        # Assert
        assert update_resp.status_code == 200
        assert Decimal(str(update_resp.json()["current_price"])) == Decimal("91500.00")

    def test_quota_limit_exceeded_for_basic_user(
        self, session: requests.Session, api_url: str, user_auth: dict, admin_auth: dict, test_category: int
    ):
        # Arrange: Модель для привязки
        model_resp = session.post(
            f"{api_url}/catalog/models",
            json={"category_id": test_category, "name": "Storage NVMe", "brand": "Samsung", "specs": {}},
            headers=admin_auth["headers"]
        )
        model_id = model_resp.json()["id"]

        # Act: Создаем предельное количество отслеживаемых предложений (лимит = 12)
        for i in range(12):
            resp = session.post(
                f"{api_url}/variants/",
                json={
                    "component_model_id": model_id,
                    "custom_name": f"Variant {i}",
                    "shop_type": "OTHER",
                    "url": f"https://shop.com/item/{i}",
                    "current_price": 1000.00,
                    "is_tracked": True
                },
                headers=user_auth["headers"]
            )
            assert resp.status_code == 201

        # Попытка добавить 13-й отслеживаемый товар должна быть отклонена
        overflow_resp = session.post(
            f"{api_url}/variants/",
            json={
                "component_model_id": model_id,
                "custom_name": "Overflow Variant",
                "shop_type": "OTHER",
                "url": "https://shop.com/overflow",
                "current_price": 1000.00,
                "is_tracked": True
            },
            headers=user_auth["headers"]
        )

        # Assert
        assert overflow_resp.status_code == 403
        assert "лимит" in overflow_resp.json()["detail"].lower() or "limit" in overflow_resp.json()["detail"].lower()


class TestBuildsAndCalculations:
    """Тестирование сборщика конфигураций, калькуляции цен и клонирования."""

    def test_build_total_price_calculation(
        self, session: requests.Session, api_url: str, user_auth: dict, admin_auth: dict, test_category: int
    ):
        # Arrange: Компонент и предложение с известной ценой
        model_resp = session.post(
            f"{api_url}/catalog/models",
            json={"category_id": test_category, "name": "RAM Module 16GB", "brand": "Kingston", "specs": {}},
            headers=admin_auth["headers"]
        )
        model_id = model_resp.json()["id"]

        price_per_unit = Decimal("4500.00")
        var_resp = session.post(
            f"{api_url}/variants/",
            json={
                "component_model_id": model_id,
                "custom_name": "Ozon Seller",
                "shop_type": "OZON",
                "url": "https://ozon.ru/item/ram",
                "current_price": float(price_per_unit),
                "is_tracked": False
            },
            headers=user_auth["headers"]
        )
        variant_id = var_resp.json()["id"]

        # Создаем сборку
        build_resp = session.post(
            f"{api_url}/builds/",
            json={"name": "Workstation", "description": "Price Test"},
            headers=user_auth["headers"]
        )
        build_id = build_resp.json()["id"]

        # Добавляем 2 модуля ОЗУ
        quantity = 2
        item_payload = {
            "component_model_id": model_id,
            "category_id": test_category,
            "quantity": quantity,
            "is_active_variant": True,
            "selected_variant_id": variant_id
        }
        session.post(f"{api_url}/builds/{build_id}/items", json=item_payload, headers=user_auth["headers"])

        # Act
        detail_resp = session.get(f"{api_url}/builds/{build_id}", headers=user_auth["headers"])

        # Assert
        assert detail_resp.status_code == 200
        expected_total = price_per_unit * quantity
        actual_total = Decimal(str(detail_resp.json()["total_price"]))
        assert actual_total == expected_total

    def test_build_cloning(self, session: requests.Session, api_url: str, user_auth: dict):
        # Arrange
        build_resp = session.post(
            f"{api_url}/builds/",
            json={"name": "Base Configuration", "description": "Original Build"},
            headers=user_auth["headers"]
        )
        original_id = build_resp.json()["id"]

        # Act
        clone_resp = session.post(
            f"{api_url}/builds/{original_id}/clone",
            json={"new_name": "Cloned Configuration"},
            headers=user_auth["headers"]
        )

        # Assert
        assert clone_resp.status_code == 201
        cloned_data = clone_resp.json()
        assert cloned_data["id"] != original_id
        assert cloned_data["name"] == "Cloned Configuration"


class TestSubscriptionLifecycle:
    """Тестирование переключения тарифных планов пользователя."""

    def test_upgrade_and_downgrade_subscription(
        self, session: requests.Session, api_url: str, user_auth: dict
    ):
        # Act 1: Повышение до PREMIUM
        sub_resp = session.post(f"{api_url}/auth/subscribe", headers=user_auth["headers"])
        assert sub_resp.status_code == 200
        assert sub_resp.json()["role"] == "PREMIUM"

        # Act 2: Отмена подписки (возврат к базовому тарифу)
        unsub_resp = session.post(f"{api_url}/auth/unsubscribe", headers=user_auth["headers"])
        assert unsub_resp.status_code == 200
        assert unsub_resp.json()["role"] == "USER"