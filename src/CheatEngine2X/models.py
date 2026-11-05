"""Core data models for Cheat Engine 2X."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, IntFlag
import re


class Access(IntFlag):
    NONE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 4


@dataclass
class Process:
    pid: int
    name: str
    path: str = ""
    access: Access = Access.READ
    modules: list[str] = field(default_factory=list)

    def enumerate_regions(self, base: int, size: int) -> list[MemoryRegion]:
        from .process_manager import enumerate_regions as _en
        return _en(self.pid, base, size)

    @property
    def display(self) -> str:
        return f"{self.name} ({self.pid})"

    @property
    def short_name(self) -> str:
        return self.name.split(".exe", 1)[0]

    def __hash__(self):
        return hash((self.pid, self.name))


@dataclass
class MemoryRegion:
    address: int
    size: int
    protect: int
    state: int
    type_: int
    access: Access
    path: str = ""          # module path for named regions
    label: str = ""

    @property
    def base(self) -> int:
        return self.address

    @property
    def end(self) -> int:
        return self.address + self.size - 1

    def __lt__(self, other: MemoryRegion) -> bool:
        return self.address < other.address


@dataclass
class ScanFilter(Enum):
    EQUAL = "Equals"
    NOT_EQUAL = "Not equal"
    GREATER = "Greater than"
    LESS = "Less than"
    RANGE = "Between"
    CHANGE = "Changed"
    PATTERN = "Pattern"
    BYTE_PATTERN = "Byte pattern"
    INC_INCREMENT = "Inc/Increment"
    REGEX = "Regular expression"


@dataclass
class ScanResult:
    index: int
    value: int
    address: int
    module: str = ""
    pointer_path: list[str] = field(default_factory=list)
    changed: bool = False
    type_name: str = ""

    def __lt__(self, other: ScanResult) -> bool:
        return self.address < other.address


@dataclass
class AOBPattern:
    bytes: bytes
    value: int | None = None
    size: int = 0
    offset: int = 0

    @property
    def hex(self) -> str:
        return self.bytes.hex()


@dataclass
class FreezeEntry:
    """One address a user has pinned into the freeze list."""

    address: int
    value: int
    module: str = ""
    original_value: int = 0
    active: bool = True
    changes: int = 0

    def __post_init__(self) -> None:
        # snapshot the current value so we can 'restore' later
        self.original_value = self.value


@dataclass
class ScanStatistics:
    started: int = 0
    finished: int = 0
    scanned: int = 0
    found: int = 0
    target_address: int | None = None
