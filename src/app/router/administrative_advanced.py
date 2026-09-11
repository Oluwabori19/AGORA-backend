import re
from fastapi import APIRouter, Body, status, HTTPException
from pydantic import BaseModel
import app.auth.database as database

router = APIRouter(prefix="/administrative-advanced", tags=["administrative-advanced"])

_SAFE_IDENT = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_ident(value: str, label: str) -> str:
    if not _SAFE_IDENT.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


class TargetColumn(BaseModel):
    name: str = "id"
    target_value_list: list[int]


administrative_table_list = [
    {"table_name": "bezirke", "name": "Bezirke", "id": 1},
    {"table_name": "gemarkungen", "name": "Gemarkungen", "id": 2},
    {"table_name": "stadtteile", "name": "Stadtteile", "id": 3},
    {"table_name": "statistischegebiete", "name": "Statistischegebiete", "id": 4},
]


@router.get("/list", status_code=status.HTTP_200_OK)
def get_administrative_tables_advanced():
    """
    Get all administrative tables in the database
    """
    try:
        return {"data": administrative_table_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@router.get("/data/{table_id}", status_code=status.HTTP_201_CREATED)
def get_administrative_table_data_advanced(table_id: int):
    """
    You can get all data from the table by sending the table_id

    sample request: {{URL}}/administrative/data/table_id
    """
    try:
        table_name = next(
            (item["table_name"] for item in administrative_table_list if item["id"] == table_id),
            None,
        )
        if table_name is None:
            raise HTTPException(status_code=404, detail="Table not found")

        sql_query = f"""
            select json_build_object(
          'type', 'FeatureCollection',
          'features', json_agg(ST_AsGeoJSON(table_name.*)::json)
          )
            from {table_name} as table_name
        """
        sql_answer = database.execute_sql_query(sql_query)
        raw_data = sql_answer.fetchone()
        return raw_data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@router.get("/data/features/{table_id}", status_code=status.HTTP_201_CREATED)
def get_administrative_feature_data_advanced(table_id: int, target_column: TargetColumn):
    try:
        table_name = next(
            (item["table_name"] for item in administrative_table_list if item["id"] == table_id),
            None,
        )
        if table_name is None:
            raise HTTPException(status_code=404, detail="Table not found")

        col = _validate_ident(target_column.name, "column name")
        params = {f"v{i}": v for i, v in enumerate(target_column.target_value_list)}
        placeholders = ", ".join(f":v{i}" for i in range(len(params)))

        sql_query = f"""
            select json_build_object(
          'type', 'FeatureCollection',
          'features', json_agg(ST_AsGeoJSON(table_name.*)::json)
          )
            from {table_name} as table_name where "{col}" in ({placeholders})
        """
        sql_answer = database.execute_sql_query(sql_query, params)
        raw_data = sql_answer.fetchone()[0]
        return raw_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
