"""GeoServer proxy router to bypass CORS issues."""

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from app.auth.database import get_db
import os

router = APIRouter(
    prefix="/geoserver",
    tags=["geoserver"],
)

# GeoServer configuration
GEOSERVER_BASE_URL = os.getenv("GEOSERVER_BASE_URL", "http://geoserver:8080/geoserver")
GEOSERVER_USERNAME = os.getenv("GEOSERVER_ADMIN_USER", "admin")
GEOSERVER_PASSWORD = os.getenv("GEOSERVER_ADMIN_PASSWORD", "geoserver")


async def get_geoserver_auth():
    """Generate Basic Auth header for GeoServer."""
    import base64
    credentials = f"{GEOSERVER_USERNAME}:{GEOSERVER_PASSWORD}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


@router.get("/rest/layers")
async def proxy_get_layers(
    db: Session = Depends(get_db),
    auth_header: dict = Depends(get_geoserver_auth),
):
    """
    Proxy: GET /rest/layers
    Fetches all layers from GeoServer.
    """
    async with httpx.AsyncClient() as client:
        url = f"{GEOSERVER_BASE_URL}/rest/layers"
        headers = {
            "Content-Type": "application/json",
            **auth_header,
        }
        response = await client.get(url, headers=headers, follow_redirects=True)
        return response.json()


@router.get("/rest/workspaces")
async def proxy_get_workspaces(
    db: Session = Depends(get_db),
    auth_header: dict = Depends(get_geoserver_auth),
):
    """
    Proxy: GET /rest/workspaces
    Fetches all workspaces from GeoServer.
    """
    async with httpx.AsyncClient() as client:
        url = f"{GEOSERVER_BASE_URL}/rest/workspaces"
        headers = {
            "Content-Type": "application/json",
            **auth_header,
        }
        response = await client.get(url, headers=headers, follow_redirects=True)
        return response.json()


@router.get("/rest/workspaces/{workspace}/layers")
async def proxy_get_workspace_layers(
    workspace: str,
    db: Session = Depends(get_db),
    auth_header: dict = Depends(get_geoserver_auth),
):
    """
    Proxy: GET /rest/workspaces/{workspace}/layers
    Fetches layers for a specific workspace.
    """
    async with httpx.AsyncClient() as client:
        url = f"{GEOSERVER_BASE_URL}/rest/workspaces/{workspace}/layers"
        headers = {
            "Content-Type": "application/json",
            **auth_header,
        }
        response = await client.get(url, headers=headers, follow_redirects=True)
        return response.json()


@router.get("/rest/workspaces/{workspace}/layers/{layer}")
async def proxy_get_layer_info(
    workspace: str,
    layer: str,
    db: Session = Depends(get_db),
    auth_header: dict = Depends(get_geoserver_auth),
):
    """
    Proxy: GET /rest/workspaces/{workspace}/layers/{layer}
    Fetches detailed information about a specific layer.
    """
    async with httpx.AsyncClient() as client:
        url = f"{GEOSERVER_BASE_URL}/rest/workspaces/{workspace}/layers/{layer}"
        headers = {
            "Content-Type": "application/json",
            **auth_header,
        }
        response = await client.get(url, headers=headers, follow_redirects=True)
        return response.json()


@router.get("/{workspace}/wms")
async def proxy_get_wms(
    workspace: str,
    service: str = Query(...),
    version: str = Query(...),
    request: str = Query(...),
    layers: str = Query(...),
    bbox: str = Query(...),
    width: int = Query(...),
    height: int = Query(...),
    srs: str = Query(...),
    format: str = Query(...),
    styles: str = Query(default=""),
    db: Session = Depends(get_db),
    auth_header: dict = Depends(get_geoserver_auth),
):
    """
    Proxy: GET /{workspace}/wms?service=...&version=...&request=...&layers=...&bbox=...&width=...&height=...&srs=...&format=...&styles=...
    Fetches WMS data (includes GeoJSON format).
    """
    async with httpx.AsyncClient() as client:
        url = f"{GEOSERVER_BASE_URL}/{workspace}/wms"
        params = {
            "service": service,
            "version": version,
            "request": request,
            "layers": layers,
            "bbox": bbox,
            "width": width,
            "height": height,
            "srs": srs,
            "format": format,
            "styles": styles,
        }
        headers = {
            "Content-Type": "application/json",
            **auth_header,
        }
        response = await client.get(
            url, params=params, headers=headers, follow_redirects=True
        )
        
        # Return appropriate response based on format
        if format == "geojson":
            return response.json()
        else:
            return response.content


