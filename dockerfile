FROM python:3.11-slim

# Install system dependencies needed by pygame/SDL and X11 forwarding
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-dev \
        libsdl2-dev \
        libsdl2-image-dev \
        libsdl2-mixer-dev \
        libsdl2-ttf-dev \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libffi-dev \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Allow pygame to locate display configuration at runtime
ENV SDL_AUDIODRIVER=dsp

ENTRYPOINT ["python", "gui.py"]
