"""Backend interface kept deliberately small for future versions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..models import AnalysisResult, SpectralData, SpectralProfile


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    """Compile-time limits relevant to tensor packing."""

    max_bands: int
    max_samples_per_line: int


class TetracorderBackend(Protocol):
    """Protocol implemented by a version-specific execution backend."""

    version: str
    capabilities: BackendCapabilities

    def analyze(
        self,
        data: SpectralData,
        profile: SpectralProfile,
        *,
        work_dir: Path,
        timeout: float,
    ) -> AnalysisResult:
        """Analyze data in work_dir and return fully materialized arrays."""
