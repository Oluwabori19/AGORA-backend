from fastapi import HTTPException, status
from app.auth import database

_ALLOWED_MODES = {"walk_network", "bike_network", "drive_network"}


def get_iso_aoi(mode, lng, lat, time):
    try:
        # mode is used as a table-name identifier in multiple positions — it cannot be
        # parameterised. Validate against the known allowlist before interpolating.
        if mode not in _ALLOWED_MODES:
            raise ValueError(
                f"Invalid mode: {mode!r}. Must be one of {sorted(_ALLOWED_MODES)}."
            )

        # mode is safe to interpolate after allowlist validation.
        # lng, lat, time appear in the outer query and are bound as named params.
        sql_query = f"""
          select json_build_object(
          'type', 'FeatureCollection',
          'features', json_agg(ST_AsGeoJSON(iso.*)::json)
          )
        from (SELECT ST_ConcaveHull(ST_Collect(the_geom), 0.9) from pgr_drivingDistance(
              'SELECT gid AS id, source, target, cost_time AS cost FROM {mode}',
            (SELECT id
        FROM {mode}_vertices_pgr
        ORDER BY st_setSRID(ST_MakePoint(:lng, :lat), 4326) <-> {mode}_vertices_pgr.the_geom
        LIMIT 1), :time, false
      ) AS pt JOIN {mode}_vertices_pgr rd ON pt.node = rd.id ) as iso;"""

        sql_answer = database.execute_sql_query(
            sql_query, {"lng": lng, "lat": lat, "time": time}
        )
        raw_data = sql_answer.fetchone()
        if raw_data:
            return raw_data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Database query failed",
            )
    except (ValueError, HTTPException):
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )
