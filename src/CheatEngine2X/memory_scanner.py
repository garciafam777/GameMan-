"""memory_scanner.py -- numpy-accelerated address scanner for Cheat Engine 2X.

Drop-in reference for src/CheatEngine2X/memory_scanner.py.

Why this exists: the pure-Python scanner applies filters in bytecode -- one
comparison per value in a multi-GB address space means minutes-to-hours.
This version does the comparisons in numpy (C speed) and batches reads:

  * first scan : chunked ReadProcessMemory (default 8 MB per call; syscall
                 overhead dominates below ~1 MB), whole-chunk vector compare.
  * next scan  : previous results are grouped into runs of nearby addresses
                 (default: within 4 KB) and re-read with ONE call per run,
                 instead of one call per result. This matters once you are
                 down from 4M hits to 10k -- and it keeps first-scan speed
                 from collapsing on the second pass.
  * alignment  : fast (aligned) scan reads one value per stride; "all" scan
                 does one pass per byte offset. Aligned is ~4x less work for
                 4-byte values and finds what you want ~always -- games
                 store typed values aligned.

Threading: first_scan/next_scan are blocking. Run them in a QThread and
drive them through cancel()/set_progress_cb(); wire the progress callback to
a Qt signal.

Map ScanFilter to your models.ScanFilter as needed; semantics follow CE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

DEFAULT_CHUNK = 8 * 1024 * 1024          # 8 MB RPM chunks for value scans
DEFAULT_AOB_CHUNK = 1024 * 1024          # 1 MB for AOB (sliding window memory)
GROUP_DISTANCE = 4096                    # next-scan batching radius


class ValueType(Enum):
    INT8 = np.int8
    UINT8 = np.uint8
    INT16 = np.int16
    UINT16 = np.uint16
    INT32 = np.int32
    UINT32 = np.uint32
    INT64 = np.int64
    UINT64 = np.uint64
    FLOAT = np.float32
    DOUBLE = np.float64

    @property
    def dtype(self) -> np.dtype:
        return np.dtype(self.value)

    @property
    def itemsize(self) -> int:
        return self.dtype.itemsize


class ScanFilter(Enum):
    # first scan
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    GREATER = "greater"
    LESS = "less"
    RANGE = "range"
    # next scan only (compare against previous values)
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    INCREASED = "increased"
    DECREASED = "decreased"
    INCREASED_BY = "increased_by"
    DECREASED_BY = "decreased_by"


NEXT_SCAN_FILTERS = frozenset({
    ScanFilter.CHANGED, ScanFilter.UNCHANGED, ScanFilter.INCREASED,
    ScanFilter.DECREASED, ScanFilter.INCREASED_BY, ScanFilter.DECREASED_BY,
})


@dataclass
class ScanSummary:
    found: int
    regions_scanned: int
    bytes_scanned: int
    cancelled: bool = False


ProgressCb = Callable[[int, int], None]   # (bytes_scanned, total_bytes)
ReadFn = Callable[[int, int], bytes]      # (address, size) -> bytes


class MemoryScanner:
    def __init__(self, read: ReadFn, regions: Sequence,
                 value_type: ValueType = ValueType.INT32,
                 aligned: bool = True, chunk: int = DEFAULT_CHUNK):
        self._read = read
        self._regions = list(regions)
        self.value_type = value_type
        self.aligned = aligned
        self.chunk = chunk
        self.addresses: Optional[np.ndarray] = None   # uint64
        self.values: Optional[np.ndarray] = None      # value_type dtype
        self._cancelled = False
        self._progress_cb: Optional[ProgressCb] = None

    # -- control -------------------------------------------------------
    def set_progress_cb(self, cb: Optional[ProgressCb]):
        self._progress_cb = cb

    def cancel(self):
        self._cancelled = True

    def reset(self):
        self.addresses = None
        self.values = None
        self._cancelled = False

    @property
    def result_count(self) -> int:
        return 0 if self.addresses is None else int(self.addresses.size)

    # -- scans ----------------------------------------------------------
    def first_scan(self, filter: ScanFilter, value=None, value2=None,
                   ) -> ScanSummary:
        if filter in NEXT_SCAN_FILTERS:
            raise ValueError(f"{filter.value} requires a previous scan")
        self._cancelled = False
        dtype = self.value_type.dtype
        isz = self.value_type.itemsize
        addrs_all: List[np.ndarray] = []
        vals_all: List[np.ndarray] = []
        scanned = regions_done = 0
        total = sum(r.size for r in self._regions)

        for region in self._regions:
            if self._cancelled:
                break
            base, end = region.address, region.end
            while base < end:
                if self._cancelled:
                    break
                size = min(self.chunk, end - base)
                data = self._read(base, size)
                scanned += len(data)
                if len(data) >= isz:
                    offsets = range(0, 1 if self.aligned else isz)
                    for off in offsets:
                        n = (len(data) - off) // isz
                        if n <= 0:
                            continue
                        vals = np.frombuffer(data, dtype=dtype,
                                             count=n, offset=off)
                        mask = self._match(vals, filter, value, value2)
                        if mask.any():
                            idx = np.nonzero(mask)[0].astype(np.uint64)
                            addrs_all.append(idx * isz + off + base)
                            vals_all.append(vals[mask])
                base += size
                self._tick(scanned, total)
            regions_done += 1

        if addrs_all:
            self.addresses = np.concatenate(addrs_all)
            self.values = np.concatenate(vals_all)
        else:
            self.addresses = np.empty(0, dtype=np.uint64)
            self.values = np.empty(0, dtype=dtype)
        return ScanSummary(self.result_count, regions_done, scanned,
                           self._cancelled)

    def next_scan(self, filter: ScanFilter, value=None,
                  value2=None) -> ScanSummary:
        if self.addresses is None:
            raise RuntimeError("next_scan before first_scan")
        self._cancelled = False
        old_addrs = self.addresses
        old_vals = self.values
        new_vals, valid = self._read_values_at(old_addrs)

        if filter in (ScanFilter.INCREASED_BY, ScanFilter.DECREASED_BY):
            delta = np.float64(value)
            diff = new_vals.astype(np.float64) - old_vals.astype(np.float64)
            mask = (diff > delta if filter is ScanFilter.INCREASED_BY
                    else diff < delta) & valid
        else:
            mask = self._match(new_vals, filter, value, value2,
                               old_vals=old_vals) & valid

        self.addresses = old_addrs[mask]
        self.values = new_vals[mask]
        return ScanSummary(self.result_count, 0, 0, self._cancelled)

    # -- internals ------------------------------------------------------
    def _match(self, vals, filter, value, value2=None,
               old_vals=None) -> np.ndarray:
        if filter is ScanFilter.EQUAL:
            return vals == self._cast(value)
        if filter is ScanFilter.NOT_EQUAL:
            return vals != self._cast(value)
        if filter is ScanFilter.GREATER:
            return vals > self._cast(value)
        if filter is ScanFilter.LESS:
            return vals < self._cast(value)
        if filter is ScanFilter.RANGE:
            return (vals >= self._cast(value)) & (vals <= self._cast(value2))
        if filter is ScanFilter.CHANGED:
            return vals != old_vals
        if filter is ScanFilter.UNCHANGED:
            return vals == old_vals
        if filter is ScanFilter.INCREASED:
            return vals > old_vals
        if filter is ScanFilter.DECREASED:
            return vals < old_vals
        raise ValueError(f"unsupported filter {filter}")

    def _cast(self, v):
        return np.array([v], dtype=self.value_type.dtype)[0]

    def _read_values_at(self, addrs: np.ndarray
                        ) -> Tuple[np.ndarray, np.ndarray]:
        """Batch-re-read values at previously found addresses. Addresses that
        fall in the same 4 KB neighborhood are fetched with a single read.
        Returns (values, valid_mask); addresses that could not be re-read
        (unmapped mid-scan, partial tail) come back invalid and are dropped
        from the results by the caller."""
        isz = self.value_type.itemsize
        dtype = self.value_type.dtype
        out = np.empty(len(addrs), dtype=dtype)
        valid = np.zeros(len(addrs), dtype=bool)
        order = np.argsort(addrs)
        s = addrs[order]
        i = 0
        while i < len(s):
            if self._cancelled:
                break
            j = i
            run_end = int(s[i]) + isz
            while (j + 1 < len(s)
                   and int(s[j + 1]) - (int(s[j]) + isz) <= GROUP_DISTANCE):
                j += 1
                run_end = max(run_end, int(s[j]) + isz)
            data = self._read(int(s[i]), run_end - int(s[i]))
            if data:
                buf = np.frombuffer(data, dtype=np.uint8)
                off = (s[i:j + 1] - s[i]).astype(np.int64)
                ok = off + isz <= len(buf)
                if ok.any():
                    win = sliding_window_view(buf, isz)
                    rows = np.ascontiguousarray(win[off[ok]])
                    out[order[i:j + 1][ok]] = rows.view(dtype).reshape(-1)
                    valid[order[i:j + 1][ok]] = True
            i = j + 1
        return out, valid

    def _tick(self, done: int, total: int):
        if self._progress_cb:
            self._progress_cb(done, total)


# ---------------------------------------------------------------------------
# AOB scan (numpy sliding window)
# ---------------------------------------------------------------------------

def parse_aob(pattern: str) -> List[Optional[int]]:
    """'FF 00 ?? 99' -> [0xFF, 0x00, None, 0x99]. Also accepts '?' wildcards."""
    toks = pattern.replace("??", "?").split()
    out: List[Optional[int]] = []
    for t in toks:
        if t == "?":
            out.append(None)
        elif re.fullmatch(r"[0-9A-Fa-f]{2}", t):
            out.append(int(t, 16))
        else:
            raise ValueError(f"bad AOB token: {t!r}")
    return out


def aob_scan(read: ReadFn, regions: Sequence, pattern: str,
             chunk: int = DEFAULT_AOB_CHUNK,
             progress: Optional[ProgressCb] = None,
             cancel: Optional[Callable[[], bool]] = None,
             ) -> np.ndarray:
    """Return uint64 array of match addresses. Chunks overlap by len(pattern)-1
    so matches crossing chunk boundaries are not missed."""
    pat_list = parse_aob(pattern)
    plen = len(pat_list)
    pat = np.array([p if p is not None else 0 for p in pat_list], np.uint8)
    mask = np.array([p is not None for p in pat_list], bool)
    hits_all: List[np.ndarray] = []
    scanned = total = 0
    total = sum(r.size for r in regions)

    for region in regions:
        base, end = region.address, region.end
        while base < end:
            if cancel and cancel():
                return np.concatenate(hits_all) if hits_all else \
                    np.empty(0, np.uint64)
            size = min(chunk + plen - 1, end - base)
            data = read(base, size)
            if len(data) >= plen:
                buf = np.frombuffer(data, dtype=np.uint8)
                win = sliding_window_view(buf, plen)   # (n, plen) view
                hit = (win[:, mask] == pat[mask]).all(axis=1)
                idx = np.nonzero(hit)[0]
                if idx.size:
                    hits_all.append(idx.astype(np.uint64) + base)
            scanned += len(data)
            if progress:
                progress(scanned, total)
            base += chunk   # overlap = plen-1 carried into next read
    if not hits_all:
        return np.empty(0, np.uint64)
    return np.unique(np.concatenate(hits_all))


# ---------------------------------------------------------------------------
# Demo: scan our own process for a known value
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import ctypes
    from ctypes import wintypes

    secret = ctypes.c_int32(1337)   # lives on this process's heap/stack
    addr = ctypes.addressof(secret)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID,
                                           wintypes.LPVOID, ctypes.c_size_t,
                                           ctypes.POINTER(ctypes.c_size_t)]
    kernel32.ReadProcessMemory.restype = wintypes.BOOL

    h = kernel32.OpenProcess(0x0410, False, os.getpid())  # QUERY|READ

    def read(a, s):
        buf = (ctypes.c_char * s)()
        n = ctypes.c_size_t(0)
        kernel32.ReadProcessMemory(h, a, buf, s, ctypes.byref(n))
        return buf.raw[:n.value]

    # walk our own regions; for the demo just scan a window around the known
    # address (replace with enumerate_regions for a real target).
    lo, hi = addr - (1 << 20), addr + (1 << 20)
    from types import SimpleNamespace
    regions = [SimpleNamespace(address=lo, end=hi, size=hi - lo)]
    sc = MemoryScanner(read, regions, ValueType.INT32, aligned=False, chunk=1 << 20)
    summary = sc.first_scan(ScanFilter.EQUAL, 1337)
    print(f"first scan: {summary.found} hits, expected >= 1")
    print(f"known address 0x{addr:x} present: "
          f"{np.any(sc.addresses == addr)}")
    secret.value = 7331
    summary2 = sc.next_scan(ScanFilter.EQUAL, 7331)
    print(f"next scan after change: {summary2.found} hits, "
          f"known address present: {np.any(sc.addresses == addr)}")
    print(aob_scan(read, regions, "39 05").size >= 0)  # demo call
