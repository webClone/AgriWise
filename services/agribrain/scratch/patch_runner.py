"""Patch script for services/agribrain/layer10_sire/runner.py.
Applies all 11 fixes identified during the deep check.
"""
import os
import re
import sys

TARGET_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "layer10_sire", "runner.py")
)

with open(TARGET_PATH, "rb") as f:
    raw = f.read()

# 1. Normalize line endings (\r\r\n and \r\n to \n)
text = raw.replace(b"\r\r\n", b"\n").replace(b"\r\n", b"\n").decode("utf-8")

# Verify initial sanity
assert "def run_layer10_sire(" in text, "Missing run_layer10_sire"
assert "_rasterize_polygon_mask(" in text, "Missing _rasterize_polygon_mask"

# 2. Delete duplicate block (lines 4691-4888)
# The duplicate block begins with '# ── V92.4-BC.8.1: Build source_policy_display_state ─────────────'
# and ends with '"authority": "scouting_only"\n        }'
dup_marker = "# ── V92.4-BC.8.1: Build source_policy_display_state ─────────────"
first_idx = text.find(dup_marker)
second_idx = text.find(dup_marker, first_idx + len(dup_marker))
assert first_idx != -1 and second_idx != -1, f"Could not find both duplicate blocks: {first_idx}, {second_idx}"

# Remove the first occurrence up to the start of the second occurrence
text = text[:first_idx] + text[second_idx:]
print(f"Removed 198-line duplicate block (bytes {first_idx} to {second_idx})")

# 3. Remove dangerous module globals at run_layer10_sire:
# global cache_key, is_quick_visual, budget_ms, start_time
globals_str = "    global cache_key, is_quick_visual, budget_ms, start_time\n"
if globals_str in text:
    text = text.replace(globals_str, "", 1)
    print("Removed module globals declaration")
else:
    # Try regex if indentation varies
    text, n = re.subn(r"^\s*global cache_key, is_quick_visual, budget_ms, start_time\s*\n", "", text, flags=re.MULTILINE)
    assert n == 1, "Failed to remove globals"
    print("Removed module globals declaration via regex")

# 4. Remove redundant uncast tgt_h and tgt_w overwrite
old_tgt = """    # Grid spec fields compatibility: check target dims
    tgt_h = display_grid_spec.get("height", tgt_h)
    tgt_w = display_grid_spec.get("width", tgt_w)"""
if old_tgt in text:
    text = text.replace(old_tgt, "    # Grid spec fields compatibility: target dims already integer-cast above", 1)
    print("Removed redundant uncast target dims overwrite")
else:
    print("Warning: old_tgt block not found verbatim, checking regex...")
    text, n = re.subn(
        r"    # Grid spec fields compatibility: check target dims\n    tgt_h = display_grid_spec\.get\(\"height\", tgt_h\)\n    tgt_w = display_grid_spec\.get\(\"width\", tgt_w\)",
        "    # Grid spec fields compatibility: target dims already integer-cast above",
        text
    )
    assert n == 1, "Failed to remove redundant tgt_h overwrite"
    print("Removed redundant uncast target dims overwrite via regex")

# 5. Guard KeyError in get_layer10_cache_key lines 1227-1232
old_cache_keys = """        info = metrics_store.get_latest_metrics_info(inp.plot_id)
        if info:
            payload["archive_metrics_hash"] = info["archive_metrics_hash"]
            payload["archive_run_id"] = info["archive_run_id"]
            payload["archive_policy_version"] = info["archive_policy_version"]
            payload["retrovalidation_policy_version"] = info["retrovalidation_policy_version"]
            payload["archive_bma_policy_version"] = info["archive_bma_policy_version"]
            payload["baseline_policy_version"] = info["baseline_policy_version"]"""

new_cache_keys = """        info = metrics_store.get_latest_metrics_info(inp.plot_id)
        if info:
            payload["archive_metrics_hash"] = info.get("archive_metrics_hash")
            payload["archive_run_id"] = info.get("archive_run_id")
            payload["archive_policy_version"] = info.get("archive_policy_version")
            payload["retrovalidation_policy_version"] = info.get("retrovalidation_policy_version")
            payload["archive_bma_policy_version"] = info.get("archive_bma_policy_version")
            payload["baseline_policy_version"] = info.get("baseline_policy_version")"""
assert old_cache_keys in text, "Failed to find old_cache_keys"
text = text.replace(old_cache_keys, new_cache_keys, 1)
print("Guarded KeyError in get_layer10_cache_key")

# 6. Delete dead migration functions _legacy_ndvi_phenology_*
legacy_start = text.find("def _legacy_ndvi_phenology_stage_for_migration(")
legacy_end = text.find("def _resolve_phenology_context(")
assert legacy_start != -1 and legacy_end != -1 and legacy_start < legacy_end, "Could not find legacy phenology functions"
text = text[:legacy_start] + text[legacy_end:]
print(f"Removed dead legacy migration code (bytes {legacy_start} to {legacy_end})")

