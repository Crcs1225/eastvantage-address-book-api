"""Request and response contracts shared by the API and persistence layer."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


class AddressInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True,
        json_schema_extra={"examples": [{
            "address": "123 Main Street, Manila", "label": "Home",
            "latitude": 14.5995, "longitude": 120.9842,
        }]},
    )

    address: str = Field(min_length=1, max_length=1000, pattern=r"^[^\x00]*$")
    label: str | None = Field(default=None, max_length=200)
    latitude: Latitude
    longitude: Longitude


class Address(AddressInput):
    id: int


class NearbyAddress(Address):
    distance_km: float
