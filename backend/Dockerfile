FROM node:20-bookworm-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-bookworm-slim
WORKDIR /app

ENV NODE_ENV=production
ENV PYTHONPATH=/app/scripts:/app/scripts/precision-medicine-toolbox
ENV STATIC_DATA_PATH=/app/static

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    git \
    build-essential \
    cmake \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
  && rm -rf /var/lib/apt/lists/*

COPY scripts/requirements-processing.txt /tmp/requirements-processing.txt
RUN pip3 install --no-cache-dir --break-system-packages numpy && \
    pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements-processing.txt

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --from=build /app/dist ./dist
COPY scripts ./scripts

RUN git clone --depth 1 https://github.com/primakov/precision-medicine-toolbox.git /app/scripts/precision-medicine-toolbox

RUN mkdir -p /app/static

EXPOSE 5000
CMD ["node", "dist/server.js"]