# 7. Remove duplicate skipped += 1
old_skipped = """        print(f"[L10] Error running agronomic models: {e}", file=sys.stderr)
        skipped += 5

        skipped += 1"""
new_skipped = """        print(f"[L10] Error running agronomic models: {e}", file=sys.stderr)
        skipped += 5"""
assert old_skipped in text, "Failed to find old_skipped block"
text = text.replace(old_skipped, new_skipped, 1)
print("Removed duplicate skipped += 1")

# 8. Fix float underflow / ZeroDivision guard in drift check
old_drift = """            if redistributed_vals:
                redis_mean = sum(redistributed_vals) / len(redistributed_vals)
                drift = abs(redis_mean - mean_val) / abs(mean_val)
                if drift > 0.01:  # 1% drift threshold
                    detail_ok = False
                    break"""
new_drift = """            if redistributed_vals:
                redis_mean = sum(redistributed_vals) / len(redistributed_vals)
                if abs(mean_val) > 1e-6:
                    drift = abs(redis_mean - mean_val) / abs(mean_val)
                    if drift > 0.01:  # 1% drift threshold
                        detail_ok = False
                        break"""
assert old_drift in text, "Failed to find old_drift block"
text = text.replace(old_drift, new_drift, 1)
print("Guarded drift check against near-zero mean_val")

# 9. In _rasterize_polygon_mask, ensure border cells touching/intersecting polygon boundary retain true/valid values
old_mask_loop = """    for row_index in range(height):
        center_y = max_y - (row_index + 0.5) * y_step
        for column_index in range(width):
            center_x = min_x + (column_index + 0.5) * x_step
            mask[row_index, column_index] = _point_in_polygon(
                center_x, center_y, polygon,
            )"""

new_mask_loop = """    dx = 0.45 * x_step
    dy = 0.45 * y_step
    for row_index in range(height):
        center_y = max_y - (row_index + 0.5) * y_step
        for column_index in range(width):
            center_x = min_x + (column_index + 0.5) * x_step
            if _point_in_polygon(center_x, center_y, polygon):
                mask[row_index, column_index] = True
            elif (
                _point_in_polygon(center_x - dx, center_y - dy, polygon)
                or _point_in_polygon(center_x + dx, center_y - dy, polygon)
                or _point_in_polygon(center_x - dx, center_y + dy, polygon)
                or _point_in_polygon(center_x + dx, center_y + dy, polygon)
            ):
                mask[row_index, column_index] = True"""
assert old_mask_loop in text, "Failed to find old_mask_loop"
text = text.replace(old_mask_loop, new_mask_loop, 1)
print("Updated _rasterize_polygon_mask to preserve border cells")

# 10. Vectorize surface_field_mask application across s.values
old_field_mask_apply = """                            surface_field_mask = _resize_boolean_mask(
                                base_field_mask, s_h, s_w,
                            )
                            dependency_mask = is_render_dependency_surface(s)
                            for r in range(s_h):
                                for c in range(s_w):
                                    if not surface_field_mask[r, c]:
                                        s.values[r][c] = 0.0 if dependency_mask else None"""

new_field_mask_apply = """                            surface_field_mask = _resize_boolean_mask(
                                base_field_mask, s_h, s_w,
                            )
                            dependency_mask = is_render_dependency_surface(s)
                            fill_val = 0.0 if dependency_mask else None
                            val_arr = np.array(s.values, dtype=object)
                            val_arr[~surface_field_mask] = fill_val
                            s.values = val_arr.tolist()"""
assert old_field_mask_apply in text, "Failed to find old_field_mask_apply"
text = text.replace(old_field_mask_apply, new_field_mask_apply, 1)
print("Vectorized surface_field_mask application")

# 11. Atomic cache rollback in save_layer10_to_cache
old_cache_cleanup = """        if npz_path and os.path.exists(npz_path):
            try: os.remove(npz_path)
            except Exception: pass
        return 0"""
new_cache_cleanup = """        if npz_path and os.path.exists(npz_path):
            try: os.remove(npz_path)
            except Exception: pass
        if cache_path and os.path.exists(cache_path):
            try: os.remove(cache_path)
            except Exception: pass
        return 0"""
assert old_cache_cleanup in text, "Failed to find old_cache_cleanup"
text = text.replace(old_cache_cleanup, new_cache_cleanup, 1)
print("Added atomic cache_path removal on save_layer10_to_cache exception")

# 12. Add logging to silent except Exception blocks
old_except_metrics = """    except ValueError:
        payload["archive_metrics_status"] = "malformed"
    except Exception:
        pass"""
new_except_metrics = """    except ValueError:
        payload["archive_metrics_status"] = "malformed"
    except Exception as e:
        logger.warning(f"Metrics store access error for plot {inp.plot_id}: {e}")"""
assert old_except_metrics in text, "Failed to find old_except_metrics"
text = text.replace(old_except_metrics, new_except_metrics, 1)
print("Added logging for metrics store access exception")

# Write out with clean LF line endings
with open(TARGET_PATH, "wb") as f:
    f.write(text.encode("utf-8"))

print("SUCCESS: services/agribrain/layer10_sire/runner.py patched successfully!")
