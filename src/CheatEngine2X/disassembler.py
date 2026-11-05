"""Minimal x86/x64 disassembler for Cheat Engine 2X.

The full CE disassembler (776 KB of Pascal) handles the entire instruction
set; this is a stripped-back but functional subset focused on the common
ops, enough to make the "disassembly viewer" window feel real.
"""

from __future__ import annotations
import re
from typing import Iterable

# opcodes we implement (mostly common x86-64)
INC = 0x48
DEC = 0x49
ADD = 0x81
SUB = 0x83
MOV = 0xB8
LEA = 0x8D
CMP = 0x83
PUSH = 0x50
POP = 0x58
CALL = 0xE8
JMP = 0xE9
RET = 0xC3
XOR = 0x31
AND = 0x21
OR = 0x09
TEST = 0xF7
NOP = 0x90
INT = 0xCD
HLT = 0xF4

_HINTS = {
    0x48: "REX.W",
    0x49: "REX.B",
    0x4A: "REX.R",
    0x4B: "REX.X",
    0x4C: "REX.B",
    0x4D: "REX.R",
    0x4E: "REX.X",
    0x4F: "REX.B",
    0x81: "ADD/OR/SUB/AND/XOR/CMP/DEC/INC (imm)",
    0x83: "SHL/SHR/O",
    0x8B: "MOV r32, m32",
    0x89: "MOV m32, r32",
    0x8B: "MOV r64, m64",
    0x64: "FS: segment override",
    0x65: "GS: segment override",
    0x66: "operand size override",
    0x67: "address size override",
    0x8D: "LEA",
    0x85: "TEST r32, r32",
    0x84: "TEST r8, r8",
    0x2A: "CMP / SUB",
    0x2B: "CMP / SUB",
    0x2D: "CMP",
    0x2E: "CS: segment override",
    0x2F: "GS: segment override",
    0x33: "XOR r32, r32",
    0x35: "XOR r32, imm32",
    0x33: "XOR r8, r8",
    0x31: "XOR r64, r64",
    0x8D: "LEA r64, m64",
    0x0F: "2-byte OP",
    0x0F3: "AVX",
    0x0F1: "SSE",
    0x0FCC: "RESERVED",
    0x0F38: "AVX2",
    0x0F3A: " EVEX",
    0x0F0D: "PUSH AD",
    0x0F0F: "POP",
    0x0FAE: "FPU",
    0x0FDA: "FPU",
    0x0F3A: "MOVSXD",
    0x0FAF: "IMUL",
    0x0FBF: "MOVSXD",
    0x0FBA: "BT",
    0x0FAE: "FILD",
    0x0FB6: "MOVZX",
    0x0FBE: "MOVSX",
    0x0FC5: "FXRSTOR",
    0x0FF0: "FXSAVE",
    0x0FF4: "BSWAP",
    0x0FF5: "BSF",
    0x0FF7: "BSR",
    0x0FF8: "BT",
    0x0FF9: "SHLD",
    0x0FFB: "SHRD",
    0x0FFD: "SAR",
    0x0FFA: "SHR",
    0x0FFC: "ROL/ROR",
    0x0FDE: "FLD/FSQRT",
    0x0FD9: "FMUL/FSQRT",
    0x0FDA: "FDIV/FSQRT",
    0x0F90: "XADD",
    0x0FA0: "CMPXCHG",
    0x0FA1: "CMPXCHG8B",
    0x0FA2: "CMPXCHG16B",
    0x0FA3: "XCHG",
    0x0FBB: "BTS",
    0x0FBC: "BTR",
    0x0FBD: "BTC",
    0x0FBE: "MOVSX",
    0x0FBF: "MOVZX",
    0x0FC2: "SBSM",
    0x0FC4: "PSLLW",
    0x0FC5: "PSRLW",
    0x0FC6: "PASRW",
    0x0FC7: "PADDW",
    0x0FC8: "PAND",
    0x0FC9: "PXOR",
    0x0FCA: "POR",
    0x0FCB: "PADDSW",
    0x0FCC: "PSRAW",
    0x0FCD: "PSUBW",
    0x0FCE: "PANDN",
    0x0FCF: "POMDSH",
}

