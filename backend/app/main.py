import uuid
import time
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="PS-04 AI Trading Copilot Prototype",
    version="1.0.0",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID & Time Middleware
@app.middleware("http")
async def add_request_id_and_process_time(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as exc:
        process_time = time.time() - start_time
        # Consistent error response as per API_CONTRACT
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred.",
                    "request_id": request_id
                }
            },
            headers={"X-Request-ID": request_id, "X-Process-Time": str(process_time)}
        )

# Liveness endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """
    Check the health of the system and report basic config mode.
    """
    return {
        "status": "ok",
        "mode": settings.TRADING_MODE,
        "environment": settings.APP_ENV
    }
