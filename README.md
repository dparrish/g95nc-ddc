# Samsung Odyssey G95NC Linux PIP/PBP control

This is a small Linux command-line controller for the Samsung Odyssey Neo G9
57-inch (G95NC). It uses the monitor's DDC/CI interface through `ddcutil`;
there is no Samsung application or USB upstream connection required.

## What was reverse engineered

The Samsung Display Manager sends three undocumented VCP features:

| VCP | Write value | Meaning |
|---|---:|---|
| `0xE2` | `0x00` | single source / leave PIP or PBP |
| `0xE2` | `0x03` | two-way PBP, 50/50 |
| `0xE2` | `0x04` | two-way approximately 21:9 |
| `0xE2` | `0x06`–`0x09` | 3PBP layouts |
| `0xE2` | `0x10` | PIP |
| `0xE3` | `(pane << 8) \| source` | pane input; pane 0=main, 1=PIP/middle, 2=right |
| `0xE8` | `0x00`–`0x02` | select the screen whose audio is used |

`0xE3` source values are `0x00` HDMI 1, `0x01` HDMI 2, `0x02` HDMI 3,
and `0x10` DisplayPort. The normal input-source VCP `0x60` is also usable for
switching the whole monitor: on the tested 1009.2 firmware, DP=`0x0F`, HDMI 1
=`0x11`, HDMI 2=`0x12`, and HDMI 3=`0x32`.

The important readback caveat is that `getvcp E2` returns a status encoding,
not the command value. ddcutil's `CNC` response format is
`maximum-high maximum-low current-high current-low`; for example,
`VCP E2 CNC x00 x7f x39 x05` means current status `0x3905`, not `0x007f`.
The controller sends vendor writes with ddcutil verification disabled and
reports the raw readback rather than comparing it to the command.

### Firmware compatibility

The protocol is confirmed on firmware `M-C9557GGPA-1009.2`. Reports indicate
that `1007.0` does not expose `E2`/`E3`; firmware `1008.2` is unknown.
Firmware behavior can vary, so treat this as a capability probe rather than
a model-name-only assumption.

## Install

Install the package with Python's standard packaging tools:

```sh
python3 -m pip install .
```

The installed command is `g95nc-ddc`. The runtime prerequisite is still the
system `ddcutil` executable, plus the Linux `i2c-dev` kernel module and
read/write access to the corresponding `/dev/i2c-*` device. On many
distributions the ddcutil package's udev rule grants access after replugging
the display or logging in again. Confirm the bus with:

```sh
ddcutil detect
```

## Usage

```sh
# After pip installation:
g95nc-ddc --display 1 status
g95nc-ddc --display 1 probe

# From a source checkout, replace `g95nc-ddc` with `./g95nc_ddc.py`.

# Main HDMI 1, PIP HDMI 2.
g95nc-ddc --display 1 pip hdmi1 hdmi2

# Select the screen used for audio. In PIP/PBP, screen1/main=0 and
# screen2/sub=1. Value 2 is available for the third screen in 3PBP.
g95nc-ddc --display 1 sound screen2
g95nc-ddc --display 1 sound 0

# Change only the PIP pane (channel 1).
g95nc-ddc --display 1 pane pip dp

# Exit PIP/PBP.
g95nc-ddc --display 1 mode off

# Preview a command without touching the monitor.
g95nc-ddc --display 1 --dry-run sound screen2
```

If display numbering is unstable, use `--bus N` from `ddcutil detect` instead.
A layout change can briefly interrupt DDC while the monitor re-enumerates; wait
for the display to settle before issuing the next command.

## Safety and limitations

- `probe` checks the G95NC-specific `0x39xx` E2 status family. Do not use the
  tool against an unrecognized display.
- Input switching is inherently disruptive: after switching the whole monitor
  with VCP `0x60`, DDC on the old active link may disappear. Send the command
  through the currently active connection.
- The tool does not infer the monitor's firmware or recover from a link that
  has disappeared. Use the OSD to recover if a firmware variant rejects a
  command.
- No display-control operation was exercised on this workstation because
  `/dev/i2c-*` is absent and loading `i2c-dev` is not permitted in the current
  environment.

Protocol sources: the Samsung Display Manager trace and replay implementation
in [mwd102/g95nc-ddc](https://github.com/mwd102/g95nc-ddc), plus the
[ddcutil issue documenting the G95NC codes](https://github.com/rockowitz/ddcutil/issues/397).
