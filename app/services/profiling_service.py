"""
Performance Profiling Service

Service for collecting and analyzing application performance data.
"""

import cProfile
import io
import logging
import pstats
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, List

logger = logging.getLogger(__name__)


@dataclass
class PerformanceSnapshot:
    """Represents a performance snapshot."""

    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    active_threads: int
    active_coroutines: int
    request_count: int
    response_time_avg: float


@dataclass
class ProfilingResult:
    """Represents profiling results."""

    function_stats: List[Dict[str, Any]]
    total_calls: int
    total_time: float
    memory_peak: int
    duration: float


class ProfilingService:
    """Service for application performance profiling and monitoring."""

    def __init__(self) -> None:
        self.snapshots: List[PerformanceSnapshot] = []
        self.max_snapshots = 1000
        self.is_tracing_memory = False
        self.memory_trace_started = False
        self.memory_tracing_active = False  # Alias for backwards compatibility

    def start_memory_tracing(self) -> None:
        """Start memory tracing."""
        if not self.is_tracing_memory:
            tracemalloc.start()
            self.memory_trace_started = True
            self.is_tracing_memory = True
            self.memory_tracing_active = True
            logger.info("Memory tracing started")

    def stop_memory_tracing(self) -> None:
        """Stop memory tracing."""
        if self.is_tracing_memory:
            tracemalloc.stop()
            self.is_tracing_memory = False
            self.memory_tracing_active = False
            logger.info("Memory tracing stopped")

    def get_memory_snapshot(self) -> Dict[str, Any]:
        """Get current memory usage snapshot."""
        if not self.memory_trace_started:
            return {"error": "Memory tracing not started"}

        try:
            current, peak = tracemalloc.get_traced_memory()
            stats = tracemalloc.take_snapshot()
            top_stats = stats.statistics("lineno")

            return {
                "current_mb": current / 1024 / 1024,
                "peak_mb": peak / 1024 / 1024,
                "top_allocators": [
                    {
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                    }
                    for stat in top_stats[:10]
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get memory snapshot: {e}")
            return {"error": str(e)}

    def record_performance_snapshot(
        self,
        cpu_percent: float,
        memory_mb: float,
        active_threads: int,
        active_coroutines: int,
        request_count: int,
        response_time_avg: float,
    ) -> None:
        """Record a performance snapshot."""
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            active_threads=active_threads,
            active_coroutines=active_coroutines,
            request_count=request_count,
            response_time_avg=response_time_avg,
        )

        self.snapshots.append(snapshot)

        # Keep only the most recent snapshots
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots = self.snapshots[-self.max_snapshots :]

    def get_performance_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get performance history for the specified time period."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        recent_snapshots = [s for s in self.snapshots if s.timestamp >= cutoff]

        return [
            {
                "timestamp": s.timestamp.isoformat() + "Z",
                "cpu_percent": s.cpu_percent,
                "memory_mb": s.memory_mb,
                "active_threads": s.active_threads,
                "active_coroutines": s.active_coroutines,
                "request_count": s.request_count,
                "response_time_avg": s.response_time_avg,
            }
            for s in recent_snapshots
        ]

    @contextmanager
    def profile_function(
        self, sort_by: str = "cumulative", lines: int = 20
    ) -> Generator[None, None, None]:
        """Context manager for profiling a function."""
        profiler = cProfile.Profile()
        profiler.enable()

        start_time = time.time()
        start_memory = None

        if self.is_tracing_memory:  # pragma: no branch
            try:
                start_memory = tracemalloc.get_traced_memory()[0]
            except Exception:  # pragma: no cover
                start_memory = None

        try:
            yield  # Let the code run
        finally:
            profiler.disable()
            end_time = time.time()

            # Get profiling stats
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats(sort_by)
            ps.print_stats(lines)

            # Parse the stats output
            stats_output = s.getvalue()
            function_stats = self._parse_profile_stats(stats_output)

            # Get memory info
            peak_memory = None
            if self.is_tracing_memory and start_memory is not None:  # pragma: no branch
                try:
                    peak_memory = tracemalloc.get_traced_memory()[1]
                except Exception:  # pragma: no cover
                    peak_memory = None

            result = ProfilingResult(
                function_stats=function_stats,
                total_calls=sum(stat["calls"] for stat in function_stats),
                total_time=end_time - start_time,
                memory_peak=peak_memory if peak_memory else 0,
                duration=end_time - start_time,
            )

            logger.info(
                f"Function profiling completed: {result.total_calls} calls, {result.duration:.2f}s"
            )

    def _parse_profile_stats(self, stats_output: str) -> List[Dict[str, Any]]:
        """Parse pstats output into structured data."""
        lines = stats_output.split("\n")
        stats = []

        # Skip header lines
        in_stats_section = False
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("ncalls"):
                in_stats_section = True
                continue

            if in_stats_section and line and not line.startswith("==="):  # pragma: no branch
                try:
                    parts = line.split()
                    if len(parts) >= 6:  # pragma: no branch
                        # Format: ncalls tottime percall cumtime percall filename:lineno(function)
                        # ncalls can be "100" or "100/50" for recursive functions (total/primitive)
                        ncalls_str = parts[0]
                        # Take the first part before '/' if present (total calls)
                        ncalls = int(ncalls_str.split("/")[0])
                        tottime = float(parts[1])
                        percall_tottime = float(parts[2])
                        cumtime = float(parts[3])
                        percall_cumtime = float(parts[4])
                        function_info = " ".join(parts[5:])

                        stats.append(
                            {
                                "calls": ncalls,
                                "total_time": tottime,
                                "time_per_call": percall_tottime,
                                "cumulative_time": cumtime,
                                "cumulative_per_call": percall_cumtime,
                                "function": function_info,
                            }
                        )
                except (ValueError, IndexError):  # pragma: no cover
                    continue

        return stats

    def get_system_performance(self) -> Dict[str, Any]:
        """Get current system performance metrics."""
        try:
            import threading

            import psutil

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_mb = memory.used / 1024 / 1024

            # Thread count
            active_threads = threading.active_count()

            # Coroutine count (approximate)
            active_coroutines = len([t for t in threading.enumerate() if "asyncio" in str(t)])

            return {
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb,
                "active_threads": active_threads,
                "active_coroutines": active_coroutines,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            }
        except ImportError:  # pragma: no cover
            return {"error": "psutil not available"}
        except Exception as e:  # pragma: no cover
            logger.error(f"Failed to get system performance: {e}")
            return {"error": str(e)}

    def get_bottleneck_analysis(self) -> Dict[str, Any]:
        """Analyze performance data for bottlenecks."""
        if not self.snapshots:
            return {"error": "No performance snapshots available"}

        # Analyze recent snapshots (last hour)
        recent_snapshots = [
            s
            for s in self.snapshots
            if s.timestamp >= datetime.now(timezone.utc) - timedelta(hours=1)
        ]

        if not recent_snapshots:
            return {"error": "No recent performance snapshots available"}

        # Calculate averages and identify patterns
        avg_cpu = sum(s.cpu_percent for s in recent_snapshots) / len(recent_snapshots)
        avg_memory = sum(s.memory_mb for s in recent_snapshots) / len(recent_snapshots)
        max_cpu = max(s.cpu_percent for s in recent_snapshots)
        max_memory = max(s.memory_mb for s in recent_snapshots)

        # Identify potential bottlenecks
        bottlenecks = []

        if avg_cpu > 80:
            bottlenecks.append(
                {
                    "type": "cpu",
                    "severity": "high",
                    "message": ".1f",
                    "recommendation": "Consider optimizing CPU-intensive operations or scaling horizontally",
                }
            )
        elif avg_cpu > 60:
            bottlenecks.append(
                {
                    "type": "cpu",
                    "severity": "medium",
                    "message": ".1f",
                    "recommendation": "Monitor CPU usage and consider optimization opportunities",
                }
            )

        if avg_memory > 1024:  # 1GB
            bottlenecks.append(
                {
                    "type": "memory",
                    "severity": "high",
                    "message": ".1f",
                    "recommendation": "Check for memory leaks and optimize memory usage",
                }
            )
        elif avg_memory > 512:  # 512MB
            bottlenecks.append(
                {
                    "type": "memory",
                    "severity": "medium",
                    "message": ".1f",
                    "recommendation": "Monitor memory usage patterns",
                }
            )

        return {
            "analysis_period_hours": 1,
            "average_cpu_percent": round(avg_cpu, 1),
            "average_memory_mb": round(avg_memory, 1),
            "peak_cpu_percent": max_cpu,
            "peak_memory_mb": max_memory,
            "bottlenecks": bottlenecks,
            "recommendations": [
                (
                    "Enable memory tracing for detailed analysis"
                    if not self.is_tracing_memory
                    else None
                ),
                "Review recent performance snapshots for trends",
                "Check database query performance",
                "Consider implementing caching for frequently accessed data",
            ],
        }


# Global profiling service instance
profiling_service = ProfilingService()