@router.get("/rest/workspaces/{workspace}/layers/{layer}/featuretype")
async def proxy_get_feature_type(
    workspace: str,
    layer: str,
    db: Session = Depends(get_db),
    auth_header: dict = Depends(get_geoserver_auth),
):
    """
    Proxy: GET /rest/workspaces/{workspace}/layers/{layer}/featuretype
    Fetches feature type information (from resource.href).
    """
    async with httpx.AsyncClient() as client:
        url = f"{GEOSERVER_BASE_URL}/rest/workspaces/{workspace}/layers/{layer}/featuretype"
        headers = {
            "Content-Type": "application/json",
            **auth_header,
        }
        response = await client.get(url, headers=headers, follow_redirects=True)
        return response.json()


@router.get("/rest/styles/{style_name}")
async def proxy_get_style(
    style_name: str,
    db: Session = Depends(get_db),
    auth_header: dict = Depends(get_geoserver_auth),
):
    """
    Proxy: GET /rest/styles/{style_name}
    Fetches style information (Mapbox Style, SLD, etc).
    """
    async with httpx.AsyncClient() as client:
        url = f"{GEOSERVER_BASE_URL}/rest/styles/{style_name}"
        headers = {
            "Content-Type": "application/vnd.geoserver.mbstyle+json",
            **auth_header,
        }
        response = await client.get(url, headers=headers, follow_redirects=True)
        return response.json()


@router.get("/rest/workspaces/{workspace}/styles/{style_name}")
async def proxy_get_workspace_style(
    workspace: str,
    style_name: str,
    db: Session = Depends(get_db),
    auth_header: dict = Depends(get_geoserver_auth),
):
    """
    Proxy: GET /rest/workspaces/{workspace}/styles/{style_name}
    Fetches workspace-specific style information.
    """
    async with httpx.AsyncClient() as client:
        url = f"{GEOSERVER_BASE_URL}/rest/workspaces/{workspace}/styles/{style_name}"
        headers = {
            "Content-Type": "application/vnd.geoserver.mbstyle+json",
            **auth_header,
        }
        response = await client.get(url, headers=headers, follow_redirects=True)
        return response.json()


# Catch-all for generic URL forwarding (for resource.href, style.href URLs, and WMTS/WMS tiles)
@router.api_route("/{path:path}", methods=["GET"])
async def proxy_generic(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
    auth_header: dict = Depends(get_geoserver_auth),
):
    """
    Catch-all proxy for any other GeoServer endpoint.
    Handles resource.href, style.href URLs, WMTS tiles, and other services.
    Forwards all query parameters to GeoServer without decompression.
    """
    # Use httpx transport that doesn't auto-decompress
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    transport = httpx.AsyncHTTPTransport(limits=limits)
    
    async with httpx.AsyncClient(transport=transport) as client:
        url = f"{GEOSERVER_BASE_URL}/{path}"
        
        # Forward all query parameters from the original request
        params = dict(request.query_params)
        
        headers = {
            "Accept": "application/json, application/vnd.geoserver.mbstyle+json, application/vnd.mapbox-vector-tile",
            "Accept-Encoding": "identity",  # Request uncompressed to avoid httpx decompression
            **auth_header,
        }
        
        # Make request without following redirects to preserve exact response
        raw_response = await client.get(
            url, 
            params=params if params else None,
            headers=headers,
            follow_redirects=True
        )
        
        # Get all headers except those that shouldn't be forwarded
        response_headers = {
            k: v for k, v in raw_response.headers.items() 
            if k.lower() not in ["transfer-encoding", "content-length", "content-encoding"]
        }
        
        # Return raw content with original content-type
        content_type = raw_response.headers.get("content-type", "application/octet-stream")
        
        return Response(
            content=raw_response.content,
            status_code=raw_response.status_code,
            headers=response_headers,
            media_type=content_type
        )
