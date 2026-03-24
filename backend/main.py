from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
import shutil
import os
import uuid
import redis
import json
import logging
from celery import Celery
from datetime import datetime, timedelta
import dns.resolver
from fastapi.responses import Response
import csv
import io

logger = logging.getLogger(__name__)

app = FastAPI(title="Captions by Jo-L API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "SACRED_HEART_OF_JESUS_AUTHENTICATION_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.from_url(REDIS_URL)

# Celery Configuration
celery = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "../uploads")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def get_sheets_service():
    pass

@app.get("/admin/users/export")
async def export_users_csv(secret: Optional[str] = None):
    # Simple secret key to protect your user list so not everyone can download it
    admin_secret = os.getenv("ADMIN_SECRET", "1234")
    if secret != admin_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Connect to Redis to get all users
    user_keys = r.keys("user:*")
    users = []
    
    for key in user_keys:
        try:
            user_data = r.get(key)
            if user_data:
                data = json.loads(user_data)
                users.append({
                    "email": data.get("email", ""),
                    "joined_at": data.get("joined_at", "Unknown")
                })
        except:
            continue

    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["email", "joined_at"])
    writer.writeheader()
    for u in users:
        writer.writerow(u)

    # Return as a downloadable CSV file
    response = Response(content=output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=jo_l_users.csv"
    response.headers["Content-Type"] = "text/csv"
    return response

# --- EMAIL DOMAIN VALIDATION ---
def validate_email_domain(email: str) -> bool:
    """Check that the email domain has at least one MX record (i.e. it can receive mail)."""
    try:
        domain = email.split("@")[1]
        dns.resolver.resolve(domain, "MX")
        return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
        return False

# --- AUTH UTILS ---
class UserAuth(BaseModel):
    email: EmailStr
    password: str

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# --- AUTH ENDPOINTS ---
@app.post("/auth/signup")
async def signup(user: UserAuth):
    email = user.email.lower()

    # Validate that the email domain actually exists and can receive mail
    if not validate_email_domain(email):
        raise HTTPException(
            status_code=400,
            detail="This email address doesn't appear to be valid. Please use a real email."
        )

    user_key = f"user:{email}"
    if r.get(user_key):
        raise HTTPException(status_code=400, detail="Account already exists for this email.")
    
    hashed_pwd = get_password_hash(user.password)
    r.set(user_key, json.dumps({
        "email": email,
        "password": hashed_pwd,
        "joined_at": datetime.utcnow().isoformat()
    }))

    # Log to CSV isn't needed here anymore since we can just export from Redis directly!
    
    token = create_access_token(data={"sub": email})
    return {"token": token, "email": email}

@app.post("/auth/login")
async def login(user: UserAuth):
    user_key = f"user:{user.email.lower()}"
    user_data = r.get(user_key)
    if not user_data:
        raise HTTPException(status_code=400, detail="Account not found. Please sign up.")
    
    data = json.loads(user_data)
    if not verify_password(user.password, data["password"]):
        raise HTTPException(status_code=400, detail="Incorrect credentials.")
    
    token = create_access_token(data={"sub": user.email.lower()})
    return {"token": token, "email": user.email.lower()}

# --- CORE ENDPOINTS ---
@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...), 
    embed_captions: bool = False, 
    user_email: str = Depends(get_current_user)
):
    job_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1]
    file_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.{ext}"))
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    
    r.set(f"job:{job_id}", json.dumps({
        "status": "processing",
        "progress": 0,
        "filename": file.filename,
        "user_email": user_email
    }))
    
    celery.send_task("transcribe_video", args=[job_id, file_path, embed_captions])
    
    return {"job_id": job_id}

@app.get("/status/{job_id}")
async def get_status(job_id: str, user_email: str = Depends(get_current_user)):
    job_data = r.get(f"job:{job_id}")
    if not job_data:
         raise HTTPException(status_code=404, detail="Job not found")
    
    data = json.loads(job_data)
    if data.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return data

@app.get("/download/{job_id}")
async def download_srt(job_id: str, user_email: str = Depends(get_current_user)):
    job_data = r.get(f"job:{job_id}")
    if not job_data:
         raise HTTPException(status_code=404, detail="Job not found")
    
    data = json.loads(job_data)
    if data.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    srt_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.srt"))
    if os.path.exists(srt_path):
        return FileResponse(srt_path, filename=f"captions_{job_id[:8]}.srt", media_type="application/x-subrip")
    raise HTTPException(status_code=404, detail="SRT file generation in progress or failed.")

@app.get("/download-video/{job_id}")
async def download_burned_video(job_id: str, user_email: str = Depends(get_current_user)):
    job_data = r.get(f"job:{job_id}")
    if not job_data:
         raise HTTPException(status_code=404, detail="Job not found")
    
    data = json.loads(job_data)
    if data.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    video_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}_burned.mp4"))
    if os.path.exists(video_path):
        original_name = os.path.splitext(data.get("filename", "video"))[0]
        return FileResponse(video_path, filename=f"{original_name}_captioned.mp4", media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Processed video not found.")

@app.get("/srt/{job_id}")
async def get_srt_content(job_id: str, user_email: str = Depends(get_current_user)):
    job_data = r.get(f"job:{job_id}")
    if not job_data:
         raise HTTPException(status_code=404, detail="Job not found")
    
    data = json.loads(job_data)
    if data.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    srt_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.srt"))
    if os.path.exists(srt_path):
        with open(srt_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    raise HTTPException(status_code=404, detail="SRT content not found.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
