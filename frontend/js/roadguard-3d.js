// ==========================================================
// ROADGUARD AI - CANONICAL 3D ROAD INSPECTION VIEWER
// frontend/js/roadguard-3d.js
// ==========================================================

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { PLYLoader } from "three/addons/loaders/PLYLoader.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

// ==========================================================
// STATE
// ==========================================================

let scene;
let camera;
let renderer;
let controls;
let roadGroup;
let potholeGroup;
let raycaster;
let mouse;

let activeReportId = null;
let currentSceneData = null;
let selectedMarker = null;
let roadBoundingBox = null;
let currentRoadObject = null;

// DOM Elements
const container = document.getElementById("three-container");
const loadingElement = document.getElementById("loading");
const loadingText = document.getElementById("loadingText");
const errorOverlay = document.getElementById("errorMessage");
const errorTitle = document.getElementById("errorTitle");
const errorDetail = document.getElementById("errorDetail");
const retryBtn = document.getElementById("retryBtn");
const reportSelector = document.getElementById("reportSelector");
const viewModeBadge = document.getElementById("viewModeBadge");

// Summary Elements
const totalPotholesEl = document.getElementById("totalPotholes");
const selectedObjectEl = document.getElementById("selectedObject");
const confidenceEl = document.getElementById("confidence");
const roadConditionEl = document.getElementById("roadCondition");

// Detail Elements
const noSelectionEl = document.getElementById("noSelection");
const potholeDetailsEl = document.getElementById("potholeDetails");
const detailIdEl = document.getElementById("detailId");
const detailSeverityEl = document.getElementById("detailSeverity");
const detailConfidenceEl = document.getElementById("detailConfidence");
const detailWidthEl = document.getElementById("detailWidth");
const detailDepthEl = document.getElementById("detailDepth");
const detailPositionEl = document.getElementById("detailPosition");
const focusSelectedBtn = document.getElementById("focusSelectedBtn");

if (!container) {
    console.error("RoadGuard 3D: #three-container not found.");
    throw new Error("3D container missing");
}

// ==========================================================
// INITIALIZATION
// ==========================================================

initThreeScene();
initInteractions();
setupViewerButtons();
loadReportCatalogAndStart();
animate();

// ==========================================================
// THREE.JS SETUP
// ==========================================================

function initThreeScene() {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060b14);

    const width = Math.max(container.clientWidth, 300);
    const height = Math.max(container.clientHeight, 300);

    camera = new THREE.PerspectiveCamera(52, width / height, 0.05, 5000);
    camera.position.set(0, 12, 28);

    renderer = new THREE.WebGLRenderer({
        antialias: true,
        powerPreference: "high-performance",
        alpha: false,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    container.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.screenSpacePanning = true;
    controls.minDistance = 0.5;
    controls.maxDistance = 500;
    controls.target.set(0, 0, 0);

    // Lights
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x1b2838, 2.2);
    scene.add(hemiLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 2.0);
    dirLight1.position.set(20, 45, 25);
    dirLight1.castShadow = true;
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x60a5fa, 1.2);
    dirLight2.position.set(-25, 20, -20);
    scene.add(dirLight2);

    roadGroup = new THREE.Group();
    roadGroup.name = "roadGroup";
    scene.add(roadGroup);

    potholeGroup = new THREE.Group();
    potholeGroup.name = "potholeGroup";
    scene.add(potholeGroup);

    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2();

    window.addEventListener("resize", onWindowResize);
}

function onWindowResize() {
    if (!container || !renderer || !camera) return;
    const width = container.clientWidth;
    const height = container.clientHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
}

// ==========================================================
// CATALOG & REPORT SELECTION
// ==========================================================

async function loadReportCatalogAndStart() {
    const urlParams = new URLSearchParams(window.location.search);
    const queryReportId = urlParams.get("report_id");

    try {
        const resp = await fetch("/3d/reports-list");
        if (resp.ok) {
            const data = await resp.json();
            const reports = data.reports || [];

            if (reportSelector) {
                reportSelector.innerHTML = "";
                reports.forEach(r => {
                    const opt = document.createElement("option");
                    opt.value = r.id;
                    opt.textContent = `Report #${r.id} (${(r.media_type || "video").toUpperCase()} - ${r.pothole_count} defects)`;
                    reportSelector.appendChild(opt);
                });

                reportSelector.addEventListener("change", () => {
                    const targetId = reportSelector.value;
                    const url = new URL(window.location);
                    url.searchParams.set("report_id", targetId);
                    window.history.pushState({}, "", url);
                    loadReport(targetId);
                });
            }

            // Determine which report to load
            let targetReportId = queryReportId;
            if (!targetReportId && reports.length > 0) {
                // Preferred report with known photogrammetry: 21, 2, 16, 17, or reports[0]
                const knownReconstructions = [21, 2, 16, 17];
                const found = reports.find(r => knownReconstructions.includes(Number(r.id)));
                targetReportId = found ? found.id : reports[0].id;
            } else if (!targetReportId) {
                targetReportId = 21;
            }

            if (reportSelector) {
                reportSelector.value = targetReportId;
            }

            loadReport(targetReportId);
        } else {
            loadReport(queryReportId || 21);
        }
    } catch (err) {
        console.warn("Failed to load reports catalog:", err);
        loadReport(queryReportId || 21);
    }
}

// ==========================================================
// LOAD REPORT 3D SCENE
// ==========================================================

async function loadReport(reportId) {
    if (!reportId) return;
    activeReportId = reportId;

    showLoading(true, `Loading COLMAP 3D scene for Report #${reportId}...`);
    hideError();
    clearSelection();

    try {
        const response = await fetch(`/3d/road-view/${reportId}`);
        if (!response.ok) {
            throw new Error(`Failed to load 3D scene data (HTTP ${response.status})`);
        }

        const data = await response.json();
        currentSceneData = data;

        updateSummaryPanels(data);

        // Clear existing objects
        clearGroup(roadGroup);
        clearGroup(potholeGroup);
        currentRoadObject = null;
        roadBoundingBox = null;

        const isReconstruction = Boolean(data.viewer && data.viewer.reconstruction_available);
        const reconstructionStatus = (data.viewer && data.viewer.reconstruction_status) || (isReconstruction ? "MESH_AVAILABLE" : "NOT_STARTED");
        const meshUrl = data.reconstruction && data.reconstruction.mesh_url;
        const pointcloudUrl = data.reconstruction && data.reconstruction.pointcloud_url;

        if (viewModeBadge) {
            if (reconstructionStatus === "MESH_AVAILABLE") {
                viewModeBadge.textContent = "COLMAP RECONSTRUCTION";
                viewModeBadge.style.color = "#38bdf8";
                viewModeBadge.style.background = "rgba(56, 189, 248, 0.15)";
                viewModeBadge.style.borderColor = "rgba(56, 189, 248, 0.35)";
            } else if (reconstructionStatus === "DENSE_POINT_CLOUD") {
                viewModeBadge.textContent = "DENSE POINT CLOUD";
                viewModeBadge.style.color = "#2dd4bf";
                viewModeBadge.style.background = "rgba(45, 212, 191, 0.15)";
                viewModeBadge.style.borderColor = "rgba(45, 212, 191, 0.35)";
            } else if (reconstructionStatus === "SPARSE_ONLY") {
                viewModeBadge.textContent = "SPARSE ONLY";
                viewModeBadge.style.color = "#f59e0b";
                viewModeBadge.style.background = "rgba(245, 158, 11, 0.15)";
                viewModeBadge.style.borderColor = "rgba(245, 158, 11, 0.35)";
            } else if (reconstructionStatus === "FAILED") {
                viewModeBadge.textContent = "RECONSTRUCTION FAILED";
                viewModeBadge.style.color = "#ef4444";
                viewModeBadge.style.background = "rgba(239, 68, 68, 0.15)";
                viewModeBadge.style.borderColor = "rgba(239, 68, 68, 0.35)";
            } else {
                viewModeBadge.textContent = "NOT AVAILABLE";
                viewModeBadge.style.color = "#94a3b8";
                viewModeBadge.style.background = "rgba(148, 163, 184, 0.15)";
                viewModeBadge.style.borderColor = "rgba(148, 163, 184, 0.35)";
            }
        }

        if (!isReconstruction) {
            showLoading(false);
            const statusMsg = (reconstructionStatus === "FAILED")
                ? "COLMAP reconstruction failed for this report"
                : "3D reconstruction unavailable";
            showError("3D Reconstruction Notice", statusMsg);
            return;
        }

        // Load the actual COLMAP model
        const primaryModelUrl = meshUrl || pointcloudUrl || `/results/photogrammetry/report_${reportId}/roadguard-road.ply`;
        const fallbackModelUrl = `/api/photogrammetry/mesh/${reportId}`;

        let loaded = false;
        showLoading(true, "Loading real COLMAP 3D model...");

        for (const candidate of [primaryModelUrl, fallbackModelUrl]) {
            if (!candidate) continue;
            try {
                await loadModelGeometry(candidate);
                loaded = true;
                break;
            } catch (plyErr) {
                console.warn(`Failed loading reconstruction candidate ${candidate}:`, plyErr);
            }
        }

        if (!loaded) {
            showLoading(false);
            showError("3D Reconstruction Notice", "3D reconstruction unavailable");
            return;
        }

        // Render defect markers
        renderPotholeMarkers(data.potholes || []);

        // Position camera to view whole road
        frameCameraOnScene();

        showLoading(false);

    } catch (err) {
        console.error("3D Road View Load Error:", err);
        showLoading(false);
        showError("3D Reconstruction Notice", "3D reconstruction unavailable");
    }
}

