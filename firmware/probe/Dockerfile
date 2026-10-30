# Build environment only. No USB devices or owner material belong in this image.
FROM docker.io/library/ubuntu@sha256:c664f8f86ed5a386b0a340d981b8f81714e21a8b9c73f658c4bea56aa179d54a
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y --no-install-recommends \
    build-essential libc6:i386 libstdc++6:i386 zlib1g:i386 \
    cpio bzip2 bc perl python3 u-boot-tools libncurses5-dev \
    && rm -rf /var/lib/apt/lists/*
COPY toolchain.tar.bz2 /tmp/toolchain.tar.bz2
RUN echo 'd09f1580a9179a3c8346bde44d6c7d828937d7afcab0ec41207f24e65aa71dca  /tmp/toolchain.tar.bz2' | sha256sum -c - \
    && tar -xjf /tmp/toolchain.tar.bz2 -C /opt \
    && rm /tmp/toolchain.tar.bz2
ENV PATH=/opt/arm-2008q3/bin:$PATH
WORKDIR /work
CMD ["/bin/sh", "/work/build.sh"]
