FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for spacy/torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the full CGC package (extraction code lives here)
COPY cgc/ ./cgc/
COPY pyproject.toml ./

# Copy relay-api as relay_api (underscore for Python imports)
COPY relay-api/ ./relay_api/

# Install CGC package and relay dependencies
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir -r relay_api/requirements.txt

# Download spacy model if needed
RUN python -c "import spacy; spacy.cli.download('en_core_web_sm')" 2>/dev/null || true

EXPOSE ${PORT:-8421}

CMD ["python", "-m", "relay_api.src.main"]
