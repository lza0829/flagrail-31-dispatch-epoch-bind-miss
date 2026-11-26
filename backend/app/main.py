from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app import seed
from app.routers import api

app = FastAPI(title="灰度轨", version="0.2.0-payload-epoch")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(HTTPException)
async def 中文HTTP异常平铺(request: Request, exc: HTTPException):
    
    
    if isinstance(exc.detail, dict):
        content = dict(exc.detail)
        content.setdefault("detail", exc.detail)
    else:
        content = {"detail": exc.detail}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


@app.on_event("startup")
def _启动():
    seed.初始化库()



seed.初始化库()

app.include_router(api)
