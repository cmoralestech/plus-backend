"""City geocoder with static cache and Nominatim (OpenStreetMap) API fallback.

Supports global cities. Checks a static dict first for fast lookups on common
US cities, then falls back to the Nominatim API for any city worldwide.
"""

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

# city_name (lowercase) -> (lat, lon)
# Includes top ~200 US cities by population + state capitals
CITY_COORDS: dict[str, tuple[float, float]] = {
    # Major metros
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "houston": (29.7604, -95.3698),
    "phoenix": (33.4484, -112.0740),
    "philadelphia": (39.9526, -75.1652),
    "san antonio": (29.4241, -98.4936),
    "san diego": (32.7157, -117.1611),
    "dallas": (32.7767, -96.7970),
    "san jose": (37.3382, -121.8863),
    "austin": (30.2672, -97.7431),
    "jacksonville": (30.3322, -81.6557),
    "fort worth": (32.7555, -97.3308),
    "columbus": (39.9612, -82.9988),
    "charlotte": (35.2271, -80.8431),
    "indianapolis": (39.7684, -86.1581),
    "san francisco": (37.7749, -122.4194),
    "seattle": (47.6062, -122.3321),
    "denver": (39.7392, -104.9903),
    "washington": (38.9072, -77.0369),
    "washington dc": (38.9072, -77.0369),
    "nashville": (36.1627, -86.7816),
    "oklahoma city": (35.4676, -97.5164),
    "el paso": (31.7619, -106.4850),
    "boston": (42.3601, -71.0589),
    "portland": (45.5152, -122.6784),
    "las vegas": (36.1699, -115.1398),
    "memphis": (35.1495, -90.0490),
    "louisville": (38.2527, -85.7585),
    "baltimore": (39.2904, -76.6122),
    "milwaukee": (43.0389, -87.9065),
    "albuquerque": (35.0844, -106.6504),
    "tucson": (32.2226, -110.9747),
    "fresno": (36.7378, -119.7871),
    "sacramento": (38.5816, -121.4944),
    "mesa": (33.4152, -111.8315),
    "kansas city": (39.0997, -94.5786),
    "atlanta": (33.7490, -84.3880),
    "omaha": (41.2565, -95.9345),
    "colorado springs": (38.8339, -104.8214),
    "raleigh": (35.7796, -78.6382),
    "long beach": (33.7701, -118.1937),
    "virginia beach": (36.8529, -75.9780),
    "miami": (25.7617, -80.1918),
    "oakland": (37.8044, -122.2712),
    "minneapolis": (44.9778, -93.2650),
    "tampa": (27.9506, -82.4572),
    "tulsa": (36.1540, -95.9928),
    "arlington": (32.7357, -97.1081),
    "new orleans": (29.9511, -90.0715),
    "wichita": (37.6872, -97.3301),
    "cleveland": (41.4993, -81.6944),
    "bakersfield": (35.3733, -119.0187),
    "aurora": (39.7294, -104.8319),
    "anaheim": (33.8366, -117.9143),
    "honolulu": (21.3069, -157.8583),
    "santa ana": (33.7455, -117.8677),
    "riverside": (33.9533, -117.3962),
    "corpus christi": (27.8006, -97.3964),
    "lexington": (38.0406, -84.5037),
    "pittsburgh": (40.4406, -79.9959),
    "anchorage": (61.2181, -149.9003),
    "stockton": (37.9577, -121.2908),
    "cincinnati": (39.1031, -84.5120),
    "saint paul": (44.9537, -93.0900),
    "st paul": (44.9537, -93.0900),
    "toledo": (41.6528, -83.5379),
    "newark": (40.7357, -74.1724),
    "greensboro": (36.0726, -79.7920),
    "buffalo": (42.8864, -78.8784),
    "plano": (33.0198, -96.6989),
    "lincoln": (40.8258, -96.6852),
    "henderson": (36.0395, -114.9817),
    "fort wayne": (41.0793, -85.1394),
    "jersey city": (40.7282, -74.0776),
    "st petersburg": (27.7676, -82.6403),
    "chula vista": (32.6401, -117.0842),
    "norfolk": (36.8508, -76.2859),
    "orlando": (28.5383, -81.3792),
    "chandler": (33.3062, -111.8413),
    "laredo": (27.5036, -99.5076),
    "madison": (43.0731, -89.4012),
    "durham": (35.9940, -78.8986),
    "lubbock": (33.5779, -101.8552),
    "garland": (32.9126, -96.6389),
    "glendale": (33.5387, -112.1860),
    "hialeah": (25.8576, -80.2781),
    "reno": (39.5296, -119.8138),
    "baton rouge": (30.4515, -91.1871),
    "irvine": (33.6846, -117.8265),
    "chesapeake": (36.7682, -76.2875),
    "irving": (32.8140, -96.9489),
    "scottsdale": (33.4942, -111.9261),
    "north las vegas": (36.1989, -115.1175),
    "fremont": (37.5485, -121.9886),
    "gilbert": (33.3528, -111.7890),
    "san bernardino": (34.1083, -117.2898),
    "boise": (43.6150, -116.2023),
    "birmingham": (33.5207, -86.8025),
    "richmond": (37.5407, -77.4360),
    "spokane": (47.6588, -117.4260),
    "rochester": (43.1566, -77.6088),
    "des moines": (41.5868, -93.6250),
    "montgomery": (32.3792, -86.3077),
    "modesto": (37.6391, -120.9969),
    "fayetteville": (35.0527, -78.8784),
    "tacoma": (47.2529, -122.4443),
    "shreveport": (32.5252, -93.7502),
    "fontana": (34.0922, -117.4350),
    "moreno valley": (33.9425, -117.2297),
    "akron": (41.0814, -81.5190),
    "yonkers": (40.9312, -73.8988),
    "little rock": (34.7465, -92.2896),
    "salt lake city": (40.7608, -111.8910),
    "huntsville": (34.7304, -86.5861),
    "grand rapids": (42.9634, -85.6681),
    "amarillo": (35.2220, -101.8313),
    "tallahassee": (30.4383, -84.2807),
    "providence": (41.8240, -71.4128),
    "hartford": (41.7658, -72.6734),
    "charleston": (32.7765, -79.9311),
    "savannah": (32.0809, -81.0912),
    "wilmington": (34.2104, -77.8868),
    "knoxville": (35.9606, -83.9207),
    "chattanooga": (35.0456, -85.3097),
    "fort lauderdale": (26.1224, -80.1373),
    "west palm beach": (26.7153, -80.0534),
    "naples": (26.1420, -81.7948),
    "sarasota": (27.3364, -82.5307),
    "st louis": (38.6270, -90.1994),
    "saint louis": (38.6270, -90.1994),
    "detroit": (42.3314, -83.0458),
    "miami beach": (25.7907, -80.1300),
    "coral gables": (25.7217, -80.2684),
    "newport beach": (33.6189, -117.9298),
    "beverly hills": (34.0736, -118.4004),
    "santa monica": (34.0195, -118.4912),
    "malibu": (34.0259, -118.7798),
    "aspen": (39.1911, -106.8175),
    "palm beach": (26.7056, -80.0364),
    "greenville": (34.8526, -82.3940),
    "columbia": (34.0007, -81.0348),
    "jackson": (32.2988, -90.1848),
    "springfield": (39.7817, -89.6501),
    "dayton": (39.7589, -84.1916),
    "provo": (40.2338, -111.6585),
    "sioux falls": (43.5446, -96.7311),
    "santa fe": (35.6870, -105.9378),
    "annapolis": (38.9784, -76.4922),
    "olympia": (47.0379, -122.9007),
    "juneau": (58.3005, -134.4197),
    "trenton": (40.2206, -74.7699),
    "dover": (39.1582, -75.5244),
    "frankfort": (38.2009, -84.8733),
    "carson city": (39.1638, -119.7674),
    "pierre": (44.3683, -100.3510),
    "bismarck": (46.8083, -100.7837),
    "helena": (46.5884, -112.0245),
    "cheyenne": (41.1400, -104.8202),
    "concord": (43.2081, -71.5376),
    "montpelier": (44.2601, -72.5754),
    "augusta": (44.3106, -69.7795),
    "topeka": (39.0473, -95.6752),
    "jefferson city": (38.5767, -92.1735),
    "lansing": (42.7325, -84.5555),
    "harrisburg": (40.2732, -76.8867),
    "albany": (42.6526, -73.7562),
}

