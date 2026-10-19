#!/usr/bin/env python3
"""Linux DDC/CI controller for Samsung Odyssey G95NC PIP/PBP modes.

The G95NC exposes its multi-input controls through vendor VCP features E2/E3.
This module deliberately delegates the low-level I2C/DDC framing to ddcutil,
which handles kernel driver quirks and DDC/CI timing.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Sequence

MODE_VALUES = {
    "off": 0x00,
    "pbp": 0x03,
    "pbp-last": 0x01,
    "pbp-large-left": 0x02,
    "pbp-21-9": 0x04,
    "pbp-uneven": 0x05,
    "3pbp-square": 0x06,
    "3pbp-left": 0x07,
    "3pbp-middle": 0x08,
    "3pbp-right": 0x09,
    "pip": 0x10,
}

MODE_NAMES = {
    0x3901: "pbp (2-way)",
    0x3905: "pbp (status 0x05)",
    0x3909: "3pbp-left",
    0x390B: "3pbp-middle",
    0x390D: "3pbp-right",
    0x390F: "pip",
    0x0000: "off",
}

SOURCE_VALUES = {
    "hdmi1": 0x00,
    "hdmi2": 0x01,
    "hdmi3": 0x02,
    "dp": 0x10,
    "displayport": 0x10,
}

PANE_VALUES = {"main": 0x00, "left": 0x00, "pip": 0x01, "middle": 0x01, "right": 0x02}
SOUND_VALUES = {
    "0": 0,
    "screen1": 0,
    "main": 0,
    "left": 0,
    "1": 1,
    "screen2": 1,
    "sub": 1,
    "middle": 1,
    "2": 2,
    "screen3": 2,
    "right": 2,
}

SOUND_NAMES = {0: "screen1/main", 1: "screen2/sub", 2: "screen3/right"}


class DdcError(RuntimeError):
    """Raised when ddcutil cannot complete a DDC/CI operation."""


@dataclass(frozen=True)
class VcpValue:
    code: int
    value: int
    kind: str
    raw: str


def parse_terse_line(line: str) -> VcpValue:
    """Parse one ddcutil ``--terse getvcp`` result line.

    ddcutil uses SNC for a one-byte non-continuous value and CNC for a
    four-byte response. For CNC, the first two bytes are the maximum and the
    last two bytes are the current value, so ``x00 x7f x39 x05`` becomes
    0x3905.
    """
    parts = line.split()
    if len(parts) < 3 or parts[0].upper() != "VCP":
        raise ValueError(f"not a terse VCP line: {line!r}")
    try:
        code = int(parts[1], 16)
    except ValueError as exc:
        raise ValueError(f"invalid VCP code in: {line!r}") from exc
    kind = parts[2].upper()
    if kind == "ERR":
        raise DdcError(f"VCP 0x{code:02X} is unsupported")
    if kind == "C":
        if len(parts) < 5:
            raise ValueError(f"missing continuous value in: {line!r}")
        value = int(parts[3], 10)
    elif kind == "SNC":
        value = int(parts[3].removeprefix("x"), 16)
    elif kind in {"CNC", "CND"}:
        values = [int(token.removeprefix("x"), 16) for token in parts[3:7]]
        if len(values) < 2:
            raise ValueError(f"missing complex value bytes in: {line!r}")
        value = (values[-2] << 8) | values[-1]
    elif kind == "T":
        value = int(parts[3].removeprefix("x"), 16)
    else:
        raise ValueError(f"unknown ddcutil value kind {kind!r}: {line!r}")
    return VcpValue(code=code, value=value, kind=kind, raw=line.strip())


def format_vcp(value: VcpValue | None) -> str:
    if value is None:
        return "unavailable"
    width = 4 if value.value > 0xFF else 2
    return f"0x{value.value:0{width}X}"


class Ddcutil:
    def __init__(self, executable: str = "ddcutil", display: int | None = None, bus: int | None = None):
        if display is not None and bus is not None:
            raise ValueError("choose --display or --bus, not both")
        self.executable = executable
        self.display = display
        self.bus = bus

    def _prefix(self) -> list[str]:
        prefix = [self.executable]
        if self.display is not None:
            prefix += ["--display", str(self.display)]
        if self.bus is not None:
            prefix += ["--bus", str(self.bus)]
        return prefix

    def run(self, args: Sequence[str]) -> str:
        if shutil.which(self.executable) is None and "/" not in self.executable:
            raise DdcError("ddcutil is not installed; install ddcutil and load the i2c-dev kernel module")
        command = self._prefix() + list(args)
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise DdcError(f"{' '.join(command)} failed ({result.returncode}): {detail}")
        return result.stdout

    def get(self, code: int) -> VcpValue:
        output = self.run(["--terse", "getvcp", f"0x{code:02X}"])
        for line in output.splitlines():
            if line.strip().upper().startswith("VCP "):
                value = parse_terse_line(line)
                if value.code == code:
                    return value
        raise DdcError(f"ddcutil returned no VCP 0x{code:02X} result")

    def set(self, code: int, value: int, *, verify_delay: float = 0.35) -> VcpValue | None:
        # E2 readback is a status encoding rather than the command value, and
        # E3/status and input switching may also legitimately differ. Avoid
        # ddcutil's equality verification and report the readback ourselves.
        self.run([
            "--noverify",
            "--permit-unknown-feature",
            "setvcp",
            f"0x{code:02X}",
            f"0x{value:04X}",
        ])
        if verify_delay:
            time.sleep(verify_delay)
        try:
            return self.get(code)
        except DdcError:
            return None


def mode_name(value: int) -> str:
    return MODE_NAMES.get(value, f"unknown (readback 0x{value:04X})")


def sound_name(value: int) -> str:
    return SOUND_NAMES.get(value, f"unknown screen (value 0x{value:04X})")


def require_choice(value: str, choices: dict[str, int], label: str) -> int:
    key = value.lower()
    if key not in choices:
        valid = ", ".join(sorted(choices))
        raise ValueError(f"invalid {label} {value!r}; choose one of: {valid}")
    return choices[key]


def write_vcp(ddc: Ddcutil, code: int, value: int, dry_run: bool) -> VcpValue | None:
    if dry_run:
        print(f"would set VCP 0x{code:02X} to 0x{value:04X}")
        return None
    result = ddc.set(code, value)
    readback = format_vcp(result)
    print(f"set VCP 0x{code:02X} to 0x{value:04X}; readback {readback}")
    return result


def cmd_status(ddc: Ddcutil) -> int:
    successes = 0
    for code, label in ((0xE2, "mode/layout"), (0xE3, "pane source"), (0xE8, "sound source"), (0x60, "input source")):
        try:
            value = ddc.get(code)
        except DdcError as exc:
            print(f"{label:<14} unavailable: {exc}", file=sys.stderr)
            continue
        successes += 1
        suffix = ""
        if code == 0xE2:
            suffix = f" ({mode_name(value.value)})"
        elif code == 0xE8:
            suffix = f" ({sound_name(value.value)})"
        print(f"{label:<14} {format_vcp(value)}{suffix} [{value.raw}]")
    return 0 if successes else 2


def cmd_probe(ddc: Ddcutil) -> int:
    try:
        value = ddc.get(0xE2)
    except DdcError as exc:
        print(f"G95NC probe failed: {exc}", file=sys.stderr)
        return 2
    if value.value == 0 or (value.value & 0xFF00) != 0x3900:
        print(f"VCP E2 readback {format_vcp(value)} is not the G95NC 0x39xx status family", file=sys.stderr)
        return 2
    print(f"G95NC detected: VCP E2 readback {format_vcp(value)} ({mode_name(value.value)})")
    return 0


def cmd_mode(ddc: Ddcutil, mode: str, dry_run: bool) -> int:
    value = require_choice(mode, MODE_VALUES, "mode")
    write_vcp(ddc, 0xE2, value, dry_run)
    return 0


def cmd_pane(ddc: Ddcutil, pane: str, source: str, dry_run: bool) -> int:
    channel = require_choice(pane, PANE_VALUES, "pane")
    source_value = require_choice(source, SOURCE_VALUES, "source")
    write_vcp(ddc, 0xE3, (channel << 8) | source_value, dry_run)
    return 0


def cmd_sound(ddc: Ddcutil, source: str, dry_run: bool) -> int:
    value = require_choice(source, SOUND_VALUES, "sound source")
    write_vcp(ddc, 0xE8, value, dry_run)
    return 0


def cmd_pip(ddc: Ddcutil, main: str, sub: str, dry_run: bool) -> int:
    # Program the sources before selecting PIP. This avoids briefly selecting
    # PIP with stale sources when the monitor was previously in PBP/3PBP.
    cmd_pane(ddc, "main", main, dry_run)
    cmd_pane(ddc, "pip", sub, dry_run)
    cmd_mode(ddc, "pip", dry_run)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control Samsung Odyssey G95NC PIP/PBP over Linux DDC/CI")
    target = parser.add_argument_group("monitor selection")
    target.add_argument("--display", type=int, help="ddcutil display number (1-based)")
    target.add_argument("--bus", type=int, help="I2C bus number instead of a ddcutil display number")
    parser.add_argument("--ddcutil", default="ddcutil", help="ddcutil executable (default: ddcutil)")
    parser.add_argument("--dry-run", action="store_true", help="print writes without sending them")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe", help="verify VCP E2 identifies a G95NC")
    sub.add_parser("status", help="read PIP/PBP and input VCP values")
    mode = sub.add_parser("mode", help="select a layout")
    mode.add_argument("value", choices=sorted(MODE_VALUES))
    pane = sub.add_parser("pane", help="select one pane's input")
    pane.add_argument("pane", choices=sorted(PANE_VALUES))
    pane.add_argument("source", choices=sorted(SOURCE_VALUES))
    pip = sub.add_parser("pip", help="set main and PIP inputs, then enable PIP")
    pip.add_argument("main", choices=sorted(SOURCE_VALUES))
    pip.add_argument("sub", choices=sorted(SOURCE_VALUES))
    sound = sub.add_parser("sound", help="select the screen used for audio")
    sound.add_argument("source", choices=sorted(SOUND_VALUES))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        ddc = Ddcutil(args.ddcutil, args.display, args.bus)
        if args.command == "probe":
            return cmd_probe(ddc)
        if args.command == "status":
            return cmd_status(ddc)
        if args.command == "mode":
            return cmd_mode(ddc, args.value, args.dry_run)
        if args.command == "pane":
            return cmd_pane(ddc, args.pane, args.source, args.dry_run)
        if args.command == "pip":
            return cmd_pip(ddc, args.main, args.sub, args.dry_run)
        if args.command == "sound":
            return cmd_sound(ddc, args.source, args.dry_run)
    except (DdcError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