// ==========================================================
// REAL 3D RECONSTRUCTION LOADER (PLY, OBJ, GLTF, GLB)
// ==========================================================

async function loadModelGeometry(url) {
    const lowerUrl = url.toLowerCase();
    let object3D = null;

    if (lowerUrl.endsWith(".obj")) {
        const loader = new OBJLoader();
        object3D = await loader.loadAsync(url);
        const box = new THREE.Box3().setFromObject(object3D);
        const center = new THREE.Vector3();
        box.getCenter(center);
        const size = new THREE.Vector3();
        box.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = maxDim > 0 ? 45.0 / maxDim : 1.0;
        object3D.position.set(-center.x * scale, -center.y * scale, -center.z * scale);
        object3D.scale.setScalar(scale);
        roadBoundingBox = {
            min: box.min.clone(),
            max: box.max.clone(),
            center: center.clone(),
            size: size.clone(),
            scale: scale,
            offset: object3D.position.clone(),
        };
    } else if (lowerUrl.endsWith(".gltf") || lowerUrl.endsWith(".glb")) {
        const loader = new GLTFLoader();
        const gltf = await loader.loadAsync(url);
        object3D = gltf.scene;
        const box = new THREE.Box3().setFromObject(object3D);
        const center = new THREE.Vector3();
        box.getCenter(center);
        const size = new THREE.Vector3();
        box.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = maxDim > 0 ? 45.0 / maxDim : 1.0;
        object3D.position.set(-center.x * scale, -center.y * scale, -center.z * scale);
        object3D.scale.setScalar(scale);
        roadBoundingBox = {
            min: box.min.clone(),
            max: box.max.clone(),
            center: center.clone(),
            size: size.clone(),
            scale: scale,
            offset: object3D.position.clone(),
        };
    } else {
        // PLY loader (COLMAP dense mesh or sparse point cloud)
        const loader = new PLYLoader();
        const geometry = await loader.loadAsync(url);

        if (!geometry || !geometry.attributes.position || geometry.attributes.position.count === 0) {
            throw new Error("Loaded PLY contains no vertex positions.");
        }

        geometry.computeBoundingBox();
        const box = geometry.boundingBox;
        const center = new THREE.Vector3();
        box.getCenter(center);
        const size = new THREE.Vector3();
        box.getSize(size);

        const maxDim = Math.max(size.x, size.y, size.z);
        const targetSize = 45.0;
        const scale = maxDim > 0 ? targetSize / maxDim : 1.0;

        const hasFaces = geometry.index !== null && geometry.index.count >= 3;
        const hasColor = geometry.hasAttribute("color");

        if (hasFaces) {
            geometry.computeVertexNormals();
            const material = new THREE.MeshStandardMaterial({
                vertexColors: hasColor,
                color: hasColor ? 0xffffff : 0x475569,
                roughness: 0.85,
                metalness: 0.08,
                side: THREE.DoubleSide,
            });
            object3D = new THREE.Mesh(geometry, material);
            object3D.castShadow = true;
            object3D.receiveShadow = true;
        } else {
            // COLMAP sparse point cloud
            const pointMaterial = new THREE.PointsMaterial({
                size: 0.65,
                vertexColors: hasColor,
                color: hasColor ? 0xffffff : 0x93c5fd,
                sizeAttenuation: true,
            });
            object3D = new THREE.Points(geometry, pointMaterial);
        }

        object3D.position.set(-center.x * scale, -center.y * scale, -center.z * scale);
        object3D.scale.setScalar(scale);

        roadBoundingBox = {
            min: box.min.clone(),
            max: box.max.clone(),
            center: center.clone(),
            size: size.clone(),
            scale: scale,
            offset: object3D.position.clone(),
        };
    }

    roadGroup.add(object3D);
    currentRoadObject = object3D;
    console.info(`[RoadGuard 3D] Loaded real COLMAP 3D model from ${url}`);
}

