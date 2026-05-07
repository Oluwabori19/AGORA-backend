from fastapi import APIRouter, Body, HTTPException, status
from typing import List, Optional, Any
from pydantic import BaseModel
from app.auth import database
from app.common.ligfinderFunc import generate_criteria_sql
from app.models.ligfinderModel import MaximizerRequest

router = APIRouter(prefix="/ligfinder", tags=["ligfinder"])


def _criteria_sql_from_request(data: MaximizerRequest):
    payload = None

    if data.groups:
        payload = {
            "between_groups_operator": data.between_groups_operator,
            "groups": [
                {
                    "inner_operator": g.inner_operator,
                    "criteria": [
                        {"data": c.data, "status": c.status}
                        for c in g.criteria
                    ]
                }
                for g in data.groups
            ]
        }
    elif data.criteria:
        payload = {
            "between_groups_operator": "AND",
            "groups": [
                {
                    "inner_operator": "OR",
                    "criteria": [
                        {"data": c.data, "status": c.status}
                        for c in data.criteria
                    ]
                }
            ]
        }

    if not payload:
        return ""

    criteria_sql, params = generate_criteria_sql(payload)
    if not criteria_sql:
        return ""

    for param_key, param_value in params.items():
        if isinstance(param_value, list):
            param_str = "ARRAY[" + ", ".join(f"'{v}'" for v in param_value) + "]"
        else:
            param_str = f"'{param_value}'"
        criteria_sql = criteria_sql.replace(f"%({param_key})s", param_str)

    return criteria_sql

@router.post("/maximizer", status_code=status.HTTP_200_OK)
def discover_parcel_islands(data: MaximizerRequest = Body(...)):
    """
    Identifies clusters (islands) of adjacent parcels using PG Routing's
    connected components algorithm, filtered by dynamic input criteria.
    Returns GeoJSON FeatureCollection of parcel clusters larger than a given threshold.
    """
    try:
        # Construct dynamic WHERE conditions based on request input
        where_clauses = []

        # Filter by geometry UUIDs if provided
        # Geometry UUIDs
        if not data.geometry or len(data.geometry) == 0:
            pass  # No geometry filter applied
        elif len(data.geometry) == 1:
            where_clauses.append(f""" "UUID" = '{data.geometry[0]}'""")
        else:
            uuids = ', '.join(f"'{uuid}'" for uuid in data.geometry)
            where_clauses.append(f" \"UUID\" IN ({uuids})")

        # Filter by complex LGB/XPlanung-style criteria
        criteria_sql = _criteria_sql_from_request(data)
        if criteria_sql:
            where_clauses.append(criteria_sql)

        # Metric-based filtering (e.g., Shape_Area > value)
        if data.metric:
            metric_sql = " AND ".join(
                f'"{m.column}" {m.operation} {m.value}' for m in data.metric
            )
            if metric_sql:
                where_clauses.append(metric_sql)

        # GRZ (site occupancy index) filtering
        if data.grz:
            grz_sql = " AND ".join(
                f'"{g.column}" {g.operation} {g.value}' for g in data.grz
            )
            if grz_sql:
                where_clauses.append(grz_sql)

        # Combine all filters into a single WHERE clause
        final_where = " AND ".join(where_clauses) if where_clauses else "TRUE"
        print(f"Final WHERE clause: {final_where}")
        # SQL query using CTEs to:
        # - Filter parcels
        # - Select edges between touching parcels
        # - Map UUIDs to PG Routing node IDs
        # - Run pgr_connectedComponents on edge list
        # - Aggregate clusters that exceed threshold area
        sql = f"""
WITH
filtered AS (
    SELECT "UUID", geom, "Shape_Area"
    FROM {data.table_name}
    WHERE {final_where}
),
touch_edges AS (
    SELECT 
        e.uuid_source,
        e.uuid_target
    FROM parcel_touch_edges_20250507 e
    JOIN filtered f1 ON e.uuid_source = f1."UUID"
    JOIN filtered f2 ON e.uuid_target = f2."UUID"
),
node_ids AS (
    SELECT "UUID", ROW_NUMBER() OVER () AS node_id
    FROM (
        SELECT uuid_source AS "UUID" FROM touch_edges
        UNION
        SELECT uuid_target AS "UUID" FROM touch_edges
    ) all_uuids
),
components AS (
    SELECT * FROM pgr_connectedComponents($$
        WITH
        filtered AS (
            SELECT "UUID" FROM {data.table_name}
            WHERE {final_where}
        ),
        touch_edges AS (
            SELECT 
                e.uuid_source,
                e.uuid_target
            FROM parcel_touch_edges_20250507 e
            JOIN filtered f1 ON e.uuid_source = f1."UUID"
            JOIN filtered f2 ON e.uuid_target = f2."UUID"
        ),
        node_ids AS (
            SELECT "UUID", ROW_NUMBER() OVER () AS node_id
            FROM (
                SELECT uuid_source AS "UUID" FROM touch_edges
                UNION
                SELECT uuid_target AS "UUID" FROM touch_edges
            ) all_uuids
        )
        SELECT 
            ROW_NUMBER() OVER () AS id,
            na.node_id AS source,
            nb.node_id AS target,
            1::float AS cost
        FROM touch_edges e
        JOIN node_ids na ON e.uuid_source = na."UUID"
        JOIN node_ids nb ON e.uuid_target = nb."UUID"
    $$)
),
clustered AS (
    SELECT c.component AS cluster_id, n."UUID"
    FROM components c
    JOIN node_ids n ON c.node = n.node_id
),
aggregated_clusters AS (
    SELECT 
        cl.cluster_id,
        SUM(f."Shape_Area") AS total_area,
        STRING_AGG(cl."UUID", ', ') AS uuids,
        ST_AsGeoJSON(ST_Union(f.geom))::json AS geometry
    FROM clustered cl
    JOIN filtered f ON cl."UUID" = f."UUID"
    GROUP BY cl.cluster_id
    HAVING SUM(f."Shape_Area") > {data.threshold}
),
single_parcels AS (
    SELECT 
        ROW_NUMBER() OVER () + (SELECT COALESCE(MAX(cluster_id), 0) FROM aggregated_clusters) AS cluster_id,
        "Shape_Area" AS total_area,
        "UUID" AS uuids,
        ST_AsGeoJSON(geom)::json AS geometry
    FROM filtered f
    WHERE NOT EXISTS (
        SELECT 1 FROM clustered cl WHERE cl."UUID" = f."UUID"
    )
    AND "Shape_Area" > {data.threshold}
)

SELECT * FROM aggregated_clusters
UNION ALL
SELECT * FROM single_parcels
ORDER BY total_area DESC;
"""

        # Execute SQL and convert results into GeoJSON
        result = database.execute_sql_query(sql).fetchall()
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": row[3],
                    "properties": {
                        "id": row[0],
                        "total_area": row[1],
                        "uuids": row[2],
                    },
                }
                for row in result
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
