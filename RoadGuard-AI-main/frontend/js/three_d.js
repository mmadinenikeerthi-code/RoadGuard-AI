// ==========================================================
// ROADGUARD AI — 3D ROAD VISUALIZATION ENGINE
// frontend/js/three_d.js
//
// Clean Three.js implementation with real PLY/COLMAP
// reconstruction loading, OrbitControls, bounding-box framing,
// bounded polling, robust error handling, and zero fake geometry.
// ==========================================================

import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js";
import { PLYLoader } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/PLYLoader.js";
import { OBJLoader } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/OBJLoader.js";
import { GLTFLoader } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/GLTFLoader.js";

// ==========================================================
// STATE
// ==========================================================

let scene = null;
let camera = null;
let renderer = null;
let controls = null;

let modelGroup = null;
let potholeGroup = null;

let raycaster = null;
let mouse = null;

let currentReportId = null;
let currentSceneData = null;
let currentBoundingBox = null;
let animationId = null;
let resizeObserver = null;

let pollingTimer = null;
let pollingTimeoutTimer = null;

// ==========================================================
// DOM ELEMENT RESOLUTION HELPERS
// ==========================================================

function getContainer() {
    return document.getElementById("threeContainer") || document.getElementById("three-container");
}

function getLoadingOverlay() {
    return document.getElementById("loadingOverlay") || document.getElementById("loading");
}

function getErrorOverlay() {
    return document.getElementById("threeErrorOverlay") || document.getElementById("errorMessage");
}

function getStatusBar() {
    return document.getElementById("threeStatusBar");
}

// ==========================================================
// INITIALIZATION
// ==========================================================

document.addEventListener("DOMContentLoaded", initializeApp);

async function initializeApp() {
    try {
        initThreeScene();
        bindUIEvents();
        await loadReportCatalogAndStart();
    } catch (error) {
        console.error("[RoadGuard 3D] Critical initialization error:", error);
        showError("Viewer Initialization Failed", error.message || "Failed to initialize 3D scene.", false, true);
    }
}

// ==========================================================
// THREE.JS SCENE SETUP
// ==========================================================

function initThreeScene() {
    const container = getContainer();
    if (!container) {
        throw new Error("3D container element (#threeContainer) was not found in document.");
    }

    // 1. Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07111f);

    // 2. Dimensions
    const width = Math.max(container.clientWidth || 900, 100);
    const height = Math.max(container.clientHeight || 620, 100);

    // 3. Camera
    camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 3000);
    camera.position.set(0, 12, 28);

    // 4. Renderer
    renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: false,
        powerPreference: "high-performance"
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height, false);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.style.display = "block";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";

    container.appendChild(renderer.domElement);

    // 5. OrbitControls
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.screenSpacePanning = true;
    controls.minDistance = 0.5;
    controls.maxDistance = 500;
    controls.target.set(0, 0, 0);

    // 6. Lights
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x182233, 2.2);
    scene.add(hemiLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 2.2);
    dirLight1.position.set(20, 35, 25);
    dirLight1.castShadow = true;
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x60a5fa, 1.2);
    dirLight2.position.set(-25, 20, -20);
    scene.add(dirLight2);

    // 7. Groups
    modelGroup = new THREE.Group();
    modelGroup.name = "reconstructedModelGroup";
    scene.add(modelGroup);

    potholeGroup = new THREE.Group();
    potholeGroup.name = "potholeMarkerGroup";
    scene.add(potholeGroup);

    // 8. Raycaster & Mouse
    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2();

    renderer.domElement.addEventListener("click", onSceneClick);
    renderer.domElement.addEventListener("mousemove", onSceneMouseMove);

    // 9. Resize Handling
    window.addEventListener("resize", onWindowResize);
    if (typeof ResizeObserver !== "undefined") {
        resizeObserver = new ResizeObserver(() => {
            requestAnimationFrame(resizeRenderer);
        });
        resizeObserver.observe(container);
    }

    // 10. Start Animation Loop
    animate();
}

// ==========================================================
// RENDER LOOP & RESIZE
// ==========================================================

function animate() {
    animationId = requestAnimationFrame(animate);
    if (controls) {
        controls.update();
    }
    if (renderer && scene && camera) {
        renderer.render(scene, camera);
    }
}

function resizeRenderer() {
    const container = getContainer();
    if (!container || !renderer || !camera) return;

    const rect = container.getBoundingClientRect();
    const width = Math.max(Math.floor(rect.width), 100);
    const height = Math.max(Math.floor(rect.height), 100);

    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
}

