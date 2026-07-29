"""Python-native interface to USGS Tetracorder."""

from .api import analyze
from .errors import (
    BackendCapabilityError,
    BackendUnavailableError,
    ProfileMismatchError,
    RuntimeSetupError,
    SpectralDataError,
    TetracorderError,
    TetracorderExecutionError,
    UnsupportedProfileError,
)
from .models import (
    AnalysisResult,
    Decision,
    Material,
    SpectralData,
    SpectralProfile,
)
from .profiles import available_profiles, get_profile

__all__ = [
    "AnalysisResult",
    "BackendCapabilityError",
    "BackendUnavailableError",
    "Decision",
    "Material",
    "ProfileMismatchError",
    "RuntimeSetupError",
    "SpectralData",
    "SpectralDataError",
    "SpectralProfile",
    "TetracorderError",
    "TetracorderExecutionError",
    "UnsupportedProfileError",
    "analyze",
    "available_profiles",
    "get_profile",
]
