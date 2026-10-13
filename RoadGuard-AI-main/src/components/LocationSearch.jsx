import { useState } from "react";
import { searchAddress } from "../services/geocoding";

export default function LocationSearch({ onLocationFound }) {
    const [mode, setMode] = useState("address");
    const [address, setAddress] = useState("");
    const [lat, setLat] = useState("12.9716");
    const [lon, setLon] = useState("77.5946");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    async function submit(event) {
        event.preventDefault();
        setError("");
        setBusy(true);
        try {
            let location;
            if (mode === "address") {
                if (!address.trim()) throw new Error("Enter an address or place name.");
                location = await searchAddress(address.trim());
            } else {
                const latitude = Number(lat);
                const longitude = Number(lon);
                if (!lat.trim() || !lon.trim() || !Number.isFinite(latitude) || !Number.isFinite(longitude)) {
                    throw new Error("Enter valid numeric latitude and longitude.");
                }
                if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
                    throw new Error("Latitude must be -90 to 90 and longitude -180 to 180.");
                }
                location = { lat: latitude, lon: longitude, label: `${latitude}, ${longitude}` };
            }
            onLocationFound(location);
        } catch (e) {
            setError(e.message || "Location search failed.");
        } finally {
            setBusy(false);
        }
    }

    return (
        <form className="tool-section" onSubmit={submit}>
            <div className="section-title-row">
                <span className="step-number">01</span>
                <h3>Find a location</h3>
            </div>
            <div className="segmented-control">
                <button type="button" className={mode === "address" ? "selected" : ""} onClick={() => { setMode("address"); setError(""); }}>
                    Address
                </button>
                <button type="button" className={mode === "coordinates" ? "selected" : ""} onClick={() => { setMode("coordinates"); setError(""); }}>
                    Lat / Long
                </button>
            </div>

            {mode === "address" ? (
                <label className="field-label">
                    Address or landmark
                    <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="e.g. MG Road, Bengaluru" />
                </label>
            ) : (
                <div className="coordinate-grid">
                    <label className="field-label">
                        Latitude
                        <input value={lat} onChange={(e) => setLat(e.target.value)} inputMode="decimal" placeholder="12.9716" />
                    </label>
                    <label className="field-label">
                        Longitude
                        <input value={lon} onChange={(e) => setLon(e.target.value)} inputMode="decimal" placeholder="77.5946" />
                    </label>
                </div>
            )}

            <button className="primary-button" type="submit" disabled={busy}>
                {busy ? "Searching…" : "⌕  Find location"}
            </button>
            {error && <p className="error-message">{error}</p>}
        </form>
    );
}
