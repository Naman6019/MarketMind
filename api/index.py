import sys
import os
import traceback

# Add root to path for module resolution
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

try:
    from app.main import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()
    
    @app.get("/api/debug")
    @app.get("/api/{path:path}")
    @app.get("/")
    async def debug_error(path: str = None):
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "traceback": traceback.format_exc(),
                "sys_path": sys.path,
                "cwd": os.getcwd()
            }
        )
