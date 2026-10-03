# ==============================================================================
# OPTIONAL DEVELOPER / MANAGER DEPLOYMENT DOCKERFILE
# MFG Predictive Maintenance & OEE Command Center
# Note: Primary judge runtime is Snowflake Native Streamlit.
# This Docker container is for optional local development and integration testing.
# ==============================================================================

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY environment.yml requirements.txt* ./
RUN pip install --no-cache-dir \
    streamlit>=1.28.0 \
    snowflake-connector-python>=3.6.0 \
    snowflake-snowpark-python>=1.11.0 \
    pandas>=2.0.0 \
    plotly>=5.18.0 \
    requests>=2.31.0 \
    pytest>=7.4.0

COPY . /app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
