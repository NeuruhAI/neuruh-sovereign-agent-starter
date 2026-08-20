from .core import (
    SCHEMA_VERSION,
    StarterError,
    StarterConfig,
    StarterRunResult,
    run,
    openai_compatible_infer,
)

__all__ = [
    "SCHEMA_VERSION",
    "StarterError",
    "StarterConfig",
    "StarterRunResult",
    "run",
    "openai_compatible_infer",
]

from importlib.metadata import PackageNotFoundError, version as _metadata_version

try:
    __version__ = _metadata_version("neuruh-sovereign-agent-starter")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "unknown"
