# event-shortener

Микросервис сокращения ссылок. Предоставляет REST API для создания, получения, обновления и удаления коротких ссылок
и публичный редирект по короткому идентификатору. В контуре events используется сервисом **event-booking** для
сокращения ссылок на встречи (Jitsi). Заменил WireMock-заглушку `/shortify`.

## Возможности

- Создание короткой ссылки с окном действия `[not_before, expires_at]`
- Идемпотентность по `external_id`: повторный `shorten` возвращает тот же `ident`
- Получение / обновление / удаление ссылки по `external_id` (при обновлении `ident` сохраняется)
- Публичный редирект `GET /{ident}` с учётом окна действия
- Liveness / readiness пробы и метрики Prometheus

## Стек

| Компонент     | Библиотека                              |
|---------------|-----------------------------------------|
| Web-фреймворк | FastAPI                                 |
| DI-контейнер  | Dishka                                  |
| База данных   | PostgreSQL (SQLAlchemy async + asyncpg) |
| Миграции      | Alembic                                 |
| Логирование   | structlog                               |
| Метрики       | prometheus-client                       |
| Конфигурация  | pydantic-settings                       |

Соглашения общие для всех Python-сервисов контура: raw `text()` SQL через `SqlExecutor` (ORM-модели только для
Alembic), Protocol-интерфейсы в `interfaces/`, frozen dataclass DTO, ruff (line length 120), без `elif`.

## Быстрый старт

### Локально

```bash
uv sync
cp .env.example .env          # заполнить POSTGRES_DSN и SHORTENER_API_KEY
alembic upgrade head
uvicorn event_shortener.main:app --host 0.0.0.0 --port 8888 --reload
```

### В составе контура (root docker-compose)

Сервис поднимается вместе со всем стеком из корня монорепозитория:

```bash
docker compose up -d --build
```

На хосте доступен на `http://localhost:8000` (внутри сети контейнеров — `http://event-shortener:8888`).

## Конфигурация

| Переменная           | Описание                                   | Пример                                                          |
|----------------------|--------------------------------------------|-----------------------------------------------------------------|
| `POSTGRES_DSN`       | Строка подключения к PostgreSQL (asyncpg)  | `postgresql+asyncpg://postgres:postgres@localhost:5432/event_shortener` |
| `SHORTENER_API_KEY`  | Статический Bearer-ключ для `/api/v1/*`     | `dev-shortify-api-key-…`                                        |
| `DEBUG`              | Цветной консольный вывод логов             | `false`                                                         |
| `LOG_LEVEL`          | Уровень логирования                        | `INFO`                                                          |

## API

Интерактивная документация: `http://localhost:8000/docs`

Аутентификация: все `/api/v1/*` требуют заголовок `Authorization: Bearer <SHORTENER_API_KEY>` (сравнение
constant-time). Публичный редирект `/{ident}` и пробы `/health` `/ready` `/metrics` — без авторизации.

| Метод    | Путь                                   | Описание                                              |
|----------|----------------------------------------|-------------------------------------------------------|
| `POST`   | `/api/v1/urls/shorten`                 | Создать короткую ссылку (идемпотентно по external_id) |
| `GET`    | `/api/v1/urls/external/{external_id}`  | Получить `ident` по `external_id`                     |
| `PATCH`  | `/api/v1/urls/external/{external_id}`  | Обновить данные ссылки (ident сохраняется)            |
| `DELETE` | `/api/v1/urls/external/{external_id}`  | Удалить ссылку                                        |
| `GET`    | `/{ident}`                             | Публичный редирект на оригинальный URL                |
| `GET`    | `/health`                              | Liveness (без обращения к зависимостям)               |
| `GET`    | `/ready`                               | Readiness (ping БД)                                   |
| `GET`    | `/metrics`                             | Метрики Prometheus                                    |

`expires_at` и `not_before` передаются как epoch-секунды (float). Редирект отдаёт `307` внутри окна,
`410` вне окна (истёк / ещё не наступил) и `404` для неизвестного `ident`.

### Примеры запросов

**Создать короткую ссылку:**

```bash
curl -X POST http://localhost:8000/api/v1/urls/shorten \
  -H 'Authorization: Bearer dev-shortify-api-key-…' \
  -H 'Content-Type: application/json' \
  -d '{
    "long_url": "https://meet.example.com/room/abc?jwt=…",
    "expires_at": 1789000000.0,
    "not_before": 1788000000.0,
    "external_id": "booking-uid-1"
  }'
# -> 201 {"ident": "vUyAOhH"}
```

**Получить по external_id:**

```bash
curl -H 'Authorization: Bearer dev-shortify-api-key-…' \
  http://localhost:8000/api/v1/urls/external/booking-uid-1
# -> 200 {"ident": "vUyAOhH"}
```

**Перейти по короткой ссылке (без авторизации):**

```bash
curl -i http://localhost:8000/vUyAOhH
# -> 307 Location: https://meet.example.com/room/abc?jwt=…
```

## Схема базы данных

```
short_urls
├── id           BIGSERIAL    PK
├── ident        TEXT         UNIQUE NOT NULL   -- base62, 7 символов
├── external_id  TEXT         UNIQUE NOT NULL   -- ключ вызывающего сервиса
├── long_url     TEXT         NOT NULL
├── not_before   TIMESTAMPTZ  NULL
├── expires_at   TIMESTAMPTZ  NULL
├── created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
└── updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
```

`ident` генерируется случайно (base62, 7 символов) с повтором при коллизии уникального индекса. Редирект — один
индексный поиск по `ident`.

## Миграции

```bash
alembic revision --autogenerate -m "add some field"
alembic upgrade head
alembic downgrade -1
alembic current
```

## Разработка

```bash
ruff check --fix .
ruff format .
pre-commit run --all-files
uv run pytest
```
