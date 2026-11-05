"""Pointer scanner: walk a pointer path to an address, then rescan.

Cheat Engine's pointer scanning follows a chain of addresses to reach the
target. This module implements the core chain-following algorithm.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable

from .models import ScanResult, ScanStatistics, Process
from .memory_scanner import MemoryScanner


@dataclass
class PointerPath:
    """A resolved pointer chain: start address + offsets."""
    name: str
    offsets: list[int] = field(default_factory=list)
    start_address: int = 0
    target_address: int = 0
    module: str = ""
    pointer_type: str = "auto"

    def resolve(self, proc: Process) -> int:
        if not self.offsets:
            return self.start_address
        addr = self.start_address
        for off in self.offsets:
            raw = proc.read_memory(addr, 8)
            if len(raw) < 8:
                return 0
            addr = int.from_bytes(raw, "little") + off
            if addr == 0 or addr > 0x7FFF00000000:
                return 0
        self.target_address = addr
        return addr

    def scan(self, proc: Process) -> list[ScanResult]:
        addr = self.resolve(proc)
        if not addr:
            return []
        return [ScanResult(0, 0, addr, module=self.module, pointer_path=self.offsets)]


# ---------------------------------------------------------------------------
# Pointer chain scanner
# ---------------------------------------------------------------------------
class PointerScanner:
    """Scan for pointer chains that lead to a target address."""

    def __init__(self, proc: Process, start_base: int, size: int,
                 target: int):
        self.proc = proc
        self.start_base = start_base
        self.size = size
        self.target = target
        self.statistics = ScanStatistics()
        self.results: list[PointerPath] = []

    def scan(self, max_depth: int = 6, max_chains: int = 200) -> list[PointerPath]:
        self.statistics.started = int(__import__("time").perf_counter() * 1000)
        self.results = []
        self._scan_depth(0, max_depth, max_chains)
        self.statistics.finished = int(__import__("time").perf_counter() * 1000)
        return list(self.results)

    def _scan_depth(self, depth: int, max_depth: int, max_chains: int) -> None:
        if depth >= max_depth or len(self.results) >= max_chains:
            return
        scanner = MemoryScanner(self.proc, self.start_base, self.size)
        for res in scanner.scan():
            if self._matches_target(res.address):
                p = PointerPath(
                    name=f"ptr_{depth}",
                    offsets=[res.address - (self.start_base + res.index)],
                    start_address=self.start_base + res.index,
                    module=res.module,
                )
                self.results.append(p)
                if len(self.results) >= max_chains:
                    return

    def _matches_target(self, addr: int) -> bool:
        return addr == self.target or self.target in (addr, addr + 1)


# ---------------------------------------------------------------------------
# AOB (array of bytes) scanner
# ---------------------------------------------------------------------------
class AOBScanner:
    """Scan for a byte pattern / array of bytes in a process's memory."""

    def __init__(self, proc: Process, base: int, size: int):
        self.proc = proc
        self.base = base
        self.size = size
        self.statistics = ScanStatistics()
        self.results: list[ScanResult] = []

    def scan(self, pattern: bytes, max_hits: int = 10_000) -> list[ScanResult]:
        self.statistics.started = int(__import__("time").perf_counter() * 1000)
        self.results = []
        if not pattern:
            self.statistics.finished = int(__import__("time").perf_counter() * 1000)
            return self.results
        scanner = MemoryScanner(self.proc, self.base, self.size)
        for res in scanner.scan():
            addr = res.address
            end = min(addr + len(pattern), self.base + self.size)
            chunk = self.proc.read_memory(addr, end - addr)
            if pattern in chunk:
                self.results.append(ScanResult(
                    index=len(self.results),
                    value=0,
                    address=addr,
                    module=res.module,
                ))
                if len(self.results) >= max_hits:
                    break
        self.statistics.finished = int(__import__("time").perf_counter() * 1000)
        return list(self.results)
