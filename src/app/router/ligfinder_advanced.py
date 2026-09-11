import re
from fastapi import APIRouter, Body, status, HTTPException
from app.models.ligfinderModelAdvanced import TableRequest
from app.auth import database
from app.common.ligfinderFuncAdvanced import generate_criteria_sql, CriteriaLimitExceeded

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


@router.post("/filter", status_code=status.HTTP_201_CREATED)
def ligfinder_advanced_filter(data: TableRequest = Body(...)):
    try:
        table = _validate_ident(data.table_name, "table_name")

        sql_query = f"""
        SELECT json_build_object(
          'type', 'FeatureCollection',
          'features', json_agg(ST_AsGeoJSON(p.*)::json)
        )
        FROM {table} AS p"""

        where_clauses = []
        all_params = {}

        # Geometry UUIDs — parameterized
        geometry = data.geometry or []
        if len(geometry) == 1:
            all_params["geom_0"] = str(geometry[0])
            where_clauses.append('p."UUID" = :geom_0')
        elif len(geometry) > 1:
            for i, uuid_val in enumerate(geometry):
                all_params[f"geom_{i}"] = str(uuid_val)
            placeholders = ", ".join(f":geom_{i}" for i in range(len(geometry)))
            where_clauses.append(f'p."UUID" IN ({placeholders})')

        # Criteria — both old (flat list) and new (groups) formats
        if data.groups:
            flat_criteria = [c for g in data.groups for c in g.criteria]
            if flat_criteria:
                criteria_sql, criteria_params = generate_criteria_sql(flat_criteria)
                if criteria_sql:
                    all_params.update(criteria_params)
                    where_clauses.append(criteria_sql)
        elif data.criteria:
            criteria_sql, criteria_params = generate_criteria_sql(data.criteria)
            if criteria_sql:
                all_params.update(criteria_params)
                where_clauses.append(criteria_sql)

        # Metric filters — column/op validated, values parameterized
        if data.metric:
            metric_conditions = []
            for i, m in enumerate(data.metric):
                col = _validate_ident(m.column, "metric column")
                op = _validate_op(m.operation)
                key = f"metric_{i}"
                all_params[key] = m.value
                metric_conditions.append(f'"{col}" {op} :{key}')
            where_clauses.append("(" + " AND ".join(metric_conditions) + ")")

        # GRZ filters — same approach as metric
        if data.grz:
            grz_conditions = []
            for i, g in enumerate(data.grz):
                col = _validate_ident(g.column, "grz column")
                op = _validate_op(g.operation)
                key = f"grz_{i}"
                all_params[key] = g.value
                grz_conditions.append(f'"{col}" {op} :{key}')
            where_clauses.append("(" + " AND ".join(grz_conditions) + ")")

        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)

        sql_answer = database.execute_sql_query(sql_query, all_params)
        raw_data = sql_answer.fetchone()

        if not raw_data or not raw_data[0] or not raw_data[0].get("features"):
            return {"type": "FeatureCollection", "features": []}
        return raw_data[0]

    except (ValueError, CriteriaLimitExceeded) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
