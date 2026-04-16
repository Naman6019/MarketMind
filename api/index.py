from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "The Vercel function is running correctly."}

@app.get("/api/{path:path}")
async def catch_all(path: str):
    return {"status": "error", "message": f"Path /api/{path} hit, but app modules not loaded for safety."}

@app.get("/")
async def root():
    return {"status": "ok", "message": "Root hit"}
