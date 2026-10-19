import unittest
from unittest.mock import patch

from g95nc_ddc import Ddcutil, VcpValue, build_parser, cmd_pip, cmd_sound, parse_terse_line


class ParseTests(unittest.TestCase):
    def test_simple_value(self):
        value = parse_terse_line("VCP 60 SNC x12")
        self.assertEqual(value, VcpValue(0x60, 0x12, "SNC", "VCP 60 SNC x12"))

    def test_complex_value_uses_current_bytes(self):
        value = parse_terse_line("VCP E2 CNC x00 x7f x39 x05")
        self.assertEqual(value.value, 0x3905)
    def test_sound_value_uses_current_byte_pair(self):
        value = parse_terse_line("VCP E8 CNC x00 x02 x00 x01")
        self.assertEqual(value.value, 0x0001)


    def test_unsupported_feature_is_error(self):
        with self.assertRaises(RuntimeError):
            parse_terse_line("VCP E2 ERR")


class CommandTests(unittest.TestCase):
    def test_pip_writes_sources_then_mode(self):
        ddc = Ddcutil("ddcutil", display=1)
        with patch.object(ddc, "set", return_value=None) as write:
            cmd_pip(ddc, "hdmi1", "hdmi2", False)
        self.assertEqual([call.args[:2] for call in write.call_args_list], [(0xE3, 0x0000), (0xE3, 0x0101), (0xE2, 0x0010)])

    def test_dry_run_does_not_write(self):
        ddc = Ddcutil("ddcutil", display=1)
        with patch.object(ddc, "set") as write:
            cmd_pip(ddc, "hdmi1", "hdmi2", True)
        write.assert_not_called()
    def test_sound_writes_e8(self):
        ddc = Ddcutil("ddcutil", display=1)
        with patch.object(ddc, "set", return_value=None) as write:
            cmd_sound(ddc, "sub", False)
        write.assert_called_once_with(0xE8, 0x0001)

    def test_display_and_bus_are_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            Ddcutil(display=1, bus=4)

    def test_cli_accepts_pip(self):
        args = build_parser().parse_args(["--display", "1", "pip", "hdmi1", "dp"])
        self.assertEqual((args.command, args.main, args.sub), ("pip", "hdmi1", "dp"))
    def test_cli_accepts_sound(self):
        args = build_parser().parse_args(["--display", "1", "sound", "screen2"])
        self.assertEqual((args.command, args.source), ("sound", "screen2"))


if __name__ == "__main__":
    unittest.main()
