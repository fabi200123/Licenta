# ---- Base image ----
FROM python:3.10-slim

# ---- 1. System-level dependencies ----
# Some Python packages (e.g., SimpleITK, scikit-image) require build tools or system libs.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        libgl1   \
        libglib2.0-0      \
        libsm6            \
        libxext6          \
        libxrender1       && \
    rm -rf /var/lib/apt/lists/*

# ---- 2. Set up working directory ----
WORKDIR /app/Dash-App

# ---- 3. Copy only requirements first (to leverage layer caching) ----
COPY requirements.txt /app/Dash-App/requirements.txt

# ---- 4. Install Python dependencies ----
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- 5. Copy application code ----
# (Assumes your .py files, and maybe a 'static/' folder if you want a baked-in default.)
COPY . /app/Dash-App

# ---- 6. Expose port ----
EXPOSE 3001

# ---- 7. Entrypoint ----
# Use gunicorn for production-grade serving (4 workers by default)
CMD ["python", "dash-app-dynamic.py"]
