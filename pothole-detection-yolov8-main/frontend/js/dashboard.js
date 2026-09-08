document.addEventListener("DOMContentLoaded", async () => {
    try {
        const [hotSummary, recentReports] = await Promise.all([
            API.get("/api/hotspots/summary").catch(() => null),
            API.get("/api/reports").catch(() => [])
        ]);

        if (hotSummary) {
            document.getElementById("stat-reports").textContent = hotSummary.total_reports || 0;
            document.getElementById("stat-potholes").textContent = hotSummary.total_potholes || 0;
            document.getElementById("stat-hotspots").textContent = hotSummary.active_hotspots || 0;
            document.getElementById("stat-critical").textContent = hotSummary.critical_zones || 0;
        }

        const tbody = document.getElementById("recent-reports-body");
        tbody.innerHTML = "";

        if (!recentReports || recentReports.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No detection reports recorded yet.</td></tr>`;
            return;
        }

        recentReports.slice(0, 5).forEach(r => {
            const tr = document.createElement("tr");
            const badgeClass = `badge-${(r.severity || "LOW").toLowerCase()}`;
            const dateStr = r.created_at ? new Date(r.created_at).toLocaleString() : "N/A";

            tr.innerHTML = `
                <td>#${r.id}</td>
                <td><span style="text-transform: uppercase; font-size: 0.75rem; font-weight: 600;">${r.media_type}</span></td>
                <td>${r.location_name || 'Unknown Location'}</td>
                <td><strong>${r.pothole_count}</strong></td>
                <td><span class="badge ${badgeClass}">${r.severity}</span></td>
                <td>${(r.confidence * 100).toFixed(0)}%</td>
                <td style="color: var(--text-muted); font-size: 0.8rem;">${dateStr}</td>
            `;
            tbody.appendChild(tr);
        });

    } catch (err) {
        console.error("Dashboard initialization error:", err);
    }
});