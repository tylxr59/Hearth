#!/bin/sh
# Public source only. No recovered libraries or private archive enters this build.
set -eu
export ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabi-
export KBUILD_BUILD_USER=hearth KBUILD_BUILD_HOST=isolated-builder
export KBUILD_BUILD_TIMESTAMP='Fri Oct 30 00:00:00 UTC 2026'
export SOURCE_DATE_EPOCH=1793318400
cd /work
mkdir -p artifacts
"${CROSS_COMPILE}gcc" -Os -Wall -Wextra -Werror -fomit-frame-pointer \
  -fno-builtin -fno-stack-protector -ffreestanding -nostdlib -static \
  -marm -march=armv7-a -Wl,-e,_start -Wl,--build-id=none \
  -o root/init fallback-init.c
cd src/Dev/linux
make gtvhacker_defconfig
python3 /work/probe_configure.py
python3 /work/tls_configure.py
make oldconfig </dev/null
python3 /work/tls_configure.py --verify
make -j4 uImage
cp arch/arm/boot/uImage /work/artifacts/kernel.uImage
cp .config /work/artifacts/kernel.config
cp /work/root/init /work/artifacts/fallback-init
