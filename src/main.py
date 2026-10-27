import uuid
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.routers import auth, catalog, variants, builds


app = FastAPI(
    title="PC Price Tracker API",
    description="REST API для мониторинга цен комплектующих ПК и конфигурирования сборок",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_and_timing_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = req_id
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


app.include_router(auth.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(variants.router, prefix="/api")
app.include_router(builds.router, prefix="/api")

@app.get("/", tags=["Системные"])
def root():
    return {
        "status": "online",
        "service": "PC Price Tracker API",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }