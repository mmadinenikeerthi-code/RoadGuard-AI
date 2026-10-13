import { useRef, useState } from "react";
import CesiumMap from "./components/CesiumMap";
import LocationSearch from "./components/LocationSearch";
import RoutePlanner from "./components/RoutePlanner";

export default function App() {
    const mapRef = useRef(null);
    const [status, setStatus] = useState("Search for a place or enter coordinates.");

    function handleLocation(location) {
        mapRef.current?.showLocation(location);
        setStatus(`Showing ${location.label}`);
    }

    async function handleRoute(start, end) {
        setStatus("Calculating route…");
        try {
            const response = await fetch(
                `https://router.project-osrm.org/route/v1/driving/${start.lon},${start.lat};${end.lon},${end.lat}?overview=full&geometries=geojson&steps=true`
            );
            if (!response.ok) throw new Error("Routing service request failed.");
            const data = await response.json();
            if (data.code !== "Ok" || !data.routes?.length) {
                throw new Error("No route found between those locations.");
            }
            const route = data.routes[0];
            mapRef.current?.showRoute(route.geometry.coordinates, start, end);
            setStatus(`Route ready · ${(route.distance / 1000).toFixed(1)} km · about ${Math.round(route.duration / 60)} min`);
            return route;
        } catch (error) {
            setStatus(error.message || "Could not calculate route.");
            throw error;
        }
    }

    return (
        <main className="app-shell">
            <header className="topbar">
                <div className="brand-mark">RG</div>
                <div>
                    <h1>RoadGuard AI</h1>
                    <p>3D road explorer & navigation</p>
                </div>
                <span className="topbar-tag">MAP CONSOLE</span>
            </header>

            <section className="workspace">
                <aside className="sidebar">
                    <div className="section-heading">
                        <span className="eyebrow">LOCATION TOOLS</span>
                        <h2>Explore roads</h2>
                        <p>Find a location, then plan a route.</p>
                    </div>
                    <LocationSearch onLocationFound={handleLocation} />
                    <div className="panel-divider" />
                    <RoutePlanner onCalculateRoute={handleRoute} />
                    <div className="status-card" role="status">
                        <span className="status-dot" />
                        <div>
                            <strong>Map status</strong>
                            <p>{status}</p>
                        </div>
                    </div>
                    <p className="disclaimer">
                        Prototype: public geocoding and routing services may have usage limits.
                        Verify road routes before real-world travel.
                    </p>
                </aside>

                <section className="map-panel" aria-label="3D map">
                    <div className="map-badge"><span /> 3D MAP VIEW</div>
                    <CesiumMap ref={mapRef} />
                    <div className="map-hint">Scroll to zoom · Drag to explore · Search to fly to a location</div>
                </section>
            </section>
        </main>
    );
}
