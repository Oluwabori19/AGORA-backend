"""Models for isochrone calculation requests using pgRouting."""

from pydantic import BaseModel, Field


class CenterObject(BaseModel):
    """Geographic center point in WGS84 coordinates."""
    lng: float = Field(..., example=13.4)
    lat: float = Field(..., example=52.5)


class IsochroneCreate(BaseModel):
    """Request model for isochrone area calculation."""
    mode: str = Field(..., example="walk_network,bike_network,drive_network")  # Routing network mode
    time: float = Field(..., example=30)  # Travel time in minutes
    center: CenterObject = Field(..., example={"lng": 13.4, "lat": 52.5})