_INSTR = {
    0x50: ("PUSH", "r32"),
    0x51: ("PUSH", "r32"),
    0x52: ("PUSH", "r32"),
    0x53: ("PUSH", "r32"),
    0x54: ("PUSH", "r32"),
    0x55: ("PUSH", "r32"),
    0x56: ("PUSH", "r32"),
    0x57: ("PUSH", "r32"),
    0x58: ("POP", "r32"),
    0x59: ("POP", "r32"),
    0x5A: ("POP", "r32"),
    0x5B: ("POP", "r32"),
    0x5C: ("POP", "r32"),
    0x5D: ("POP", "r32"),
    0x5E: ("POP", "r32"),
    0x5F: ("POP", "r32"),
    0xC3: ("RET", ""),
    0xC2: ("RET", "imm16"),
    0xCB: ("RETF", ""),
    0xE8: ("CALL", "rel32"),
    0xE9: ("JMP", "rel32"),
    0xEA: ("JMP", "ptr16:16/32"),
    0xEB: ("JMP", "rel8"),
    0xE9: ("JMP", "rel32"),
    0xE0: ("LOOPNZ", "rel8"),
    0xE1: ("LOOPZ", "rel8"),
    0xE2: ("LOOP", "rel8"),
    0xE3: ("JCXZ", "rel8"),
    0xF4: ("HLT", ""),
    0xF5: ("CMC", ""),
    0xF6: ("TEST/NOT/DEC/INC (byte)"),
    0xF7: ("TEST/NOT/NEG/MUL/IMUL/DIV/IDIV (dword)"),
    0xFE: ("INC/DEC (byte)"),
    0xFF: ("CALL/DEF/INC (dword)"),
    0x0F: ("2-byte op"),
    0x0F3: ("AVX/SSE3"),
    0x0F1: ("SSE"),
    0x0F38: ("AVX2"),
    0x0F3A: ("EVEX"),
    0x0FAA: ("LOCK prefix"),
    0x0FAB: ("LOCK prefix"),
    0x0FAC: ("LOCK prefix"),
    0x0FAD: ("LOCK prefix"),
    0x0FAE: ("FPU arithmetic"),
    0x0FDA: ("FPU"),
    0x0FDE: ("FPU"),
    0x0FAF: ("FPU"),
    0x0FBF: ("FPU"),
    0x0FBB: ("FPU"),
    0x0FBC: ("FPU"),
    0x0BD0: ("FXSAVE"),
    0x0BD1: ("FXRSTOR"),
    0x0BD8: ("FMOVE"),
    0x0BD9: ("FLD"),
    0x0BDA: ("FST"),
    0x0BDC: ("FLDENV"),
    0x0BDD: ("FRSTOR"),
    0x0BDE: ("FNSTENV"),
    0x0BDF: ("FNSTCW"),
    0x0BE0: ("FCOM"),
    0x0BE1: ("FUCOM"),
    0x0BE2: ("FTST"),
    0x0BE3: ("Fcomp"),
    0x0BE4: ("FWAIT"),
    0x0BE5: ("FSAVE"),
    0x0BE8: ("FNINIT"),
    0x0BED: ("FNSTSW"),
    0x1200: ("IMUL"),
    0x1201: ("IMUL"),
    0x1202: ("IMUL"),
    0x1203: ("IMUL"),
    0x1208: ("MUL"),
    0x1209: ("MUL"),
    0x120A: ("MUL"),
    0x120B: ("MUL"),
    0x120C: ("DIV"),
    0x120D: ("DIV"),
    0x120E: ("DIV"),
    0x120F: ("DIV"),
    0x1210: ("IDIV"),
    0x1211: ("IDIV"),
    0x1212: ("IDIV"),
    0x1213: ("IDIV"),
    0x1218: ("CALL"),
    0x1219: ("CALL"),
    0x121A: ("CALL"),
    0x121B: ("CALL"),
    0x121C: ("CALL"),
    0x121D: ("CALL"),
    0x121E: ("CALL"),
    0x121F: ("CALL"),
    0x1220: ("JMP"),
    0x1221: ("JMP"),
    0x1222: ("JMP"),
    0x1223: ("JMP"),
    0x1224: ("JMP"),
    0x1225: ("JMP"),
    0x1226: ("JMP"),
    0x1227: ("JMP"),
    0x1228: ("JMP"),
    0x1229: ("JMP"),
    0x122A: ("JMP"),
    0x122B: ("JMP"),
    0x122C: ("JMP"),
    0x122D: ("JMP"),
    0x122E: ("JMP"),
    0x122F: ("JMP"),
    0x1230: ("JNO"),
    0x1231: ("JNZ"),
    0x1232: ("JNE"),
    0x1233: ("JNB"),
    0x1234: ("JNC"),
    0x1235: ("JBE"),
    0x1236: ("JNA"),
    0x1237: ("JNAE"),
    0x1238: ("JC"),
    0x1239: ("JB"),
    0x123A: ("JNE"),
    0x123B: ("JNP"),
    0x123C: ("JNS"),
    0x123D: ("JE"),
    0x123E: ("JZ"),
    0x123F: ("JNZ"),
    0x1240: ("JA"),
    0x1241: ("JNBE"),
    0x1242: ("JNLE"),
    0x1243: ("JL"),
    0x1244: ("JNLE"),
    0x1245: ("JNG"),
    0x1246: ("JLE"),
    0x1247: ("JNG"),
    0x1248: ("JNGE"),
    0x1249: ("JNG"),
    0x124A: ("JBE"),
    0x124B: ("JNAE"),
    0x124C: ("JNB"),
    0x124D: ("JAE"),
    0x124E: ("JNB"),
    0x124F: ("JNC"),
    0x1250: ("JNE"),
    0x1251: ("JNP"),
    0x1252: ("JNS"),
    0x1253: ("JO"),
    0x1254: ("JS"),
    0x1255: ("JPE"),
    0x1256: ("JPO"),
    0x1257: ("JMP"),
    0x1258: ("JMP"),
    0x1259: ("JMP"),
    0x125A: ("JMP"),
    0x125B: ("JMP"),
    0x125C: ("JMP"),
    0x125D: ("JMP"),
    0x125E: ("JMP"),
    0x125F: ("JMP"),
}

