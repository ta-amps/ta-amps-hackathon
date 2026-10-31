# Reproducible verification container for ta-amps-hackathon.
# Runs public-safety, architecture, index parity, documentation, and unit checks offline.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . /workspace

RUN make check

CMD ["make", "check"]