// ==========================================================
// POTHOLE MARKERS
// ==========================================================

function getSeverityColorHex(severity) {
    switch (String(severity || "").toUpperCase()) {
        case "CRITICAL": return 0xef4444;
        case "HIGH": return 0xf97316;
        case "MODERATE": return 0xf59e0b;
        case "LOW":
        default: return 0x22c55e;
    }
}

function renderPotholeMarkers(potholes) {
    clearGroup(potholeGroup);
    if (!potholes || potholes.length === 0) return;

    potholes.forEach((pothole, index) => {
        let posX = 0;
        let posY = 0.3;
        let posZ = 0;

        const pos3d = pothole.position_3d;
        let hasDirect3D = false;

        if (pos3d) {
            let rx = 0, ry = 0, rz = 0;
            if (typeof pos3d.x === "number") {
                rx = pos3d.x; ry = pos3d.y; rz = pos3d.z;
                hasDirect3D = true;
            } else if (Array.isArray(pos3d) && pos3d.length >= 3) {
                rx = pos3d[0]; ry = pos3d[1]; rz = pos3d[2];
                hasDirect3D = true;
            }

            if (hasDirect3D && roadBoundingBox) {
                // Transform into scene world space matching roadGroup
                posX = (rx - roadBoundingBox.center.x) * roadBoundingBox.scale;
                posY = (ry - roadBoundingBox.center.y) * roadBoundingBox.scale + 0.35;
                posZ = (rz - roadBoundingBox.center.z) * roadBoundingBox.scale;
            }
        }

        if (!hasDirect3D && roadBoundingBox) {
            // Project using normalized coordinates (0..1000 or 0..1)
            let nx = pothole.center_x != null ? (pothole.center_x > 1 ? pothole.center_x / 1000 : pothole.center_x) : 0.5;
            let ny = pothole.center_y != null ? (pothole.center_y > 1 ? pothole.center_y / 1000 : pothole.center_y) : 0.5;
            nx = Math.max(0.05, Math.min(0.95, nx));
            ny = Math.max(0.05, Math.min(0.95, ny));

            const sWidth = roadBoundingBox.size.x * roadBoundingBox.scale;
            const sLength = roadBoundingBox.size.z * roadBoundingBox.scale;

            posX = (nx - 0.5) * sWidth * 0.85;
            posZ = (ny - 0.5) * sLength * 0.85;
            posY = 0.35;
        }

        const colorHex = getSeverityColorHex(pothole.severity);

        // Marker mesh (Sphere)
        const markerGeo = new THREE.SphereGeometry(0.55, 20, 20);
        const markerMat = new THREE.MeshStandardMaterial({
            color: colorHex,
            emissive: colorHex,
            emissiveIntensity: 0.45,
            roughness: 0.3,
            metalness: 0.2,
        });
        const marker = new THREE.Mesh(markerGeo, markerMat);
        marker.position.set(posX, posY, posZ);

        // Store user data
        marker.userData = {
            pothole: pothole,
            index: index,
            baseColor: colorHex,
            worldPos: new THREE.Vector3(posX, posY, posZ),
        };

        // Pin vertical indicator
        const pinPoints = [
            new THREE.Vector3(posX, posY - 0.5, posZ),
            new THREE.Vector3(posX, posY + 1.8, posZ),
        ];
        const pinGeo = new THREE.BufferGeometry().setFromPoints(pinPoints);
        const pinMat = new THREE.LineBasicMaterial({
            color: colorHex,
            transparent: true,
            opacity: 0.7,
        });
        const pin = new THREE.Line(pinGeo, pinMat);

        potholeGroup.add(marker);
        potholeGroup.add(pin);
    });
}

