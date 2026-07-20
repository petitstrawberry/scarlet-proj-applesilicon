#!/bin/sh
set -e

BASE="$(cd "$(dirname "$0")" && pwd)"
UBOOT="$BASE/u-boot"
M1N1="$BASE/m1n1"
PATCH_DIR="$BASE/patches/u-boot"
UBOOT_BASE_COMMIT="8aa706b2daa49b64102e44067d8514de8a26dc42"

IMAGE="${UBOOT}/u-boot-nodtb.bin"
PAYLOADS="$M1N1/payloads"

actual_commit="$(git -C "$UBOOT" rev-parse HEAD)"
if [ "$actual_commit" != "$UBOOT_BASE_COMMIT" ]; then
  echo "Unsupported U-Boot commit: $actual_commit" >&2
  echo "Expected: $UBOOT_BASE_COMMIT" >&2
  exit 1
fi

for patch in "$PATCH_DIR"/*.patch; do
  [ -e "$patch" ] || continue
  if git -C "$UBOOT" apply --reverse --check "$patch" >/dev/null 2>&1; then
    echo "U-Boot patch already applied: $(basename "$patch")"
  elif git -C "$UBOOT" apply --check "$patch"; then
    echo "Applying U-Boot patch: $(basename "$patch")"
    git -C "$UBOOT" apply "$patch"
  else
    echo "U-Boot patch does not apply cleanly: $patch" >&2
    exit 1
  fi
done

docker run --rm -v "$UBOOT":/work -w /work ubuntu:24.04 bash -c '
  apt-get update -qq && apt-get install -y -qq build-essential bc bison flex libssl-dev libgnutls28-dev python3 device-tree-compiler >/dev/null 2>&1 &&
  make apple_m1_defconfig &&
  make -j$(nproc)
'

if ! strings "$IMAGE" | grep -Fq \
  'bootcmd=blkmap create s; blkmap map s 0 0x200000 mem 0x900000000;'; then
  echo "Built U-Boot does not contain the Scarlet RAM-backed boot command" >&2
  exit 1
fi

cp "$IMAGE" "$PAYLOADS/u-boot-nodtb.bin"
gzip -kf "$PAYLOADS/u-boot-nodtb.bin"

for machine in "$@"; do
  echo "Generating boot-${machine}.bin..."
  python3 "$M1N1/make-boot.py" "$machine"
  if [ -n "${SCARLET_AVD_INFO_JSON:-}" ]; then
    echo "Patching boot-${machine}.bin with Apple AVD nodes..."
    python3 "$BASE/tools/apple_avd_dtb.py" patch-payload \
      --info-json "$SCARLET_AVD_INFO_JSON" \
      --input "$PAYLOADS/boot-${machine}.bin" \
      --output "$PAYLOADS/boot-${machine}.bin" \
      --m1n1-bin "$PAYLOADS/m1n1.bin"
  fi
done
