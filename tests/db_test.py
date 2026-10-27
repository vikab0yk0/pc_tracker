from decimal import Decimal
from database import engine, Base, SessionLocal
import crud
from models import UserRole, ShopType, ModelStatus


# 1. Создание всех таблиц
print("\n[Шаг 1] Создание таблиц БД в PostgreSQL...")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # 2. Создание пользователей с разными ролями
    print("\n[Шаг 2] Создание пользователей (User, Premium, Admin)...")
    admin = crud.create_user(db, "admin@pctracker.ru", "admin_hash_pw", role=UserRole.ADMIN)
    user_ivan = crud.create_user(db, "ivan@mail.ru", "user_hash_pw", role=UserRole.USER)
    user_pro = crud.create_user(db, "enthusiast@gmail.com", "pro_hash_pw", role=UserRole.PREMIUM)
    print(f" Создан администратор: {admin}")
    print(f" Создан базовый пользователь: {user_ivan}")
    print(f" Создан PRO-пользователь: {user_pro}")

    # 3. Наполнение категорий
    print("\n[Шаг 3] Заполнение базовых категорий комплектующих...")
    cat_cpu = crud.create_category(db, "Процессоры", "cpu")
    cat_mb = crud.create_category(db, "Материнские платы", "motherboard")
    cat_ram = crud.create_category(db, "Оперативная память", "ram")
    cat_gpu = crud.create_category(db, "Видеокарты", "gpu")
    cat_psu = crud.create_category(db, "Блоки питания", "psu")
    cat_case = crud.create_category(db, "Корпуса", "case")
    print(" Категории добавлены (CPU, Motherboard, RAM, GPU, PSU, Case).")

    # 4. Создание моделей комплектующих
    print("\n[Шаг 4] Создание моделей в каталоге...")
    # Модель от админа (сразу APPROVED)
    cpu_7800x3d = crud.create_component_model(
        db=db,
        category_id=cat_cpu.id,
        name="Ryzen 7 7800X3D",
        brand="AMD",
        specs={"socket": "AM5", "tdp": 120, "cores": 8},
        is_admin=True
    )
    mb_b650 = crud.create_component_model(
        db=db,
        category_id=cat_mb.id,
        name="MSI B650 Gaming Plus",
        brand="MSI",
        specs={"socket": "AM5", "ram_type": "DDR5", "ram_slots": 4},
        is_admin=True
    )
    ram_kingston = crud.create_component_model(
        db=db,
        category_id=cat_ram.id,
        name="Kingston Fury Beast 16GB",
        brand="Kingston",
        specs={"ram_type": "DDR5", "kit_count": 1, "frequency": 6000},
        is_admin=True
    )
    gpu_rtx4070 = crud.create_component_model(
        db=db,
        category_id=cat_gpu.id,
        name="GeForce RTX 4070 Super",
        brand="Palit",
        specs={"length_mm": 269, "tdp": 220, "min_psu": 650},
        is_admin=True
    )
    gpu_rx7800 = crud.create_component_model(
        db=db,
        category_id=cat_gpu.id,
        name="Radeon RX 7800 XT",
        brand="Sapphire",
        specs={"length_mm": 280, "tdp": 263, "min_psu": 700},
        is_admin=True
    )

    # Модель от пользователя (отправляется на проверку)
    custom_case = crud.create_component_model(
        db=db,
        category_id=cat_case.id,
        name="Deepcool CC560 V2",
        brand="Deepcool",
        specs={"max_gpu_len": 370, "max_cooler_height": 163},
        author_id=user_ivan.id,
        is_admin=False
    )
    print(f" Добавлена модель от админа: {cpu_7800x3d}")
    print(f" Пользователь предложил модель: {custom_case} (статус ожидания проверки)")

    # 5. Админ одобряет пользовательскую модель
    print("\n[Шаг 5] Модерация: Администратор проверяет и одобряет модель...")
    crud.approve_model_by_admin(db, custom_case.id)
    print(f" Статус модели после модерации: {custom_case.status.value}")

    # 6. Добавление вариантов покупки (StoreVariant: DNS, Ozon, WB)
    print("\n[Шаг 6] Добавление вариантов покупки товаров с маркетплейсов...")
    v_dns = crud.add_store_variant(
        db=db, user_id=user_ivan.id, model_id=gpu_rtx4070.id,
        custom_name="DNS с гарантией 3 года", shop_type=ShopType.DNS,
        url="https://dns-shop.ru/product/rtx4070", price=Decimal("64999.00"),
        delivery_info="Сегодня в магазине", track=True
    )
    v_ozon = crud.add_store_variant(
        db=db, user_id=user_ivan.id, model_id=gpu_rtx4070.id,
        custom_name="Ozon доставка из РФ", shop_type=ShopType.OZON,
        url="https://ozon.ru/product/rtx4070", price=Decimal("59990.00"),
        delivery_info="до 2 дней", track=True
    )
    v_wb = crud.add_store_variant(
        db=db, user_id=user_ivan.id, model_id=gpu_rx7800.id,
        custom_name="WB Скидка по WB-кошельку", shop_type=ShopType.WILDBERRIES,
        url="https://wildberries.ru/product/rx7800", price=Decimal("54200.00"),
        track=True
    )
    v_cpu = crud.add_store_variant(
        db=db, user_id=user_ivan.id, model_id=cpu_7800x3d.id,
        custom_name="Ozon Global", shop_type=ShopType.OZON,
        url="https://ozon.ru/product/7800x3d", price=Decimal("33500.00"),
        track=True
    )
    v_ram = crud.add_store_variant(
        db=db, user_id=user_ivan.id, model_id=ram_kingston.id,
        custom_name="DNS Одиночная планка 16GB", shop_type=ShopType.DNS,
        url="https://dns-shop.ru/product/ram16", price=Decimal("5400.00"),
        track=True
    )
    print(f" Создан вариант покупки: {v_dns.custom_name} [{v_dns.shop_type.value}] - {v_dns.current_price} руб.")
    print(f" Создан вариант покупки: {v_ozon.custom_name} [{v_ozon.shop_type.value}] - {v_ozon.current_price} руб.")

    # 7. Проверка квоты трекинга для базового пользователя
    print("\n[Шаг 7] Тест контроля квоты отслеживания (максимум 12 вариантов для базового)...")
    try:
        for i in range(15):
            crud.add_store_variant(
                db=db, user_id=user_ivan.id, model_id=cpu_7800x3d.id,
                custom_name=f"Тест лимита {i}", shop_type=ShopType.OTHER,
                url=f"https://shop.ru/{i}", price=Decimal("1000.00"),
                track=True
            )
    except PermissionError as e:
        print(f" Успешно сработало ограничение тарифа: {e}")

    # 8. Сборка ПК: слоты, количество (quantity) и ветвления
    print("\n[Шаг 8] Создание сборки ПК и конфигурирование компонентов...")
    my_build = crud.create_build(
        db=db, user_id=user_ivan.id, 
        name="Игровой сетап 2026", 
        description="Сборка под 2K гейминг"
    )
    
    # Добавляем CPU (1 шт)
    crud.add_component_to_build(
        db=db, build_id=my_build.id, model_id=cpu_7800x3d.id,
        category_id=cat_cpu.id, quantity=1, selected_variant_id=v_cpu.id
    )
    
    # Добавляем RAM (2 планки по 16GB)
    crud.add_component_to_build(
        db=db, build_id=my_build.id, model_id=ram_kingston.id,
        category_id=cat_ram.id, quantity=2, selected_variant_id=v_ram.id
    )

    # Ветвление в слоте GPU: пользователь добавил RTX 4070 (активна) и RX 7800 XT (неактивна)
    item_rtx = crud.add_component_to_build(
        db=db, build_id=my_build.id, model_id=gpu_rtx4070.id,
        category_id=cat_gpu.id, quantity=1, is_active=True, selected_variant_id=v_ozon.id
    )
    item_rx = crud.add_component_to_build(
        db=db, build_id=my_build.id, model_id=gpu_rx7800.id,
        category_id=cat_gpu.id, quantity=1, is_active=False, selected_variant_id=v_wb.id
    )

    total_price = crud.calculate_build_total_price(db, my_build.id)
    print(f" Сборка '{my_build.name}' сконфигурирована.")
    print(f" Расчет стоимости с активной RTX 4070 Super: {total_price:,.2f} руб.")

    # 9. Переключение ветки в сборке
    print("\n[Шаг 9] Переключение альтернативной ветки комплектующего...")
    item_rtx.is_active_variant = False
    item_rx.is_active_variant = True
    db.commit()
    new_total = crud.calculate_build_total_price(db, my_build.id)
    print(f" Переключились на RX 7800 XT. Новая стоимость сборки: {new_total:,.2f} руб.")

    # 10. Клонирование сборки
    print("\n[Шаг 10] Клонирование сборки в один клик...")
    cloned = crud.clone_build(db, my_build.id, new_name="Игровой сетап 2026 (Версия AMD)")
    print(f" Создана копия сборки: ID={cloned.id}, Имя='{cloned.name}' с тем же составом слотов.")

    # 11. Изменение цены и ведение истории (PriceHistory)
    print("\n[Шаг 11] Симуляция изменения цены на маркетплейсе...")
    print(f" Исходная цена Ozon на RTX 4070: {v_ozon.current_price} руб.")
    crud.update_variant_price(db, v_ozon.id, Decimal("56490.00"), in_stock=True)
    print(f" Цена упала до: {v_ozon.current_price} руб. Запись занесена в price_history.")

    # Проверка записей истории
    history_records = v_ozon.price_history
    print(f" Количество записей в истории для этого товара: {len(history_records)}")
    for rec in history_records:
        print(f"  - Фиксация цены: {rec.price} руб. в {rec.recorded_at.strftime('%H:%M:%S')}")

    # 12. Проверка работы воркера с учетом TTL активности
    print("\n[Шаг 12] Фильтрация товаров для фонового опроса цен...")
    tracked_list = crud.get_active_tracked_variants(db)
    print(f" Активных товаров на мониторинге у незаброшенных аккаунтов: {len(tracked_list)} шт.")

finally:
    db.close()
