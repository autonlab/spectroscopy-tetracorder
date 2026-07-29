"""Exceptions raised by tetracorderpy."""


class TetracorderError(Exception):
    """Base class for all wrapper errors."""


class SpectralDataError(TetracorderError, ValueError):
    """The supplied spectral tensor or metadata are invalid."""


class ProfileError(TetracorderError, ValueError):
    """Base class for spectral-profile errors."""


class ProfileMismatchError(ProfileError):
    """The spectral tensor does not match the selected profile."""


class UnsupportedProfileError(ProfileError):
    """No usable Tetracorder configuration exists for a profile."""


class BackendUnavailableError(TetracorderError, RuntimeError):
    """The requested backend, runtime, or container cannot be used."""


class BackendCapabilityError(TetracorderError, ValueError):
    """The input exceeds a backend's compiled capabilities."""


class TetracorderExecutionError(TetracorderError, RuntimeError):
    """Tetracorder failed to complete or did not produce valid output."""

    def __init__(self, message: str, *, log_tail: str = "") -> None:
        super().__init__(message)
        self.log_tail = log_tail
