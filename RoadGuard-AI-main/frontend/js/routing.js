// Optional reusable OSRM route helper. App.jsx currently calls OSRM directly.
export async function getDrivingRoute(start, end) {
    const url = `https://router.project-osrm.org/route/v1/driving/${start.lon},${start.lat};${end.lon},${end.lat}?overview=full&geometries=geojson&steps=true`;
    const response = await fetch(url);
    if (!response.ok) throw new Error("Routing service request failed.");
    const data = await response.json();
    if (data.code !== "Ok" || !data.routes?.length) {
        throw new Error("No driving route found.");
    }
    return data.routes[0];
}
