// frontend/js/reports.js
document.addEventListener("DOMContentLoaded", async () => {
    try {
        const res = await fetch("http://localhost:8000/api/reports/");
        const reports = await res.json();
        
        const tbody = document.getElementById("full-reports-table");
        if (reports.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center;">No persistent damage logs found.</td></tr>`;
            return;
        }
        
        tbody.innerHTML = reports.map(r => `
            <tr>
                <td>#${r.id}</td>
                <td>${r.media_type.toUpperCase()}</td>
                <td>📍 ${r.location_name}</td>
                <td>${r.pothole_count}</td>
                <td><span class="text-${r.severity === 'Critical' ? 'danger' : (r.severity === 'Moderate' ? 'warning' : 'success')}">${r.severity}</span></td>
                <td>${r.confidence}%</td>
                <td>${new Date(r.created_at).toLocaleString()}</td>
            </tr>
        `).join('');
    } catch (e) {
        console.error("Reports loading error:", e);
    }
});