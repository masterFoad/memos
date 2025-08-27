FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tini ca-certificates iproute2 procps net-tools && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv && . /opt/venv/bin/activate && \
    pip install -U pip wheel setuptools uv rich && \
    pip install requests psycopg2-binary redis pyjwt cryptography

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    RUNNER_SOCK=/run/runner.sock

COPY runner.py /opt/runner.py

ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["python","/opt/runner.py"]
