# Contributing

Thanks for helping improve G95NC support.

## Development

The project has no runtime Python dependencies. Run the test suite from the
repository root:

```sh
python3 -m unittest -v
python3 -m py_compile g95nc_ddc.py test_g95nc_ddc.py
```

Use `--dry-run` for CLI experiments. Do not send unverified VCP writes to a
monitor model that has not passed `g95nc-ddc probe`.

## Protocol reports

When reporting a firmware-specific result, include:

- the monitor firmware version;
- the connection type and active input;
- the raw `ddcutil --terse getvcp` response;
- the exact command sent and its observable result.

Never include serial numbers, EDIDs, or other identifying information unless
redacted.
