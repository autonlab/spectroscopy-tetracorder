# API map

The top-level package exports the small, stable analysis surface:

```python
from tetracorderpy import (
    AnalysisResult,
    SpectralData,
    SpectralProfile,
    analyze,
    available_profiles,
    get_profile,
)
```

## Choose an entry point

| Task | Entry point |
|---|---|
| Analyze a NumPy-like tensor | `tetracorderpy.analyze` |
| Carry values and metadata together | `tetracorderpy.SpectralData` |
| Discover native dataset presets | `tetracorderpy.available_profiles` |
| Load a packaged profile | `tetracorderpy.get_profile` |
| Read or write ENVI | `tetracorderpy.formats` |
| Provision the shared SIF | `uv run tetracorderpy setup` |
| Analyze ENVI from a shell | `uv run tetracorderpy INPUT --profile NAME` |

## Reference sections

- [Analysis & models](analysis.md) — unified call, canonical input, and output
  objects
- [Profiles](profiles.md) — sensor-response and dataset-preset discovery
- [ENVI adapter](formats.md) — header, memory-map, and writer functions
- [Errors](errors.md) — typed failure modes

Classes in `tetracorderpy.backends` are extension seams rather than the normal
user interface. Passing a custom `backend=` is useful for testing or a future
version-specific implementation.
