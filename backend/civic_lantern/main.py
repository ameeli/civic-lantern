from typing import TypedDict

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from civic_lantern.api.deps import require_api_key
from civic_lantern.api.routers import candidate_spending, candidates, election_spending
from civic_lantern.core.config import Settings, get_settings
from civic_lantern.utils.logging import configure_logging


class DocsRoutes(TypedDict):
    docs_url: str | None
    redoc_url: str | None
    openapi_url: str | None


def docs_routes(settings: Settings) -> DocsRoutes:
    """Swagger, ReDoc and the OpenAPI schema exist only when EXPOSE_DOCS is on."""
    if settings.EXPOSE_DOCS:
        return {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        }
    return {"docs_url": None, "redoc_url": None, "openapi_url": None}


configure_logging()
settings = get_settings()

app = FastAPI(
    **docs_routes(settings),
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


# Everything under /api/v1 requires the API key; only /health is open.
api_v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
api_v1.include_router(candidates.router)
api_v1.include_router(candidate_spending.router)
api_v1.include_router(election_spending.router)
app.include_router(api_v1)
