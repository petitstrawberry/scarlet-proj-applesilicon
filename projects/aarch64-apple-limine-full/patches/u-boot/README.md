# U-Boot patches

These patches apply to AsahiLinux U-Boot commit
`8aa706b2daa49b64102e44067d8514de8a26dc42`.

`0001-apple-m1-boot-ram-backed-scarlet-image.patch` restores the local
Apple M1 boot configuration that existed before the U-Boot tree was converted
to a submodule. The deployment runner writes the complete Scarlet Limine UEFI
image to physical address `0x900000000`. U-Boot exposes up to 1 GiB of that
memory as a block device, loads `BOOTAA64.EFI`, and passes the live FDT to
Limine. Limine then loads the kernel and initramfs from the same in-memory
image.

The patch is derived from the project's former U-Boot working-tree diff and is
distributed under U-Boot's applicable GPL-2.0-or-later terms.
