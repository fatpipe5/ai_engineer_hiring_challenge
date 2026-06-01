FROM python:3.13-slim
RUN pip install --no-cache-dir pandas==2.2.3 numpy==2.1.3
RUN useradd --create-home --uid 1000 sandboxuser
USER sandboxuser
WORKDIR /workspace