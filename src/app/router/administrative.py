from fastapi import APIRouter, Body, status, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import app.auth.database as database


router = APIRouter(prefix="/administrative", tags=["administrative"])
"""
 /list > get 
 return list of all administrative table name in databse with id
 return {"table_name": "staddtile", name:"Staddtile", "id": 1}

 /data/:id > post
 id yi alip, tabloya ait tüm verileri döndür

 /data/:id/:name > post
    id yi ve name i alip, where= name olan tüm verileri döndür
"""


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
def get_administrative_tables():
    """
    Get all administrative tables in the database
    
    """
    try:
        return {"data": administrative_table_list}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )


@router.get("/data/{table_id}", status_code=status.HTTP_201_CREATED)
def get_administrative_table_data(table_id: int):
    """
    You can get all data from the table by sending the table_id

    sample request: {{URL}}/administrative/data/table_id
    """
    try:
        print("table_id", table_id)
        table_name = next(
            (
                item["table_name"]
                for item in administrative_table_list
                if item["id"] == table_id
            ),
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
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )


@router.get("/data/features/{table_id}", status_code=status.HTTP_201_CREATED)
def get_administrative_feature_data(table_id: int, target_column: TargetColumn):
    try:
        # Belirtilen table_id'ye göre tablo adını bul
        table_name = next(
            (
                item["table_name"]
                for item in administrative_table_list
                if item["id"] == table_id
            ),
            None,
        )
        if table_name is None:
            raise HTTPException(status_code=404, detail="Table not found")
        # Create SQL query
        tuple_gid = tuple(target_column.target_value_list)
        sql_query = f"""
            select json_build_object(
          'type', 'FeatureCollection',
          'features', json_agg(ST_AsGeoJSON(table_name.*)::json)
          ) 
            from {table_name} as table_name where {target_column.name} in {tuple_gid}
        """
        sql_answer = database.execute_sql_query(sql_query)
        raw_data = sql_answer.fetchone()[0]
        return raw_data
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )
