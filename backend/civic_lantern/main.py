from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from civic_lantern.api.routers import candidate_spending, candidates, election_spending
from civic_lantern.core.config import get_settings
from civic_lantern.utils.logging import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(
    title="The Civic Lantern",
    description="Campaign finance transparency platform tracking outside spending.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(candidates.router, prefix="/api/v1")
app.include_router(candidate_spending.router, prefix="/api/v1")
app.include_router(election_spending.router, prefix="/api/v1")
