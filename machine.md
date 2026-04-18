Project Path: it-academy-hackathon-solution-example

Source Tree:

```txt
it-academy-hackathon-solution-example
├── README.md
├── data
│   └── Go Nova.json
├── docker-compose.yml
├── index
│   ├── Dockerfile
│   ├── Makefile
│   ├── main.py
│   └── requirements.txt
└── search
    ├── Dockerfile
    ├── Makefile
    ├── main.py
    └── requirements.txt

```

`README.md`:

```md
# Пример решения

Этот репозиторий содержит минимальный шаблон решения, совместимый с нашей проверяющей системой.

В шаблоне есть два сервиса:
- `index` — получает сообщения и строит чанки для индексации;
- `search` — получает вопрос и возвращает `message_ids` найденных сообщений.

Это не эталонное решение по качеству поиска. Его задача — показать корректный контракт и базовый pipeline.

## Состав репозитория

- `index/main.py` — сервис индексации;
- `search/main.py` — сервис поиска;
- `data/Go Nova.json` — анонимизированный пример реального чата;
- `index/Makefile`, `search/Makefile` — локальная сборка и публикация образов.

## Что можно менять

Вы можете менять:
- внутреннюю логику chunking;
- формирование текста для dense;
- формирование sparse векторов;
- retrieval и rerank pipeline;
- любые эвристики и фильтры.

Вы не должны менять:
- контракт `POST /index`;
- контракт `POST /sparse_embedding`;
- контракт `POST /search`.

Если вы меняете request/response этих endpoint'ов, решение перестанет проходить проверку.

## Формат данных

Для разбора входных данных используйте `data/Go Nova.json`.

Особенно важно посмотреть:
- `messages`;
- поля `text`, `parts`, `mentions`;
- metadata чанков в payload Qdrant (можете увидеть её формат в коде сервиса `search`).

Во многих сообщениях значимая часть текста находится не в корневом `text`, а в `parts[*].text`.

Поле `parts` может содержать:
- обычный текст;
- цитату;
- пересланное сообщение.

Если вы только начинаете работу с шаблоном, сначала откройте `data/Go Nova.json`, затем сравните его со схемами в `index/main.py` и `search/main.py`.

При индексации в metadata чанка мы также сохраняем полезные поля:
- `participants` — уникальные `sender_id` сообщений, попавших в чанк;
- `mentions` — уникальные упоминания из сообщений чанка;
- `contains_forward` — есть ли в чанке пересланные сообщения;
- `contains_quote` — есть ли в чанке цитаты других сообщений.

Этими полями можно пользоваться в запросе к `Qdrant`.

## Сервис `index`

`index` должен реализовать:
- `GET /health`
- `POST /index`
- `POST /sparse_embedding`

>ВАЖНО! У `index`-контейнера нет доступа в интернет. Поэтому sparse-модель должна быть доступна локально внутри образа.

### `GET /health`

Endpoint для health check контейнера.

Мы используем его, чтобы проверить, что контейнер успешно запустился и сервис готов принимать запросы.

На выходе endpoint должен вернуть `200 OK`.

### `POST /index`

На вход приходят:
- `chat`;
- `overlap_messages`;
- `new_messages`.

Endpoint должен:
- принять новую порцию сообщений для индексации;
- построить чанки;
- вернуть текст чанков и связанные `message_ids`.

На выходе сервис должен вернуть `results[]`, где каждый элемент содержит:
- `page_content` — текст чанка, который сохраняется в payload;
- `dense_content` — текст для dense embedding;
- `sparse_content` — текст для sparse embedding;
- `message_ids` — id сообщений, связанных с чанком.

Пример запроса:

```bash
curl -X POST "http://localhost:8001/index" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "chat": {
        "id": "chat-1",
        "name": "Go Nova",
        "sn": "chat-1@chat.agent",
        "type": "channel",
        "is_public": true
      },
      "overlap_messages": [
        {
          "id": "1",
          "time": 1710000000,
          "text": "Обсуждаем релиз Go",
          "sender_id": "u1",
          "file_snippets": "",
          "parts": [],
          "mentions": [],
          "is_system": false,
          "is_hidden": false,
          "is_forward": false,
          "is_quote": false
        }
      ],
      "new_messages": [
        {
          "id": "2",
          "time": 1710000060,
          "text": "Релиз Go перенесли на следующую неделю",
          "sender_id": "u2",
          "file_snippets": "",
          "parts": [],
          "mentions": [],
          "is_system": false,
          "is_hidden": false,
          "is_forward": false,
          "is_quote": false
        }
      ]
    }
  }'
```

Пример ответа:

```json
{
  "results": [
    {
      "page_content": "Обсуждаем релиз Go\nРелиз Go перенесли на следующую неделю",
      "dense_content": "Обсуждаем релиз Go\nРелиз Go перенесли на следующую неделю",
      "sparse_content": "Обсуждаем релиз Go\nРелиз Go перенесли на следующую неделю",
      "message_ids": ["1", "2"]
    }
  ]
}
```

### `POST /sparse_embedding`

На вход endpoint получает:
- `texts: string[]`

Endpoint должен:
- принять batch текстов;
- посчитать sparse-вектора;
- вернуть их в формате, совместимом с Qdrant.

На выходе должен вернуть:
- `vectors[].indices`
- `vectors[].values`

Этот endpoint мы используем для вычисления sparse векторов.

Пример запроса:

```bash
curl -X POST "http://localhost:8001/sparse_embedding" \
  -H "Content-Type: application/json" \
  -d '{
    "texts": [
      "Релиз Go перенесли на следующую неделю",
      "VK GPT обсуждали в отдельном чате"
    ]
  }'
```

Пример ответа:

```json
{
  "vectors": [
    {
      "indices": [1452, 9081, 12044],
      "values": [0.6931, 1.0986, 0.6931]
    },
    {
      "indices": [317, 2801, 9102],
      "values": [0.6931, 0.6931, 1.3863]
    }
  ]
}
```


## Сервис `search`

`search` должен реализовать:
- `GET /health`
- `POST /search`

>ВАЖНО! У `search`-контейнера тоже нет доступа в интернет. Поэтому sparse-модель должна быть доступна локально внутри образа.


### `GET /health`

Endpoint для health check контейнера.

Мы используем его, чтобы проверить, что контейнер успешно запустился и сервис готов принимать запросы.

На выходе endpoint должен вернуть `200 OK`.

### `POST /search`

На вход `POST /search` приходит вопрос пользователя с некоторой метадатой (можете изучить её в коде сервиса `search`).

Endpoint должен:
1. получить вектора для поискового запроса;
2. выполнить retrieval по коллекции в Qdrant;
3. при необходимости выполнить rerank;
4. вернуть `message_ids` найденных сообщений.

На выходе `POST /search` должен вернуть `results[]`, где каждый элемент содержит:
- `message_ids`

Пример запроса:

```bash
curl -X POST "http://localhost:8002/search" \
  -H "Content-Type: application/json" \
  -d '{
    "question": {
      "text": "Что писали про релиз Go?"
    }
  }'
