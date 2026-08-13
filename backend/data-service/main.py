"""
Data service — FastAPI app entry point.
Runs as a pod in EKS with Pod Identity for S3 access.
Handles all data plane operations: list files, presigned URLs, space metadata.
"""
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.routers import spaces, files, members

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="SDC Lake Data Service",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten when auth is added
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(spaces.router, prefix="/spaces", tags=["spaces"])
app.include_router(files.router,  prefix="/spaces", tags=["files"])
app.include_router(members.router, prefix="/spaces", tags=["members"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": str(exc)})
