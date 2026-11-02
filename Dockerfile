FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml requirements.txt ./
COPY tansaku ./tansaku
COPY README.md ./README.md

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install .

COPY config.example.yaml team.example.json knowledge-base.example.json ./

CMD ["tansaku", "run"]