```

Пример ответа:

```json
{
  "results": [
    {
      "message_ids": ["2", "1"]
    }
  ]
}
```

## Доступ к нашим сервисам из ваших контейнеров

Во время проверки мы передаем адреса наших сервисов через env. Внутри ваших контейнеров нужно использовать именно эти переменные, а не хардкодить адреса.

### `index`

`index` должен использовать:
- `HOST`
- `PORT`

### `search`

`search` должен использовать:
- `HOST`
- `PORT`
- `API_KEY`
- `EMBEDDINGS_DENSE_URL`
- `RERANKER_URL`
- `QDRANT_URL`
- `QDRANT_COLLECTION_NAME`
- `QDRANT_DENSE_VECTOR_NAME`
- `QDRANT_SPARSE_VECTOR_NAME`

## Открытый API dense и rerank

Для dense embeddings и rerank мы предоставляем внешний HTTP API с Basic Auth. 
Будьте осторожны при использовании этих URL'ов, для каждой команды есть ограничение для использования (rate limit) в символах в минуту.

Базовый URL:
- `http://83.166.249.64:18001`

Доступные endpoint'ы:
- `POST /embeddings` — dense embeddings;
- `GET /embeddings/models` — список dense embedding моделей;
- `POST /score` — rerank;
- `GET /score/models` — список rerank моделей.

Примеры запросов:

Dense embeddings:

```bash
curl -u "$LOGIN:$PASSWORD" \
  -X POST "http://83.166.249.64:18001/embeddings" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-Embedding-0.6B",
    "input": ["Пример поискового запроса"],
    "encoding_format": "base64"
  }'
```

Список dense embedding моделей:

```bash
curl -u "$LOGIN:$PASSWORD" \
  "http://83.166.249.64:18001/embeddings/models"
```

Rerank:

```bash
curl -u "$LOGIN:$PASSWORD" \
  -X POST "http://83.166.249.64:18001/score" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nvidia/llama-nemotron-rerank-1b-v2",
    "text_1": "Что обсуждали про релиз Go?",
    "text_2": [
      "Первый кандидат для реранка",
      "Второй кандидат для реранка"
    ]
  }'
```

Список rerank моделей:

```bash
curl -u "$LOGIN:$PASSWORD" \
  "http://83.166.249.64:18001/score/models"
```

## Примеры вопросов

Примеры вопросов из test датасета, на котором оцениваются ваши решения.

Примеры:
- `В какой чат можно написать вопрос про VK GPT?`
- `Кто сейчас является руководителем команды коробочных продуктов Tarantool?`
- `Какие проблемы были с сервисом oauth-antibot в августе 2020?`

## Оценивание

При оценивании мы считаем две метрики:
- `Recall@K`
- `nDCG@K`

Где `K` = 50. Если ваше решение возвращает больше 50-и `message_id`, то все после первых 50-и отбрасываются и не учитываются.

Для каждой посылки мы усредняем значения этих метрик по всем вопросам датасета и получаем:
- `recall_avg`
- `ndcg_avg`

Итоговый `score` рассчитывается по формуле:

```text
score = recall_avg * 0.8 + ndcg_avg * 0.2
```

## Время выполнения

Время выполнения почти полностью состоит из вычисления векторов и индексации и занимает приблизительно `15 минут`
Вы должны уложиться в `20 минут`

## Локальный запуск

Для локального запуска используйте `docker compose`.

Перед запуском укажите учетные данные для внешнего dense/rerank API:

```bash
export OPEN_API_LOGIN=...
export OPEN_API_PASSWORD=...
```

Если эти переменные не заданы, `docker compose up` завершится с ошибкой.

Запуск:

```bash
docker compose up --build
```

Будут подняты:
- `qdrant` на `localhost:6333`
- `index` на `localhost:8001`
- `search` на `localhost:8002`

`docker compose` также создаст локальную коллекцию `evaluation` в Qdrant.

>ВАЖНО! В текущем примере INDEX не вставляет чанки в Qdrant, поэтому `search` не вернет чанков

Сборка и запуск `index`:

```bash
cd index
make build
make run
```

Сборка и запуск `search`:

```bash
cd search
make build
make run
```

## Сдача решения

### Шаг 1. Получение логина и пароля

В личном кабинете получите логин и пароль для входа в Docker registry

### Шаг 2. Настройка Docker

Registry для хранения образов будет доступен по адресу `83.166.249.64:5000`.
Поскольку он работает без TLS, необходимо добавить его в список insecure registries в настройках Docker.

#### Docker Desktop (macOS / Windows)

1. Откройте Docker Desktop -> **Settings** -> **Docker Engine**.
2. Добавьте в JSON-конфиг поле `insecure-registries`:

```json
{
  "insecure-registries": ["83.166.249.64:5000"]
}
```

3. Нажмите **Apply & Restart**.

#### CLI — Linux

1. Откройте файл с конфигурацией докер демона в режиме редактирования

```bash
sudo nano /etc/docker/daemon.json
```

2. Добавьте в JSON-конфиг поле `insecure-registries`:

```json
{
  "insecure-registries": ["83.166.249.64:5000"]
}
```

3. Перезапустите docker

```bash
sudo systemctl restart docker
```

### Шаг 3. Логин в registry

Необходимо пройти аутентификацию в docker registry, используя логин и пароль, полученные на шаге 1.

```bash
docker login 83.166.249.64:5000 -u <login> -p <password>
```

Ожидаемый вывод: `Login Succeeded`.

### Шаг 4. Сборка образов

Соберите образы своих Index Service и Search Service.
Образы должны иметь тег, который имеет строгий формат:

- Для Index Service - 83.166.249.64:5000/{team_id}/index-service:latest
- Для Search Service - 83.166.249.64:5000/{team_id}/search-service:latest

Образы должны быть собраны под платформу linux/amd64

```bash
docker build --platform linux/amd64 -t 83.166.249.64:5000/{team_id}/index-service:latest {path_to_index_service_dir}
docker build --platform linux/amd64 -t 83.166.249.64:5000/{team_id}/search-service:latest {path_to_search_service_dir}
```

### Шаг 5. Публикация образов в registry

```bash
docker push 83.166.249.64:5000/{team_id}/index-service:latest
docker push 83.166.249.64:5000/{team_id}/search-service:latest
```

### Шаг 6. Запуск процесса оценивания

На страничке оценивания нажать кнопку "Запустить/Оценить"

### Примечание

Для удобства сборки и публикации образов в шаблоне решения уже есть `Makefile`'ы с нужными командами

Примеры:

```bash
cd index
export LOGIN=... PASSWORD=... TEAM_ID=...
make push
```

```bash
cd search
export LOGIN=... PASSWORD=... TEAM_ID=...
make push
```

