from fastapi import APIRouter, Depends, status, HTTPException, Request, Query, Response
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer

from app.auth import database, utils, oauth2
from app.schemas import user_login
from app.models import user_model
from app.auth.config import settings
import requests
from pydantic import BaseModel

# class Item(BaseModel):
#     item_id: int


router = APIRouter(prefix="/test", tags=["Test"])


@router.get("/v1/{item_id}")
def test(
    item_id: int,
    current_user: int = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    print(item_id)
    return {"message": "Vote deleted successfully"}


from sqlalchemy import text
import logging


@router.get("/table/{table_name}")
def get_table(table_name: str, db: Session = Depends(database.get_db)):
    print(table_name)
    try:
        # Prepare SQL query
        query = text(
            f"""
            SELECT json_build_object(
                'name', 'public.{table_name}', 
                'oid', (SELECT 'public.{table_name}'::regclass::oid), 
                'left', (SELECT min(ST_XMin(geom)) FROM public.{table_name}), 
                'bottom', (SELECT min(ST_YMin(geom)) FROM public.{table_name}), 
                'right', (SELECT max(ST_XMax(geom)) FROM public.{table_name}), 
                'top', (SELECT max(ST_YMax(geom)) FROM public.{table_name}),
                'type', 'FeatureCollection',
                'features', json_agg(ST_AsGeoJSON(t.*)::json ORDER BY t.name ASC)
            )
            FROM public.{table_name} AS t;
        """
        )
        print(query)
        # Execute query and get result
        result = db.execute(query)
        print(result)
        table_info = result.fetchone()[0]  # Get first column value

        return table_info
    except Exception as error:
        print(error)
        logging.error(f"!!! Error : {error}")
        raise HTTPException(status_code=500, detail="Internal server error")


GEOSERVER_URL = "http://dev.geoserver.tosca.dcs.hcu-hamburg.de/geoserver"


@router.get("/get_geoserver_data")
async def get_vector_tile(
    request: Request, current_user: int = Depends(oauth2.get_current_user),
):
    # Request'ten parametreleri al
    params = request.query_params
    workspaceName = params.get("workspaceName")
    layerName = params.get("layerName")
    STYLE = params.get("STYLE")
    TILEMATRIX = params.get("TILEMATRIX")
    TILEMATRIXSET = params.get("TILEMATRIXSET")
    TILECOL = params.get("TILECOL")
    TILEROW = params.get("TILEROW")
    format = params.get("format")

    if not (TILEMATRIX and TILEMATRIXSET and TILECOL and TILEROW and format):
        raise HTTPException(
            status_code=400,
            detail="TILEMATRIX, TILEMATRIXSET, TILECOL, TILEROW, and format are required parameters",
        )

    geoserver_url = f"{GEOSERVER_URL}/gwc/service/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&LAYER={workspaceName}:{layerName}"
    if STYLE:
        geoserver_url += f"&STYLE={STYLE}"
    geoserver_url += f"&TILEMATRIX={TILEMATRIX}&TILEMATRIXSET={TILEMATRIXSET}&TILECOL={TILECOL}&TILEROW={TILEROW}&format={format}"

    response = requests.get(geoserver_url)
    # Bad request check
    if response.status_code == 403:
        raise HTTPException(status_code=400, detail="Bad Request")
    # Raise an exception if the request failed
    response.raise_for_status()
    return Response(content=response.content, media_type="application/octet-stream")


# http://dev.geoserver.tosca.dcs.hcu-hamburg.de/geoserver/gwc/service/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&LAYER=public:parcelEimsbuttel3857&STYLE=&TILEMATRIX=EPSG:900913:16&TILEMATRIXSET=EPSG:900913&TILECOL=34585&TILEROW=21179&format=application/vnd.mapbox-vector-tile

GEOSERVER_REST_URL = "http://dev.geoserver.tosca.dcs.hcu-hamburg.de/geoserver/rest"


@router.get("/geoserver/roles")
async def get_geoserver_roles():
    # Create client to access Geoserver RESTConfig API
    session = requests.Session()
    session.auth = ("hcu", "hcu123")  # Geoserver admin username and password

    # Make request to get roles from Geoserver RESTConfig API
    response = session.get(f"{GEOSERVER_REST_URL}/roles.json")
    print(response)
    # If request is successful, get roles in JSON format
    if response.status_code == 200:
        roles = response.json()["roles"]["role"]
        role_names = [role["name"] for role in roles]
        return role_names
    else:
        return {"error": "Could not fetch Geoserver roles."}
