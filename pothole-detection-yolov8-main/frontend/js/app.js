// frontend/js/app.js
const API_BASE = "http://localhost:8000/api";

document.addEventListener("DOMContentLoaded", async () => {
    try {
        const reportsRes = await fetch(`${API_BASE}/reports/`);
        const reports = await reportsRes.json();
        
        const hotspotsRes = await fetch(`${API_BASE}/map/hotspots`);
        const hotspots = await hotspotsRes.json();
        
        let totalPotholes = reports.reduce((sum, r) => sum + r.pothole_count, 0);
        let criticalCount = reports.filter(r => r.severity === "Critical").length;
        
        document.getElementById("stat-reports").innerText = reports.length;
        document.getElementById("stat-potholes").innerText = totalPotholes;
        document.getElementById("stat-critical").innerText = criticalCount;
        document.getElementById("stat-hotspots").innerText = hotspots.length;
        
        const tbody = document.getElementById("recent-reports-table");
        if (reports.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center;">No reports filed yet. Run an inspection!</td></tr>`;
            return;
        }
        
        tbody.innerHTML = reports.slice(0, 5).map(r => `
            <tr>
                <td>📍 ${r.location_name}</td>
                <td>${r.pothole_count}</td>
                <td><span class="text-${r.severity === 'Critical' ? 'danger' : (r.severity === 'Moderate' ? 'warning' : 'success')}">${r.severity}</span></td>
                <td>${r.confidence}%</td>
                <td>${new Date(r.created_at).toLocaleDateString()}</td>
            </tr>
        `).join('');
        
    } catch (e) {
        console.error("Dashboard synchronization error:", e);
    }
});