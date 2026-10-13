
document.addEventListener("DOMContentLoaded", () => {
    const statReports = document.getElementById("stat-reports");
    const statPotholes = document.getElementById("stat-potholes");
    const statHotspots = document.getElementById("stat-hotspots");
    const statCritical = document.getElementById("stat-critical");
    const tbody = document.getElementById("recent-reports-body");

    // Start with empty dashboard statistics
    function showEmptyDashboard() {
        if (statReports) statReports.textContent = "0";
        if (statPotholes) statPotholes.textContent = "0";
        if (statHotspots) statHotspots.textContent = "0";
        if (statCritical) statCritical.textContent = "0";

        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7"
                        style="text-align:center; color:var(--text-muted); padding:2rem;">
                        No video reports yet. Upload a video to get started!
                    </td>
                </tr>
            `;
        }
    }

    async function loadDashboard() {
        try {
            const [reportsResponse, summaryResponse] = await Promise.all([
                API.get("/api/reports"),
                API.get("/api/hotspots/summary")
            ]);

            // Support either a direct array or { reports: [...] }
            const reports = Array.isArray(reportsResponse)
                ? reportsResponse
                : Array.isArray(reportsResponse?.reports)
                    ? reportsResponse.reports
                    : [];

            // No reports: show a genuinely empty dashboard
            if (reports.length === 0) {
                showEmptyDashboard();
                return;
            }

            const summary = summaryResponse || {};

            // Calculate report statistics from stored reports
            const totalPotholes = reports.reduce((total, report) => {
                const count = Number(report.pothole_count) || 0;
                return total + count;
            }, 0);

            if (statReports) {
                statReports.textContent = reports.length;
            }

            if (statPotholes) {
                statPotholes.textContent = totalPotholes;
            }

            if (statHotspots) {
                statHotspots.textContent = summary.total_hotspots ?? 0;
            }

            if (statCritical) {
                statCritical.textContent = summary.critical_hotspots ?? 0;
            }

            // Update recent reports table
            if (!tbody) return;

            tbody.innerHTML = "";

            reports.slice(0, 5).forEach((report) => {
                const tr = document.createElement("tr");
                const severity = report.severity || "LOW";
                const badgeClass = `badge-${severity.toLowerCase()}`;

                const date = report.created_at
                    ? new Date(report.created_at).toLocaleString()
                    : "N/A";

                const confidence = Number(report.confidence) || 0;

                tr.innerHTML = `
                    <td>#${report.id ?? "N/A"}</td>
                    <td>
                        <span style="text-transform:uppercase;font-size:0.75rem;font-weight:600;">
                            ${report.media_type || "N/A"}
                        </span>
                    </td>
                    <td></td>
                    <td><strong>${report.pothole_count ?? 0}</strong></td>
                    <td><span class="badge ${badgeClass}">${severity}</span></td>
                    <td>${(confidence * 100).toFixed(0)}%</td>
                    <td style="color:var(--text-muted);font-size:0.8rem;">${date}</td>
                `;

                // Insert location as text rather than interpreting it as HTML
                tr.children[2].textContent =
                    report.location_name || "Unknown Location";

                tbody.appendChild(tr);
            });

        } catch (error) {
            console.error("Failed to load dashboard:", error);

            // Do not show stale numbers when the API fails
            if (statReports) statReports.textContent = "—";
            if (statPotholes) statPotholes.textContent = "—";
            if (statHotspots) statHotspots.textContent = "—";
            if (statCritical) statCritical.textContent = "—";

            if (tbody) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7"
                            style="text-align:center;color:var(--text-muted);padding:2rem;">
                            Unable to load data. Check that the backend is running.
                        </td>
                    </tr>
                `;
            }
        }
    }

    // Load immediately
    loadDashboard();

    // Refresh automatically after uploads and processing
    setInterval(loadDashboard, 5000);
});
