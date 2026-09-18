from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.features.rfq.router import router as rfq_router
from app.features.quote.router import router as quote_router
from app.features.chat.router import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(rfq_router)
app.include_router(quote_router)
app.include_router(chat_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Server is running",
    }
