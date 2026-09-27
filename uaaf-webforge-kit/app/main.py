import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import HOST, PORT, IS_DEMO_MODE

app = FastAPI(title="UAAF WebForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "UAAF WebForge", "demo_mode": IS_DEMO_MODE}

# Mount static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    print(f"🚀 Starting UAAF WebForge on http://{HOST}:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
