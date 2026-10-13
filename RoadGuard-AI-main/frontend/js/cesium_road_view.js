/* =========================================================
   RoadGuard AI - CesiumJS 3D Satellite Road View
   Satellite Imagery + Real Geolocated Pothole Defect Layers
   ========================================================= */

(() => {
    "use strict";

    const CONFIG_URL = "/api/cesium/config";
    const REPORTS_URL = "/api/reports/";

    let viewer = null;
    let allReports = [];
    let geolocatedReports = [];
    let unlocatedReports = [];
    let markersVisible = true;
    let currentFilter = "all";
    let selectedReport = null;

    // DOM Elements
    const container = document.getElementById("cesiumContainer");
    const statusElement = document.getElementById("mapStatus");
    const loadingElement = document.getElementById("mapLoading");
    const loadingMessage = document.getElementById("loadingMessage");
    const drawerElement = document.getElementById("detectionsDrawer");
    const popupElement = document.getElementById("potholePopupCard");

    /* =========================================================
       STATUS AND LOADING HELPERS
    ========================================================= */

    function setStatus(message, state = "loading") {
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.dataset.state = state;
        }
        console.log(`[RoadGuard Cesium] ${message}`);
    }

    function setLoading(visible, message = "") {
        if (loadingElement) {
            loadingElement.classList.toggle("hidden", !visible);
        }
        if (loadingMessage && message) {
            loadingMessage.textContent = message;
        }
    }

    /* =========================================================
       API REQUEST HELPER
    ========================================================= */

    async function fetchJSON(url) {
        const response = await fetch(url, {
            headers: { Accept: "application/json" },
            cache: "no-store"
        });
        if (!response.ok) {
            throw new Error(`Request failed (${response.status}): ${url}`);
        }
        return await response.json();
    }

    /* =========================================================
       COORDINATE & REPORT HELPERS
    ========================================================= */

    function isValidGPS(lat, lon) {
        if (lat === null || lat === undefined || lon === null || lon === undefined) return false;
        const nLat = Number(lat);
        const nLon = Number(lon);
        if (!Number.isFinite(nLat) || !Number.isFinite(nLon)) return false;
        if (nLat === 0 && nLon === 0) return false; // Common empty placeholder
        if (nLat < -90 || nLat > 90 || nLon < -180 || nLon > 180) return false;
        return true;
    }

    function getSeverity(report) {
        const sev = String(report.severity || "LOW").toUpperCase();
        if (sev.includes("CRIT") || sev.includes("HIGH") || sev.includes("SEV")) return "HIGH";
        if (sev.includes("MED") || sev.includes("MOD")) return "MEDIUM";
        return "LOW";
    }

    function getSeverityCesiumColor(severity) {
        switch (severity) {
            case "HIGH":
                return Cesium.Color.fromCssColorString("#ef4444"); // Red
            case "MEDIUM":
                return Cesium.Color.fromCssColorString("#f97316"); // Orange
            case "LOW":
            default:
                return Cesium.Color.fromCssColorString("#eab308"); // Yellow
        }
    }

    function getSeverityBadgeClass(severity) {
        switch (severity) {
            case "HIGH":
                return "badge-high";
            case "MEDIUM":
                return "badge-medium";
            case "LOW":
            default:
                return "badge-low";
        }
    }

    function escapeHtml(str) {
        return String(str || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    /* =========================================================
       MARKER GENERATION ENGINE
    ========================================================= */

    function createPotholeEntity(report) {
        const lat = Number(report.latitude);
        const lon = Number(report.longitude);
        const severity = getSeverity(report);
        const color = getSeverityCesiumColor(severity);
        const potholes = Number(report.pothole_count) || 1;
        const conf = report.confidence ? Math.round(report.confidence <= 1.0 ? report.confidence * 100 : report.confidence) : 0;

        const position = Cesium.Cartesian3.fromDegrees(lon, lat, 2.0);

        const entity = viewer.entities.add({
            id: `pothole-report-${report.id}`,
            name: `Report #${report.id} (${potholes} Potholes)`,
            position: position,
            properties: report,
            point: {
                pixelSize: 14,
                color: color,
                outlineColor: Cesium.Color.WHITE,
                outlineWidth: 2.5,
                heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                disableDepthTestDistance: Number.POSITIVE_INFINITY
            },
            label: {
                text: `#${report.id} · ${potholes} pothole${potholes > 1 ? 's' : ''}`,
                font: "12px 'Inter', sans-serif",
                fillColor: Cesium.Color.WHITE,
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 3,
                style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                pixelOffset: new Cesium.Cartesian2(0, -22),
                heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000),
                disableDepthTestDistance: Number.POSITIVE_INFINITY
            }
        });

        return entity;
    }

    /* =========================================================
       SIDEBAR DRAWER RENDERING
    ========================================================= */

    function renderGeolocatedList(reports) {
        const list = document.getElementById("geolocatedList");
        if (!list) return;

        const filtered = reports.filter(r => {
            if (currentFilter === "all") return true;
            return getSeverity(r).toLowerCase() === currentFilter.toLowerCase();
        });

        if (filtered.length === 0) {
            list.innerHTML = `
                <div style="text-align:center; padding:30px 10px; color:var(--text-muted); font-size:13px;">
                    <i class="fa-solid fa-map-location-dot" style="font-size:26px; margin-bottom:8px; display:block; color:#64748b;"></i>
                    No geolocated pothole reports match this filter.
                </div>
            `;
            return;
        }

        list.innerHTML = "";
        filtered.forEach(report => {
            const severity = getSeverity(report);
            const badgeClass = getSeverityBadgeClass(severity);
            const conf = report.confidence ? Math.round(report.confidence <= 1.0 ? report.confidence * 100 : report.confidence) : 0;
            const potholes = Number(report.pothole_count) || 1;
            const lat = Number(report.latitude).toFixed(6);
            const lon = Number(report.longitude).toFixed(6);
            const locName = (report.location_name && report.location_name !== "Unknown Location") 
                ? report.location_name 
                : "Road Inspection Point";

            const card = document.createElement("div");
            card.className = "detection-card";
            card.dataset.reportId = report.id;
            card.innerHTML = `
                <div class="detection-card-top">
                    <span class="detection-card-title">Report #${report.id}</span>
                    <span class="badge ${badgeClass}">${severity} RISK</span>
                </div>
                <div class="detection-card-meta">
                    <div><i class="fa-solid fa-map-pin"></i> <strong>${escapeHtml(locName)}</strong></div>
                    <div style="margin-top:3px; color:#94a3b8; font-size:11px;">
                        <i class="fa-solid fa-location-dot"></i> ${lat}, ${lon}
                    </div>
                </div>
                <div class="detection-card-actions">
                    <span class="card-stat-pill">
                        <strong>${potholes}</strong> pothole${potholes > 1 ? 's' : ''} · ${conf}% conf.
                    </span>
                    <button class="zoom-to-road-btn" type="button" onclick="window.RoadGuardCesium.zoomToPothole(${report.id})">
                        <i class="fa-solid fa-street-view"></i> Zoom to Road
                    </button>
                </div>
            `;

            card.addEventListener("click", (e) => {
                if (e.target.closest(".zoom-to-road-btn")) return;
                showPotholePopup(report);
            });

            list.appendChild(card);
        });
    }

    function renderUnlocatedList(reports) {
        const list = document.getElementById("unlocatedList");
        if (!list) return;

        if (reports.length === 0) {
            list.innerHTML = `
                <div style="text-align:center; padding:30px 10px; color:var(--text-muted); font-size:13px;">
                    <i class="fa-solid fa-circle-check" style="font-size:26px; margin-bottom:8px; display:block; color:#22c55e;"></i>
                    All processed media files have valid GPS coordinates.
                </div>
            `;
            return;
        }

        list.innerHTML = "";
        reports.forEach(report => {
            const severity = getSeverity(report);
            const badgeClass = getSeverityBadgeClass(severity);
            const conf = report.confidence ? Math.round(report.confidence <= 1.0 ? report.confidence * 100 : report.confidence) : 0;
            const potholes = Number(report.pothole_count) || 0;
            const dateStr = report.created_at ? new Date(report.created_at).toLocaleDateString() : "Recent";

            const card = document.createElement("div");
            card.className = "detection-card";
            card.innerHTML = `
                <div class="detection-card-top">
                    <span class="detection-card-title">Report #${report.id} (${dateStr})</span>
                    <span class="badge ${badgeClass}">${severity}</span>
                </div>
                <div class="detection-card-meta">
                    <div><i class="fa-solid fa-video"></i> Media: ${escapeHtml(report.media_type || 'video')} · <strong>${potholes} potholes</strong></div>
                    <div style="color:#ef4444; font-size:11px; margin-top:4px;">
                        <i class="fa-solid fa-triangle-exclamation"></i> GPS coordinates missing or (0, 0)
                    </div>
                </div>
                <div class="detection-card-actions">
                    <span class="card-stat-pill">AI Confidence: ${conf}%</span>
                    <a href="/reports" class="zoom-to-road-btn" style="text-decoration:none;">
                        <i class="fa-solid fa-file-lines"></i> View Report
                    </a>
                </div>
            `;
            list.appendChild(card);
        });
    }

    /* =========================================================
       POPUP HUD CARD
    ========================================================= */

    function showPotholePopup(report) {
        if (!report || !popupElement) return;
        selectedReport = report;

        const severity = getSeverity(report);
        const badgeClass = getSeverityBadgeClass(severity);
        const conf = report.confidence ? Math.round(report.confidence <= 1.0 ? report.confidence * 100 : report.confidence) : 0;
        const potholes = Number(report.pothole_count) || 1;
        const lat = Number(report.latitude).toFixed(6);
        const lon = Number(report.longitude).toFixed(6);
        const locName = (report.location_name && report.location_name !== "Unknown Location") 
            ? report.location_name 
            : "Road Inspection Point";
        const dateStr = report.created_at ? new Date(report.created_at).toLocaleString() : "Recent inspection";

        document.getElementById("popupTitle").textContent = `Pothole Report #${report.id}`;
        const sevBadge = document.getElementById("popupSeverityBadge");
        sevBadge.className = `badge ${badgeClass}`;
        sevBadge.textContent = `${severity} RISK`;

        document.getElementById("popupCoords").textContent = `${lat}° N, ${lon}° E`;
        document.getElementById("popupLocationName").textContent = locName;
        document.getElementById("popupPotholesCount").textContent = `${potholes} Defect${potholes > 1 ? 's' : ''}`;
        document.getElementById("popupConfidence").textContent = `${conf}% YOLOv8 Accuracy`;
        document.getElementById("popupTimestamp").textContent = dateStr;
        document.getElementById("popupMediaType").textContent = report.media_type || "Inspection Video";

        const zoomBtn = document.getElementById("btnPopupZoomRoad");
        zoomBtn.onclick = () => zoomToPothole(report.id);

        const repLink = document.getElementById("popupReportLink");
        repLink.href = `/reports`;

        popupElement.classList.remove("hidden");
    }

    function hidePotholePopup() {
        if (popupElement) {
            popupElement.classList.add("hidden");
        }
    }

    /* =========================================================
       CAMERA FLIGHT & VIEW PRESETS
    ========================================================= */

    function zoomToPothole(reportId) {
        const report = geolocatedReports.find(r => r.id === Number(reportId));
        if (!report) {
            console.warn(`[RoadGuard Cesium] Report #${reportId} not found in geolocated list.`);
            return;
        }

        const lat = Number(report.latitude);
        const lon = Number(report.longitude);

        // Smooth flight down to road level (~120m altitude, 45 degree tilt for realistic 3D perspective)
        viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(lon, lat - 0.0008, 120),
            orientation: {
                heading: Cesium.Math.toRadians(0),
                pitch: Cesium.Math.toRadians(-45),
                roll: 0.0
            },
            duration: 2.2,
            complete: () => {
                showPotholePopup(report);
            }
        });
    }

    function focusAllPotholes() {
        if (!viewer || geolocatedReports.length === 0) return;

        viewer.flyTo(viewer.entities, {
            duration: 2.0,
            offset: new Cesium.HeadingPitchRange(
                Cesium.Math.toRadians(0),
                Cesium.Math.toRadians(-40),
                Math.max(2500, geolocatedReports.length * 1000)
            )
        });
    }

    function setTopDownView() {
        if (!viewer) return;
        const currentPos = viewer.camera.positionCartographic;
        viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromRadians(currentPos.longitude, currentPos.latitude, Math.max(currentPos.height, 1500)),
            orientation: {
                heading: viewer.camera.heading,
                pitch: Cesium.Math.toRadians(-90),
                roll: 0.0
            },
            duration: 1.5
        });
    }

    function set3DAngledView() {
        if (!viewer) return;
        const currentPos = viewer.camera.positionCartographic;
        viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromRadians(currentPos.longitude, currentPos.latitude, Math.max(currentPos.height, 800)),
            orientation: {
                heading: viewer.camera.heading,
                pitch: Cesium.Math.toRadians(-35),
                roll: 0.0
            },
            duration: 1.5
        });
    }

    function resetOrbitView() {
        if (!viewer) return;
        viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(78.9629, 20.5937, 8500000),
            orientation: {
                heading: Cesium.Math.toRadians(0),
                pitch: Cesium.Math.toRadians(-90),
                roll: 0.0
            },
            duration: 2.0
        });
    }

    function toggleMarkers() {
        markersVisible = !markersVisible;
        const btn = document.getElementById("btnToggleMarkers");
        const txt = document.getElementById("toggleMarkersText");

        if (viewer) {
            viewer.entities.values.forEach(entity => {
                entity.show = markersVisible;
            });
        }

        if (btn && txt) {
            btn.classList.toggle("active", markersVisible);
            txt.textContent = markersVisible ? "Markers: ON" : "Markers: OFF";
        }
    }

    /* =========================================================
       DATA LOADER
    ========================================================= */

    async function loadReports() {
        setLoading(true, "Loading verified GPS pothole detections...");

        try {
            const data = await fetchJSON(REPORTS_URL);
            allReports = Array.isArray(data) ? data : (data.reports || []);

            geolocatedReports = [];
            unlocatedReports = [];

            allReports.forEach(report => {
                if (isValidGPS(report.latitude, report.longitude)) {
                    geolocatedReports.push(report);
                } else {
                    unlocatedReports.push(report);
                }
            });

            console.log(`[RoadGuard Cesium] Loaded ${allReports.length} reports: ${geolocatedReports.length} geolocated, ${unlocatedReports.length} unlocated.`);

            // Clear old entities
            viewer.entities.removeAll();

            // Populate Cesium map with geolocated pothole markers
            geolocatedReports.forEach(report => {
                createPotholeEntity(report);
            });

            // Update badge counts in UI
            const countGeoEl = document.getElementById("countGeolocated");
            const countUnlocEl = document.getElementById("countUnlocated");
            const badgeEl = document.getElementById("drawerBadge");

            if (countGeoEl) countGeoEl.textContent = String(geolocatedReports.length);
            if (countUnlocEl) countUnlocEl.textContent = String(unlocatedReports.length);
            if (badgeEl) badgeEl.textContent = String(geolocatedReports.length);

            // Render sidebar drawer lists
            renderGeolocatedList(geolocatedReports);
            renderUnlocatedList(unlocatedReports);

            // Set status
            if (geolocatedReports.length > 0) {
                setStatus(`Satellite map ready · ${geolocatedReports.length} geolocated pothole detection(s)`, "success");

                // Check URL params for specific report focus
                const urlParams = new URLSearchParams(window.location.search);
                const targetReportId = urlParams.get("report_id");

                if (targetReportId) {
                    setTimeout(() => zoomToPothole(targetReportId), 600);
                } else {
                    focusAllPotholes();
                }
            } else {
                setStatus("Satellite map active · No GPS-geolocated potholes found", "success");
                resetOrbitView();
            }

        } catch (error) {
            console.error("[RoadGuard Cesium] Error loading reports:", error);
            setStatus("Failed to load reports from backend.", "error");
        } finally {
            setLoading(false);
        }
    }

    /* =========================================================
       INITIALIZE CESIUM GLOBE
    ========================================================= */

    async function initializeCesium() {
        if (!container) {
            throw new Error("Missing #cesiumContainer on page.");
        }
        if (!window.Cesium) {
            throw new Error("CesiumJS library failed to load from CDN. Check your internet connection.");
        }

        setLoading(true, "Connecting to Cesium ion...");

        // 1. Fetch Cesium ion Token
        let token = "";
        try {
            const config = await fetchJSON(CONFIG_URL);
            if (config.configured && config.cesium_token) {
                token = config.cesium_token;
            }
        } catch (cfgErr) {
            console.warn("[RoadGuard Cesium] Config endpoint error:", cfgErr);
        }

        if (!token) {
            throw new Error("Cesium ion token is missing. Please configure CESIUM_ION_TOKEN in your project .env file.");
        }

        Cesium.Ion.defaultAccessToken = token;

        setLoading(true, "Loading Cesium ion real satellite imagery...");

        // 2. Pre-fetch Satellite Imagery Provider (Asset ID 2 = Bing Maps Aerial / Cesium World Imagery)
        let baseLayer = undefined;
        try {
            const imageryProvider = await Cesium.IonImageryProvider.fromAssetId(2);
            baseLayer = new Cesium.ImageryLayer(imageryProvider);
            console.log("[RoadGuard Cesium] Cesium ion Asset 2 aerial satellite imagery loaded successfully.");
        } catch (imageryErr) {
            console.warn("[RoadGuard Cesium] Direct Asset 2 load failed, attempting createWorldImageryAsync:", imageryErr);
            try {
                baseLayer = await Cesium.createWorldImageryAsync({
                    style: Cesium.IonWorldImageryStyle.AERIAL_WITH_LABELS
                });
            } catch (fallbackErr) {
                console.error("[RoadGuard Cesium] Could not initialize satellite imagery provider:", fallbackErr);
            }
        }

        // 3. Pre-fetch World Terrain
        let terrainProvider = undefined;
        try {
            terrainProvider = await Cesium.createWorldTerrainAsync({
                requestWaterMask: false,
                requestVertexNormals: true
            });
            console.log("[RoadGuard Cesium] Cesium World Terrain initialized.");
        } catch (terrainErr) {
            console.warn("[RoadGuard Cesium] World Terrain unavailable, continuing with standard surface:", terrainErr);
        }

        // 4. Initialize Cesium Viewer
        viewer = new Cesium.Viewer("cesiumContainer", {
            baseLayer: baseLayer,
            terrainProvider: terrainProvider,
            animation: false,
            timeline: false,
            geocoder: true,
            homeButton: false,
            sceneModePicker: true,
            navigationHelpButton: false,
            baseLayerPicker: true,
            fullscreenButton: true,
            infoBox: false, // Handled via our custom HUD popup modal
            selectionIndicator: false,
            shouldAnimate: false
        });

        // 5. Enhance Visual Scene
        viewer.scene.globe.enableLighting = true;
        viewer.scene.globe.depthTestAgainstTerrain = true;

        // 6. Entity Clustering Configuration
        if (viewer.clustering) {
            viewer.clustering.enabled = true;
            viewer.clustering.pixelRange = 25;
            viewer.clustering.minimumClusterSize = 3;
        }

        // 7. Interactive ScreenSpace Click Handler
        const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        handler.setInputAction((movement) => {
            const picked = viewer.scene.pick(movement.position);
            if (Cesium.defined(picked) && picked.id && picked.id.properties) {
                const report = picked.id.properties.getValue(Cesium.JulianDate.now());
                showPotholePopup(report);
            } else {
                hidePotholePopup();
            }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        // 8. Bind Toolbar & Drawer Events
        bindUIEvents();

        // 9. Load Genuine Reports
        await loadReports();
    }

    /* =========================================================
       UI EVENT LISTENERS
    ========================================================= */

    function bindUIEvents() {
        const btnToggleMarkers = document.getElementById("btnToggleMarkers");
        if (btnToggleMarkers) btnToggleMarkers.onclick = toggleMarkers;

        const btnFocusAll = document.getElementById("btnFocusAll");
        if (btnFocusAll) btnFocusAll.onclick = focusAllPotholes;

        const btnTopDown = document.getElementById("btnTopDown");
        if (btnTopDown) btnTopDown.onclick = setTopDownView;

        const btn3DAngle = document.getElementById("btn3DAngle");
        if (btn3DAngle) btn3DAngle.onclick = set3DAngledView;

        const btnResetGlobe = document.getElementById("btnResetGlobe");
        if (btnResetGlobe) btnResetGlobe.onclick = resetOrbitView;

        const btnToggleDrawer = document.getElementById("btnToggleDrawer");
        if (btnToggleDrawer) btnToggleDrawer.onclick = () => drawerElement.classList.toggle("open");

        const btnCloseDrawer = document.getElementById("btnCloseDrawer");
        if (btnCloseDrawer) btnCloseDrawer.onclick = () => drawerElement.classList.remove("open");

        const btnClosePopup = document.getElementById("btnClosePopup");
        if (btnClosePopup) btnClosePopup.onclick = hidePotholePopup;

        // Drawer Tabs
        window.switchDrawerTab = (tab) => {
            const tabBtnGeo = document.getElementById("tabBtnGeolocated");
            const tabBtnUnloc = document.getElementById("tabBtnUnlocated");
            const contentGeo = document.getElementById("tabContentGeolocated");
            const contentUnloc = document.getElementById("tabContentUnlocated");

            if (tab === "geolocated") {
                tabBtnGeo.classList.add("active");
                tabBtnUnloc.classList.remove("active");
                contentGeo.classList.remove("hidden");
                contentUnloc.classList.add("hidden");
            } else {
                tabBtnGeo.classList.remove("active");
                tabBtnUnloc.classList.add("active");
                contentGeo.classList.add("hidden");
                contentUnloc.classList.remove("hidden");
            }
        };

        // Risk Filter
        window.filterRisk = (level) => {
            currentFilter = level;
            document.querySelectorAll(".filter-pill").forEach(pill => {
                pill.classList.toggle("active", pill.dataset.filter === level);
            });

            // Filter Cesium markers
            if (viewer) {
                viewer.entities.values.forEach(entity => {
                    if (!markersVisible) {
                        entity.show = false;
                        return;
                    }
                    if (level === "all") {
                        entity.show = true;
                    } else {
                        const rep = entity.properties ? entity.properties.getValue(Cesium.JulianDate.now()) : null;
                        if (rep) {
                            entity.show = getSeverity(rep).toLowerCase() === level.toLowerCase();
                        }
                    }
                });
            }

            // Re-render list
            renderGeolocatedList(geolocatedReports);
        };
    }

    // Expose global methods for inline HTML onclick handlers
    window.RoadGuardCesium = {
        zoomToPothole: zoomToPothole,
        focusAllPotholes: focusAllPotholes,
        loadReports: loadReports
    };

    /* =========================================================
       INITIALIZATION ENTRYPOINT
    ========================================================= */

    async function start() {
        try {
            await initializeCesium();
        } catch (error) {
            console.error("[RoadGuard Cesium] Initialization error:", error);
            setStatus(error.message || "Could not load satellite map.", "error");
            setLoading(true, error.message || "Failed to initialize satellite imagery.");
        }
    }

    document.addEventListener("DOMContentLoaded", start);

})();
