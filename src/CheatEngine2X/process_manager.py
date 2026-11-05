"""process_manager.py -- corrected Windows process/memory layer for Cheat Engine 2X.

The authoritative corrected version (see AppData/Local/hermes/composer-pastes).
Drop-in replacement for src/CheatEngine2X/process_manager.py.

Key fixes vs. the original:
  * Every HANDLE/pointer-returning kernel32/psapi function gets an explicit
    restype. The "OpenProcess returns None" bug was ctypes defaulting
    restype to c_int, which TRUNCATES 64-bit handles. Same class of bug
    hit EnumProcessModules (HMODULE array) and VirtualQueryEx.
  * EnumProcessModules uses a sized-buffer loop instead of a fixed guess.
  * write_process_memory wraps writes in VirtualProtectEx
    (PAGE_EXECUTE_READWRITE) and restores the original protection, so
    writes to code pages work when elevated. This helper is also the
    foundation for the future "restore original bytes" injection lifecycle.
  * enumerate_regions walks the full 64-bit user address space via
    VirtualQueryEx and skips guard/no-access pages.

Notes:
  * Use 64-bit Python to inspect 64-bit processes.
  * Reading memory of another process at the same integrity level is fine;
    writing usually needs the app run as administrator.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from enum import IntFlag
from typing import List, Optional

import os
import shlex
shell32 = ctypes.WinDLL("shell32")

# Elevation helpers
def is_elevated() -> bool:
    """Return True if the current process is running as Administrator."""
    try:
        return shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_elevation() -> bool:
    """Relaunch this process with administrator privileges.

    Returns True when a new elevated instance was launched successfully
    (the caller should exit). The original instance is replaced via the
    'runas' verb, so the user never sees two windows."""
    try:
        exe = os.path.abspath(sys.argv[0])
        args = " ".join(shlex.quote(a) for a in sys.argv[1:])
        h_inst = shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
        return h_inst is not None and int(h_inst) > 32
    except Exception:
        return False

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

# ---------------------------------------------------------------------------
# Signatures -- the audit that fixes the None/[] bugs.
# ---------------------------------------------------------------------------

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wintypes.BOOL

kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID,
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.WriteProcessMemory.restype = wintypes.BOOL

kernel32.VirtualProtectEx.argtypes = [
    wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t,
    wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
kernel32.VirtualProtectEx.restype = wintypes.BOOL

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    """Matches the 64-bit layout; c_void_p/c_size_t sized with the interpreter."""
    _fields_ = [
        ("BaseAddress", wintypes.LPVOID),
        ("AllocationBase", wintypes.LPVOID),
        ("AllocationProtect", wintypes.DWORD),
        ("__alignment1", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("__alignment2", wintypes.DWORD),
    ]


kernel32.VirtualQueryEx.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID,
    ctypes.POINTER(MEMORY_BASIC_INFORMATION),
    ctypes.c_size_t]
kernel32.VirtualQueryEx.restype = ctypes.c_size_t

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

psapi.EnumProcessModules.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE),
    wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
psapi.EnumProcessModules.restype = wintypes.BOOL

psapi.GetModuleFileNameExW.argtypes = [
    wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
psapi.GetModuleFileNameExW.restype = wintypes.DWORD

psapi.GetModuleBaseNameW.argtypes = [
    wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
psapi.GetModuleBaseNameW.restype = wintypes.DWORD

TH32CS_SNAPPROCESS = 0x00000002

kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ULONG_PTR),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


# ---------------------------------------------------------------------------
# Constants and protection mapping
# ---------------------------------------------------------------------------

PROCESS_TERMINATE = 0x0001
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

PROCESS_READ = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
PROCESS_WRITE = PROCESS_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000

MEM_PRIVATE = 0x20000
MEM_MAPPED = 0x40000
MEM_IMAGE = 0x1000000

PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD = 0x100

INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


class Access(IntFlag):
    NONE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 4


def prot_to_access(protect: int) -> Access:
    """Map a page-protection flag to the Access enum. Guard pages excluded
    (reads against them fail)."""
    if protect & PAGE_GUARD:
        return Access.NONE
    p = protect & 0xFF
    access = Access.NONE
    if p in (PAGE_READONLY, PAGE_READWRITE, PAGE_WRITECOPY):
        access |= Access.READ
    if p in (PAGE_READWRITE, PAGE_WRITECOPY,
             PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY):
        access |= Access.READ | Access.WRITE
    if p in (PAGE_EXECUTE, PAGE_EXECUTE_READ,
             PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY):
        access |= Access.EXECUTE
        if p in (PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE,
                 PAGE_EXECUTE_WRITECOPY):
            access |= Access.READ
    return access


# ---------------------------------------------------------------------------
# Data model (kept compatible with models.py)
# ---------------------------------------------------------------------------

@dataclass
class Module:
    base: int
    size: int = 0
    name: str = ""
    path: str = ""


@dataclass
class MemoryRegion:
    address: int
    size: int
    protect: int
    state: int
    type: int
    access: Access
    module_path: str = ""
    label: str = ""

    @property
    def end(self) -> int:
        return self.address + self.size


@dataclass
class Process:
    pid: int
    name: str
    path: str = ""
    handle: Optional[int] = field(default=None, repr=False)

    # -- lifecycle -----------------------------------------------------
    @classmethod
    def open(cls, pid: int, access: int = PROCESS_READ, write: bool = False):
        """Open a handle to `pid`.

        write=False (default): read-only access (safe for any process).
        write=True: adds PROCESS_VM_WRITE|PROCESS_VM_OPERATION. Writing to
        another process requires Administrator elevation - if the app isn't
        elevated and write is requested, PermissionError is raised so the UI
        can prompt for elevation via request_elevation()."""
        if write and not is_elevated():
            raise PermissionError(
                "Write access requires Administrator. Re-launch as Administrator "
                "to edit memory / use the freeze list.")
        effective = access
        if write:
            effective = PROCESS_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        h = kernel32.OpenProcess(effective, False, pid)
        if not h:
            raise ctypes.WinError(ctypes.get_last_error())
        return cls(pid=pid, name="", path="", handle=h)

    def close(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- memory --------------------------------------------------------
    def read(self, address: int, size: int) -> bytes:
        return read_process_memory(self.handle, address, size)

    def write(self, address: int, data: bytes) -> int:
        return write_process_memory(self.handle, address, data)

    def regions(self) -> List[MemoryRegion]:
        return enumerate_regions(self.handle)

    def modules(self) -> List[Module]:
        return list_modules(self.handle)


# ---------------------------------------------------------------------------
# Process enumeration
# ---------------------------------------------------------------------------

def list_processes() -> List[Process]:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    processes: List[Process] = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
            while True:
                processes.append(Process(pid=entry.th32ProcessID,
                                         name=entry.szExeFile))
                if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return processes


# ---------------------------------------------------------------------------
# Raw memory primitives
# ---------------------------------------------------------------------------

def read_process_memory(handle, address: int, size: int) -> bytes:
    """Read up to `size` bytes. Returns fewer on partial reads (region edges),
    empty bytes on total failure -- scanners should tolerate this."""
    buf = (ctypes.c_char * max(1, size))()
    n = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(handle, address, buf, size,
                                    ctypes.byref(n))
    if not ok:
        if n.value == 0:
            return b""
        # partial read: n holds what was actually read on some paths;
        # if not, fall through to buffer length
    return buf.raw[:n.value if n.value else (size if ok else 0)]


def write_process_memory(handle, address: int, data: bytes) -> int:
    """Write with protection flip. Raises on hard failure. Returns bytes written.

    VirtualProtectEx(PAGE_EXECUTE_READWRITE) makes this work on code pages;
    the original protection is restored in a finally block. Save the original
    bytes yourself if you need a 'disable patch' feature later."""
    size = len(data)
    old_protect = wintypes.DWORD()
    if not kernel32.VirtualProtectEx(handle, address, size,
                                     PAGE_EXECUTE_READWRITE,
                                     ctypes.byref(old_protect)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        n = ctypes.c_size_t(0)
        if not kernel32.WriteProcessMemory(handle, address, data, size,
                                           ctypes.byref(n)):
            raise ctypes.WinError(ctypes.get_last_error())
        return n.value
    finally:
        tmp = wintypes.DWORD()
        kernel32.VirtualProtectEx(handle, address, size, old_protect.value,
                                  ctypes.byref(tmp))


# ---------------------------------------------------------------------------
# Regions and modules
# ---------------------------------------------------------------------------

MAX_USER_ADDRESS = 0x00007FFFFFFFFFFF  # x64 user space


def enumerate_regions(handle, skip_no_access: bool = True) -> List[MemoryRegion]:
    """Walk the address space with VirtualQueryEx. Committed, readable pages
    only (guard pages skipped)."""
    regions: List[MemoryRegion] = []
    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    while address <= MAX_USER_ADDRESS:
        ret = kernel32.VirtualQueryEx(
            handle, address, ctypes.byref(mbi), ctypes.sizeof(mbi))
        if ret == 0:
            break
        base = mbi.BaseAddress or 0
        access = prot_to_access(mbi.Protect)
        if mbi.State == MEM_COMMIT and (not skip_no_access
                                        or access != Access.NONE):
            regions.append(MemoryRegion(
                address=base,
                size=mbi.RegionSize,
                protect=mbi.Protect,
                state=mbi.State,
                type=mbi.Type,
                access=access,
            ))
        nxt = base + mbi.RegionSize
        if nxt <= address:  # paranoia guard against wraparound
            break
        address = nxt
    return regions


def list_modules(handle) -> List[Module]:
    """Sized-buffer loop -- handles any module count."""
    needed = wintypes.DWORD(0)
    # first call: ask how big the buffer must be
    psapi.EnumProcessModules(handle, None, 0, ctypes.byref(needed))
    count = needed.value // ctypes.sizeof(wintypes.HMODULE)
    if count == 0:
        return []
    arr = (wintypes.HMODULE * count)()
    if not psapi.EnumProcessModules(handle, arr, needed, ctypes.byref(needed)):
        raise ctypes.WinError(ctypes.get_last_error())
    modules: List[Module] = []
    for i in range(needed.value // ctypes.sizeof(wintypes.HMODULE)):
        hmod = arr[i]
        path_buf = ctypes.create_unicode_buffer(260)
        name_buf = ctypes.create_unicode_buffer(260)
        psapi.GetModuleFileNameExW(handle, hmod, path_buf, 260)
        psapi.GetModuleBaseNameW(handle, hmod, name_buf, 260)
        modules.append(Module(base=int(hmod), name=name_buf.value,
                              path=path_buf.value))
    return modules


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    procs = list_processes()
    print(f"{len(procs)} processes")
    for p in procs[:5]:
        print(f"  {p.pid:>6}  {p.name}")
    me = next((p for p in procs if p.pid == 0), None)  # just listing here
    print("Opening current process for a self-read demo...")
    with Process.open(__import__("os").getpid()) as proc:
        regs = proc.regions()
        print(f"  regions: {len(regs)}")
        mods = proc.modules()
        print(f"  modules: {len(mods)} (first: {mods[0].name if mods else '-'})")
