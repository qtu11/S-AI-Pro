"""
System Monitor — CPU, RAM, GPU metrics collector.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import time
import threading
from typing import Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class SystemMetrics:
    """Snapshot metrics hệ thống."""
    cpu_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    ram_percent: float = 0.0
    gpu_name: str = ""
    gpu_vram_used_mb: float = 0.0
    gpu_vram_total_mb: float = 0.0
    gpu_percent: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    network_latency_ms: Dict[str, float] = field(default_factory=dict)
    agent_loop_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class SystemMonitor:
    """Theo dõi tài nguyên hệ thống real-time."""

    def __init__(self):
        self._metrics = SystemMetrics()
        self._history: List[SystemMetrics] = []
        self._max_history = 120  # ~2 phút nếu poll 1s/lần
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._psutil_available = False

        try:
            import psutil
            self._psutil_available = True
        except ImportError:
            pass

    def start(self, interval: float = 2.0):
        """Bắt đầu monitor thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop, args=(interval,), daemon=True
        )
        self._thread.start()

    def stop(self):
        self._running = False

    def get_metrics(self) -> dict:
        """Lấy metrics hiện tại dạng dict."""
        m = self._metrics
        return {
            "cpu": round(m.cpu_percent, 1),
            "ram": {
                "used_gb": round(m.ram_used_gb, 1),
                "total_gb": round(m.ram_total_gb, 1),
                "percent": round(m.ram_percent, 1),
            },
            "gpu": {
                "name": m.gpu_name,
                "vram_used_mb": round(m.gpu_vram_used_mb, 0),
                "vram_total_mb": round(m.gpu_vram_total_mb, 0),
                "percent": round(m.gpu_percent, 1),
            } if m.gpu_name else None,
            "timestamp": int(m.timestamp * 1000),
        }

    def get_history(self, last_n: int = 60) -> list:
        """Lấy lịch sử metrics."""
        return [
            {
                "cpu": round(m.cpu_percent, 1),
                "ram": round(m.ram_percent, 1),
                "ts": int(m.timestamp * 1000),
            }
            for m in self._history[-last_n:]
        ]

    def _monitor_loop(self, interval: float):
        while self._running:
            try:
                self._collect()
            except Exception:
                pass
            time.sleep(interval)

    def _collect(self):
        m = SystemMetrics()

        if self._psutil_available:
            import psutil

            # CPU
            m.cpu_percent = psutil.cpu_percent(interval=0.5)

            # RAM
            ram = psutil.virtual_memory()
            m.ram_total_gb = ram.total / (1024 ** 3)
            m.ram_used_gb = ram.used / (1024 ** 3)
            m.ram_percent = ram.percent

            # Disk
            try:
                disk = psutil.disk_usage("/")
                m.disk_total_gb = disk.total / (1024 ** 3)
                m.disk_used_gb = disk.used / (1024 ** 3)
            except Exception:
                pass
        else:
            # Fallback: basic OS info
            try:
                import platform
                if platform.system() == "Windows":
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    c_ularge = ctypes.c_ulonglong
                    free = c_ularge()
                    total = c_ularge()
                    kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(total))
                    m.ram_total_gb = total.value / (1024 * 1024)
            except Exception:
                m.ram_total_gb = 16.0  # Default assumption

        # GPU (NVIDIA)
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 4:
                    m.gpu_name = parts[0].strip()
                    m.gpu_vram_used_mb = float(parts[1].strip())
                    m.gpu_vram_total_mb = float(parts[2].strip())
                    m.gpu_percent = float(parts[3].strip())
        except Exception:
            pass

        m.timestamp = time.time()
        self._metrics = m
        self._history.append(m)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]


# Singleton
system_monitor = SystemMonitor()
