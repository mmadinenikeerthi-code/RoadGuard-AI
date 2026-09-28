from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(
    prefix="/api/routing",
    tags=["Routing"]
)

OSRM_URL = "https://router.project-osrm.org"


@router.get("/route")
async def get_route(
    start_lat: float = Query(...),
    start_lon: float = Query(...),
    end_lat: float = Query(...),
    end_lon: float = Query(...),
    alternatives: bool = True
):
    """
    Calculate routes between the user's live location
    and the selected destination using OSRM.
    """

    coordinates = (
        f"{start_lon},{start_lat};"
        f"{end_lon},{end_lat}"
    )

    url = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{coordinates}"
    )

    params = {
        "alternatives": "true" if alternatives else "false",
        "steps": "true",
        "overview": "full",
        "geometries": "geojson"
    }

    try:
        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:

            response = await client.get(
                url,
                params=params
            )

        response.raise_for_status()

        data = response.json()

        if data.get("code") != "Ok":
            raise HTTPException(
                status_code=404,
                detail="No route could be found."
            )

        routes = []

        for index, route in enumerate(
            data.get("routes", [])
        ):

            routes.append({
                "id": index + 1,

                "distance_meters": route.get(
                    "distance",
                    0
                ),

                "duration_seconds": route.get(
                    "duration",
                    0
                ),

                "geometry": route.get(
                    "geometry",
                    {}
                ),

                "legs": route.get(
                    "legs",
                    []
                )
            })

        return {
            "success": True,
            "routes": routes
        }

    except httpx.HTTPError as exc:

        raise HTTPException(
            status_code=502,
            detail=f"Routing service error: {exc}"
        )