```

`data/Go Nova.json`:

```json
{
  "chat": {
    "id": "58201@chat.example",
    "name": "Go Nova",
    "sn": "58201@chat.example",
    "type": "group",
    "is_public": true,
    "members_count": 766,
    "members": null
  },
  "messages": [
    {
      "id": "3555555555555555555",
      "thread_sn": null,
      "time": 1634136654,
      "text": "",
      "sender_id": "n.lebedev@corp.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": {
        "type": "addMembers",
        "members": [
          "l.smirnova@corp.example",
          "m.orlova@corp.example",
          "v.baranova@corp.example",
          "n.lebedev@corp.example"
        ]
      },
      "is_system": true,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "3666666666666666666",
      "thread_sn": null,
      "time": 1639744586,
      "text": "Передадите приглашение знакомым PHPшникам? \n\nАктивисты PHP-сообщества проводят опрос, чтобы подвести итоги PHP-года: развитие технологий и людей, важные события, интересный контент и т.д.\n\nОпрос короткий, займет не больше 3 минут, а результаты помогут и нам в том числе лучше представлять индустрию.\n\nhttps://redacted.example/resource/005",
      "sender_id": "v.baranova@corp.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "3777777777777777777",
      "thread_sn": null,
      "time": 1639909047,
      "text": "",
      "sender_id": "v.baranova@corp.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "forward",
          "sn": "48377@chat.example",
          "time": 1639755713,
          "text": "Приглашаем на DC Backend Tech Talk\n\nВсем привет!\nТехтолки Rocket Deli не заканчиваются, и мы готовы рассказать о новом событии. Вечер 21 декабря посвятим обсуждению Go и автоматизации. \n\nПрограмма: \n📍 «Автоматизация в помощь разработчику. Как избежать ручной работы», Кирилл Веденин \nКирилл поделится несколькими способами экономии времени и избегания ошибок путем автоматизации ручного труда. Расскажет о настройке IDE, чтобы warnings были полезными и не замыливали глаз, а также о том, как не парсить вывод глазами, какие API есть у инструментов и как его можно использовать.\n📍«DC rules линтер», Антон Жаров \nАнтон покажет наш новый линтер для проверки Go-правил. Рассмотрит, что уже умеем проверять, какие планы развития проекта. А также поделится тем, какие оптимизации из https://redacted.example/resource/009 (прошлого митапа) получилось реализовать.\n\nДетали встречи: \n\nДата: 21 декабря.\n\nВремя: 18:30 — 19:30.\n\nОнлайн встречаемся в https://redacted.example/resource/004 (Zoom).\n\nОфлайн увидимся в конференц-зале Севере. \n\nДекабрь у всех горит, поэтому ставьте плюсик ниже в форме, чтобы не забыть присоединиться. До встречи!\n\nhttps://redacted.example/resource/006"
        }
      ],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": true,
      "is_quote": false
    },
    {
      "id": "3888888888888888888",
      "thread_sn": null,
      "time": 1643028410,
      "text": "",
      "sender_id": "i.volkova@corp.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "forward",
          "sn": "48377@chat.example",
          "time": 1643024502,
          "text": "​DC Backend Tech Talk | Релиз Go 1.18\n\nВсем привет! Техтолки Rocket Deli по Backend превращаются в регулярную традицию. Начинали в ноябре с одного спикера и теперь расширяем свои горизонты. Встречу посвятим релизу Go 1.18.\nПрограмма:\n📍«Generic’и в Golang — обзор и способы применения»,Роман Кедров\nВ февральском релизе Go добавляются Generic'и. Рома сделает обзор функционала и поделится несколькими способами их применения. Вместе обсудим их плюсы и минусы.\nАнтон Жаров  дополнит Рому и расскажет про Fuzzing тестирование. \n📍«Новым методы sync пакета: Mutex.TryLock, RWMutex.TryLock, and RWMutex.TryRLock», Павел Миронов\nС Павлом рассмотрим преимущества методов: благодаря чему, они упрощают работу, которую до этого делали через канал или атомик.\n📍«Escape analysis и влияние указателей на производительность», Илья Корнеев\nПоговорим с Ильёй про работу с памятью (про стек и кучу) и посмотрим как, используя указатели, можно получить x20 просадку производительности и поймать занимательные баги.\nДетали встречи:\n\nДата: 25 января.Время: 18:30 — 19:30.Онлайн встречаемся в https://redacted.example/resource/003 (Zoom). Релиз будет интересный, ставьте плюсик ниже в форме, чтобы не забыть присоединиться. До встречи и не болейте!\n\nhttps://redacted.example/resource/007"
        }
      ],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": true,
      "is_quote": false
    },
    {
      "id": "3999999999999999999",
      "thread_sn": null,
      "time": 1643372755,
      "text": "",
      "sender_id": "l.smirnova@corp.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "text",
          "text": "Всем привет! Ребята из внутрикома планируют зарелизить страничку в интранете, где будут собраны все технологии, которые есть у нас в компании в разных проектах.\n\nНапример, распознавание по лицу, детектор токсичности в чатах, распознавание речи, перевод в текст и многое другое. \n\nИнформация о технологиях будет реализована в виде карточек с техническим описанием, перечнем проектов, в которых используется эта технология и списком коллег, к которым можно обратиться с вопросами.\n\nКак это лучше реализовать, про что не забыть и насколько страничка будет полезна, никто лучше вас не расскажет. Поэтому делитесь своим мнением и оставляйте фидбэк по ссылке: https://redacted.example/resource/010\n\nЕсли будут доп вопросы — пишите Лене Вороновой."
        }
      ],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "4111111111111111110",
      "thread_sn": null,
      "time": 1643377398,
      "text": "",
      "sender_id": "a.zimina@team.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "text",
          "text": "👋🏼Друзья, привет! \nПланируем провести внешний митап Nova TechTalk для Go-разработчиков в конце февраля или начале марте, как раз после нового релиза Go 1.18. \n\nСейчас в программе уже есть один спикер из команды Rocket Deli, поэтому если у вас есть желание, идеи или предложения по темам, вэлкам, пишите мне)  Буду рада помочь подготовить доклад!"
        }
      ],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "4222222222222222221",
      "thread_sn": null,
      "time": 1645110008,
      "text": "",
      "sender_id": "a.zimina@team.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "text",
          "text": "Хэй, привет всем, кто недавно присоединился к этому чатику! Здесь вы можете  делиться наработками и болью, задавать вопросы и обсуждать все, что душе угодно) \n\nМеня зовут Ника, я devrel и буду помогать сообществу GO-разработчиков расти, общаться, собираться на всякие движухи и прочее)\n\nПоэтому вы всегда можете обратиться ко мне, если: \n- у вас есть (или появятся) идеи для выступлений на внутренних митапах или демо. Это не всегда что-то сложное и масштабное, иногда самые обычные для вас вещи неочевидны для соседней команды)\n- захочется написать статью  \n- выступить на конференции\n\nЗа все активности мы щедро наградим вас ачивками и плюсами к карме!  \nБолее подробно прочитать про форматы мероприятий и ачивки можно тут)"
        }
      ],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "4333333333333333332",
      "thread_sn": null,
      "time": 1648734136,
      "text": "Всем привет, кто-нибудь сталкивался с абортом syscall такого вида?",
      "sender_id": "d.sokolov@team.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "4444444444444444444",
      "thread_sn": null,
      "time": 1648734137,
      "text": "SIGABRT: abort\nPC=0x191919191 m=0 sigcode=0\n\ngoroutine 0 [idle]:\ncrypto/x509/internal/macos.syscall(0x999999999, 0x0, 0xaaaaaaaaa, 0x17, 0x1d1d1d1, 0x0, 0x0)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/sys_darwin.go:95 +0x14 fp=0x2121212121 sp=0x2020202020 pc=0x555555555\ncrypto/x509/internal/macos.ID0046ID0046ID00({0xaaaaaaaaa, 0x17})\n        /Users/dev-sokolov/go/go1.17.3/src/crypto/x509/internal/macos/corefoundation.go:49 +0x84 fp=0x2222222222 sp=0x2121212121 pc=0x777777777\ncrypto/x509/internal/macos.init()\n        /Users/dev-sokolov/go/go1.17.3/src/crypto/x509/internal/macos/security.go:59 +0x80 fp=0x2323232323 sp=0x2222222222 pc=0x888888888\nruntime.doInit(0xbbbbbbbbb)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6498 +0x138 fp=0x2424242424 sp=0x2323232323 pc=0x444444444\nruntime.doInit(0xfffffffff)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2525252525 sp=0x2424242424 pc=0x333333333\nruntime.doInit(0x101010101)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2626262626 sp=0x2525252525 pc=0x333333333\nruntime.doInit(0x111111111)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2727272727 sp=0x2626262626 pc=0x333333333\nruntime.doInit(0xeeeeeeeee)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2828282828 sp=0x2727272727 pc=0x333333333\nruntime.doInit(0xddddddddd)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2929292929 sp=0x2828282828 pc=0x333333333\nruntime.doInit(0xccccccccc)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2a2a2a2a2a sp=0x2929292929 pc=0x333333333\nruntime.main()\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:238 +0x22c fp=0x2b2b2b2b2b sp=0x2a2a2a2a2a pc=0x222222222\nruntime.goexit()\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/asm_arm64.s:1133 +0x4 fp=0x2b2b2b2b2b sp=0x2b2b2b2b2b pc=0x666666666\n\ngoroutine 1 [syscall, locked to thread]:\ncrypto/x509/internal/macos.syscall(0x999999999, 0x0, 0xaaaaaaaaa, 0x17, 0x1d1d1d1, 0x0, 0x0)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/sys_darwin.go:95 +0x14 fp=0x2121212121 sp=0x2020202020 pc=0x555555555\ncrypto/x509/internal/macos.ID0046ID0046ID00({0xaaaaaaaaa, 0x17})\n        /Users/dev-sokolov/go/go1.17.3/src/crypto/x509/internal/macos/corefoundation.go:49 +0x84 fp=0x2222222222 sp=0x2121212121 pc=0x777777777\ncrypto/x509/internal/macos.init()\n        /Users/dev-sokolov/go/go1.17.3/src/crypto/x509/internal/macos/security.go:59 +0x80 fp=0x2323232323 sp=0x2222222222 pc=0x888888888\nruntime.doInit(0xbbbbbbbbb)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6498 +0x138 fp=0x2424242424 sp=0x2323232323 pc=0x444444444\nruntime.doInit(0xfffffffff)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2525252525 sp=0x2424242424 pc=0x333333333\nruntime.doInit(0x101010101)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2626262626 sp=0x2525252525 pc=0x333333333\nruntime.doInit(0x111111111)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2727272727 sp=0x2626262626 pc=0x333333333\nruntime.doInit(0xeeeeeeeee)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2828282828 sp=0x2727272727 pc=0x333333333\nruntime.doInit(0xddddddddd)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2929292929 sp=0x2828282828 pc=0x333333333\nruntime.doInit(0xccccccccc)\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:6475 +0x70 fp=0x2a2a2a2a2a sp=0x2929292929 pc=0x333333333\nruntime.main()\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/proc.go:238 +0x22c fp=0x2b2b2b2b2b sp=0x2a2a2a2a2a pc=0x222222222\nruntime.goexit()\n        /Users/dev-sokolov/go/go1.17.3/src/runtime/asm_arm64.s:1133 +0x4 fp=0x2b2b2b2b2b sp=0x2b2b2b2b2b pc=0x666666666\n\nr0      0x0\nr1      0x0\nr2      0x0\nr3      0x0\nr4      0x0\nr5      0x0\nr6      0x1\nr7      0x131313131\nr8      0x1f1f1f1f1f1f1f1f\nr9      0x1e1e1e1e1e1e1e1e\nr10     0x2c2c2c2c2c2c2c2c\nr11     0xa\nr12     0x0\nr13     0x38\nr14     0x1c1c1c1\nr15     0x0\nr16     0x148\nr17     0x1b1b1b1b1\nr18     0x0\nr19     0x6\nr20     0x141414141\nr21     0x103\nr22     0x171717171\nr23     0x121212121\nr24     0x0\nr25     0x0\nr26     0x181818181\nr27     0x141414141\nr28     0x760\nr29     0x161616161\nlr      0x1a1a1a1a1\nsp      0x151515151\npc      0x191919191\nfault   0x191919191",
      "sender_id": "d.sokolov@team.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "4555555555555555555",
      "thread_sn": null,
      "time": 1648734205,
      "text": "Железка MacBook Air (M1, 2020)",
      "sender_id": "d.sokolov@team.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "4666666666666666666",
      "thread_sn": null,
      "time": 1648740500,
      "text": "видимо тебе под strace'ом смотреть, что там за сисколл был и что в него передали",
      "sender_id": "p.korovin@corp.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "4777777777777777777",
      "thread_sn": null,
      "time": 1648807412,
      "text": "не оно? https://redacted.example/resource/002",
      "sender_id": "g.belov@team.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "4888888888888888888",
      "thread_sn": null,
      "time": 1648810304,
      "text": "Не похоже",
      "sender_id": "d.sokolov@team.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "4999999999999999999",
      "thread_sn": null,
      "time": 1649143033,
      "text": "",
      "sender_id": "a.zimina@team.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "text",
          "text": "Всем привет ✌️\n14 апреля мы приглашаем всех, кому интересна Go-разработка, на митап, который пройдёт в гибридном формате (офлайн у нас в Панораме + онлайн-трансляция) в 19:00 (Мск).  \n\nДа-да, вы не ослышались, офлайн-митапы возвращаются!🎉 \nТак что приходите сами и отправляйте своим друзьям ссылку на регистрацию. \n\nРебята из NovaNet, Юлы и Nova Cloud поделятся своими наработками и бесценным опытом.   \n\n⭐В программе:\n\n1. Тимур Беляев, старший разработчик команды KPHP, NovaNet\nQuasigo: интерпретатор Go, используемый в ruleguard\nЗачем писать интерпретатор для Go, как он используется и соотносится с уже существующими решениями.\n\n2. Егор Власов, ведущий программист, Nova Cloud\nВоркшоп: как написать свой Terraform-провайдер и зачем?\nКак написать и зарелизить в официальный реджистри свой терраформ-провайдер на примере провайдера Nova Cloud.\n\n3. Максим Дорофеев, старший Go-разработчик, Marketo (проект Nova)\nТипизация Kafka-топиков в среде Golang + JSON/Protobuf\nСценарии использования Confluent Schema Registry в мире Golang, PHP и Protobuf для типизации сообщений, передающихся через Kafka.\n\n ! Чтобы добавить напоминание и ссылку на стрим к себе в календарь, плюсуйте в форме под постом. \n\nЕсли будет много желающих и места в переговорной А1 на всех не хватит, мы организуем для сотрудников уютную трансляцию в кинозале💙"
        }
      ],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "5111111111111111110",
      "thread_sn": null,
      "time": 1649327231,
      "text": "",
      "sender_id": "a.zimina@team.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "text",
          "text": "Привет-привет!\nАнонсировали всеобщий внутренний хакатон Inner Spark, так что если вы давно мечтали поделать что-то прикольное, для души и c Nova, объединяйтесь со знакомыми разработчиками и регистрируйтесь)"
        }
      ],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "5222222222222222221",
      "thread_sn": null,
      "time": 1649414881,
      "text": "Всем привет! 👋 Написано, что чатик и для вопросов тоже, нужен совет :D решили причесать структуру гошного проекта под какой-нибудь +- общепринятый вид, но возникла проблема c тем, в какую папку положить файлы создания/схем баз данных, потому что вроде как оно и не build/, и не scripts/, а ресерч по прочим репам опенсорса ничего ясного не дал (  где такие скрипты лучше разместить или где бы вы их ожидали увидеть в репе?",
      "sender_id": "n.ermakova@team.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "5333333333333333332",
      "thread_sn": null,
      "time": 1649416005,
      "text": "У нас в корне в migrations валяются запросы на альтер таблиц)",
      "sender_id": "r.efimov@corp.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "5444444444444444443",
      "thread_sn": null,
      "time": 1649418855,
      "text": "",
      "sender_id": "d.sokolov@team.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "quote",
          "sn": "n.ermakova@team.example",
          "time": 1649414882,
          "text": "Всем привет! 👋 Написано, что чатик и для вопросов тоже, нужен совет :D решили причесать структуру гошного проекта под какой-нибудь +- общепринятый вид, но возникла проблема c тем, в какую папку положить файлы создания/схем баз данных, потому что вроде как оно и не build/, и не scripts/, а ресерч по прочим репам опенсорса ничего ясного не дал (  где такие скрипты лучше разместить или где бы вы их ожидали увидеть в репе?"
        },
        {
          "mediaType": "text",
          "text": "как правило в корне в migrations лежат фалики миграций, и самое лучшее что я видел это формирование файлов миграций через утилиту goose она формирует название формата \"timstamp_migration_name.sql\", а процесс миграций привязан был к make migrate → он запускал небольшой гусевый скрипт в cmd/migrations/main.go и он мигрировал это все в базку"
        }
      ],
      "mentions": [
        "n.ermakova@team.example"
      ],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": true
    },
    {
      "id": "5555555555555555555",
      "thread_sn": null,
      "time": 1649421154,
      "text": "",
      "sender_id": "d.sokolov@team.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "text",
          "text": "Всем ещё раз привет. Кто-нибудь пробовал делать билд го проекта с зависимостью от CGO, где Сишка только под Линукс, при билде пробовал разные переменные перед билдом, но нужно правильно указать CC, никто не сталкивался? Понимаю что выглядит как чёрная магия, но все же"
        }
      ],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "5666666666666666666",
      "thread_sn": null,
      "time": 1649668929,
      "text": "",
      "sender_id": "k.zorin@corp.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "quote",
          "sn": "d.sokolov@team.example",
          "time": 1649421153,
          "text": "Всем ещё раз привет. Кто-нибудь пробовал делать билд го проекта с зависимостью от CGO, где Сишка только под Линукс, при билде пробовал разные переменные перед билдом, но нужно правильно указать CC, никто не сталкивался? Понимаю что выглядит как чёрная магия, но все же"
        },
        {
          "mediaType": "text",
          "text": "Привет. Проект собирается под линуксом?"
        }
      ],
      "mentions": [
        "d.sokolov@team.example"
      ],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": true
    },
    {
      "id": "5777777777777777777",
      "thread_sn": null,
      "time": 1649669799,
      "text": "",
      "sender_id": "d.sokolov@team.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "text",
          "text": "Была попытка собрать это все на маке. Но все же пришлось заказывать машину на линухе"
        },
        {
          "mediaType": "quote",
          "sn": "k.zorin@corp.example",
          "time": 1649668929,
          "text": "Привет. Проект собирается под линуксом?"
        }
      ],
      "mentions": [
        "k.zorin@corp.example"
      ],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": true
    },
    {
      "id": "5888888888888888888",
      "thread_sn": null,
      "time": 1649672098,
      "text": "",
      "sender_id": "k.zorin@corp.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "quote",
          "sn": "d.sokolov@team.example",
          "time": 1649669799,
          "text": "Была попытка собрать это все на маке. Но все же пришлось заказывать машину на линухе"
        },
        {
          "mediaType": "text",
          "text": "CGO позволяет прям в коде указать, какие либы где искать, и соответственно, нет необходимости указывать переменные перед билдом."
        }
      ],
      "mentions": [
        "k.zorin@corp.example",
        "d.sokolov@team.example"
      ],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": true
    },
    {
      "id": "5999999999999999999",
      "thread_sn": null,
      "time": 1649672301,
      "text": "",
      "sender_id": "d.sokolov@team.example",
      "file_snippets": "[{\"antivirus_check\": \"unchecked\", \"content_id\": \"ID0045ID0045ID0045ID0045ID0045ID\", \"date_create\": \"2022-04-11 13:18:21\", \"id\": \"ID0001ID0001ID0001ID0001ID0001ID0\", \"is_previewable\": true, \"mime\": \"image/webp\", \"name\": \"IMG_8471.webp\", \"order\": 0, \"original_url\": \"https://redacted.example/resource/001\", \"size\": \"30240\", \"status\": \"3\", \"uid\": \"d.sokolov@team.example\"}]",
      "parts": [
        {
          "mediaType": "text",
          "text": "https://redacted.example/resource/001"
        }
      ],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "6111111111111111110",
      "thread_sn": null,
      "time": 1649672384,
      "text": "Какой командой сборка происходит?",
      "sender_id": "k.zorin@corp.example",
      "file_snippets": "",
      "parts": [],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": false
    },
    {
      "id": "6222222222222222221",
      "thread_sn": null,
      "time": 1649952853,
      "text": "",
      "sender_id": "a.zimina@team.example",
      "file_snippets": "",
      "parts": [
        {
          "mediaType": "text",
          "text": "Мы уже начали Nova TechTalk, присоединяйтесь к трансляции https://redacted.example/resource/008"
        },
        {
          "mediaType": "quote",
          "sn": "a.zimina@team.example",
          "time": 1649143033,
          "text": "Всем привет ✌️\n14 апреля мы приглашаем всех, кому интересна Go-разработка, на митап, который пройдёт в гибридном формате (офлайн у нас в Панораме + онлайн-трансляция) в 19:00 (Мск).  \n\nДа-да, вы не ослышались, офлайн-митапы возвращаются!🎉 \nТак что приходите сами и отправляйте своим друзьям ссылку на регистрацию. \n\nРебята из NovaNet, Юлы и Nova Cloud поделятся своими наработками и бесценным опытом.   \n\n⭐В программе:\n\n1. Тимур Беляев, старший разработчик команды KPHP, NovaNet\nQuasigo: интерпретатор Go, используемый в ruleguard\nЗачем писать интерпретатор для Go, как он используется и соотносится с уже существующими решениями.\n\n2. Егор Власов, ведущий программист, Nova Cloud\nВоркшоп: как написать свой Terraform-провайдер и зачем?\nКак написать и зарелизить в официальный реджистри свой терраформ-провайдер на примере провайдера Nova Cloud.\n\n3. Максим Дорофеев, старший Go-разработчик, Marketo (проект Nova)\nТипизация Kafka-топиков в среде Golang + JSON/Protobuf\nСценарии использования Confluent Schema Registry в мире Golang, PHP и Protobuf для типизации сообщений, передающихся через Kafka.\n\n ! Чтобы добавить напоминание и ссылку на стрим к себе в календарь, плюсуйте в форме под постом. \n\nЕсли будет много желающих и места в переговорной А1 на всех не хватит, мы организуем для сотрудников уютную трансляцию в кинозале💙"
        }
      ],
      "mentions": [],
      "member_event": null,
      "is_system": false,
      "is_hidden": false,
      "is_forward": false,
      "is_quote": true
    }
  ]
}
```

`docker-compose.yml`:

```yml
services:
  qdrant:
    image: qdrant/qdrant:v1.14.1
    ports:
      - "6333:6333"

  qdrant-init:
    image: curlimages/curl:8.12.1
    depends_on:
      - qdrant
    command:
      - sh
      - -c
      - |
        until curl -sf http://qdrant:6333/collections; do
          sleep 1
        done
        if curl -sf http://qdrant:6333/collections/evaluation >/dev/null; then
          exit 0
        fi
        curl -sf -X PUT http://qdrant:6333/collections/evaluation \
          -H 'Content-Type: application/json' \
          -d '{
            "vectors": {
              "dense": {
                "size": 1024,
                "distance": "Cosine"
              }
            },
            "sparse_vectors": {
              "sparse": {
                "modifier": "idf"
              }
            }
          }'
    restart: "no"

  index:
    build:
      context: ./index
    depends_on:
      - qdrant
    ports:
      - "8001:8000"

  search:
    build:
      context: ./search
    depends_on:
      qdrant-init:
        condition: service_completed_successfully
    environment:
      QDRANT_URL: http://qdrant:6333
      QDRANT_COLLECTION_NAME: evaluation
      QDRANT_DENSE_VECTOR_NAME: dense
      QDRANT_SPARSE_VECTOR_NAME: sparse
      EMBEDDINGS_DENSE_URL: ${EMBEDDINGS_DENSE_URL:-http://83.166.249.64:18001/embeddings}
      RERANKER_URL: ${RERANKER_URL:-http://83.166.249.64:18001/score}
      OPEN_API_LOGIN: ${OPEN_API_LOGIN:?set OPEN_API_LOGIN before docker compose up}
      OPEN_API_PASSWORD: ${OPEN_API_PASSWORD:?set OPEN_API_PASSWORD before docker compose up}
    ports:
      - "8002:8000"

```

`index/Dockerfile`:

```
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENV HOST=0.0.0.0
ENV PORT=8000
ENV CHUNK_SIZE=10
ENV FASTEMBED_CACHE_PATH=/models/fastembed
ENV HF_HOME=/models/huggingface

RUN mkdir -p /models/fastembed /models/huggingface
RUN python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding(model_name='Qdrant/bm25')"

EXPOSE 8000

CMD ["python", "main.py"]

```

`index/Makefile`:

```
LOGIN ?= 
PASSWORD ?= 
TEAM_ID ?= 
DOCKER_REGISTRY_URL ?= 83.166.249.64:5000
PORT ?= 8000

IMAGE = $(DOCKER_REGISTRY_URL)/$(TEAM_ID)/index-service:latest

.PHONY: login build run push

login:
	@: $(if $(LOGIN),,$(error LOGIN is required for make login))
	@: $(if $(PASSWORD),,$(error PASSWORD is required for make login))
	docker login $(DOCKER_REGISTRY_URL) -u $(LOGIN)  -p $(PASSWORD)

build:
	@: $(if $(TEAM_ID),,$(error TEAM_ID is required for make build))
	docker build -t $(IMAGE) ./

run: build
	docker run --rm -p $(PORT):8000 $(IMAGE)

push: login build
	docker push $(IMAGE)

```

`index/main.py`:

```py
import logging
import os
from functools import lru_cache
from typing import Any
import asyncio
import hashlib

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Ваш сервис должен считывать эти переменные из окружения (env), так как проверяющая система управляет ими
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8004"))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("index-service")


# Модель данных, которую мы предоставляем и рассчитываем получать от вас
class Chat(BaseModel):
    id: str
    name: str
    sn: str
    type: str  # group, channel, private
    is_public: bool | None = None
    members_count: int | None = None
    members: list[dict[str, Any]] | None = None


class Message(BaseModel):
    id: str
    thread_sn: str | None = None
    time: int
    text: str
    sender_id: str
    file_snippets: str
    parts: list[dict[str, Any]] | None = None
    mentions: list[str] | None = None
    member_event: dict[str, Any] | None = None
    is_system: bool
    is_hidden: bool
    is_forward: bool
    is_quote: bool


class ChatData(BaseModel):
    chat: Chat
    overlap_messages: list[Message]
    new_messages: list[Message]


class IndexAPIRequest(BaseModel):
    data: ChatData


# dense_content будет передан в dense embedding модель для построения семантического вектора.
# sparse_content будет передан в sparse модель для построения разреженного индекса "по словам".
# Можно оставить dense_content и sparse_content равными page_content,
# а можно формировать для них разные версии текста.
class IndexAPIItem(BaseModel):
    page_content: str
    dense_content: str
    sparse_content: str
    message_ids: list[str]


class IndexAPIResponse(BaseModel):
    results: list[IndexAPIItem]


class SparseEmbeddingRequest(BaseModel):
    texts: list[str]


class SparseVector(BaseModel):
    indices: list[int]
    values: list[float]


class SparseEmbeddingResponse(BaseModel):
    vectors: list[SparseVector]


app = FastAPI(title="Index Service", version="0.1.0")

# Ваша внутренняя логика построения чанков. Можете делать всё, что посчитаете нужным.
# Текущий код – минимальный пример

CHUNK_SIZE = 512
OVERLAP_SIZE = 256
SPARSE_MODEL_NAME = "Qdrant/bm25"
FASTEMBED_CACHE_PATH = "/models/fastembed"

# Важная переманная, которая позволяет вычислять sparse вектор в несколько ядер. Не рекомендуется изменять.
UVICORN_WORKERS=8

def render_message(message: Message) -> str:
    text = ""

    if message.text:
        text += message.text

    if message.parts:
        parts_text: list[str] = []
        for part in message.parts:
            # parts различаются по своему типу, см. README.md
            part_text = part.get("text")
            if isinstance(part_text, str) and part_text:
                parts_text.append(part_text)
        if parts_text:
            text += "\n".join(parts_text)

    return text


def build_chunks(
    overlap_messages: list[Message],
    new_messages: list[Message],
) -> list[IndexAPIItem]:
    result: list[IndexAPIItem] = []

    def build_text_and_ranges(messages: list[Message]) -> tuple[str, list[tuple[int, int, str]]]:
        text_parts: list[str] = []
        message_ranges: list[tuple[int, int, str]] = []
        position = 0

        for index, message in enumerate(messages):
            text = render_message(message)
            if not text:
                continue

            if index > 0 and text_parts:
                text_parts.append("\n")
                position += 1

            start = position
            text_parts.append(text)
            position += len(text)
            message_ranges.append((start, position, message.id))

        return "".join(text_parts), message_ranges

    def slice_tail(
        text: str,
        tail_size: int,
    ) -> str:
        if tail_size <= 0:
            return ""

        tail_start = max(0, len(text) - tail_size)
        return text[tail_start:]

    overlap_text, overlap_message_ranges = build_text_and_ranges(overlap_messages)
    previous_chunk_text = slice_tail(overlap_text, OVERLAP_SIZE)

    new_text, new_message_ranges = build_text_and_ranges(new_messages)

    for start in range(0, len(new_text), CHUNK_SIZE):
        chunk_body = new_text[start : start + CHUNK_SIZE]
        if not chunk_body:
            continue

        chunk_body_ranges = [
            (
                max(message_start, start) - start,
                min(message_end, start + len(chunk_body)) - start,
                message_id,
            )
            for message_start, message_end, message_id in new_message_ranges
            if message_end > start and message_start < start + len(chunk_body)
        ]
        chunk_overlap = previous_chunk_text
        chunk_text = chunk_overlap
        if chunk_text and chunk_body:
            chunk_text += "\n"
        chunk_text += chunk_body

        result.append(
            IndexAPIItem(
                page_content=chunk_text,
                dense_content=chunk_text,
                sparse_content=chunk_text,
                message_ids=[message_id for _, _, message_id in chunk_body_ranges],
            )
        )
        previous_chunk_text = slice_tail(chunk_text, OVERLAP_SIZE)

    return result

# Ваш сервис должен имплементировать оба этих метода
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/index", response_model=IndexAPIResponse)
async def index(payload: IndexAPIRequest) -> IndexAPIResponse:
    return IndexAPIResponse(
        results=build_chunks(
            payload.data.overlap_messages,
            payload.data.new_messages,
        )
    )


@lru_cache(maxsize=1)
def get_sparse_model():
    from fastembed import SparseTextEmbedding

    # можете делать любой вектор, который будет совместим с вашим поиском в Qdrant
    # помните об ограничении времени выполнения вашей работы в тестирующей системе
    logger.info(
        "Loading sparse model %s from cache %s",
        SPARSE_MODEL_NAME,
        FASTEMBED_CACHE_PATH,
    )
    return SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)


def embed_sparse_texts(texts: list[str]) -> list[SparseVector]:
    model = get_sparse_model()
    vectors: list[dict[str, list[int] | list[float]]] = []

    for item in model.embed(texts):
        vectors.append(
            {
                "indices": item.indices.tolist(),
                "values": item.values.tolist(),
            }
        )

    return vectors


@app.post("/sparse_embedding")
async def sparse_embedding(payload: SparseEmbeddingRequest) -> dict[str, Any]:
    # Проверяющая система вызывает этот endpoint при создании коллекции
    vectors = await asyncio.to_thread(embed_sparse_texts, payload.texts)
    return {"vectors": vectors}

# красивая обработка ошибок
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(exc)

    if isinstance(exc, RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    return JSONResponse(status_code=500, content={"detail": str(exc)})


def main() -> None:
    import uvicorn

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
        workers=UVICORN_WORKERS,
    )


if __name__ == "__main__":
    main()

```

`index/requirements.txt`:

```txt
fastapi==0.135.1
uvicorn[standard]==0.42.0
pydantic==2.12.5
fastembed==0.7.4

```

`search/Dockerfile`:

```
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENV HOST=0.0.0.0
ENV PORT=8000
ENV QDRANT_COLLECTION_NAME=evaluation
ENV QDRANT_DENSE_VECTOR_NAME=dense
ENV QDRANT_SPARSE_VECTOR_NAME=sparse
ENV EMBEDDINGS_DENSE_MODEL=Qwen/Qwen3-Embedding-0.6B
ENV FASTEMBED_CACHE_PATH=/models/fastembed
ENV HF_HOME=/models/huggingface

RUN mkdir -p /models/fastembed /models/huggingface
RUN python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding(model_name='Qdrant/bm25')"

EXPOSE 8000

CMD ["python", "main.py"]

```

`search/Makefile`:

```
LOGIN ?= 
PASSWORD ?= 
TEAM_ID ?= 
DOCKER_REGISTRY_URL ?= 83.166.249.64:5000
PORT ?= 8000
QDRANT_URL ?= 
QDRANT_COLLECTION_NAME ?= evaluation
EMBEDDINGS_DENSE_URL ?= 
EMBEDDINGS_DENSE_MODEL ?= Qwen/Qwen3-Embedding-0.6B
API_KEY ?= dev-api-key
RERANKER_URL ?= 
QDRANT_DENSE_VECTOR_NAME ?= dense
QDRANT_SPARSE_VECTOR_NAME ?= sparse

REQUIRED_RUN_VARS := QDRANT_URL EMBEDDINGS_DENSE_URL API_KEY RERANKER_URL

IMAGE = $(DOCKER_REGISTRY_URL)/$(TEAM_ID)/search-service:latest

.PHONY: login build run push check-run-env

login:
	@: $(if $(LOGIN),,$(error LOGIN is required for make login))
	@: $(if $(PASSWORD),,$(error PASSWORD is required for make login))
	docker login $(DOCKER_REGISTRY_URL) -u $(LOGIN) -p $(PASSWORD)

build:
	@: $(if $(TEAM_ID),,$(error TEAM_ID is required for make build))
	docker build -t $(IMAGE) ./

run: build
	@: $(foreach var,$(REQUIRED_RUN_VARS),$(if $($(var)),,$(error $(var) is required for make run)))
	docker run --rm -p $(PORT):8000 \
		--add-host=host.docker.internal:host-gateway \
		-e QDRANT_URL=$(QDRANT_URL) \
		-e QDRANT_COLLECTION_NAME=$(QDRANT_COLLECTION_NAME) \
		-e EMBEDDINGS_DENSE_URL=$(EMBEDDINGS_DENSE_URL) \
		-e EMBEDDINGS_DENSE_MODEL=$(EMBEDDINGS_DENSE_MODEL) \
		-e API_KEY=$(API_KEY) \
		-e RERANKER_URL=$(RERANKER_URL) \
		-e QDRANT_DENSE_VECTOR_NAME=$(QDRANT_DENSE_VECTOR_NAME) \
		-e QDRANT_SPARSE_VECTOR_NAME=$(QDRANT_SPARSE_VECTOR_NAME) \
		$(IMAGE)

push: login build
	docker push $(IMAGE)

```

`search/main.py`:

```py
import logging
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

import httpx
from fastembed import SparseTextEmbedding
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient, models

EMBEDDINGS_DENSE_MODEL = "Qwen/Qwen3-Embedding-0.6B"

# Ваш сервис должен считывать эти переменные из окружения (env), так как проверяющая система управляет ими
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8003"))

API_KEY = os.getenv("API_KEY")
EMBEDDINGS_DENSE_URL = os.getenv("EMBEDDINGS_DENSE_URL")
QDRANT_DENSE_VECTOR_NAME = os.getenv("QDRANT_DENSE_VECTOR_NAME", "dense")
QDRANT_SPARSE_VECTOR_NAME = os.getenv("QDRANT_SPARSE_VECTOR_NAME", "sparse")
SPARSE_MODEL_NAME = "Qdrant/bm25"
RERANKER_MODEL = "nvidia/llama-nemotron-rerank-1b-v2"
RERANKER_URL = os.getenv("RERANKER_URL")
OPEN_API_LOGIN = os.getenv("OPEN_API_LOGIN")
OPEN_API_PASSWORD = os.getenv("OPEN_API_PASSWORD")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "evaluation")
REQUIRED_ENV_VARS = [
    "EMBEDDINGS_DENSE_URL",
    "RERANKER_URL",
    "QDRANT_URL",
]
 
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("search-service")


