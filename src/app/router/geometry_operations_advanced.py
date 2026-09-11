"""Geometry operations endpoints for filtering and isochrone calculations."""

import re
import json
from fastapi import APIRouter, Body, status, HTTPException, Response
import geopandas as gpd

from app.auth import database
from app.models.geometryOperationModel import FilterFeatureCollection
import app.common.geopandsFuncs as geopandsFuncs

router = APIRouter(prefix="/geometry-advanced", tags=["geometryOperations-advanced"])

_SAFE_IDENT = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_ident(value: str, label: str) -> str:
    if not _SAFE_IDENT.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


@router.post("/filter", status_code=status.HTTP_201_CREATED)
def geo_filter_advanced(data: FilterFeatureCollection = Body(...)):
    """Filter parcels by geometry intersection.

    Accepts GeoJSON features and returns UUIDs of parcels that intersect
    with either the union or intersection of input geometries.
    """
    try:
        table = _validate_ident(data.tableName, "tableName")
        gdf = gpd.read_file(data.model_dump_json(), driver="GeoJSON")

        # Compute target geometry: union (combine all) or intersection (overlap)
        if data.union == True:
            input_geometry = gdf.unary_union
        else:
            input_geometry = geopandsFuncs.intersect_geodataframe(gdf)
            if not input_geometry:
                return Response(status_code=status.HTTP_409_CONFLICT)

        geom_json = json.dumps(input_geometry.__geo_interface__)
        sql_query = f"""
        SELECT json_build_object('UUIDs', json_agg("UUID")) AS result
        FROM {table} AS p
        WHERE ST_Intersects(p.geom, ST_GeomFromGeoJSON(:geom)::geometry);
        """
        sql_answer = database.execute_sql_query(sql_query, {"geom": geom_json})
        raw_data = sql_answer.fetchone()
        return raw_data[0]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"A ValueError error occurred: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


from app.models.isochronesModel import IsochroneCreate
from app.common.isochronesFuncsAdvanced import get_iso_aoi


@router.post("/isochrone", status_code=status.HTTP_201_CREATED)
def create_isochrones_advanced(data: IsochroneCreate = Body(...)):
    """
    Create isochrones by sending the center coordinates, time and mode.
    Sample request object:

    Modes: walk_network,bike_network,drive_network


    {
        "time": "3",
        "center": {
          "lng": 9.990004262251006,
          "lat": 53.55316847206518
        },
        "mode": "walk_network"
    }
    """
    try:
        time = float(data.time) * 60
        center = data.center
        lng = float(center.lng)
        lat = float(center.lat)
        mode = data.mode
        return get_iso_aoi(mode, lng, lat, time)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"An ValueError error occurred: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
