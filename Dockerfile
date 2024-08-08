FROM python:3.11-slim

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the Backend and Frontend directories
COPY Backend /app/Backend
COPY Frontend /app/Frontend

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r Backend/requirements.txt

EXPOSE 8502

# Run the Streamlit app
CMD ["streamlit", "run", "--server.port", "8502", "Backend/app.py"]