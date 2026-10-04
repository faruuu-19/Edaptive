import importlib
import pkgutil

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import modules as feature_modules
from app.core.config import get_settings
from app.session_log.router import router as session_log_router


def create_app() -> FastAPI:
    api = FastAPI(title="Edaptive", version="0.1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api.get("/api/health", tags=["platform"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    api.include_router(session_log_router)

    # Each module that ships app/modules/<name>/router.py with a `router` is mounted
    # automatically, so no track has to edit this file to add endpoints.
    for info in pkgutil.iter_modules(feature_modules.__path__):
        try:
            module = importlib.import_module(f"app.modules.{info.name}.router")
        except ModuleNotFoundError as exc:
            if exc.name == f"app.modules.{info.name}.router":
                continue
            raise
        api.include_router(module.router, prefix=f"/api/{info.name}", tags=[info.name])
    return api


app = create_app()
