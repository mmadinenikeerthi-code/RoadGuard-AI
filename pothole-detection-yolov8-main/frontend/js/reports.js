// ==========================================================
// ROADGUARD AI
// REPORTS AUDIT REGISTER
// ==========================================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        loadReports();

        // Refresh every 5 seconds
        setInterval(
            loadReports,
            5000
        );
    }
);


// ==========================================================
// LOAD REPORTS
// ==========================================================

async function loadReports() {

    const tbody =
        document.getElementById(
            "reports-table-body"
        );

    if (!tbody) {

        console.error(
            "reports-table-body not found."
        );

        return;
    }

    try {

        const reports =
            await API.get(
                "/api/reports"
            );

        tbody.innerHTML = "";

        // --------------------------------------------------
        // NO REPORTS
        // --------------------------------------------------

        if (
            !Array.isArray(reports) ||
            reports.length === 0
        ) {

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
                        No detection logs recorded
                        in database.
                    </td>
                </tr>
            `;

            return;
        }

        // --------------------------------------------------
        // DISPLAY REPORTS
        // --------------------------------------------------

        reports.forEach(
            report => {

                const tr =
                    document.createElement(
                        "tr"
                    );

                // ------------------------------------------
                // Severity
                // ------------------------------------------

                const severity =
                    (
                        report.severity ||
                        "LOW"
                    ).toUpperCase();

                const badgeClass =
                    `badge-${severity.toLowerCase()}`;

                // ------------------------------------------
                // Coordinates
                // ------------------------------------------

                let coordinates =
                    "N/A";

                if (
                    report.latitude !== null &&
                    report.latitude !== undefined &&
                    report.longitude !== null &&
                    report.longitude !== undefined
                ) {

                    const lat =
                        Number(
                            report.latitude
                        );

                    const lon =
                        Number(
                            report.longitude
                        );

                    if (
                        Number.isFinite(lat) &&
                        Number.isFinite(lon)
                    ) {

                        coordinates =
                            `${lat.toFixed(5)}, ` +
                            `${lon.toFixed(5)}`;
                    }
                }

                // ------------------------------------------
                // Pothole count
                // ------------------------------------------

                const potholeCount =
                    Number(
                        report.pothole_count || 0
                    );

                // ------------------------------------------
                // Confidence
                // ------------------------------------------

                const confidence =
                    Number(
                        report.confidence || 0
                    );

                const confidencePercent =
                    Math.max(
                        0,
                        Math.min(
                            100,
                            confidence * 100
                        )
                    );

                // ------------------------------------------
                // Date
                // ------------------------------------------

                let dateText = "N/A";

                if (
                    report.created_at
                ) {

                    const date =
                        new Date(
                            report.created_at
                        );

                    if (
                        !Number.isNaN(
                            date.getTime()
                        )
                    ) {

                        dateText =
                            date.toLocaleString();
                    }
                }

                // ------------------------------------------
                // Media type
                // ------------------------------------------

                const mediaType =
                    (
                        report.media_type ||
                        "UNKNOWN"
                    ).toUpperCase();

                // ------------------------------------------
                // Location
                // ------------------------------------------

                const location =
                    report.location_name ||
                    "Unknown Location";

                // ------------------------------------------
                // CREATE TABLE ROW
                // ------------------------------------------

                tr.innerHTML = `

                    <td>
                        #${report.id}
                    </td>

                    <td>
                        <span
                            style="
                                text-transform:uppercase;
                                font-size:0.75rem;
                                font-weight:600;
                            "
                        >
                            ${escapeHtml(
                                mediaType
                            )}
                        </span>
                    </td>

                    <td>
                        ${escapeHtml(
                            location
                        )}
                    </td>

                    <td
                        style="
                            font-family:monospace;
                            font-size:0.8rem;
                            color:var(--text-muted);
                        "
                    >
                        ${coordinates}
                    </td>

                    <td>
                        <strong>
                            ${potholeCount}
                        </strong>
                    </td>

                    <td>
                        <span
                            class="badge ${badgeClass}"
                        >
                            ${escapeHtml(
                                severity
                            )}
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
                        ${dateText}
                    </td>

                    <td>

                        <button
                            class="btn btn-danger"
                            style="
                                padding:0.35rem 0.6rem;
                                font-size:0.75rem;
                            "
                            onclick="
                                deleteReport(
                                    ${report.id}
                                )
                            "
                            title="Delete report"
                        >

                            <i
                                class="fa-solid fa-trash"
                            ></i>

                        </button>

                    </td>
                `;

                tbody.appendChild(
                    tr
                );
            }
        );

    } catch (error) {

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
                    Failed to load reports
                    from API.
                    <br>
                    <small>
                        Check that the
                        RoadGuard AI backend
                        is running.
                    </small>
                </td>
            </tr>
        `;
    }
}


// ==========================================================
// DELETE REPORT
// ==========================================================

async function deleteReport(
    id
) {

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

    } catch (error) {

        console.error(
            "Delete report failed:",
            error
        );

        alert(
            "Failed to delete record: " +
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

function escapeHtml(
    value
) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}