// ==========================================================
// INTERACTION & RAYCASTING
// ==========================================================

function initInteractions() {
    renderer.domElement.addEventListener("click", onCanvasClick);
    renderer.domElement.addEventListener("pointermove", onCanvasPointerMove);

    if (retryBtn) {
        retryBtn.addEventListener("click", () => {
            if (activeReportId) loadReport(activeReportId);
        });
    }

    if (focusSelectedBtn) {
        focusSelectedBtn.addEventListener("click", () => {
            if (selectedMarker) {
                focusOnMarker(selectedMarker);
            }
        });
    }
}

function onCanvasPointerMove(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const meshes = potholeGroup.children.filter(c => c.isMesh);
    const intersects = raycaster.intersectObjects(meshes, false);

    if (intersects.length > 0) {
        renderer.domElement.style.cursor = "pointer";
    } else {
        renderer.domElement.style.cursor = "default";
    }
}

function onCanvasClick(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const meshes = potholeGroup.children.filter(c => c.isMesh);
    const intersects = raycaster.intersectObjects(meshes, false);

    if (intersects.length > 0) {
        const hit = intersects[0].object;
        selectMarker(hit);
    }
}

function selectMarker(marker) {
    // Reset previous selection
    if (selectedMarker && selectedMarker.material) {
        selectedMarker.scale.set(1, 1, 1);
        selectedMarker.material.emissiveIntensity = 0.45;
    }

    selectedMarker = marker;
    if (!marker) {
        clearSelection();
        return;
    }

    // Highlight
    marker.scale.set(1.4, 1.4, 1.4);
    if (marker.material) {
        marker.material.emissiveIntensity = 0.95;
    }

    const pothole = marker.userData.pothole;
    const index = marker.userData.index;

    if (selectedObjectEl) {
        selectedObjectEl.textContent = `Pothole #${pothole.pothole_id || pothole.id || (index + 1)}`;
    }

    if (noSelectionEl) noSelectionEl.style.display = "none";
    if (potholeDetailsEl) potholeDetailsEl.classList.remove("hidden");

    if (detailIdEl) {
        detailIdEl.textContent = `P-${String(pothole.pothole_id || pothole.id || (index + 1)).padStart(3, "0")}`;
    }

    const sev = String(pothole.severity || "LOW").toUpperCase();
    if (detailSeverityEl) {
        detailSeverityEl.textContent = sev;
        detailSeverityEl.className = "severity-badge";
        if (sev === "CRITICAL" || sev === "HIGH") detailSeverityEl.classList.add("high");
        else if (sev === "MODERATE") detailSeverityEl.classList.add("medium");
        else detailSeverityEl.classList.add("low");
    }

    const confVal = Number(pothole.confidence || 0);
    if (detailConfidenceEl) {
        detailConfidenceEl.textContent = `${(confVal * 100).toFixed(1)}%`;
    }

    const widthVal = pothole.width ? `${(Number(pothole.width) * 100).toFixed(1)} cm` : "Est. 35 cm";
    if (detailWidthEl) detailWidthEl.textContent = widthVal;

    const depthVal = pothole.depth_m ? `${(Number(pothole.depth_m) * 100).toFixed(1)} cm` : "Est. 4.5 cm";
    if (detailDepthEl) detailDepthEl.textContent = depthVal;

    if (detailPositionEl) {
        const wp = marker.userData.worldPos;
        detailPositionEl.textContent = `X: ${wp.x.toFixed(2)}, Y: ${wp.y.toFixed(2)}, Z: ${wp.z.toFixed(2)}`;
    }
}

function clearSelection() {
    selectedMarker = null;
    if (selectedObjectEl) selectedObjectEl.textContent = "None";
    if (noSelectionEl) noSelectionEl.style.display = "block";
    if (potholeDetailsEl) potholeDetailsEl.classList.add("hidden");
}

