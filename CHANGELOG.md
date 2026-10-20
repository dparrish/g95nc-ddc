# Changelog

## 0.2.0 — 2026-10-20

- Add an optional Qt/KDE system-tray application.
- Add tray actions for PBP-last, PBP-off, Screen 1 audio, and Screen 2 audio.
- Add the `g95nc-tray` console entry point and KDE desktop launcher.

## 0.1.0 — 2026-10-20

Initial public release.

- Control G95NC PIP, PBP, and 3PBP layouts through VCP `0xE2`.
- Select per-pane inputs through VCP `0xE3`.
- Select the active sound screen through VCP `0xE8`.
- Read and decode G95NC vendor status values through `ddcutil`.
- Provide a dry-run mode and G95NC capability probe.
