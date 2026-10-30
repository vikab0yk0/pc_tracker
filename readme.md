# PC Tracker

Конфигуратор сборок ПК с автоматической проверкой аппаратной совместимости и трекером цен на маркетплейсах (DNS, Ozon, Wildberries).

Распределённая система, построенная на базе FastAPI (REST API Gateway), изолированного gRPC-микросервиса валидации конфигураций, СУБД PostgreSQL, брокера сообщений RabbitMQ и WebSocket-уведомлений.

* Подробное описание предметной области, use cases и схемы БД: в [about.md](docs/about.md)
* Стратегия тестирования, тест-дизайн и матрица трассируемости: в [testing.md](docs/testing.md)
* Архитектура и реализация парсера Wildberries: в [wildberries.md](docs/wildberries.md)

---

## Архитектура системы

```mermaid
graph TD
    Client["Клиент: Web / Postman"] -->|HTTP / REST + JWT| API["FastAPI Gateway"]
    API -->|SQLAlchemy 2.0| DB[("PostgreSQL")]
    API -->|gRPC / Protobuf| GRPC["Compatibility Service"]
    
    Worker["Price Scraper Worker"] -->|Playwright + Stealth| WB["Wildberries (WAF / API)"]
    Worker -->|Sync Updates| DB
    Worker -.->|PriceDropEvent| Broker["RabbitMQ (В разработке)"]

    Broker -.->|Consume| WS["WebSocket Service (В разработке)"]
    WS -.->|Real-time Alert| Client

    Broker -.->|Consume| TG["Telegram Bot (Планируется)"]
    TG -.->|Push Alert| UserTG["Пользователь в Telegram"]
```

---

## Текущий статус проекта

### Реализовано
- **Слой данных (PostgreSQL + SQLAlchemy 2.0):** 7 нормализованных сущностей, поддержка `JSONB` для спецификаций деталей, каскадные удаления, версионирование через Alembic.
- **REST API (FastAPI):** аутентификация и авторизация на базе JWT (Bearer tokens), ролевая модель доступа (RBAC: `USER` / `PREMIUM` / `ADMIN`).
- **Конструктор сборок:** CRUD сборок с поддержкой альтернативных вариантов (ветвлений) в одном слоте и мультипликатора количества (`quantity` для планок ОЗУ и накопителей).
- **Контроль квот и тарифов:** жесткое ограничение на 12 активных отслеживаемых позиций для базового тарифа и безлимит для Premium.
- **Двухуровневая модерация:** пользовательские модели поступают в статус `PENDING_REVIEW` и становятся глобальными только после ревью администратором.
- **gRPC-микросервис (`CheckCompatibility`):** контракт на Protocol Buffers, валидация сокетов CPU/MB, типов памяти, габаритов GPU относительно корпуса и расчет суммарного энергопотребления с подбором мощности БП.
- **Модуль сбора цен с Wildberries**: автономный парсинг карточек на headless Chromium (Playwright + Stealth) с обходом WAF-защиты, перехватом чистого JSON из внутреннего API витрины и надежным резервным контуром (DOM Fallback на CSS Modules). Контроль нагрузки через `asyncio.Semaphore`.
- **Комплекс автотестов (Pytest):** 39 автоматизированных теста, покрывающих ORM-ограничения, бизнес-логику REST API, gRPC-контракт, регулярные выражения скрапера, сквозные сетевые проверки и тест надежности DOM-фолбэка.

### В разработке
- **Событийная шина (RabbitMQ + aio-pika):** публикация событий `PriceDropEvent` при обнаружении снижения стоимости позиций воркером.
- **Real-Time уведомления (WebSocket Service):** дуплексный канал доставки мгновенных оповещений об изменении цен прямо в открытую вкладку браузера пользователя.

### Запланировано
- Telegram-бот для персональной отправки уведомлений о снижении цен в мессенджер.
- Модульные скраперы для сбора цен с DNS и Ozon.
- Серверный рендеринг веб-интерфейса (Jinja2).
- Полная контейнеризация мультисервисной системы через Docker Compose.

---

## Стек технологий

- **Язык:** Python 3.12+
- **Веб-сервер:** FastAPI, Uvicorn, Pydantic V2
- **База данных:** PostgreSQL, SQLAlchemy 2.0, Alembic, psycopg3
- **Микросервисное взаимодействие:** gRPC, Protocol Buffers
- **Сбор данных & Автоматизация:** Playwright, Playwright-Stealth
- **Тестирование:** Pytest, Requests, pytest-asyncio, HTTPX
- **Асинхронные очереди и события (в разработке):** RabbitMQ, aio-pika, WebSockets
- **Инфраструктура (в планах):** Docker, Docker Compose

---

## Локальный запуск и тестирование

### 1. Подготовка окружения
Клонируйте репозиторий и настройте виртуальное окружение:
```bash
git clone https://github.com/<ваш-аккаунт>/pc_tracker.git
cd pc_tracker
python -m venv venv
# Активация: venv\Scripts\activate (Windows) или source venv/bin/activate (Linux/macOS)
pip install -r requirements.txt
playwright install chromium
```

Создайте файл `.env` в корне проекта (на основе `.env.example`):
```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/pc_tracker_db
JWT_SECRET=CHANGE_ME
```

### 2. Запуск сервисов

Сервисы функционируют как независимые распределенные компоненты:

**Терминал 1 (gRPC Microservice):**
```bash
python -m src.grpc_services.server
```

**Терминал 2 (FastAPI REST Gateway):**
```bash
uvicorn src.main:app --reload --port 8000
```

Интерактивная документация API (Swagger UI) доступна по адресу:  
`http://127.0.0.1:8000/docs`

### 3. Запуск автоматизированных тестов
```bash
pytest
```
Подробнее в [testing.md](docs/testing.md)