function focusOnMarker(marker) {
    if (!marker) return;
    const pos = marker.userData.worldPos;
    controls.target.copy(pos);
    camera.position.set(pos.x + 4, pos.y + 4, pos.z + 6);
    controls.update();
}

function frameCameraOnScene() {
    const box = new THREE.Box3();
    let hasObjects = false;

    if (roadGroup.children.length > 0) {
        box.expandByObject(roadGroup);
        hasObjects = true;
    }
    if (potholeGroup.children.length > 0) {
        box.expandByObject(potholeGroup);
        hasObjects = true;
    }

    if (!hasObjects) {
        camera.position.set(0, 12, 28);
        controls.target.set(0, 0, 0);
        controls.update();
        return;
    }

    const center = new THREE.Vector3();
    box.getCenter(center);
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z, 15);

    controls.target.copy(center);
    camera.position.set(center.x + maxDim * 0.8, center.y + maxDim * 0.7, center.z + maxDim * 1.0);
    controls.update();
}

// ==========================================================
// VIEWER BUTTONS
// ==========================================================

function setupViewerButtons() {
    const perspectiveBtn = document.getElementById("perspectiveBtn");
    const topBtn = document.getElementById("topBtn");
    const resetBtn = document.getElementById("resetBtn");
    const focusAllBtn = document.getElementById("focusAllBtn");

    if (perspectiveBtn) {
        perspectiveBtn.addEventListener("click", () => {
            frameCameraOnScene();
        });
    }

    if (topBtn) {
        topBtn.addEventListener("click", () => {
            const target = controls.target.clone();
            camera.position.set(target.x, target.y + 40, target.z + 0.001);
            controls.update();
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            clearSelection();
            frameCameraOnScene();
        });
    }

    if (focusAllBtn) {
        focusAllBtn.addEventListener("click", () => {
            frameCameraOnScene();
        });
    }
}

// ==========================================================
// SUMMARY PANEL UPDATER
// ==========================================================

function updateSummaryPanels(data) {
    const potholes = data.potholes || [];
    const count = data.report && data.report.pothole_count != null ? data.report.pothole_count : potholes.length;
    if (totalPotholesEl) totalPotholesEl.textContent = String(count);

    const conf = data.report && data.report.confidence != null ? Number(data.report.confidence) : 0;
    if (confidenceEl) {
        confidenceEl.textContent = conf > 0 ? `${(conf * 100).toFixed(1)}%` : "--";
    }

    const severity = (data.report && data.report.severity) || "LOW";
    if (roadConditionEl) {
        roadConditionEl.textContent = String(severity).toUpperCase();
        roadConditionEl.style.color = getSeverityColorHex(severity) === 0xef4444 ? "#ef4444" : (getSeverityColorHex(severity) === 0xf97316 ? "#f97316" : "#22c55e");
    }
}

// ==========================================================
// LOADING & ERROR HELPERS
// ==========================================================

function showLoading(show, message) {
    if (!loadingElement) return;
    if (show) {
        loadingElement.classList.remove("hidden");
        loadingElement.style.display = "flex";
        loadingElement.style.opacity = "1";
        if (loadingText) loadingText.textContent = message || "Loading 3D scene...";
    } else {
        loadingElement.classList.add("hidden");
        setTimeout(() => {
            if (loadingElement.classList.contains("hidden")) {
                loadingElement.style.display = "none";
            }
        }, 400);
    }
}

function showError(title, detail) {
    if (!errorOverlay) return;
    errorOverlay.style.display = "flex";
    if (errorTitle) errorTitle.textContent = title || "Error";
    if (errorDetail) errorDetail.textContent = detail || "Could not complete operation.";
}

function hideError() {
    if (!errorOverlay) return;
    errorOverlay.style.display = "none";
}

function clearGroup(group) {
    while (group.children.length > 0) {
        const obj = group.children[0];
        group.remove(obj);
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
            if (Array.isArray(obj.material)) {
                obj.material.forEach(m => m.dispose());
            } else {
                obj.material.dispose();
            }
        }
    }
}

// ==========================================================
// ANIMATION LOOP
// ==========================================================

function animate() {
    requestAnimationFrame(animate);
    if (controls) controls.update();
    if (renderer && scene && camera) {
        renderer.render(scene, camera);
    }
}