from fastapi import FastAPI

from app.api.routes import router


app = FastAPI(
    title="Policy-Aware Multi-Agent RAG Claim Decision Engine",
    description=(
        "A policy-grounded multi-agent system for analyzing "
        "health insurance claim cases."
    ),
    version="1.0.0",
)

app.include_router(router)