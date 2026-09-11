from fastapi import APIRouter, Body, status, HTTPException
from geojson_pydantic import FeatureCollection
from app.models.ligfinderModel import TableRequest
from app.auth import database
from app.common.ligfinderFunc import generate_criteria_sql


router = APIRouter(prefix="/ligfinder", tags=["ligfinder"])

@router.post("/filter", status_code=status.HTTP_201_CREATED)
def ligfinder_filter(data: TableRequest = Body(...)):
    try:
        sql_query = """
        SELECT json_build_object(
          'type', 'FeatureCollection',
          'features', json_agg(ST_AsGeoJSON(p.*)::json)
        )
        FROM
        """
        sql_query += f"{data.table_name} AS p"
        where_clauses = []

        # Geometry UUIDs
        if len(data.geometry) == 0:
            pass  # No geometry filter applied
        elif len(data.geometry) == 1:
            where_clauses.append(f"""p."UUID" = '{data.geometry[0]}'""")
        else:
            uuids = ', '.join(f"'{uuid}'" for uuid in data.geometry)
            where_clauses.append(f"p.\"UUID\" IN ({uuids})")
        print(f"Geometry UUIDs: {data}")
        # Criteria
        if data.criteria:
            criteria_sql = generate_criteria_sql(data.criteria)
            if criteria_sql:
                where_clauses.append(criteria_sql)
        # Metric filters
        if data.metric:
            metric_conditions = [
                f'"{m.column}" {m.operation} {m.value}'
                for m in data.metric
            ]
            where_clauses.append("(" + " AND ".join(metric_conditions) + ")")
        # GRZ filters
        if data.grz:
            grz_conditions = [
                f'"{g.column}" {g.operation} {g.value}'
                for g in data.grz
            ]
            where_clauses.append("(" + " AND ".join(grz_conditions) + ")")
        # Final WHERE clause
        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)

        print(f"Constructed SQL Query: {sql_query}")
        sql_answer = database.execute_sql_query(sql_query)
        raw_data = sql_answer.fetchone()

        if not raw_data or not raw_data[0] or not raw_data[0].get("features"):
            return {"type": "FeatureCollection", "features": []}
        return raw_data[0]

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"A ValueError occurred: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
