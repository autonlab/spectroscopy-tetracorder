from __future__ import annotations

import json
from pathlib import Path
from typing import Any

NOTEBOOK = (
    Path(__file__).parent.parent / "docs" / "tutorials" / "python-api-tutorial.ipynb"
)


def _load_notebook() -> dict[str, Any]:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def test_tutorial_notebook_is_fully_executed_without_errors() -> None:
    notebook = _load_notebook()
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]

    assert code_cells
    assert all(cell["execution_count"] is not None for cell in code_cells)
    assert not [
        output
        for cell in code_cells
        for output in cell.get("outputs", [])
        if output["output_type"] == "error"
    ]


def test_tutorial_notebook_stores_real_single_and_batch_results() -> None:
    notebook_text = NOTEBOOK.read_text(encoding="utf-8")

    assert "matched decisions: 3" in notebook_text
    assert "spectra handled by this one run: 6" in notebook_text
    assert '"image/png"' in notebook_text or '"image/svg+xml"' in notebook_text
    assert "/cteh/spectroscopy-tetracorder" not in notebook_text
