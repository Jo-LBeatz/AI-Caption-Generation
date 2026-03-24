# 🎬 Captions by Jo-L

A production-ready full-stack application that automatically generates .SRT subtitles for video files using OpenAI's Whisper.

## 🚀 Features

- **High-Accuracy Transcription**: Powered by Whisper `base` (can be configured to `small` or `medium`).
- **Supports Large Videos**: Processing capacity for videos up to 2 hours.
- **Background Jobs**: Celery + Redis workers prevent API blocking.
- **Production-Ready UI**: Premium React interface with real-time status updates and progress tracking.
- **Standard SRT Format**: Accurate timestamps (HH:MM:SS,mmm).
- **Dockerized Architecture**: One-command deployment for all services.

---

## 🏗 System Architecture

- **Frontend**: React (Vite) + Lucide Icons + Axios.
- **Backend API**: FastAPI (Python).
- **Task Worker**: Celery + FFmpeg (Audio Extraction).
- **Message Broker**: Redis.
- **Transcription**: OpenAI Whisper.

---

## 🛠 Setup & Installation

### Option 1: Docker (Recommended)

1. Ensure you have [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed.
2. Clone the repository and navigate to the project root.
3. Run:
   ```bash
   docker-compose up --build
   ```
4. Access the app at: `http://localhost:3000`

### Option 2: Local Development

#### 1. Requirements
- Python 3.10+
- Node.js 20+
- FFmpeg (Must be installed on your system PATH)
- Redis Server

#### 2. Backend Setup
```bash
cd backend
pip install -r requirements.txt
# Set REDIS_URL environment variable if not localhost
uvicorn main:app --reload
```

#### 3. Worker Setup (Run in a separate terminal)
```bash
cd backend
celery -A worker.celery worker --loglevel=info
```

#### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | URL for the Redis server | `redis://localhost:6379/0` |
| `WHISPER_MODEL` | Whisper model size (`tiny`, `base`, `small`, `medium`) | `base` |
| `UPLOAD_DIR` | Directory to store temporary files | `/uploads` |
| `VITE_API_URL` | Backend API URL for frontend | `http://localhost:8000` |

---

## 🎥 Sample Test Video Instructions

To test the application:
1.  **Download a sample clip** (e.g., a 2-minute YouTube video or a personal MP4 recording).
2.  **Upload the file** via the "Antigravity Captions" UI.
3.  **Wait for the pipeline**:
    - **Step 1**: Audio extraction (FFmpeg).
    - **Step 2**: Transcription (Whisper).
    - **Step 3**: Completion.
4.  **Download the SRT**: Open the downloaded file in a text editor to verify the structure or import it into VLC player with the original video.

---

## 📂 Deliverables Overview

- `backend/`: API logic and worker task definition.
- `frontend/`: React components and premium design.
- `docker-compose.yml`: Orchestration of all system layers.
- `uploads/`: Temporary data store (shared volume in Docker).

---

## 🔥 Performance Tips

- **GPU Acceleration**: If running on a GPU-enabled machine with Docker, update the `Dockerfile` to use `nvidia/cuda` base images and install `torch` with CUDA support. This will make transcription 5x-10x faster.
- **Model Size**: For the best results with multiple accents, change `WHISPER_MODEL` to `small` or `medium` in `docker-compose.yml`.

---

## 🔒 Security & Cleanup

- The application automatically removes original video and audio files after transcription to save disk space.
- Only the final SRT remains available for download.
- For production use, consider adding a scheduled cron job (Celery Beat) to purge old SRT files older than 24 hours.

---

Built by **Jo-L**.
