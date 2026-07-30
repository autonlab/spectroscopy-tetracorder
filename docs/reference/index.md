# API Reference

This section documents exact public objects, parameters, return values, and
exceptions. If you are learning the wrapper for the first time, begin with
[Getting Started](../index.md). For task-oriented explanations and complete
workflows, use the [User Guide](../guides/tensors.md).

## Public imports

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
| Provision or locate the shared SIF | `uv run tetracorderpy setup` |
| Analyze ENVI from a shell | `uv run tetracorderpy INPUT --profile NAME` |

## Reference pages

- [Analysis & models](analysis.md) — the unified call and canonical input and
  output objects
- [Profiles](profiles.md) — sensor-response and native dataset-preset discovery
- [ENVI adapter](formats.md) — headers, memory mapping, and writer functions
- [Errors](errors.md) — typed validation, runtime, and backend failures

Classes under `tetracorderpy.backends` are extension seams, not the normal
user interface. A custom `backend=` is primarily useful for tests or a future
version-specific implementation.