function onWindowResize() {
    resizeRenderer();
}

// ==========================================================
// UI FEEDBACK HELPERS
// ==========================================================

function showLoading(visible, message = "Loading report...") {
    const overlay = getLoadingOverlay();
    if (overlay) {
        overlay.style.display = visible ? "flex" : "none";
    }

    const statusP = document.getElementById("threeStatus");
    if (statusP && message) {
        statusP.textContent = message;
    }

    if (visible) {
        hideError();
    }

    setStatusBar(message, false);
}

function showError(title, detail, canBuild = false, isDanger = false) {
    showLoading(false);

    const overlay = getErrorOverlay();
    if (overlay) {
        overlay.style.display = "flex";
    }

    const titleEl = document.getElementById("threeErrorTitle") || document.getElementById("errorTitle");
    if (titleEl) {
        titleEl.textContent = title;
    }

    const detailEl = document.getElementById("threeErrorDetail") || document.getElementById("errorDetail");
    if (detailEl) {
        detailEl.textContent = detail;
    }

    const iconEl = document.getElementById("threeErrorIcon");
    if (iconEl) {
        iconEl.className = "three-error-icon" + (isDanger ? " danger" : "");
    }

    const buildBtn = document.getElementById("errorBuildModelBtn");
    if (buildBtn) {
        buildBtn.style.display = canBuild ? "inline-flex" : "none";
    }

    setStatusBar(`${title}: ${detail}`, true);
}

function hideError() {
    const overlay = getErrorOverlay();
    if (overlay) {
        overlay.style.display = "none";
    }
}

function setStatusBar(message, isError = false) {
    const bar = getStatusBar();
    if (!bar) return;
    bar.textContent = message;
    bar.classList.toggle("error", Boolean(isError));
}

function updateViewModeBadge(statusText, isAvailable) {
    const badge = document.getElementById("viewModeBadge");
    if (!badge) return;

    badge.textContent = statusText;
    badge.className = "view-mode-badge " + (isAvailable ? "reconstruction" : "unavailable");

    if (isAvailable) {
        badge.style.color = "#38bdf8";
        badge.style.background = "rgba(56, 189, 248, 0.15)";
        badge.style.borderColor = "rgba(56, 189, 248, 0.35)";
    } else {
        badge.style.color = "#94a3b8";
        badge.style.background = "rgba(148, 163, 184, 0.12)";
        badge.style.borderColor = "rgba(148, 163, 184, 0.25)";
    }
}

function updateSummaryCards(data) {
    const report = data?.report || {};
    const reportIdEl = document.getElementById("reportId");
    if (reportIdEl) {
        reportIdEl.textContent = report.id != null ? `#${report.id}` : "--";
    }

    const totalObjectsEl = document.getElementById("totalObjects");
    if (totalObjectsEl) {
        totalObjectsEl.textContent = report.pothole_count != null ? String(report.pothole_count) : "--";
    }

    const mediaFormatEl = document.getElementById("mediaFormat");
    if (mediaFormatEl) {
        mediaFormatEl.textContent = report.media_type ? String(report.media_type).toUpperCase() : "--";
    }
}

// ==========================================================
// REPORT CATALOG LOADING
// ==========================================================

async function loadReportCatalogAndStart() {
    showLoading(true, "Connecting to RoadGuard AI...");

    const selector = document.getElementById("reportSelector");
    if (selector) {
        selector.innerHTML = '<option value="">Loading reports...</option>';
    }

    try {
        const response = await fetch("/3d/reports-list", { cache: "no-store" });
        if (!response.ok) {
            throw new Error(`Failed to load reports (HTTP ${response.status})`);
        }

        const data = await response.json();
        const reports = Array.isArray(data.reports) ? data.reports : [];

        if (reports.length === 0) {
            if (selector) {
                selector.innerHTML = '<option value="">No reports available</option>';
            }
            updateSummaryCards({ report: { id: null, pothole_count: 0, media_type: "NONE" } });
            updateViewModeBadge("NO REPORTS", false);
            showError(
                "No Reports Available",
                "No detection reports have been created yet. Please upload a road video or image from the dashboard to get started.",
                false,
                false
            );
            return;
        }

        // Populate selector
        if (selector) {
            selector.innerHTML = "";
            reports.forEach(report => {
                const opt = document.createElement("option");
                opt.value = String(report.id);
                opt.textContent = `Report #${report.id} (${(report.media_type || "media").toUpperCase()} - ${report.pothole_count || 0} defects)`;
                selector.appendChild(opt);
            });
        }

        // Check URL parameter
        const params = new URLSearchParams(window.location.search);
        const requestedId = params.get("report_id");

        if (requestedId) {
            const matched = reports.find(r => String(r.id) === String(requestedId));
            if (!matched) {
                if (selector) selector.value = String(reports[0].id);
                showError(
                    "Report Not Found",
                    `Report #${requestedId} does not exist in the database. Please select an available report above or return to the dashboard.`,
                    false,
                    true
                );
                return;
            }
            if (selector) selector.value = String(requestedId);
            await loadRoadView(requestedId);
        } else {
            const defaultId = reports[0].id;
            if (selector) selector.value = String(defaultId);
            await loadRoadView(defaultId);
        }
    } catch (error) {
        console.error("[RoadGuard 3D] Failed to load report catalog:", error);
        showError("Backend Connection Error", error.message || "Could not load report catalog from backend.", false, true);
    }
}

