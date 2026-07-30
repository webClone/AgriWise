"""
AgriBrain V56 Runtime & Memory Profiler.

Accurately measures execution timing and peak memory usage of runtime blocks
using Python's tracemalloc and time libraries.
"""

from __future__ import annotations

import os
import time
import tracemalloc
from typing import Any, Callable, Dict, Optional

try:
    import psutil
except ImportError:
    psutil = None


class RuntimeProfiler:
    """
    Unified profiler implementing tracemalloc to record execution timing
    and peak memory usage dynamically per module runtime block.
    """

    @staticmethod
    def profile_block(callable_obj: Callable[[], Any]) -> Dict[str, Any]:
        """
        Executes a callable under active memory and timing instrumentation,
        returning its output along with execution profile statistics.
        """
        tracemalloc.start()
        t0 = time.perf_counter()

        # Execute block
        result = None
        status = "passing"
        failure_reason = None
        try:
            result = callable_obj()
        except Exception as e:
            import traceback
            traceback.print_exc()
            status = "failed"
            failure_reason = f"{type(e).__name__}: {str(e)}"

        current, peak = tracemalloc.get_traced_memory()
        elapsed = time.perf_counter() - t0
        tracemalloc.stop()

        peak_memory_mb = float(peak) / 1024.0 / 1024.0
        
        rss_mb = 0.0
        if psutil is not None:
            try:
                process = psutil.Process(os.getpid())
                rss_mb = float(process.memory_info().rss) / 1024.0 / 1024.0
            except Exception:
                pass

        profile = {
            "runtime_seconds": round(elapsed, 6),
            "peak_memory_mb": round(peak_memory_mb, 4),
            "status": status,
            "failure_reason": failure_reason
        }
        if rss_mb > 0.0:
            profile["process_rss_mb"] = round(rss_mb, 4)

        return {
            "result": result,
            "profile": profile
        }
