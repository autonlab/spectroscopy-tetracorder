# Results & artifacts

`analyze()` returns an `AnalysisResult`: compact, aligned NumPy arrays plus
decision, material, profile, and runtime metadata.

## Result variables

Every variable has shape `input_sample_shape + (decisions,)`.

| Attribute | dtype | Meaning |
|---|---|---|
| `material_id` | int32 | winning native material ID; `-1` means no match |
| `fit` | float32 | decoded native spectral fit |
| `depth` | float32 | decoded feature depth |
| `fit_depth` | float32 | decoded native `fd` metric |
| `matched` | bool | authoritative convenience mask |
| `decisions` | tuple | group/case metadata for the final axis |
| `materials` | mapping | material ID to stable output name |

Use `matched` before interpreting the other arrays. Unmatched
`material_id` cells are normalized to `-1`.

## Name the decision axis

```python
decision_index = {
    (decision.kind, decision.number, decision.name): index
    for index, decision in enumerate(result.decisions)
}

for decision in result.decisions:
    print(decision.kind, decision.number, decision.name)
```

The decision axis includes every configured group and case, even when no
native map contains a winner. This makes array positions stable within the
selected expert-system configuration.

Do not hard-code the number of decisions across a different SIF or expert
system. Store `result.decisions` with derived products.

## Resolve material names

```python
ids = np.unique(result.material_id[result.matched])

for material_id in ids:
    print(int(material_id), result.material_name(int(material_id)))
```

Names describe the native material records selected by the expert system.
They are not a substitute for library spectrum and sample metadata.

## Summarize a cube

```python
matched_ids = result.material_id[result.matched]
ids, counts = np.unique(matched_ids, return_counts=True)

summary = [
    {
        "material_id": int(material_id),
        "name": result.material_name(int(material_id)),
        "cells": int(count),
    }
    for material_id, count in zip(ids, counts, strict=True)
]
```

This counts matched decision cells, not necessarily unique spatial pixels. One
pixel can match materials in more than one group/case.

## Provenance

`result.provenance` currently records:

- resolved container path;
- resolved runtime executable;
- native line and sample packing;
- number of input spectra; and
- number of padded spectra.

`result.profile` and `result.backend_version` record the selected sensor
profile and Python backend version. For a reproducible scientific product,
also record your input product, preprocessing, Git commit, SIF checksum, and
expert-system/library provenance outside this object.

## Temporary versus retained artifacts

By default:

```python
result = analyze(data, profile=profile)
assert result.artifacts_path is None
```

The wrapper writes its input, driver, logs, and native output maps in a
`TemporaryDirectory`, decodes them, and removes the directory.

To retain everything:

```python
result = analyze(
    data,
    profile=profile,
    output_dir="artifacts/run-001",
)
```

`output_dir` must be absent or empty. The directory can be much larger than
the compact result tensors, so keep it for debugging, native-product review,
or archival requirements—not by default for every batch.
