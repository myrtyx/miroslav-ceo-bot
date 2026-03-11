# Miroslav CEO Bot

Telegram-бот "Мирослав" — виртуальный CEO компании LakeChain. Бот участвует в семейной группе Telegram, общается от лица саркастичного латвийского CEO-стартапера, управляет "сотрудниками" (участниками чата), раздаёт KPI, реагирует на ключевые слова и шлёт утренние heartbeat-сообщения.

## Стек

- **Python 3.12**, python-telegram-bot v21+
- **Anthropic API** (Claude Sonnet) — генерация ответов
- **APScheduler** — периодические задачи (heartbeat, напоминания)
- **Docker / docker-compose** — деплой
- **Hetzner VPS** — продакшн

## Структура проекта

```
miroslav-ceo-bot/
├── src/
│   ├── main.py          # Entry point, сборка компонентов
│   ├── bot.py           # MiroslavBot — основной обработчик сообщений
│   ├── config.py        # Config — загрузка .env + JSON-конфиг
│   ├── claude_client.py # ClaudeClient — обёртка Anthropic API
│   ├── prompts.py       # System prompt Мирослава
│   ├── memory.py        # ProfileManager — профили участников
│   ├── message_buffer.py# MessageBuffer — буфер последних сообщений
│   ├── router.py        # Router — решение отвечать/молчать
│   ├── safety.py        # SafetyManager — rate limiting, cooldown
│   ├── commands.py      # AdminCommands — /assign, /profile, /team и др.
│   ├── scheduler.py     # BotScheduler — heartbeat, запланированные задачи
│   └── stickers.py      # Маппинг стикеров на эмоции
├── data/
│   ├── config.json      # Рантайм конфиг (frequency, keywords и т.д.)
│   ├── profiles/        # JSON-файлы профилей участников
│   └── stats.json       # Статистика бота
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Запуск

```bash
cp miroslav-ceo-bot/.env.example miroslav-ceo-bot/.env
# Заполнить .env реальными токенами
cd miroslav-ceo-bot
docker-compose up -d
docker logs miroslav-ceo -f
```

## Ключевые admin-команды (только в личке)

- `/health` — статус бота
- `/settings` — текущие настройки
- `/assign @user Role, Department` — назначить роль
- `/backstory @user text` — добавить бэкстори
- `/profile @user` — посмотреть профиль
- `/team` — список всех сотрудников
- `/frequency 0.3` — частота случайных ответов (0-1)
- `/cooldown 5` — минимум минут между ответами
- `/heartbeat on/off` — утренние сообщения
- `/pause` / `/resume` — пауза бота
- `/keywords` — управление ключевыми словами
- `/kpi @user +metric` — добавить KPI
- `/fact @user текст` — добавить факт о сотруднике

## Документация

- `miroslav-ceo-bot-spec.md` — полная спецификация бота
- `milestones.md` — план разработки по milestones (M1-M5)
- `miroslav-test-plan.md` — пошаговый тест-план

## Conventions

- Весь код бота в `miroslav-ceo-bot/src/`
- Конфиг через переменные окружения (.env) + JSON файл для рантайм-настроек
- Профили хранятся как отдельные JSON в `data/profiles/`
- Бот общается ТОЛЬКО в одной целевой группе (TARGET_GROUP_ID)
- Админ-команды работают ТОЛЬКО в личке от ADMIN_TELEGRAM_ID
