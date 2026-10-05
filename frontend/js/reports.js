// ==========================================================
// ROADGUARD AI
// REPORTS AUDIT REGISTER
// ==========================================================

document.addEventListener("DOMContentLoaded", () => {
    loadReports();

    // Refresh report list every 5 seconds
    setInterval(loadReports, 5000);
});


// ==========================================================
// LOAD REPORTS FROM DATABASE
// ==========================================================

async function loadReports() {

    const tbody = document.getElementById("reports-table-body");

    if (!tbody) {
        console.error("reports-table-body not found.");
        return;
    }

    try {

        const reports = await API.get("/api/reports");

        if (!Array.isArray(reports)) {
            throw new Error("Reports API did not return an array.");
        }

        tbody.innerHTML = "";

        // --------------------------------------------------
        // NO REPORTS
        // --------------------------------------------------

        if (reports.length === 0) {

            tbody.innerHTML = `
                <tr>
                    <td
                        colspan="9"
                        style="
                            text-align:center;
                            color:var(--text-muted);
                            padding:2rem;
                        "
                    >
                        <i class="fa-solid fa-database"
                           style="font-size:1.5rem; margin-bottom:0.6rem;">
                        </i>

                        <div>
                            No detection reports found.
                        </div>

                        <small>
                            Run an AI detection to create a report.
                        </small>
                    </td>
                </tr>
            `;

            return;
        }


        // --------------------------------------------------
        // DISPLAY REAL DATABASE REPORTS
        // --------------------------------------------------

        reports.forEach(report => {

            const tr = document.createElement("tr");

            // ------------------------------------------------
            // SEVERITY
            // ------------------------------------------------

            const severity =
                String(report.severity || "LOW").toUpperCase();

            const badgeClass =
                `badge-${severity.toLowerCase()}`;


            // ------------------------------------------------
            // COORDINATES
            // ------------------------------------------------

            let coordinates = "N/A";

            const lat = Number(report.latitude);
            const lon = Number(report.longitude);

            if (
                Number.isFinite(lat) &&
                Number.isFinite(lon) &&
                !(lat === 0 && lon === 0)
            ) {
                coordinates =
                    `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
            }


            // ------------------------------------------------
            // POTHOLE COUNT
            // ------------------------------------------------

            const potholeCount =
                Number(report.pothole_count || 0);


            // ------------------------------------------------
            // CONFIDENCE
            // ------------------------------------------------

            const confidence =
                Number(report.confidence || 0);

            const confidencePercent =
                Math.max(
                    0,
                    Math.min(
                        100,
                        confidence * 100
                    )
                );


            // ------------------------------------------------
            // CREATED DATE
            // ------------------------------------------------

            let dateText = "N/A";

            if (report.created_at) {

                const date =
                    new Date(report.created_at);

                if (!Number.isNaN(date.getTime())) {

                    dateText =
                        date.toLocaleString();
                }
            }


            // ------------------------------------------------
            // MEDIA TYPE
            // ------------------------------------------------

            const mediaType =
                String(
                    report.media_type || "UNKNOWN"
                ).toUpperCase();


            // ------------------------------------------------
            // LOCATION
            // ------------------------------------------------

            const location =
                report.location_name ||
                "Unknown Location";


            // ------------------------------------------------
            // BUILD ROW
            // ------------------------------------------------

            tr.innerHTML = `

                <td>
                    <strong>
                        #${Number(report.id)}
                    </strong>
                </td>


                <td>
                    <span
                        style="
                            text-transform:uppercase;
                            font-size:0.75rem;
                            font-weight:600;
                        "
                    >
                        ${escapeHtml(mediaType)}
                    </span>
                </td>


                <td>
                    ${escapeHtml(location)}
                </td>


                <td
                    style="
                        font-family:monospace;
                        font-size:0.8rem;
                        color:var(--text-muted);
                    "
                >
                    ${escapeHtml(coordinates)}
                </td>


                <td>
                    <strong>
                        ${potholeCount}
                    </strong>
                </td>


                <td>
                    <span class="badge ${badgeClass}">
                        ${escapeHtml(severity)}
                    </span>
                </td>


                <td>
                    ${confidencePercent.toFixed(0)}%
                </td>


                <td
                    style="
                        color:var(--text-muted);
                        font-size:0.8rem;
                    "
                >
                    ${escapeHtml(dateText)}
                </td>


                <td style="white-space:nowrap;">

                    <!-- REAL COLMAP 3D VIEW -->
                    <a
                        class="btn btn-primary"
                        style="
                            padding:0.35rem 0.6rem;
                            font-size:0.75rem;
                            margin-right:0.35rem;
                            text-decoration:none;
                        "
                        href="/3d-view?report_id=${Number(report.id)}"
                        title="Open real 3D reconstruction"
                    >
                        <i class="fa-solid fa-cube"></i>
                        3D
                    </a>


                    <!-- PDF DOWNLOAD -->
                    <a
                        class="btn"
                        style="
                            padding:0.35rem 0.55rem;
                            font-size:0.75rem;
                            margin-right:0.35rem;
                            text-decoration:none;
                            background:#b91c1c;
                            color:#ffffff;
                            border-radius:4px;
                            font-weight:600;
                        "
                        href="/api/reports/${Number(report.id)}/download/pdf"
                        download="RoadGuard_Report_${Number(report.id)}.pdf"
                        title="Download PDF report"
                    >
                        <i class="fa-solid fa-file-pdf"></i>
                        PDF
                    </a>


                    <!-- CSV DOWNLOAD -->
                    <a
                        class="btn"
                        style="
                            padding:0.35rem 0.55rem;
                            font-size:0.75rem;
                            margin-right:0.35rem;
                            text-decoration:none;
                            background:#047857;
                            color:#ffffff;
                            border-radius:4px;
                            font-weight:600;
                        "
                        href="/api/reports/${Number(report.id)}/download/csv"
                        download="RoadGuard_Report_${Number(report.id)}.csv"
                        title="Download CSV report"
                    >
                        <i class="fa-solid fa-file-csv"></i>
                        CSV
                    </a>


                    <!-- DELETE -->
                    <button
                        class="btn btn-danger"
                        style="
                            padding:0.35rem 0.6rem;
                            font-size:0.75rem;
                        "
                        onclick="deleteReport(${Number(report.id)})"
                        title="Delete report"
                    >
                        <i class="fa-solid fa-trash"></i>
                    </button>

                </td>
            `;


            tbody.appendChild(tr);

        });

    }

    catch (error) {

        console.error(
            "Failed to load reports:",
            error
        );

        tbody.innerHTML = `
            <tr>
                <td
                    colspan="9"
                    style="
                        text-align:center;
                        color:var(--severity-critical);
                        padding:2rem;
                    "
                >
                    <i class="fa-solid fa-triangle-exclamation"></i>

                    <div>
                        Failed to load reports from backend.
                    </div>

                    <small>
                        ${escapeHtml(
            error.message ||
            "Unknown API error"
        )}
                    </small>
                </td>
            </tr>
        `;
    }
}


// ==========================================================
// DELETE REPORT
// ==========================================================

async function deleteReport(id) {

    const confirmed =
        confirm(
            `Are you sure you want to delete report #${id}?`
        );

    if (!confirmed) {
        return;
    }

    try {

        await API.delete(
            `/api/reports/${id}`
        );

        await loadReports();

    }

    catch (error) {

        console.error(
            "Delete report failed:",
            error
        );

        alert(
            "Failed to delete report: " +
            (
                error.message ||
                error
            )
        );
    }
}


// ==========================================================
// HTML ESCAPE
// ==========================================================

function escapeHtml(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}