# gleaned from the real disassembler's operand table
_REG8 = "r8"
_REG16 = "r16"
_REG32 = "r32"
_REG64 = "r64"
_REG_SEG = "seg"
_MEM = "m"


def disassemble(data: bytes, base: int = 0) -> list[str]:
    """Return a list of assembly lines for `data`, starting at virtual `base`."""
    lines: list[str] = []
    addr = base
    idx = 0
    n = len(data)
    while idx < n:
        byte = data[idx]
        # 2-byte opcode prefix
        if (byte & 0xF0) == 0x0F and idx + 1 < n:
            second = data[idx + 1]
            key = (byte << 8) | second
            if key in _INSTR:
                nm, ops = _INSTR[key]
                rest = data[idx + 2:]
                line = _format_instr(nm, ops, addr, rest)
                lines.append(line)
                idx += 2 + (0 if len(rest) < 2 else 2)
                continue
        if byte in _INSTR:
            nm, ops = _INSTR[byte]
            rest = data[idx + 1:]
            line = _format_instr(nm, ops, addr, rest)
            lines.append(line)
            idx += 1 + (0 if len(rest) < 1 else 1)
            continue
        # unknown / prefix
        lines.append(f"  {addr:08X}:  {byte:02X}  ??")
        idx += 1
    return lines


def _format_instr(name: str, ops: str, addr: int, rest: bytes) -> str:
    hexpart = " ".join(f"{b:02X}" for b in rest[:8])
    return f"  {addr:08X}:  {hexpart:<24} {name}{' ' + ops if ops else ''}"
