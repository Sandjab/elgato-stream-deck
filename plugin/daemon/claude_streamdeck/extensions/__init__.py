"""Extension loader: imports modules by name and initializes them."""

from __future__ import annotations

import importlib
import logging
from typing import Any, Protocol

from ..core.core_api import CoreAPI

logger = logging.getLogger(__name__)


class Extension(Protocol):
    def init(self, api: CoreAPI) -> None: ...
    def shutdown(self) -> None: ...


# Track loaded extensions for shutdown.
_loaded: list[tuple[str, Any]] = []


def load_extensions(api: CoreAPI, specs: list[dict]) -> list[str]:
    """Load each extension by module name. Returns the names that loaded successfully."""
    loaded: list[str] = []
    for spec in specs:
        module_name = spec["module"]
        cfg = spec.get("config", {})
        try:
            mod = importlib.import_module(module_name)
            ext_cls = getattr(mod, "Extension")
            ext = ext_cls()
            # Provide the per-extension config slice without polluting api.config.
            scoped_api = CoreAPI(
                devices=api.devices,
                assets=api.assets,
                display=api.display,
                input=api.input,
                events=api.events,
                commands=api.commands,
                config=cfg,
            )
            ext.init(scoped_api)
            _loaded.append((module_name, ext))
            loaded.append(module_name)
            logger.info("Loaded extension: %s", module_name)
        except Exception:
            logger.exception("Failed to load extension %s", module_name)
    # Make the list of loaded extensions visible to system.version.
    api.config["loaded_extensions"] = loaded
    return loaded


def shutdown_extensions() -> None:
    while _loaded:
        name, ext = _loaded.pop()
        try:
            ext.shutdown()
        except Exception:
            logger.exception("Failed to shutdown extension %s", name)