def validate_required_env() -> None:
    if bool(OPEN_API_LOGIN) != bool(OPEN_API_PASSWORD):
        raise RuntimeError("OPEN_API_LOGIN and OPEN_API_PASSWORD must be set together")

    if not API_KEY and not (OPEN_API_LOGIN and OPEN_API_PASSWORD):
        raise RuntimeError("Either API_KEY or OPEN_API_LOGIN and OPEN_API_PASSWORD must be set")

    missing_env_vars = [
        name for name in REQUIRED_ENV_VARS if os.getenv(name) is None or os.getenv(name) == ""
    ]
    if not missing_env_vars:
        return

    logger.error("Empty required env vars: %s", ", ".join(missing_env_vars))
    raise RuntimeError(f"Empty required env vars: {', '.join(missing_env_vars)}")


validate_required_env()


def get_upstream_request_kwargs() -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    kwargs: dict[str, Any] = {"headers": headers}

    if OPEN_API_LOGIN and OPEN_API_PASSWORD:
        kwargs["auth"] = (OPEN_API_LOGIN, OPEN_API_PASSWORD)
        return kwargs

    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    return kwargs


# Модель данных, которую мы предоставляем и рассчитываем получать от вас
class DateRange(BaseModel):
    from_: str = Field(alias="from")
    to: str


