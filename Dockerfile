FROM debian:bookworm

RUN apt-get update && \
    apt-get install -y \
    python3 \
    frr \
    iperf3 \
    tcpdump \
    iproute2 \
    iputils-ping \
    traceroute \
    procps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

CMD ["sleep", "infinity"]