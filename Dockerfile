FROM debian:bookworm

RUN apt-get update && \
    apt-get install -y \
    frr \
    iproute2 \
    iputils-ping \
    traceroute \
    procps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

CMD ["sleep", "infinity"]