class Entities(BaseModel):
    people: list[str] | None = None
    emails: list[str] | None = None
    documents: list[str] | None = None
    names: list[str] | None = None
    links: list[str] | None = None


class Question(BaseModel):
    text: str
    asker: str = ""
    asked_on: str = ""
    variants: list[str] | None = None
    hyde: list[str] | None = None
    keywords: list[str] | None = None
    entities: Entities | None = None
    date_mentions: list[str] | None = None
    date_range: DateRange | None = None
    search_text: str = ""


class SearchAPIRequest(BaseModel):
    question: Question


class SearchAPIItem(BaseModel):
    message_ids: list[str]


class SearchAPIResponse(BaseModel):
    results: list[SearchAPIItem]


class DenseEmbeddingItem(BaseModel):
    index: int
    embedding: list[float]


class DenseEmbeddingResponse(BaseModel):
    data: list[DenseEmbeddingItem]


class SparseVector(BaseModel):
    indices: list[int] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)


class SparseEmbeddingResponse(BaseModel):
    vectors: list[SparseVector]

# Метадата чанков в Qdrant'e, по которой вы можете фильтровать
class ChunkMetadata(BaseModel):
    chat_name: str
    chat_type: str # channel, group, private, thread
    chat_id: str
    chat_sn: str
    thread_sn: str | None = None
    message_ids: list[str]
    start: str
    end: str
    participants: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    contains_forward: bool = False
    contains_quote: bool = False


