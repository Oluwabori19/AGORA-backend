from fastapi import HTTPException, status
from app.auth import database


def get_iso_aoi(mode, lng, lat, time):
    """Return an isochrone area (AOI) as a GeoJSON FeatureCollection.

    Args:
        mode: Base pgRouting table prefix (for example, road network mode).
        lng: Longitude of the origin point.
        lat: Latitude of the origin point.
        time: Maximum travel-time/cost value used in driving distance.
    """
    try:
        # Build a spatial SQL query that:
        # 1) finds the nearest graph vertex to the provided point,
        # 2) runs pgr_drivingDistance from that start vertex up to `time`,
        # 3) collects reachable node geometries,
        # 4) creates a concave hull polygon,
        # 5) returns the result as GeoJSON FeatureCollection.
        sql_query = """
          select json_build_object(
          'type', 'FeatureCollection',
          'features', json_agg(ST_AsGeoJSON(iso.*)::json)
          )
        from (SELECT ST_ConcaveHull(ST_Collect(the_geom), 0.9) from pgr_drivingDistance(
              'SELECT gid AS id, source, target, cost_time AS cost FROM %s',
            (SELECT id
        FROM %s_vertices_pgr
        ORDER BY st_setSRID(ST_MakePoint( %s, %s), 4326) <-> %s_vertices_pgr.the_geom
        LIMIT 1),%s, false
      ) AS pt JOIN %s_vertices_pgr rd ON pt.node = rd.id ) as iso;""" % (
            mode,
            mode,
            lng,
            lat,
            mode,
            time,
            mode,
        )

        # Execute SQL against the configured database connection.
        sql_answer = database.execute_sql_query(sql_query)
        raw_data = sql_answer.fetchone()

        # Return the GeoJSON payload if query produced a row.
        if raw_data:
            return raw_data[0]
        else:
            # Query executed but did not return expected payload.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Database query failed",
            )
    except Exception as e:
        # Normalize unexpected runtime/database errors to HTTP 500.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )