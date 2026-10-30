# PC Tracker

Конфигуратор сборок ПК с автоматической проверкой аппаратной совместимости и трекером цен на маркетплейсах (DNS, Ozon, Wildberries).

Распределённая система, построенная на базе FastAPI (REST API Gateway), изолированного gRPC-микросервиса валидации конфигураций, СУБД PostgreSQL, брокера сообщений RabbitMQ и WebSocket-уведомлений.

* Подробное описание предметной области, use cases и схемы БД: в [about.md](docs/about.md)
* Стратегия тестирования, тест-дизайн и матрица трассируемости: [testing.md](docs/testing.md)
* Описание реализации модуля извлечения данных с [wildberries](docs/wildberries.md)

---

## Архитектура системы

```mermaid
graph TD
    Client["Клиент: Web / Postman"] -->|HTTP / REST + JWT| API["FastAPI Gateway"]
    API -->|SQLAlchemy 2.0| DB[("PostgreSQL")]
    API -->|gRPC / Protobuf| GRPC["Compatibility Service"]
    
    Worker["Price Scraper Worker"] -.->|Async Check| DB
    Worker -.->|AMQP Events| Broker["RabbitMQ (Планируется)"]
    Broker -.->|Push| WS["WebSocket Service (Планируется)"]
    WS -.->|Real-time Alert| Client
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
- **Комплекс автотестов (Pytest):** 24 автоматизированных теста, покрывающих ORM-ограничения, бизнес-логику REST API и gRPC-контракт с соблюдением изоляции данных.

### В разработке
- Модульные скраперы для сбора цен с Wildberries, DNS и Ozon.
- Фоновый воркер опроса с фильтрацией по неактивности учетной записи (TTL 30 дней).

### Запланировано
- Публикация событий `PriceDropEvent` в брокер RabbitMQ при снижении цен.
- Сервис уведомлений в реальном времени (Notification Service на WebSockets).
- Серверный рендеринг веб-интерфейса (Jinja2).
- Полная контейнеризация мультисервисной системы через Docker Compose.

---

## Стек технологий

- **Язык:** Python 3.12+
- **Веб-сервер:** FastAPI, Uvicorn, Pydantic V2
- **База данных:** PostgreSQL, SQLAlchemy 2.0, Alembic, psycopg3
- **Микросервисное взаимодействие:** gRPC, Protocol Buffers
- **Тестирование:** Pytest, Requests
- **Асинхронные очереди и события (в планах):** RabbitMQ, aio-pika, WebSockets
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
