"""Application factory and HTTP routes; run with uvicorn app.main:app."""

import logging
import math
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path as PathParameter, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import AddressRepository
from app.distance import haversine_km
from app.models import Address, AddressInput, NearbyAddress

logger = logging.getLogger("uvicorn.error.address_book")
AddressId = Annotated[int, PathParameter(ge=1, le=9223372036854775807)]


def create_app(database_path: str | Path | None = None) -> FastAPI:
    default_path = Path(__file__).resolve().parent.parent / "data" / "addresses.db"
    configured_path = database_path if database_path is not None else os.getenv("ADDRESS_BOOK_DB", str(default_path))
    repository = AddressRepository(Path(configured_path).expanduser().resolve())

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        repository.initialize()
        logger.info("Address book database initialized")
        yield

    application = FastAPI(
        title="Address Book API", version="1.0.0", lifespan=lifespan,
        description="Create and manage addresses, or search by great-circle distance in kilometres.",
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exception: RequestValidationError):
        # Avoid echoing addresses and nonfinite floats in JSON error responses.
        detail = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                  for error in exception.errors()]
        logger.info("Request rejected by input validation")
        return JSONResponse(status_code=422, content={"detail": detail})

    @application.exception_handler(sqlite3.Error)
    async def database_error(request: Request, exception: sqlite3.Error):
        logger.error("Database operation failed (%s)", type(exception).__name__)
        return JSONResponse(status_code=500, content={"detail": "Database operation failed"})

    @application.post("/addresses", response_model=Address, status_code=201, tags=["Addresses"])
    def create_address(payload: AddressInput):
        result = repository.create(payload)
        logger.info("Created address id=%s", result.id)
        return result

    @application.get("/addresses", response_model=list[Address], tags=["Addresses"])
    def list_addresses(
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    ):
        return repository.list_addresses(limit, offset)

    # Register this static path before /addresses/{address_id}.
    @application.get("/addresses/nearby", response_model=list[NearbyAddress], tags=["Addresses"])
    def nearby_addresses(
        latitude: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
        longitude: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
        radius_km: Annotated[float, Query(ge=0, allow_inf_nan=False,
                                       description="Inclusive great-circle radius in kilometres")],
    ):
        matches = []
        for saved in repository.all():
            distance = haversine_km(latitude, longitude, saved.latitude, saved.longitude)
            # A one-micrometre tolerance keeps mathematical boundaries inclusive.
            if distance <= radius_km or math.isclose(distance, radius_km, rel_tol=0, abs_tol=1e-9):
                matches.append(NearbyAddress(**saved.model_dump(), distance_km=distance))
        return sorted(matches, key=lambda result: (result.distance_km, result.id))

    @application.get("/addresses/{address_id}", response_model=Address, tags=["Addresses"])
    def get_address(address_id: AddressId):
        result = repository.get(address_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Address not found")
        return result

    @application.put("/addresses/{address_id}", response_model=Address, tags=["Addresses"],
                     summary="Replace all address fields")
    def replace_address(address_id: AddressId, payload: AddressInput):
        result = repository.replace(address_id, payload)
        if result is None:
            raise HTTPException(status_code=404, detail="Address not found")
        logger.info("Updated address id=%s", address_id)
        return result

    @application.delete("/addresses/{address_id}", status_code=204, tags=["Addresses"])
    def delete_address(address_id: AddressId):
        if not repository.delete(address_id):
            raise HTTPException(status_code=404, detail="Address not found")
        logger.info("Deleted address id=%s", address_id)
        return Response(status_code=204)

    return application


app = create_app()