@lru_cache(maxsize=1)
def get_sparse_model() -> SparseTextEmbedding:
    logger.info("Loading local sparse model %s", SPARSE_MODEL_NAME)
    return SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient()
    app.state.qdrant = AsyncQdrantClient(
        url=QDRANT_URL,
        api_key=API_KEY,
    )
    try:
        yield
    finally:
        await app.state.http.aclose()
        await app.state.qdrant.close()


app = FastAPI(title="Search Service", version="0.1.0", lifespan=lifespan)


# Внутри шаблона dense и rerank берутся из внешних HTTP endpoint'ов,
# которые предоставляет проверяющая система.
# Текущий код ниже — минимальный пример search pipeline.
DENSE_PREFETCH_K = 10
SPRASE_PREFETCH_K = 30
RETRIEVE_K = 20
RERANK_LIMIT = 10

async def embed_dense(client: httpx.AsyncClient, text: str) -> list[float]:
    # Dense endpoint ожидает OpenAI-compatible body с input как списком строк.
    response = await client.post(
        EMBEDDINGS_DENSE_URL,
        **get_upstream_request_kwargs(),
        json={
            "model": os.getenv("EMBEDDINGS_DENSE_MODEL", EMBEDDINGS_DENSE_MODEL),
            "input": [text],
        },
    )
    response.raise_for_status()

    payload = DenseEmbeddingResponse.model_validate(response.json())
    if not payload.data:
        raise ValueError("Dense embedding response is empty")

    return payload.data[0].embedding


