import re
from fastapi import APIRouter, Body, HTTPException, status
from app.auth import database
from app.common.ligfinderFuncAdvanced import generate_criteria_sql, CriteriaLimitExceeded
from app.models.ligfinderModelAdvanced import MaximizerRequest

router = APIRouter(prefix="/ligfinder-advanced", tags=["ligfinder-advanced"])

_SAFE_IDENT = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
_ALLOWED_OPS = {"=", "!=", "<>", "<", ">", "<=", ">="}


def _validate_ident(value: str, label: str) -> str:
    if not _SAFE_IDENT.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def _validate_op(op: str) -> str:
    if op not in _ALLOWED_OPS:
        raise ValueError(f"Invalid SQL operator: {op!r}")
    return op


def _embed_params(sql: str, params: dict) -> str:
    # Named params (`:p0`) cannot bind inside dollar-quoted $$ blocks executed by
    # pgr_connectedComponents. Substitute them with properly-escaped SQL literals instead.
    result = sql
    for key, val in params.items():
        safe_val = str(val).replace("'", "''")
        result = result.replace(f":{key}", f"'{safe_val}'")
    return result


@router.post("/maximizer", status_code=status.HTTP_200_OK)
def discover_parcel_islands_advanced(data: MaximizerRequest = Body(...)):
    """
    Identifies clusters (islands) of adjacent parcels using PG Routing's
    connected components algorithm, filtered by dynamic input criteria.
    Returns GeoJSON FeatureCollection of parcel clusters larger than a given threshold.
    """
    try:
        table = _validate_ident(data.table_name, "table_name")

        # Build two parallel WHERE clause lists:
        #   outer_* — uses named :params, passed to execute_sql_query
        #   inner_* — values embedded as SQL literals, used inside pgr_connectedComponents $$...$$
        outer_clauses = []
        inner_clauses = []
        all_params = {}

        # Geometry UUIDs — parameterized for outer query, embedded for inner
        geometry = data.geometry or []
        if len(geometry) == 1:
            all_params["geom_0"] = str(geometry[0])
            outer_clauses.append('"UUID" = :geom_0')
            inner_clauses.append(f'"UUID" = \'{str(geometry[0]).replace(chr(39), chr(39)*2)}\'')
        elif len(geometry) > 1:
            for i, uuid_val in enumerate(geometry):
                all_params[f"geom_{i}"] = str(uuid_val)
            outer_clauses.append(
                f'"UUID" IN ({", ".join(f":geom_{i}" for i in range(len(geometry)))})'
            )
            _quoted_uuids = ", ".join("'" + str(u).replace("'", "''") + "'" for u in geometry)
            inner_clauses.append(f'"UUID" IN ({_quoted_uuids})')

        # Criteria — unpack tuple, build outer (params) and inner (embedded) versions
        if data.criteria:
            criteria_sql, criteria_params = generate_criteria_sql(data.criteria)
            if criteria_sql:
                all_params.update(criteria_params)
                outer_clauses.append(criteria_sql)
                inner_clauses.append(_embed_params(criteria_sql, criteria_params))

        # Metric filters — column/op validated, values parameterized for outer, embedded for inner
        if data.metric:
            for i, m in enumerate(data.metric):
                col = _validate_ident(m.column, "metric column")
                op = _validate_op(m.operation)
                key = f"metric_{i}"
                all_params[key] = m.value
                outer_clauses.append(f'"{col}" {op} :{key}')
                safe_val = str(m.value).replace("'", "''")
                inner_clauses.append(f'"{col}" {op} \'{safe_val}\'')

        # GRZ filters — same approach as metric
        if data.grz:
            for i, g in enumerate(data.grz):
                col = _validate_ident(g.column, "grz column")
                op = _validate_op(g.operation)
                key = f"grz_{i}"
                all_params[key] = g.value
                outer_clauses.append(f'"{col}" {op} :{key}')
                safe_val = str(g.value).replace("'", "''")
                inner_clauses.append(f'"{col}" {op} \'{safe_val}\'')

        outer_where = " AND ".join(outer_clauses) if outer_clauses else "TRUE"
        inner_where = " AND ".join(inner_clauses) if inner_clauses else "TRUE"

        all_params["threshold"] = float(data.threshold)

        sql = f"""
WITH
filtered AS (
    SELECT "UUID", geom, "Shape_Area"
    FROM {table}
    WHERE {outer_where}
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
            SELECT "UUID" FROM {table}
            WHERE {inner_where}
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
    HAVING SUM(f."Shape_Area") > :threshold
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
    AND "Shape_Area" > :threshold
)

SELECT * FROM aggregated_clusters
UNION ALL
SELECT * FROM single_parcels
ORDER BY total_area DESC;
"""

        result = database.execute_sql_query(sql, all_params).fetchall()
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

    except (ValueError, CriteriaLimitExceeded) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
