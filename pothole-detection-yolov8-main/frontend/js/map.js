// frontend/js/map.js
document.addEventListener("DOMContentLoaded", async () => {
    // Initialize Leaflet map centered over a default location (e.g., Bangalore)
    const map = L.map('map').setView([12.9716, 77.5946], 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    try {
        const res = await fetch("http://localhost:8000/api/map/hotspots");
        const hotspots = await res.json();
        
        const hotspotListContainer = document.getElementById("hotspot-list-container");
        if (hotspots.length === 0) {
            hotspotListContainer.innerHTML = `<p style="color: #888;">No geographic clusters registered.</p>`;
            return;
        }
        
        hotspotListContainer.innerHTML = "";
        
        hotspots.forEach(h => {
            let markerColor = "green";
            if (h.hotspot_level === "High") markerColor = "red";
            else if (h.hotspot_level === "Moderate") markerColor = "orange";
            
            // Add custom visual representation or circle marker
            const marker = L.circleMarker([h.latitude || 12.9716, h.longitude || 77.5946], {
                radius: Math.max(8, h.report_count * 4),
                fillColor: markerColor,
                color: "#000",
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(map);
            
            marker.bindPopup(`
                <b>📍 ${h.location_name}</b><br>
                Reports Filed: ${h.report_count}<br>
                Potholes Count: ${h.total_potholes}<br>
                Severity Status: <b>${h.highest_severity}</b><br>
                Hotspot Priority: <b>${h.hotspot_level}</b>
            `);
            
            hotspotListContainer.innerHTML += `
                <div class="hotspot-item">
                    <strong>📍 ${h.location_name}</strong><br>
                    <small>Reports: ${h.report_count} | Potholes: ${h.total_potholes}</small><br>
                    <span style="color: ${markerColor === 'red' ? '#f85149' : (markerColor === 'orange' ? '#d29922' : '#3fb950')}">Priority: ${h.hotspot_level}</span>
                </div>
            `;
        });
        
    } catch (e) {
        console.error("Map intelligence fetch error:", e);
    }
});