// ==========================================================
// LOAD SELECTED REPORT VIEW
// ==========================================================

async function loadRoadView(reportId) {
    if (reportId == null || String(reportId).trim() === "") {
        return;
    }

    currentReportId = String(reportId);
    stopPolling();

    // Update URL without reload
    const url = new URL(window.location.href);
    url.searchParams.set("report_id", currentReportId);
    window.history.replaceState({}, "", url.toString());

    // Update selector
    const selector = document.getElementById("reportSelector");
    if (selector && selector.value !== currentReportId) {
        selector.value = currentReportId;
    }

    showLoading(true, `Fetching 3D reconstruction data for Report #${reportId}...`);

    // Abort controller with 15s timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    try {
        const response = await fetch(`/3d/road-view/${encodeURIComponent(reportId)}`, {
            cache: "no-store",
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (response.status === 404) {
            throw new Error(`Report #${reportId} was not found on the server.`);
        }
        if (!response.ok) {
            throw new Error(`Server returned HTTP ${response.status} when fetching 3D scene.`);
        }

        const data = await response.json();
        currentSceneData = data;

        updateSummaryCards(data);

        // Clear previous 3D geometry
        clear3DScene();

        const viewer = data.viewer || {};
        const reconstruction = data.reconstruction || {};
        const isReconstructionAvailable = Boolean(viewer.reconstruction_available);
        const reconstructionStatus = viewer.reconstruction_status || reconstruction.status || "NOT_STARTED";
        const isVideo = String(data.report?.media_type || "").toLowerCase() === "video";

        if (!isReconstructionAvailable) {
            // RECONSTRUCTION UNAVAILABLE: Stop loader and show clear explanation
            updateViewModeBadge("RECONSTRUCTION UNAVAILABLE", false);

            let statusDetail = "3D reconstruction is not available for this report yet.";
            if (reconstructionStatus === "FAILED") {
                statusDetail = "COLMAP photogrammetry reconstruction failed to generate 3D geometry for this media.";
            } else if (!isVideo) {
                statusDetail = "3D photogrammetric reconstruction requires multi-frame video input. This report was created from a single image.";
            } else {
                statusDetail = "3D reconstruction is not available for this report yet. You can build a 3D model from the uploaded video frames using COLMAP.";
            }

            showError("3D Reconstruction Unavailable", statusDetail, isVideo && reconstructionStatus !== "FAILED", false);
            return;
        }

        // RECONSTRUCTION AVAILABLE: Load model
        const modelUrl = reconstruction.mesh_url || reconstruction.pointcloud_url;
        if (!modelUrl) {
            throw new Error("Backend indicated reconstruction is available, but provided no valid model URL.");
        }

        showLoading(true, "Rendering reconstructed road mesh...");
        await loadReconstructedModel(modelUrl, data);

        // Render markers if available
        renderPotholeMarkers(data.potholes || []);

        updateViewModeBadge("COLMAP RECONSTRUCTION", true);
        setStatusBar(`Report #${reportId} — 3D reconstruction active (${reconstruction.vertex_count || 0} vertices).`, false);
        showLoading(false);

    } catch (error) {
        clearTimeout(timeoutId);
        console.error("[RoadGuard 3D] Error loading road view:", error);
        showLoading(false);

        const isAbort = error.name === "AbortError";
        const message = isAbort ? "Request timed out while contacting the 3D server." : error.message;
        showError("Unable to Load 3D View", message, false, true);
    }
}

// ==========================================================
// 3D MODEL LOADER (PLY, OBJ, GLTF)
// ==========================================================

async function loadReconstructedModel(modelUrl, sceneData) {
    const cleanUrl = modelUrl.split("?")[0].toLowerCase();

    let loadedObject = null;

    if (cleanUrl.endsWith(".ply")) {
        const loader = new PLYLoader();
        const geometry = await loader.loadAsync(modelUrl);

        if (!geometry || !geometry.attributes || !geometry.attributes.position || geometry.attributes.position.count === 0) {
            throw new Error("Loaded PLY model contains no vertex coordinates.");
        }

        geometry.computeBoundingBox();
        const hasFaces = geometry.index !== null && geometry.index.count >= 3;
        const hasColor = geometry.hasAttribute("color");

        if (hasFaces) {
            geometry.computeVertexNormals();
            const material = new THREE.MeshStandardMaterial({
                vertexColors: hasColor,
                color: hasColor ? 0xffffff : 0x5a6578,
                roughness: 0.85,
                metalness: 0.05,
                side: THREE.DoubleSide
            });
            loadedObject = new THREE.Mesh(geometry, material);
            loadedObject.castShadow = true;
            loadedObject.receiveShadow = true;
        } else {
            const material = new THREE.PointsMaterial({
                size: 0.25,
                sizeAttenuation: true,
                vertexColors: hasColor,
                color: hasColor ? 0xffffff : 0x38bdf8
            });
            loadedObject = new THREE.Points(geometry, material);
        }

    } else if (cleanUrl.endsWith(".obj")) {
        const loader = new OBJLoader();
        loadedObject = await loader.loadAsync(modelUrl);
    } else if (cleanUrl.endsWith(".gltf") || cleanUrl.endsWith(".glb")) {
        const loader = new GLTFLoader();
        const gltf = await loader.loadAsync(modelUrl);
        loadedObject = gltf.scene;
    } else {
        throw new Error(`Unsupported 3D model extension in URL: ${modelUrl}`);
    }

    // Normalize scale and center
    normalizeAndCenterObject(loadedObject);
    modelGroup.add(loadedObject);

    // Frame camera on bounding box
    frameCameraOnObject(loadedObject);
}

// ==========================================================
// GEOMETRY NORMALIZATION & CAMERA FRAMING
// ==========================================================

function normalizeAndCenterObject(object) {
    const box = new THREE.Box3().setFromObject(object);
    const center = new THREE.Vector3();
    const size = new THREE.Vector3();
    box.getCenter(center);
    box.getSize(size);

    const maxDim = Math.max(size.x, size.y, size.z);
    if (!Number.isFinite(maxDim) || maxDim <= 0) return;

    const targetSize = 35.0;
    const scale = targetSize / maxDim;

    object.scale.setScalar(scale);
    object.position.set(-center.x * scale, -center.y * scale, -center.z * scale);

    currentBoundingBox = new THREE.Box3().setFromObject(object);
}

function frameCameraOnObject(object) {
    const box = new THREE.Box3().setFromObject(object);
    const center = new THREE.Vector3();
    const size = new THREE.Vector3();
    box.getCenter(center);
    box.getSize(size);

    const maxDim = Math.max(size.x, size.y, size.z);
    const distance = Math.max(maxDim * 1.5, 12.0);

    camera.near = 0.1;
    camera.far = Math.max(distance * 10, 1500);
    camera.position.set(center.x, center.y + distance * 0.65, center.z + distance * 1.1);
    camera.updateProjectionMatrix();

    controls.target.copy(center);
    controls.minDistance = Math.max(maxDim * 0.1, 1.0);
    controls.maxDistance = Math.max(maxDim * 5.0, 100.0);
    controls.update();
}

// ==========================================================
// 3D POTHOLE MARKERS
// ==========================================================

function renderPotholeMarkers(markers) {
    clearPotholeMarkers();
    if (!Array.isArray(markers) || markers.length === 0) return;

    const severityColors = {
        CRITICAL: 0xef4444,
        HIGH: 0xf97316,
        MODERATE: 0xf59e0b,
        LOW: 0x22c55e
    };

    markers.forEach((marker, index) => {
        const severity = String(marker.severity || "LOW").toUpperCase();
        const color = severityColors[severity] || 0x38bdf8;

        const sphereGeo = new THREE.SphereGeometry(0.4, 20, 20);
        const sphereMat = new THREE.MeshStandardMaterial({
            color: color,
            emissive: color,
            emissiveIntensity: 0.45,
            roughness: 0.3
        });
        const mesh = new THREE.Mesh(sphereGeo, sphereMat);

        let posX = 0;
        let posY = 0.5;
        let posZ = 0;

        if (marker.position_3d && typeof marker.position_3d === "object") {
            posX = Number(marker.position_3d.x || 0);
            posY = Number(marker.position_3d.y || 0) + 0.5;
            posZ = Number(marker.position_3d.z || 0);
        } else if (marker.center_x != null && marker.center_y != null) {
            posX = ((Number(marker.center_x) / 1000) - 0.5) * 20;
            posZ = ((Number(marker.center_y) / 1000) - 0.5) * 20;
        } else {
            posX = (index - markers.length / 2) * 2.5;
        }

        mesh.position.set(posX, posY, posZ);
        mesh.userData = { ...marker, index: index + 1 };
        mesh.name = `pothole_marker_${index + 1}`;
        potholeGroup.add(mesh);
    });
}

function clear3DScene() {
    clearGroup(modelGroup);
    clearPotholeMarkers();
    currentBoundingBox = null;
}

function clearGroup(group) {
    if (!group) return;
    while (group.children.length > 0) {
        const child = group.children[0];
        group.remove(child);
        disposeObject(child);
    }
}

function clearPotholeMarkers() {
    clearGroup(potholeGroup);
}

function disposeObject(obj) {
    if (!obj) return;
    if (obj.geometry) {
        obj.geometry.dispose();
    }
    if (obj.material) {
        if (Array.isArray(obj.material)) {
            obj.material.forEach(m => m.dispose());
        } else {
            obj.material.dispose();
        }
    }
}

// ==========================================================
// INTERACTIVE RAYCASTING (POTHOLE CLICK/HOVER)
// ==========================================================

function onSceneClick(event) {
    if (!renderer || !camera || !potholeGroup) return;

    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(potholeGroup.children, false);

    if (intersects.length > 0) {
        const markerData = intersects[0].object.userData;
        showPotholeDetails(markerData);
    }
}

function onSceneMouseMove(event) {
    if (!renderer || !camera || !potholeGroup) return;

    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(potholeGroup.children, false);

    renderer.domElement.style.cursor = intersects.length > 0 ? "pointer" : "default";
}

function showPotholeDetails(data) {
    const panel = document.getElementById("potholeInfoPanel");
    if (!panel) return;

    const severity = data.severity || "LOW";
    const confidence = data.confidence != null ? `${(Number(data.confidence) * 100).toFixed(0)}%` : "N/A";
    const id = data.pothole_id ?? data.index ?? "--";

    panel.innerHTML = `
        <div class="pothole-info-card" style="border-left: 4px solid ${getSeverityColor(severity)};">
            <h4 style="margin: 0 0 8px; color: #f8fafc;">Defect #${id}</h4>
            <p style="margin: 4px 0;"><strong>Severity:</strong> <span class="badge ${severity.toLowerCase()}">${severity}</span></p>
            <p style="margin: 4px 0;"><strong>Confidence:</strong> ${confidence}</p>
            <p style="margin: 4px 0; color: #94a3b8; font-size: 11px;">Selected from 3D road inspection model</p>
        </div>
    `;
}

function getSeverityColor(sev) {
    const map = { CRITICAL: "#ef4444", HIGH: "#f97316", MODERATE: "#f59e0b", LOW: "#22c55e" };
    return map[String(sev).toUpperCase()] || "#38bdf8";
}

// ==========================================================
// PHOTOGRAMMETRY RECONSTRUCTION TRIGGER & BOUNDED POLLING
// ==========================================================

async function triggerReconstruction() {
    if (!currentReportId) {
        showError("No Report Selected", "Please select a valid report before generating 3D reconstruction.", false, false);
        return;
    }

    const report = currentSceneData?.report;
    if (report && String(report.media_type).toLowerCase() !== "video") {
        alert("Photogrammetric 3D reconstruction requires multi-frame video input. This report was created from a single image.");
        return;
    }

    showLoading(true, `Starting COLMAP 3D reconstruction for Report #${currentReportId}...`);

    try {
        const response = await fetch(`/api/photogrammetry/reconstruct/${encodeURIComponent(currentReportId)}`, {
            method: "POST"
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned HTTP ${response.status}`);
        }

        // Bounded polling every 3 seconds for max 180 seconds
        startPollingReconstruction(currentReportId);

    } catch (error) {
        console.error("[RoadGuard 3D] Failed to trigger reconstruction:", error);
        showLoading(false);
        showError("Reconstruction Trigger Failed", error.message || "Could not start COLMAP process.", true, true);
    }
}

function startPollingReconstruction(reportId) {
    stopPolling();

    let attempts = 0;
    const maxAttempts = 60; // 60 * 3s = 180s = 3 minutes

    showLoading(true, "COLMAP 3D reconstruction running... Please wait (1-3 minutes).");

    pollingTimer = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts) {
            stopPolling();
            showLoading(false);
            showError("Reconstruction Timeout", "COLMAP reconstruction is taking longer than expected. You can retry shortly.", true, false);
            return;
        }

        try {
            const statusRes = await fetch(`/api/photogrammetry/status/${encodeURIComponent(reportId)}`, { cache: "no-store" });
            if (!statusRes.ok) return;

            const statusData = await statusRes.json();
            const isReady = Boolean(statusData.mesh_ready || statusData.pointcloud_ready || statusData.reconstruction_available);
            const isFailed = statusData.status === "FAILED" || statusData.reconstruction_status === "FAILED";

            if (isReady) {
                stopPolling();
                showLoading(true, "3D model generated successfully! Loading scene...");
                await loadRoadView(reportId);
            } else if (isFailed) {
                stopPolling();
                showLoading(false);
                showError("Reconstruction Failed", "COLMAP reconstruction finished with an error or could not match enough road features.", true, false);
            }
        } catch (e) {
            console.warn("[RoadGuard 3D] Polling status check:", e);
        }
    }, 3000);
}

function stopPolling() {
    if (pollingTimer) {
        clearInterval(pollingTimer);
        pollingTimer = null;
    }
    if (pollingTimeoutTimer) {
        clearTimeout(pollingTimeoutTimer);
        pollingTimeoutTimer = null;
    }
}

// ==========================================================
// EVENT BINDINGS
// ==========================================================

function bindUIEvents() {
    // 1. Report Selector
    const selector = document.getElementById("reportSelector");
    if (selector) {
        selector.addEventListener("change", () => {
            const val = selector.value;
            if (val) {
                loadRoadView(val);
            }
        });
    }

    // 2. Reload Button
    const reloadBtn = document.getElementById("reloadSceneBtn");
    if (reloadBtn) {
        reloadBtn.addEventListener("click", () => {
            if (currentReportId) {
                loadRoadView(currentReportId);
            }
        });
    }

    // 3. Reset Camera Button
    const resetCameraBtn = document.getElementById("resetCameraBtn");
    if (resetCameraBtn) {
        resetCameraBtn.addEventListener("click", () => {
            if (modelGroup && modelGroup.children.length > 0) {
                frameCameraOnObject(modelGroup);
            } else {
                camera.position.set(0, 12, 28);
                controls.target.set(0, 0, 0);
                controls.update();
            }
        });
    }

    // 4. Build 3D Model Buttons
    const runBtn = document.getElementById("runReconstructionBtn");
    if (runBtn) {
        runBtn.addEventListener("click", triggerReconstruction);
    }

    const errorBuildBtn = document.getElementById("errorBuildModelBtn");
    if (errorBuildBtn) {
        errorBuildBtn.addEventListener("click", triggerReconstruction);
    }

    // 5. Retry Buttons
    const errorRetryBtn = document.getElementById("errorRetryBtn");
    if (errorRetryBtn) {
        errorRetryBtn.addEventListener("click", () => {
            if (currentReportId) {
                loadRoadView(currentReportId);
            } else {
                loadReportCatalogAndStart();
            }
        });
    }

    // 6. Open Reconstruction Button
    const openPlyBtn = document.getElementById("openPlyViewerBtn");
    if (openPlyBtn) {
        openPlyBtn.addEventListener("click", () => {
            if (currentReportId) {
                loadRoadView(currentReportId);
            }
        });
    }
}

// ==========================================================
// CLEANUP ON UNLOAD
// ==========================================================

window.addEventListener("beforeunload", () => {
    stopPolling();
    if (animationId) {
        cancelAnimationFrame(animationId);
    }
    if (resizeObserver) {
        resizeObserver.disconnect();
    }
    if (renderer) {
        renderer.dispose();
    }
});