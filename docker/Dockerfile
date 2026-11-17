FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY packages ./packages
COPY adapters ./adapters

RUN pip install --no-cache-dir .

EXPOSE 8000

# Runs the local API only. Scanning stays read-only inside the container.
CMD ["agentfence", "dashboard", "--host", "0.0.0.0", "--port", "8000"]
