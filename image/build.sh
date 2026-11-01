#!/bin/sh
# Build the Home Base SD card image with pi-gen in Docker.
# Output: image/deploy/homebase-<date>.img.xz
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
WORK="$HERE/work"
PIGEN="$WORK/pi-gen"
PIGEN_REF=${PIGEN_REF:-arm64}

mkdir -p "$WORK"
if [ ! -d "$PIGEN" ]; then
  git clone --depth 1 -b "$PIGEN_REF" https://github.com/RPi-Distro/pi-gen.git "$PIGEN"
fi

# Fresh copy of the Home Base stage and source
rm -rf "$PIGEN/stage-homebase"
cp -r "$HERE/stage-homebase" "$PIGEN/stage-homebase"
mkdir -p "$PIGEN/stage-homebase/00-install/files/homebase"
for d in backend ui chromium-ext bin system; do
  cp -r "$ROOT/$d" "$PIGEN/stage-homebase/00-install/files/homebase/$d"
done
touch "$PIGEN/stage2/SKIP_IMAGES"

# A throwaway password satisfies pi-gen; the account is locked again in stage-homebase.
cp "$HERE/config" "$PIGEN/config"
printf 'FIRST_USER_PASS=%s\n' "$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)" >> "$PIGEN/config"

cd "$PIGEN"
CONTINUE=${CONTINUE:-0} PRESERVE_CONTAINER=${PRESERVE_CONTAINER:-0} ./build-docker.sh

mkdir -p "$HERE/deploy"
cp "$PIGEN"/deploy/*homebase*.img.xz "$HERE/deploy/"
ls -lh "$HERE/deploy"