# State name -> capital coords (fallback)
STATE_CAPITALS: dict[str, tuple[float, float]] = {
    "alabama": (32.3792, -86.3077),
    "alaska": (58.3005, -134.4197),
    "arizona": (33.4484, -112.0740),
    "arkansas": (34.7465, -92.2896),
    "california": (38.5816, -121.4944),
    "colorado": (39.7392, -104.9903),
    "connecticut": (41.7658, -72.6734),
    "delaware": (39.1582, -75.5244),
    "florida": (30.4383, -84.2807),
    "georgia": (33.7490, -84.3880),
    "hawaii": (21.3069, -157.8583),
    "idaho": (43.6150, -116.2023),
    "illinois": (39.7817, -89.6501),
    "indiana": (39.7684, -86.1581),
    "iowa": (41.5868, -93.6250),
    "kansas": (39.0473, -95.6752),
    "kentucky": (38.2009, -84.8733),
    "louisiana": (30.4515, -91.1871),
    "maine": (44.3106, -69.7795),
    "maryland": (38.9784, -76.4922),
    "massachusetts": (42.3601, -71.0589),
    "michigan": (42.7325, -84.5555),
    "minnesota": (44.9778, -93.2650),
    "mississippi": (32.2988, -90.1848),
    "missouri": (38.5767, -92.1735),
    "montana": (46.5884, -112.0245),
    "nebraska": (40.8258, -96.6852),
    "nevada": (39.1638, -119.7674),
    "new hampshire": (43.2081, -71.5376),
    "new jersey": (40.2206, -74.7699),
    "new mexico": (35.6870, -105.9378),
    "new york": (42.6526, -73.7562),
    "north carolina": (35.7796, -78.6382),
    "north dakota": (46.8083, -100.7837),
    "ohio": (39.9612, -82.9988),
    "oklahoma": (35.4676, -97.5164),
    "oregon": (45.5152, -122.6784),
    "pennsylvania": (40.2732, -76.8867),
    "rhode island": (41.8240, -71.4128),
    "south carolina": (34.0007, -81.0348),
    "south dakota": (44.3683, -100.3510),
    "tennessee": (36.1627, -86.7816),
    "texas": (30.2672, -97.7431),
    "utah": (40.7608, -111.8910),
    "vermont": (44.2601, -72.5754),
    "virginia": (37.5407, -77.4360),
    "washington": (47.0379, -122.9007),
    "west virginia": (38.3498, -81.6326),
    "wisconsin": (43.0731, -89.4012),
    "wyoming": (41.1400, -104.8202),
    "district of columbia": (38.9072, -77.0369),
}

