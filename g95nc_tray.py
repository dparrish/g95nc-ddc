#!/usr/bin/env python3
"""Minimal KDE/Qt tray controller for Samsung Odyssey G95NC."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from g95nc_ddc import DdcError, Ddcutil, MODE_VALUES, SOUND_VALUES


class TrayController:
    """Small, Qt-independent action layer used by the tray UI and tests."""

    def __init__(self, ddc: Ddcutil):
        self.ddc = ddc

    def set_mode(self, mode: str) -> None:
        self.ddc.set(0xE2, MODE_VALUES[mode])

    def set_sound(self, source: str) -> None:
        self.ddc.set(0xE8, SOUND_VALUES[source])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KDE tray controller for Samsung Odyssey G95NC")
    parser.add_argument("--display", type=int, help="ddcutil display number (1-based)")
    parser.add_argument("--bus", type=int, help="I2C bus number instead of a ddcutil display number")
    parser.add_argument("--ddcutil", default="ddcutil", help="ddcutil executable (default: ddcutil)")
    return parser


def load_qt():
    try:
        from PySide6.QtGui import QAction, QIcon
        from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QStyle, QSystemTrayIcon
    except ImportError as exc:
        raise RuntimeError("the tray requires PySide6; install with: python3 -m pip install '.[tray]'") from exc
    return QApplication, QAction, QIcon, QMenu, QMessageBox, QStyle, QSystemTrayIcon


def run_tray(controller: TrayController, argv: Sequence[str] | None = None) -> int:
    QApplication, QAction, QIcon, QMenu, QMessageBox, QStyle, QSystemTrayIcon = load_qt()
    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "G95NC tray", "No system tray is available in this desktop session.")
        return 2

    icon = QIcon.fromTheme("video-display")
    if icon.isNull():
        icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

    tray = QSystemTrayIcon(icon)
    tray.setToolTip("Samsung Odyssey G95NC")
    menu = QMenu()

    title = QAction("Samsung Odyssey G95NC", menu)
    title.setEnabled(False)
    menu.addAction(title)
    menu.addSeparator()

    mode_menu = menu.addMenu("PBP mode")
    mode_actions: dict[str, QAction] = {}
    mode_group = mode_menu.addAction("PBP last")
    mode_off = mode_menu.addAction("Off")
    mode_actions["pbp-last"] = mode_group
    mode_actions["off"] = mode_off
    for action in mode_actions.values():
        action.setCheckable(True)
    mode_group.setChecked(True)

    sound_menu = menu.addMenu("Sound source")
    sound_actions: dict[str, QAction] = {}
    for key, label in (("screen1", "Screen 1 / main"), ("screen2", "Screen 2 / sub")):
        action = sound_menu.addAction(label)
        action.setCheckable(True)
        sound_actions[key] = action
    sound_actions["screen1"].setChecked(True)

    menu.addSeparator()
    quit_action = menu.addAction("Quit")
    menu.addSeparator()
    status_action = menu.addAction("Status unavailable")
    status_action.setEnabled(False)
    tray.setContextMenu(menu)

    def notify(title_text: str, message: str, error: bool = False) -> None:
        if error:
            tray.showMessage(title_text, message, QSystemTrayIcon.MessageIcon.Critical, 5000)
        else:
            tray.showMessage(title_text, message, QSystemTrayIcon.MessageIcon.Information, 2500)

    def perform(action: QAction, operation: Callable[[], None], label: str) -> None:
        try:
            operation()
        except (DdcError, KeyError, ValueError) as exc:
            action.setChecked(False)
            notify("G95NC command failed", str(exc), error=True)
            return
        for candidate in mode_actions.values():
            if candidate is not action:
                candidate.setChecked(False)
        for candidate in sound_actions.values():
            if candidate is not action:
                candidate.setChecked(False)
        action.setChecked(True)
        status_action.setText(label)
        notify("G95NC updated", label)

    mode_group.triggered.connect(lambda checked=False: perform(mode_group, lambda: controller.set_mode("pbp-last"), "PBP last"))
    mode_off.triggered.connect(lambda checked=False: perform(mode_off, lambda: controller.set_mode("off"), "PBP off"))
    sound_actions["screen1"].triggered.connect(lambda checked=False: perform(sound_actions["screen1"], lambda: controller.set_sound("screen1"), "Sound: screen 1"))
    sound_actions["screen2"].triggered.connect(lambda checked=False: perform(sound_actions["screen2"], lambda: controller.set_sound("screen2"), "Sound: screen 2"))
    quit_action.triggered.connect(app.quit)

    tray.show()
    return app.exec()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        controller = TrayController(Ddcutil(args.ddcutil, args.display, args.bus))
        return run_tray(controller, argv)
    except (DdcError, RuntimeError, ValueError) as exc:
        print(f"g95nc-tray: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
