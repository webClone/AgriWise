from __future__ import annotations

import pytest

from services.agribrain.asmae_learn.plot_memory import get_memory_file_path


def test_canonical_sha256_geometry_identity_has_windows_safe_storage_path():
    digest = "a" * 64
    path = get_memory_file_path(
        "plot-1", f"sha256:{digest}", "season-1"
    )

    assert path.parts[-4:] == (
        "plot-1",
        f"sha256-{digest}",
        "season-1",
        "memory.json",
    )
    assert ":" not in path.parts[-3]


def test_legacy_geometry_hash_path_remains_compatible():
    path = get_memory_file_path("plot-1", "e424d062", "season-1")
    assert path.parts[-4:] == (
        "plot-1", "e424d062", "season-1", "memory.json"
    )


@pytest.mark.parametrize(
    "unsafe",
    (
        "sha256:not-a-digest",
        "other:aaaaaaaa",
        "../escape",
        "nested/path",
        "nested\\path",
    ),
)
def test_unknown_or_unsafe_geometry_path_forms_remain_rejected(unsafe):
    with pytest.raises(ValueError, match="unsafe path segment"):
        get_memory_file_path("plot-1", unsafe, "season-1")
