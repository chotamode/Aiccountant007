FROM python:3.12-slim

WORKDIR /app

RUN useradd -m -u 1000 appuser

COPY pyproject.toml .
RUN pip install --no-cache-dir ".[agents]"

COPY common/ common/
COPY seller/ seller/
COPY buyer/ buyer/
COPY data/ data/
COPY docs/ docs/
COPY scripts/ scripts/
COPY DESIGN.md .
COPY PRODUCT.md .

RUN mkdir -p buyer/state seller/state && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000 8001 8002

CMD ["python", "-m", "buyer.dashboard.app"]