async def embed_sparse(text: str) -> SparseVector:
    vectors = list(get_sparse_model().embed([text]))
    if not vectors:
        raise ValueError("Sparse embedding response is empty")

    item = vectors[0]
    return SparseVector(
        indices=[int(index) for index in item.indices.tolist()],
        values=[float(value) for value in item.values.tolist()],
    )


async def qdrant_search(
    client: AsyncQdrantClient,
    dense_vector: list[float],
    sparse_vector: SparseVector,
) -> Any | None:
    response = await client.query_points(
        collection_name=QDRANT_COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=dense_vector,
                using=QDRANT_DENSE_VECTOR_NAME,
                limit=DENSE_PREFETCH_K,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_vector.indices,
                    values=sparse_vector.values,
                ),
                using=QDRANT_SPARSE_VECTOR_NAME,
                limit=SPRASE_PREFETCH_K,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=RETRIEVE_K,
        with_payload=True,
    )

    if not response.points:
        return None

    return response.points


def extract_message_ids(point: Any) -> list[str]:
    payload = point.payload or {}
    metadata = payload.get("metadata") or {}
    message_ids = metadata.get("message_ids") or []

    return [str(message_id) for message_id in message_ids]


async def get_rerank_scores(
    client: httpx.AsyncClient,
    label: str,
    targets: list[str],
) -> list[float]:
    if not targets:
        return []

    # Rerank endpoint возвращает score для пары query -> candidate text.
    response = await client.post(
        RERANKER_URL,
        **get_upstream_request_kwargs(),
        json={
            "model": RERANKER_MODEL,
            "encoding_format": "float",
            "text_1": label,
            "text_2": targets,
        },
    )
    response.raise_for_status()

    payload = response.json()
    data = payload.get("data") or []

    return [float(sample["score"]) for sample in data]


