# Reproducible verification and offline developer sandbox container for teleionlabs-teleion-fabric.
# Runs public-safety, architecture, index parity, documentation, unit checks, and the
# two-worker local sandbox smoke test offline with zero cloud credentials.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . /workspace

RUN make check && python3 -m sandbox.worker_smoke

CMD ["python3", "-m", "sandbox.worker_smoke"]
