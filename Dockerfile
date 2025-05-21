FROM python:3.10-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt pyproject.toml ./

# Install system dependencies and Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir networkx torch transformers

# Copy the rest of the application
COPY . .

# Expose the port Gradio runs on
EXPOSE 7860

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Command to run the application
CMD ["python", "app.py"] 