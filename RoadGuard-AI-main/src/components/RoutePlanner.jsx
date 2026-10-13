import { useState } from "react";
import { searchAddress } from "../services/geocoding";

async function resolvePlace(value) {
    const trimmed = value.trim();
    if (!trimmed) throw new Error("Enter both a start and destination.");
    const parts = trimmed.split(/[,\s]+/).filter(Boolean);
    if (parts.length === 2 && parts.every((part) => Number.isFinite(Number(part)))) {
        const lat = Number(parts[0]);
        const lon = Number(parts[1]);
        if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
            throw new Error(`Invalid coordinates: ${trimmed}`);
        }
        return { lat, lon, label: trimmed };
    }
    return searchAddress(trimmed);
}

export default function RoutePlanner({ onCalculateRoute }) {
    const [start, setStart] = useState("12.9716, 77.5946");
    const [destination, setDestination] = useState("12.2958, 76.6394");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    async function submit(event) {
        event.preventDefault();
        setBusy(true);
        setError("");
        try {
            const [startPoint, endPoint] = await Promise.all([
                resolvePlace(start),
                resolvePlace(destination)
            ]);
            await onCalculateRoute(startPoint, endPoint);
        } catch (e) {
            setError(e.message || "Could not plan route.");
        } finally {
            setBusy(false);
        }
    }

    return (
        <form className="tool-section" onSubmit={submit}>
            <div className="section-title-row">
                <span className="step-number">02</span>
                <h3>Plan a route</h3>
            </div>
            <p className="helper-text">Enter an address or coordinates as “latitude, longitude”.</p>
            <label className="field-label">
                <span className="label-with-icon"><span className="route-dot start-dot" /> Starting point</span>
                <input value={start} onChange={(e) => setStart(e.target.value)} placeholder="e.g. 12.9716, 77.5946" />
            </label>
            <label className="field-label">
                <span className="label-with-icon"><span className="route-dot end-dot" /> Destination</span>
                <input value={destination} onChange={(e) => setDestination(e.target.value)} placeholder="e.g. Mysuru Palace, Mysuru" />
            </label>
            <button className="secondary-button" type="submit" disabled={busy}>
                {busy ? "Calculating route…" : "↗  Show road directions"}
            </button>
            {error && <p className="error-message">{error}</p>}
        </form>
    );
}