async def rerank_points(
    client: httpx.AsyncClient,
    query: str,
    points: list[Any],
) -> list[Any]:
    rerank_candidates = points[:10]
    rerank_targets = [point.payload.get("page_content") for point in rerank_candidates]
    scores = await get_rerank_scores(client, query, rerank_targets)

    reranked_candidates = [
        point
        for _, point in sorted(
            zip(scores, rerank_candidates, strict=True),
            key=lambda item: item[0],
            reverse=True,
        )
    ]

    return reranked_candidates


# Ваш сервис должен имплементировать оба этих метода
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search", response_model=SearchAPIResponse)
async def search(payload: SearchAPIRequest) -> SearchAPIResponse:
    query = payload.question.text.strip()
    if not query:
        raise HTTPException(status_code=400, detail="question.text is required")

    client: httpx.AsyncClient = app.state.http
    qdrant: AsyncQdrantClient = app.state.qdrant

    dense_vector = await embed_dense(client, query)
    sparse_vector = await embed_sparse(query)
    best_points = await qdrant_search(qdrant, dense_vector, sparse_vector)

    if best_points is None:
        return SearchAPIResponse(results=[])

    best_points = await rerank_points(client, query, list(best_points))

    message_ids: list[str] = [] 
    for point in best_points:
        message_ids += extract_message_ids(point)

    return SearchAPIResponse(
        results=[SearchAPIItem(message_ids=message_ids)]
    )


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(exc)
    detail = str(exc) or repr(exc)

    if isinstance(exc, RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return JSONResponse(status_code=500, content={"detail": detail})


def main() -> None:
    import uvicorn

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()

```

`search/requirements.txt`:

```txt
fastapi==0.135.1
uvicorn[standard]==0.42.0
pydantic==2.12.5
httpx==0.28.1
qdrant-client==1.15.1
fastembed==0.7.4

```