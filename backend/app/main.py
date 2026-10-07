import importlib
import pkgutil

from fastapi import FastAPI

from app import modules as feature_modules
from app.session_log.router import router as session_log_router


def create_app() -> FastAPI:
    api = FastAPI(title="Edaptive", version="0.1.0")

    @api.get("/api/health", tags=["platform"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    api.include_router(session_log_router)

    # Each module that ships app/modules/<name>/router.py with a `router` is mounted
    # automatically, so no track has to edit this file to add endpoints. A router module may
    # also define `on_mount(api)` for one-time setup (the auth module installs the actor
    # resolver this way; see app/core/identity.py).
    for info in pkgutil.iter_modules(feature_modules.__path__):
        try:
            module = importlib.import_module(f"app.modules.{info.name}.router")
        except ModuleNotFoundError as exc:
            if exc.name == f"app.modules.{info.name}.router":
                continue
            raise
        api.include_router(module.router, prefix=f"/api/{info.name}", tags=[info.name])
        if hasattr(module, "on_mount"):
            module.on_mount(api)
    return api


app = create_app()
