from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import engine, Base, run_migrations
from routes import health_router, products_router, chat_router, cart_router, payment_router, orders_router, contracts_router, replay_router, auth_router, buyer_agent_router, decision_trace_router, decision_lab_router
from seed.seed_products import seed_products
from database import SessionLocal
import config
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="NexaCart API",
    description="AI-Native Conversational Commerce Backend",
    version="0.1.0"
)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=headers,
    )

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(products_router)
app.include_router(chat_router)
app.include_router(cart_router)
app.include_router(payment_router)
app.include_router(orders_router)
app.include_router(contracts_router)
app.include_router(replay_router)
app.include_router(buyer_agent_router)
app.include_router(decision_trace_router)
app.include_router(decision_lab_router)



@app.on_event("startup")
def startup():
    run_migrations()
    db = SessionLocal()
    try:
        seed_products(db)
    finally:
        db.close()
