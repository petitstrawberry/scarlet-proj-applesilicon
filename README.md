# scarlet-proj-applesilicon

Apple Silicon support for the [Scarlet](https://github.com/petitstrawberry/Scarlet) operating system.

This repository is a standalone cargo-scarlet project that adds Apple Silicon
(M1/T8103/T8112/...) bring-up support to Scarlet. It is licensed under the GNU
General Public License v2 (GPL-2.0-only) because it ships vendored or derived
code from U-Boot, m1n1, and AsahiLinux, all of which are GPL-2.0 lineage.

## What lives here

- `projects/aarch64-apple-limine-full/` — cargo-scarlet project manifest, BSP
  package, m1n1/U-Boot submodules, deploy tooling
- `drivers/` — Apple-specific driver crates (AIC, DART, PMGR, RTKit, ASC, DCP,
  AVD, MCA, ADMAC, PCIe, DWC3, ATCPHY, S5L UART, etc.) plus the Apple SoC
  cpufreq driver extracted from the kernel
- `firmware/apple-avd-fw-rs/` — firmware payload for the Apple AVD video
  decode coprocessor

## Build model

`scarlet-proj-applesilicon` is a standalone cargo-scarlet project. The Scarlet
kernel, scarlet-modules, and reusable filesystem bundles are pulled in via
pinned git dependencies — no sibling checkout of Scarlet is required.

Build with:

```bash
cargo scarlet update --project projects/aarch64-apple-limine-full
cargo scarlet image --project projects/aarch64-apple-limine-full
```

Deployment to Apple Silicon hardware requires m1n1 and a USB recovery
workflow. See [`projects/aarch64-apple-limine-full/DEPLOY.md`](projects/aarch64-apple-limine-full/DEPLOY.md)
for the full procedure.

## Status

Experimental bring-up. Hardware-specific rough edges. Pinned to a specific
Scarlet revision; advancing the Scarlet pin requires coordinated testing on
real Apple Silicon hardware.

## License

GPL-2.0-only. See [`LICENSE`](LICENSE).
