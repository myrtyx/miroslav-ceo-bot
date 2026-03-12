# Miroslav CEO Bot

Telegram-бот "Мирослав" — виртуальный CEO компании LakeChain. Бот участвует в семейной группе Telegram, общается от лица саркастичного латвийского CEO-стартапера, управляет "сотрудниками" (участниками чата), раздаёт KPI, реагирует на ключевые слова и шлёт утренние heartbeat-сообщения.

## Стек

- **Python 3.12**, python-telegram-bot v21+
- **Anthropic API** (Claude Sonnet) — генерация ответов
- **APScheduler** — периодические задачи (heartbeat, напоминания)
- **Docker / docker-compose** — деплой
- **Hetzner VPS** (89.167.24.201) — продакшн

## Структура проекта

```
miroslav-ceo-bot/
├── src/
│   ├── main.py          # Entry point, сборка компонентов
│   ├── bot.py           # MiroslavBot — основной обработчик сообщений
│   ├── config.py        # Config — загрузка .env + JSON-конфиг
│   ├── claude_client.py # ClaudeClient — обёртка Anthropic API
│   ├── prompts.py       # System prompt, tone modes, memory, batch update промпты
│   ├── memory.py        # ProfileManager — профили участников
│   ├── message_buffer.py# MessageBuffer — буфер последних сообщений
│   ├── router.py        # Router — решение отвечать/молчать
│   ├── safety.py        # SafetyManager — rate limiting, cooldown
│   ├── commands.py      # AdminCommands — все admin-команды
│   ├── scheduler.py     # BotScheduler — heartbeat, batch update, chat memory
│   └── stickers.py      # Маппинг стикеров на эмоции
├── data/
│   ├── config.json      # Рантайм конфиг (frequency, keywords, tone_mode и т.д.)
│   ├── profiles/        # JSON-файлы профилей участников
│   ├── chat_memory.md   # Долгосрочная память — саммари разговоров по часам
│   └── stats.json       # Статистика бота
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Деплой

```bash
# Локально
cp miroslav-ceo-bot/.env.example miroslav-ceo-bot/.env
# Заполнить .env реальными токенами
cd miroslav-ceo-bot
docker-compose up -d
docker logs miroslav-ceo -f

# На сервере
ssh root@89.167.24.201
cd /opt/miroslav-ceo-bot/miroslav-ceo-bot && git pull && docker compose up -d --build
```

## Admin-команды (только в личке)

### Информация
- `/help` — список всех команд
- `/health` — статус бота (uptime, ошибки, rate)
- `/settings` — текущие настройки
- `/status` — статистика бота

### Профили
- `/assign @user Роль, Отдел` — назначить роль
- `/backstory @user текст` — добавить предысторию
- `/profile @user` — посмотреть профиль
- `/team` — список всех сотрудников
- `/updateprofiles` — принудительно обновить профили и память
- `/probe` — допросить наименее известного сотрудника
- `/probe @user` — допросить конкретного (создаст профиль если нет)

### Настройки поведения
- `/frequency 0.3` — частота случайных ответов (0-1)
- `/cooldown 5` — минимум минут между ответами
- `/keywords` — список ключевых слов
- `/keywords add слово1, слово2` — добавить ключевые слова
- `/keywords remove слово` — удалить ключевое слово
- `/tone normal` — обычный режим
- `/tone bold` — дерзкий режим (макс сарказм и троллинг)
- `/tone brutal` — дерзкий + мат разрешён

### Управление
- `/pause` / `/resume` — пауза/возобновление бота
- `/broadcast текст` — отправить сообщение в группу
- `/heartbeat on|off|now` — утренние сообщения

## Ключевые фичи

### Долгосрочная память (chat_memory.md)
- Каждые 4 часа scheduler сжимает разговоры в bullet points через Claude
- Память инжектится в system prompt при каждом вызове Claude
- Лимит 6.5K символов, старые записи обрезаются автоматически
- Ручной триггер: `/updateprofiles`

### Три режима тона
- **normal** — обычный разговорный стиль
- **bold** — максимальный сарказм, жёсткий троллинг
- **brutal** — bold + мат разрешён и приветствуется

### Профили сотрудников
- Автоматическое создание при первом сообщении в группе
- Batch update каждые 4 часа — Claude анализирует сообщения и обновляет факты
- Мирослав верит всему что говорят и запоминает как факт
- Факты сказанные одним участником о другом тоже сохраняются

### Probe (допрос)
- `/probe` — выбирает сотрудника с наименьшим количеством фактов
- `/probe @user` — допрашивает конкретного (создаёт профиль если нет)
- Задаёт жизненные вопросы (не собеседование) от лица CEO

## Conventions

- Весь код бота в `miroslav-ceo-bot/src/`
- Конфиг через переменные окружения (.env) + JSON файл для рантайм-настроек
- Профили хранятся как отдельные JSON в `data/profiles/`
- Бот общается ТОЛЬКО в одной целевой группе (TARGET_GROUP_ID)
- Админ-команды работают ТОЛЬКО в личке от ADMIN_TELEGRAM_ID
- Мирослав говорит на простом разговорном русском, минимум корпоративного сленга