# Runtime cache for Nominatim results (query string -> (lat, lon))
_nominatim_cache: dict[str, tuple[float, float]] = {}

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "Plus/1.0 (meetyourplus.com)"


async def _query_nominatim(city: str, state: str | None, country: str | None) -> tuple[float | None, float | None]:
    """Call Nominatim API and return (lat, lon) or (None, None) on failure."""
    parts = [p for p in [city, state, country] if p]
    query = ", ".join(parts)

    # Check runtime cache
    cache_key = query.lower()
    if cache_key in _nominatim_cache:
        return _nominatim_cache[cache_key]

    # Respect Nominatim rate limit (max 1 request/sec)
    await asyncio.sleep(1)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": _USER_AGENT},
                timeout=10.0,
            )
        resp.raise_for_status()
        results = resp.json()

        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            _nominatim_cache[cache_key] = (lat, lon)
            return lat, lon

    except Exception:
        logger.warning("Nominatim geocoding failed for %r", query, exc_info=True)

    return None, None


async def geocode_city(
    city: str | None,
    state: str | None,
    country: str | None = None,
) -> tuple[float | None, float | None]:
    """Resolve city (+ optional state/country) to lat/lon.

    Lookup order:
    1. Static CITY_COORDS dict (fast, no network)
    2. Nominatim API (global coverage, cached per server lifetime)
    3. STATE_CAPITALS fallback for US states

    Returns (latitude, longitude) or (None, None) if not found.
    """
    if not city:
        return None, None

    city_lower = city.strip().lower()

    # 1. Direct city lookup in static cache
    if city_lower in CITY_COORDS:
        return CITY_COORDS[city_lower]

    # Try "city, state abbreviation" patterns
    # e.g. someone might type "New York City" -> try "new york"
    for suffix in [" city", " town", " township"]:
        stripped = city_lower.replace(suffix, "").strip()
        if stripped in CITY_COORDS:
            return CITY_COORDS[stripped]

    # 2. Query Nominatim API for global coverage
    lat, lon = await _query_nominatim(city, state, country)
    if lat is not None:
        return lat, lon

    # 3. Fall back to state capital (US only)
    if state:
        state_lower = state.strip().lower()
        if state_lower in STATE_CAPITALS:
            return STATE_CAPITALS[state_lower]

    return None, None
