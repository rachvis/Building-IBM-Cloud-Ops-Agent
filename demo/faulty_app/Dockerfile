# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Faulty API Demo App
# ─────────────────────────────────────────────────────────────────────────────
# This builds the deliberately broken Flask app used in the
# IBM Cloud Ops Agent demo.
#
# Build:
#   docker build -t faulty-api:demo .
#
# Push to IBM Container Registry:
#   ibmcloud cr login
#   docker tag faulty-api:demo icr.io/<your-namespace>/faulty-api:demo
#   docker push icr.io/<your-namespace>/faulty-api:demo
#
# Or push to Docker Hub:
#   docker tag faulty-api:demo <your-dockerhub>/faulty-api:demo
#   docker push <your-dockerhub>/faulty-api:demo
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Don't buffer stdout — ensures logs appear immediately in Code Engine
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# ────────────────────────────────────────────────────────
# BUG 1 in action:
#   EXPOSE declares port 5000 (what the app actually binds)
#   but the Code Engine deployment will be set to port 3000.
#   This mismatch means Code Engine's proxy gets no response.
# ────────────────────────────────────────────────────────
EXPOSE 5000

CMD ["python", "app.py"]
