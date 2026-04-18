import logging
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any
import httpx
import uuid  # <-- Добавлено для генерации ID точек
from fastembed import SparseTextEmbedding
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient, models

EMBEDDINGS_DENSE_MODEL = "Qwen/Qwen3-Embedding-0.6B"

# Ваш сервис должен считывать эти переменные из окружения (env), так как проверяющая система управляет ими
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8002"))
API_KEY = os.getenv("API_KEY") # <-- Исправлена ошибка в имени переменной
EMBEDDINGS_DENSE_URL = os.getenv("EMBEDDINGS_DENSE_URL")
QDRANT_DENSE_VECTOR_NAME = os.getenv("QDRANT_DENSE_VECTOR_NAME", "dense") # <-- Исправлена ошибка в имени переменной
QDRANT_SPARSE_VECTOR_NAME = os.getenv("QDRANT_SPARSE_VECTOR_NAME", "sparse") # <-- Исправлена ошибка в имени переменной
SPARSE_MODEL_NAME = "Qdrant/bm25"
RERANKER_MODEL = "nvidia/llama-nemotron-rerank-1b-v2"
RERANKER_URL = os.getenv("RERANKER_URL")
OPEN_API_LOGIN = os.getenv("OPEN_API_LOGIN")
OPEN_API_PASSWORD = os.getenv("OPEN_API_PASSWORD")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "evaluation") # <-- Исправлена ошибка в имени переменной

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


# --- Модели из Index Service для совместимости ---
# Эти модели должны быть определены или импортированы из общего модуля,
# если используется несколько файлов. Для одного файла они определены здесь.
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

class IndexAPIItem(BaseModel):
    page_content: str
    dense_content: str
    sparse_content: str
    message_ids: list[str]

class BulkInsertRequest(BaseModel):
    chunks: list[IndexAPIItem]
    chat_metadata: dict[str, Any] # Словарь для передачи метаданных чата

# --- Конец моделей из Index Service ---

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
             "model": RERANKER_MODEL, # <-- Исправлена ошибка в имени ключа
             "encoding_format": "float", # <-- Исправлена ошибка в имени ключа
             "text_1": label,
             "text_2": targets,
        },
    )
    response.raise_for_status()

    payload = response.json()
    data = payload.get("data") or [] # <-- Исправлена ошибка в имени ключа

    return [float(sample["score"]) for sample in data] # <-- Исправлена ошибка в имени ключа

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

# --- Новый эндпоинт для вставки чанков ---
@app.post("/insert_chunks")
async def insert_chunks(payload: BulkInsertRequest) -> dict[str, str]:
    qdrant: AsyncQdrantClient = app.state.qdrant
    client_http: httpx.AsyncClient = app.state.http

    if not payload.chunks:
        return {"status": "No chunks provided"}

    # --- Подготовка данных для Qdrant ---
    points_to_insert = []
    for item in payload.chunks:
        # 1. Генерация ID точки (можно использовать UUID)
        point_id = str(uuid.uuid4())

        # 2. Получение векторов
        # Плотный вектор
        try:
            dense_vector = await embed_dense(client_http, item.dense_content)
        except Exception as e:
            logger.error(f"Error embedding dense content for chunk {point_id}: {e}")
            # Пропускаем этот чанк или обрабатываем ошибку
            continue

        # Разреженный вектор
        try:
            sparse_vector_obj = await embed_sparse(item.sparse_content)
            sparse_vector_dict = {
                "indices": sparse_vector_obj.indices,
                "values": sparse_vector_obj.values,
            }
        except Exception as e:
            logger.error(f"Error embedding sparse content for chunk {point_id}: {e}")
            # Пропускаем этот чанк или обрабатываете ошибку
            continue

        # 3. Подготовка payload
        # Здесь нужно создать ChunkMetadata из доступной информации
        # Предположим, payload.chat_metadata содержит базовые данные чата
        # и мы берем message_ids из самого чанка (item.message_ids)
        # Замените dummy значения на реальные из payload.chat_metadata и item
        metadata = ChunkMetadata(
            chat_name=payload.chat_metadata.get('chat_name', ''), # Пример
            chat_type=payload.chat_metadata.get('chat_type', ''), # Пример
            chat_id=payload.chat_metadata.get('chat_id', ''), # Пример
            chat_sn=payload.chat_metadata.get('chat_sn', ''), # Пример
            thread_sn=payload.chat_metadata.get('thread_sn'), # Может быть None
            message_ids=item.message_ids, # Из самого чанка
            start="", # Заполните реальной информацией, если доступна
            end="",   # Заполните реальной информацией, если доступна
            participants=[], # Заполните реальной информацией, если доступна
            mentions=[],     # Заполните реальной информацией, если доступна
            contains_forward=False, # Заполните реальной информацией, если доступна
            contains_quote=False,   # Заполните реальной информацией, если доступна
        )

        payload_data = {
            "metadata": metadata.model_dump(), # Преобразование Pydantic модели в словарь
            "page_content": item.page_content
            # Можно добавить другие поля, если нужно
        }

        # 4. Подготовка точки для вставки
        point = models.PointStruct(
            id=point_id,
            vector={
                QDRANT_DENSE_VECTOR_NAME: dense_vector,
                QDRANT_SPARSE_VECTOR_NAME: sparse_vector_dict,
            },
            payload=payload_data
        )
        points_to_insert.append(point)

    if not points_to_insert:
        return {"status": "No valid chunks to insert after processing"}

    # --- Вставка в Qdrant ---
    try:
        # batch_size можно настроить для производительности
        batch_size = 100
        for i in range(0, len(points_to_insert), batch_size):
            batch = points_to_insert[i:i+batch_size]
            await qdrant.upsert(collection_name=QDRANT_COLLECTION_NAME, points=batch)
        logger.info(f"Successfully inserted {len(points_to_insert)} chunks into collection '{QDRANT_COLLECTION_NAME}'")
        return {"status": f"Successfully inserted {len(points_to_insert)} chunks"}
    except Exception as e:
        logger.error(f"Error inserting chunks into Qdrant: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to insert chunks into Qdrant: {str(e)}")


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
