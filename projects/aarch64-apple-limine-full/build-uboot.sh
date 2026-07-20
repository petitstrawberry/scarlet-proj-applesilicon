#!/bin/sh
set -e

BASE="$(cd "$(dirname "$0")" && pwd)"
UBOOT="$BASE/u-boot"
M1N1="$BASE/m1n1"
PATCH_DIR="$BASE/patches/u-boot"
UBOOT_BASE_COMMIT="8aa706b2daa49b64102e44067d8514de8a26dc42"
M1N1_BASE_COMMIT="e132477af421247dbdad654e527ff230c0abfb71"

IMAGE="${UBOOT}/u-boot-nodtb.bin"
PAYLOAD_BUILDER="$BASE/tools/apple_boot_payload.py"

actual_commit="$(git -C "$UBOOT" rev-parse HEAD)"
if [ "$actual_commit" != "$UBOOT_BASE_COMMIT" ]; then
  echo "Unsupported U-Boot commit: $actual_commit" >&2
  echo "Expected: $UBOOT_BASE_COMMIT" >&2
  exit 1
fi

actual_m1n1_commit="$(git -C "$M1N1" rev-parse HEAD)"
if [ "$actual_m1n1_commit" != "$M1N1_BASE_COMMIT" ]; then
  echo "Unsupported m1n1 commit: $actual_m1n1_commit" >&2
  echo "Expected: $M1N1_BASE_COMMIT" >&2
  exit 1
fi

if [ ! -f "$M1N1/rust/vendor/rust-fatfs/Cargo.toml" ]; then
  echo "m1n1 nested submodules are missing" >&2
  echo "Run: git submodule update --init --recursive" >&2
  exit 1
fi

echo "Building m1n1 payload from $actual_m1n1_commit..."
m1n1_version="$(git -C "$M1N1" rev-parse --short=7 HEAD)"
M1N1_VERSION_TAG="$m1n1_version" \
  make -C "$M1N1" TOOLCHAIN= LLDDIR= BUILDSTD=1 build/m1n1.bin

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

for machine in "$@"; do
  echo "Generating boot-${machine}.bin..."
  payload="$(python3 "$PAYLOAD_BUILDER" compose --project "$BASE" --machine "$machine")"
  if [ -n "${SCARLET_AVD_INFO_JSON:-}" ]; then
    echo "Patching boot-${machine}.bin with Apple AVD nodes..."
    python3 "$BASE/tools/apple_avd_dtb.py" patch-payload \
      --info-json "$SCARLET_AVD_INFO_JSON" \
      --input "$payload" \
      --output "$payload" \
      --m1n1-bin "$M1N1/build/m1n1.bin"
    python3 "$PAYLOAD_BUILDER" record-patched \
      --project "$BASE" \
      --machine "$machine" \
      --info-json "$SCARLET_AVD_INFO_JSON"
  fi
done
