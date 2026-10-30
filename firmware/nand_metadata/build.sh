#!/bin/sh
# Offline container build. Validated bootloaders/native loader were copied by staging.
set -eu
export ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabi-
export KBUILD_BUILD_USER=hearth KBUILD_BUILD_HOST=isolated-builder
export KBUILD_BUILD_TIMESTAMP='Fri Oct 30 00:00:00 UTC 2026'
export SOURCE_DATE_EPOCH=1793318400
cd /work
"${CROSS_COMPILE}gcc" -Os -Wall -Wextra -Werror -fomit-frame-pointer \
    -fno-builtin -fno-stack-protector -ffreestanding -nostdlib -static \
    -marm -march=armv7-a -Wl,-e,_start -Wl,--build-id=none \
    -o root/init probe-init.c
cd src/Dev/linux
make gtvhacker_defconfig
python3 /work/configure.py
make oldconfig </dev/null
python3 /work/configure.py --verify
make -j4 uImage
cp arch/arm/boot/uImage /work/artifacts/uImage
cp .config /work/artifacts/kernel.config
cp /work/root/init /work/artifacts/probe-init
cd /work/artifacts
sha256sum x-load-gen2.bin u-boot.bin uImage kernel.config probe-init omap_loader > SHA256SUMS
arm-none-linux-gnueabi-readelf -h -l probe-init > probe-init-elf.txt
