"""FastAPI application entry point with CORS middleware and router registration."""

from typing import Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.router import auth, geometry_operations, test, administrative, ligfinder, parcel_maximizer, geoserver_proxy, ligfinder_advanced, parcel_maximizer_advanced, geometry_operations_advanced, administrative_advanced

from app.auth.database import Base
from app.auth.database import engine

from sqlalchemy.orm import Session
from app.auth.database import get_db
from fastapi import FastAPI, Depends
from sqlalchemy import text


# Create database tables on startup
Base.metadata.create_all(bind=engine)

# Initialize FastAPI application
app = FastAPI()

# Configure CORS (Cross-Origin Resource Sharing) with specific origins for credential support
origins = [
    "http://localhost:5173",    # Vite dev server (frontend)
    "http://localhost:3000",    # Alternative port
    "http://localhost:8080",    # GeoServer UI
    "http://localhost:8002",    # Backend itself
    "https://agora.dcs.hcu-hamburg.de"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"message": "Hello world"}


# Register all API endpoint routers
app.include_router(test.router)
app.include_router(auth.router)
app.include_router(geometry_operations.router)
app.include_router(administrative.router)
app.include_router(ligfinder.router)
app.include_router(parcel_maximizer.router)
app.include_router(geoserver_proxy.router)
app.include_router(ligfinder_advanced.router)
app.include_router(parcel_maximizer_advanced.router)
app.include_router(geometry_operations_advanced.router)
app.include_router(administrative_advanced.router)
