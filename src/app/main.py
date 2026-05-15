"""FastAPI application entry point with CORS middleware and router registration."""

from typing import Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.router import auth, geometry_operations, test, administrative, ligfinder, parcel_maximizer

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

# Configure CORS (Cross-Origin Resource Sharing) to allow all origins
origin = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origin,  # Allow requests from any origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all request headers
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
