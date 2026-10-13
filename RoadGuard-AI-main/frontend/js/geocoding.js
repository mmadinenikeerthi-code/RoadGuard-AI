// Prototype geocoder using OpenStreetMap Nominatim.
// Follow its usage policy and avoid sending high-volume or automated requests.
export async function searchAddress(query) {
    const url = new URL("https://nominatim.openstreetmap.org/search");
    url.searchParams.set("q", query);
    url.searchParams.set("format", "jsonv2");
    url.searchParams.set("limit", "1");

    const response = await fetch(url.toString(), {
        headers: { Accept: "application/json" }
    });
    if (!response.ok) throw new Error("Address lookup failed. Try again or enter coordinates.");
    const results = await response.json();
    if (!results.length) throw new Error("No matching address found.");

    return {
        lat: Number(results[0].lat),
        lon: Number(results[0].lon),
        label: results[0].display_name
    };
}
