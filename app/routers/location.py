import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.profile import Profile
from app.services.geocoder import geocode_city

router = APIRouter(prefix="/api/location", tags=["location"])


class LocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)


class TravelModeRequest(BaseModel):
    travel_city: str = Field(..., min_length=1, max_length=100)
    travel_latitude: float = Field(..., ge=-90, le=90)
    travel_longitude: float = Field(..., ge=-180, le=180)
    travel_until: datetime | None = None


class LocationResponse(BaseModel):
    city: str | None
    state: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
    is_traveling: bool
    travel_city: str | None
    active_city: str | None  # Which city is currently active (travel or home)
    active_latitude: float | None
    active_longitude: float | None

    model_config = {"from_attributes": True}


def get_active_location(profile: Profile) -> tuple[str | None, float | None, float | None]:
    """Return the user's current effective location (travel if active, home otherwise)."""
    if profile.is_traveling and profile.travel_city:
        if profile.travel_until and profile.travel_until < datetime.utcnow():
            return profile.city, profile.latitude, profile.longitude
        return profile.travel_city, profile.travel_latitude, profile.travel_longitude
    return profile.city, profile.latitude, profile.longitude


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in miles."""
    R = 3959  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@router.patch("/update", response_model=LocationResponse)
async def update_location(
    data: LocationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    user.profile.latitude = data.latitude
    user.profile.longitude = data.longitude
    if data.city:
        user.profile.city = data.city
    if data.state:
        user.profile.state = data.state
    if data.country:
        user.profile.country = data.country

    # If lat/lon were not explicitly provided but city was, geocode it
    # (the client usually sends lat/lon from device GPS, but geocoder
    # ensures we have coords even when only city name is available)
    if data.city and data.latitude == 0 and data.longitude == 0:
        lat, lon = await geocode_city(data.city, data.state, data.country)
        if lat is not None:
            user.profile.latitude = lat
            user.profile.longitude = lon

    await db.commit()
    await db.refresh(user.profile)

    active_city, active_lat, active_lon = get_active_location(user.profile)
    return LocationResponse(
        city=user.profile.city,
        state=user.profile.state,
        country=user.profile.country,
        latitude=user.profile.latitude,
        longitude=user.profile.longitude,
        is_traveling=user.profile.is_traveling,
        travel_city=user.profile.travel_city,
        active_city=active_city,
        active_latitude=active_lat,
        active_longitude=active_lon,
    )


@router.post("/travel", response_model=LocationResponse)
async def enable_travel_mode(
    data: TravelModeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    user.profile.is_traveling = True
    user.profile.travel_city = data.travel_city
    user.profile.travel_latitude = data.travel_latitude
    user.profile.travel_longitude = data.travel_longitude
    user.profile.travel_until = data.travel_until

    await db.commit()
    await db.refresh(user.profile)

    return LocationResponse(
        city=user.profile.city,
        state=user.profile.state,
        country=user.profile.country,
        latitude=user.profile.latitude,
        longitude=user.profile.longitude,
        is_traveling=True,
        travel_city=user.profile.travel_city,
        active_city=data.travel_city,
        active_latitude=data.travel_latitude,
        active_longitude=data.travel_longitude,
    )


@router.delete("/travel", response_model=LocationResponse)
async def disable_travel_mode(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    user.profile.is_traveling = False
    user.profile.travel_city = None
    user.profile.travel_latitude = None
    user.profile.travel_longitude = None
    user.profile.travel_until = None

    await db.commit()
    await db.refresh(user.profile)

    return LocationResponse(
        city=user.profile.city,
        state=user.profile.state,
        country=user.profile.country,
        latitude=user.profile.latitude,
        longitude=user.profile.longitude,
        is_traveling=False,
        travel_city=None,
        active_city=user.profile.city,
        active_latitude=user.profile.latitude,
        active_longitude=user.profile.longitude,
    )


@router.get("/me", response_model=LocationResponse)
async def get_my_location(
    user: User = Depends(get_current_user),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    active_city, active_lat, active_lon = get_active_location(user.profile)
    return LocationResponse(
        city=user.profile.city,
        state=user.profile.state,
        country=user.profile.country,
        latitude=user.profile.latitude,
        longitude=user.profile.longitude,
        is_traveling=user.profile.is_traveling,
        travel_city=user.profile.travel_city,
        active_city=active_city,
        active_latitude=active_lat,
        active_longitude=active_lon,
    )


# Popular cities for quick travel-to selection
POPULAR_CITIES = [
    {"city": "New York", "state": "NY", "country": "US", "lat": 40.7128, "lon": -74.0060},
    {"city": "Los Angeles", "state": "CA", "country": "US", "lat": 34.0522, "lon": -118.2437},
    {"city": "Miami", "state": "FL", "country": "US", "lat": 25.7617, "lon": -80.1918},
    {"city": "Las Vegas", "state": "NV", "country": "US", "lat": 36.1699, "lon": -115.1398},
    {"city": "San Francisco", "state": "CA", "country": "US", "lat": 37.7749, "lon": -122.4194},
    {"city": "Chicago", "state": "IL", "country": "US", "lat": 41.8781, "lon": -87.6298},
    {"city": "London", "state": None, "country": "UK", "lat": 51.5074, "lon": -0.1278},
    {"city": "Paris", "state": None, "country": "FR", "lat": 48.8566, "lon": 2.3522},
    {"city": "Dubai", "state": None, "country": "AE", "lat": 25.2048, "lon": 55.2708},
    {"city": "Tokyo", "state": None, "country": "JP", "lat": 35.6762, "lon": 139.6503},
    {"city": "Monaco", "state": None, "country": "MC", "lat": 43.7384, "lon": 7.4246},
    {"city": "Ibiza", "state": None, "country": "ES", "lat": 38.9067, "lon": 1.4206},
    {"city": "São Paulo", "state": None, "country": "BR", "lat": -23.5505, "lon": -46.6333},
    {"city": "Mexico City", "state": None, "country": "MX", "lat": 19.4326, "lon": -99.1332},
    {"city": "Mumbai", "state": None, "country": "IN", "lat": 19.0760, "lon": 72.8777},
    {"city": "Delhi", "state": None, "country": "IN", "lat": 28.7041, "lon": 77.1025},
    {"city": "Singapore", "state": None, "country": "SG", "lat": 1.3521, "lon": 103.8198},
    {"city": "Sydney", "state": None, "country": "AU", "lat": -33.8688, "lon": 151.2093},
    {"city": "Toronto", "state": None, "country": "CA", "lat": 43.6532, "lon": -79.3832},
    {"city": "Berlin", "state": None, "country": "DE", "lat": 52.5200, "lon": 13.4050},
    {"city": "Madrid", "state": None, "country": "ES", "lat": 40.4168, "lon": -3.7038},
    {"city": "Barcelona", "state": None, "country": "ES", "lat": 41.3874, "lon": 2.1686},
    {"city": "Amsterdam", "state": None, "country": "NL", "lat": 52.3676, "lon": 4.9041},
    {"city": "Milan", "state": None, "country": "IT", "lat": 45.4642, "lon": 9.1900},
    {"city": "Zurich", "state": None, "country": "CH", "lat": 47.3769, "lon": 8.5417},
    {"city": "Hong Kong", "state": None, "country": "HK", "lat": 22.3193, "lon": 114.1694},
    {"city": "Bangkok", "state": None, "country": "TH", "lat": 13.7563, "lon": 100.5018},
    {"city": "Jakarta", "state": None, "country": "ID", "lat": -6.2088, "lon": 106.8456},
    {"city": "Lagos", "state": None, "country": "NG", "lat": 6.5244, "lon": 3.3792},
    {"city": "Bogotá", "state": None, "country": "CO", "lat": 4.7110, "lon": -74.0721},
    {"city": "Buenos Aires", "state": None, "country": "AR", "lat": -34.6037, "lon": -58.3816},
    {"city": "Lima", "state": None, "country": "PE", "lat": -12.0464, "lon": -77.0428},
]


@router.get("/popular-cities")
async def get_popular_cities():
    return POPULAR_CITIES
