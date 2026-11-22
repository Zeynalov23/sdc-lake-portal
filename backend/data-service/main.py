"""
Data service — FastAPI app entry point.
Runs as a pod in EKS with Pod Identity for S3 access.
Handles all data plane operations: list files, presigned URLs, space metadata.
"""
import logging
import os
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from prometheus_fastapi_instrumentator import Instrumentator, metrics

from src.routers import spaces, files, members, products
from src.utils.obs_logging import configure_logging, request_id

configure_logging()

app = FastAPI(
    title="SDC Lake Data Service",
    version="0.1.0",
)

@app.middleware("http")
async def request_context(request: Request, call_next):
    """
    Carry a request id across the whole call.

    The frontend generates it and forwards it as a header, so one user
    action produces log lines in both services that share a key. If the
    header is absent - a direct call, or a probe - one is generated here,
    so the field is never missing.
    """
    rid = request.headers.get("x-request-id") or uuid4().hex
    token = request_id.set(rid)
    try:
        response = await call_next(request)
    finally:
        # Reset even on an exception, or the id leaks into whatever task
        # reuses this context next.
        request_id.reset(token)
    response.headers["x-request-id"] = rid
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten when auth is added
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(spaces.router, prefix="/spaces", tags=["spaces"])
app.include_router(files.router,  prefix="/spaces", tags=["files"])
app.include_router(members.router, prefix="/spaces", tags=["members"])
app.include_router(products.router, prefix="/spaces", tags=["data products"])

# RED metrics on /metrics, scraped by Prometheus through a ServiceMonitor.
#
# The handler label is the ROUTE TEMPLATE - "/spaces/{space_id}/files", not
# "/spaces/a3f9.../files". That distinction is the whole game: a space id in a
# label would create one time series per space per method per status, which is
# unbounded, and unbounded label values are how people take a Prometheus
# server down. The library does this by reading the matched route, so it is
# correct by construction rather than by remembering.
#
# Status codes are grouped into 2xx/4xx/5xx by default, which is enough to
# alert on an error ratio and keeps the series count low. It does mean the
# deliberate 404s from authz.py (ADR 001) are indistinguishable from genuine
# ones here; that is a trade worth revisiting if the 4xx rate ever needs
# splitting.
#
# /health is excluded. The kubelet probes it every 10 seconds per pod, which
# would dominate the request rate and make the RED numbers describe the
# probes rather than the users.

# The default latency buckets stop at 1 second, so every request slower than
# that lands in +Inf and a p99 above one second cannot be estimated at all -
# which is exactly the number the latency alert is built on. These go to 10s.
_LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf"))

_instrumentator = Instrumentator(excluded_handlers=["/health", "/metrics"])
_instrumentator.add(metrics.default(latency_lowr_buckets=_LATENCY_BUCKETS))
_instrumentator.instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": str(exc)})
