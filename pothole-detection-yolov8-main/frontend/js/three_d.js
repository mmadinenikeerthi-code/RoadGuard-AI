// ==========================================================
// ROADGUARD AI — IMMERSIVE 3D / 360° ROAD VIEW
// FILE: frontend/js/three_d.js
// ==========================================================

import * as THREE from "https://esm.sh/three@0.160.0";
import { OrbitControls } from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";

let scene, camera, renderer, controls, potholeGroup, animationId;
let raycaster, mouse;
let currentReportId = null;

document.addEventListener("DOMContentLoaded", initializeThreeViewer);

async function initializeThreeViewer() {
    try {
        createThreeScene();
        initializeControls();
        animate();
        await loadReportList();
    } catch (error) {
        console.error("❌ 3D initialization error:", error);
        updateThreeStatus(`❌ Failed to initialize: ${error.message}`);
    }
}

function createThreeScene() {
    const container = document.getElementById("threeContainer");
    if (!container) throw new Error("threeContainer not found in three_d.html");

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;

    camera = new THREE.PerspectiveCamera(70, width / height, 0.1, 1000);
    camera.position.set(0, 0, 0.1);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.rotateSpeed = -0.5; // inverted feels natural "looking around from inside"
    controls.enablePan = false;
    controls.minDistance = 0.01;
    controls.maxDistance = 0.01; // default: locked at center (panorama mode)
    controls.target.set(0, 0, -1);

    potholeGroup = new THREE.Group();
    scene.add(potholeGroup);

    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2();
    renderer.domElement.addEventListener("click", onSceneClick);

    window.addEventListener("resize", resizeThreeViewer);
}

// ==========================================================
// LOAD REPORT LIST -> POPULATE SELECTOR
// ==========================================================

async function loadReportList() {
    try {
        const response = await fetch(`${API_ENDPOINTS.base}/3d/reports-list`);
        const data = await response.json();

        const selector = document.getElementById("reportSelector");
        selector.innerHTML = "";

        (data.reports || []).forEach((report) => {
            const option = document.createElement("option");
            option.value = report.id;
            option.textContent = `#${report.id} — ${report.media_type} — ${report.pothole_count} potholes (${report.severity})`;
            selector.appendChild(option);
        });

        selector.addEventListener("change", () => loadRoadView(selector.value));

        if (data.reports && data.reports.length > 0) {
            loadRoadView(data.reports[0].id);
        } else {
            updateThreeStatus("⚠️ No reports available yet. Upload media first.");
        }
    } catch (error) {
        console.error("❌ Could not load report list:", error);
        updateThreeStatus(`❌ ${error.message}`);
    }
}

// ==========================================================
// LOAD ROAD VIEW FOR A SPECIFIC REPORT
// ==========================================================

async function loadRoadView(reportId) {
    currentReportId = reportId;
    updateThreeStatus("⏳ Loading road view...");
    showLoadingOverlay(true);

    try {
        const response = await fetch(`${API_ENDPOINTS.base}/3d/road-view/${reportId}`);
        if (!response.ok) throw new Error(`Server error: ${response.status}`);
        const data = await response.json();

        updateModeBadge(data.is_true_360, data.view_label);
        document.getElementById("mediaFormat").textContent = data.media_format;
        document.getElementById("totalObjects").textContent = data.pothole_count;

        if (data.is_true_360 && data.panorama_image) {
            await buildPanoramaMode(data.panorama_image);
        } else {
            buildReconstructionMode();
        }

        renderPotholeMarkers(data.markers || []);

        updateThreeStatus(
            data.pothole_count > 0
                ? `✅ Loaded ${data.pothole_count} pothole marker(s)`
                : "⚠️ No pothole markers for this report"
        );
    } catch (error) {
        console.error("❌ Error loading road view:", error);
        updateThreeStatus(`❌ ${error.message}`);
    } finally {
        showLoadingOverlay(false);
    }
}

// ==========================================================
// PANORAMA MODE (real 360° — user is INSIDE a textured sphere)
// ==========================================================

async function buildPanoramaMode(panoramaImagePath) {
    clearWorld();

    const geometry = new THREE.SphereGeometry(50, 60, 40);
    geometry.scale(-1, 1, 1); // invert so texture faces inward

    const texture = await new THREE.TextureLoader().loadAsync(
        `${API_ENDPOINTS.base}/results/${panoramaImagePath}`
    );
    texture.colorSpace = THREE.SRGBColorSpace;

    const material = new THREE.MeshBasicMaterial({ map: texture });
    const sphere = new THREE.Mesh(geometry, material);
    sphere.name = "panoramaSphere";
    scene.add(sphere);

    camera.position.set(0, 0, 0.1);
    controls.minDistance = 0.01;
    controls.maxDistance = 0.01; // locked at center: pure look-around
    controls.target.set(0, 0, -1);
    controls.update();
}

// ==========================================================
// RECONSTRUCTION MODE (forward-facing video/image — synthetic scene)
// ==========================================================

function buildReconstructionMode() {
    clearWorld();

    scene.background = new THREE.Color(0x0f172a);

    const ambient = new THREE.AmbientLight(0xffffff, 1.4);
    scene.add(ambient);

    const directional = new THREE.DirectionalLight(0xffffff, 1.8);
    directional.position.set(10, 20, 10);
    scene.add(directional);

    const roadGeometry = new THREE.PlaneGeometry(20, 60);
    const roadMaterial = new THREE.MeshStandardMaterial({ color: 0x374151, roughness: 0.9 });
    const road = new THREE.Mesh(roadGeometry, roadMaterial);
    road.rotation.x = -Math.PI / 2;
    road.position.set(0, -0.5, -25);
    road.name = "roadPlane";
    scene.add(road);

    const grid = new THREE.GridHelper(60, 30, 0x64748b, 0x334155);
    grid.position.set(0, -0.49, -25);
    grid.name = "roadGrid";
    scene.add(grid);

    camera.position.set(0, 1.5, 5);
    controls.minDistance = 1;
    controls.maxDistance = 30;
    controls.target.set(0, 0, -10);
    controls.rotateSpeed = 0.5; // normal orbit feel, not "inside a sphere"
    controls.update();
}

function clearWorld() {
    const toRemove = scene.children.filter(
        (child) => child.name === "panoramaSphere" || child.name === "roadPlane" || child.name === "roadGrid"
    );
    toRemove.forEach((child) => {
        scene.remove(child);
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
    });
    while (potholeGroup.children.length > 0) {
        const obj = potholeGroup.children[0];
        potholeGroup.remove(obj);
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) obj.material.dispose();
    }
}

// ==========================================================
// POTHOLE MARKERS
// ==========================================================

function renderPotholeMarkers(markers) {
    while (potholeGroup.children.length > 0) {
        const obj = potholeGroup.children[0];
        potholeGroup.remove(obj);
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) obj.material.dispose();
    }

    markers.forEach((marker) => {
        const geometry = new THREE.SphereGeometry(0.3, 20, 16);
        const material = new THREE.MeshStandardMaterial({
            color: getThreeColor(marker.severity),
            emissive: getThreeColor(marker.severity),
            emissiveIntensity: 0.4,
        });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.set(marker.position.x, marker.position.y, marker.position.z);
        mesh.userData = marker;
        potholeGroup.add(mesh);
    });
}

function onSceneClick(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(potholeGroup.children);

    if (intersects.length > 0) {
        showPotholeInfo(intersects[0].object.userData);
    }
}

function showPotholeInfo(marker) {
    const panel = document.getElementById("potholeInfoPanel");
    const locationText =
        marker.location === "unknown"
            ? "Location unknown"
            : `${marker.location.latitude.toFixed(6)}, ${marker.location.longitude.toFixed(6)}`;

    panel.innerHTML = `
        <div class="pothole-info-card">
            <h4>Pothole #${marker.pothole_id}</h4>
            <p><strong>Severity:</strong> ${marker.severity}</p>
            <p><strong>Confidence:</strong> ${(marker.confidence * 100).toFixed(0)}%</p>
            <p><strong>Location:</strong> ${locationText}</p>
        </div>
    `;
}

function updateModeBadge(isTrue360, label) {
    const badge = document.getElementById("viewModeBadge");
    if (!badge) return;
    badge.textContent = label;
    badge.className = "view-mode-badge " + (isTrue360 ? "true-360" : "reconstruction");
}

function getThreeColor(severity) {
    const colors = { LOW: 0x22c55e, MODERATE: 0xf59e0b, HIGH: 0xf97316, CRITICAL: 0xef4444 };
    return colors[severity] || 0x64748b;
}

// ==========================================================
// ANIMATION / CONTROLS / RESIZE
// ==========================================================

function animate() {
    animationId = requestAnimationFrame(animate);
    if (controls) controls.update();
    if (renderer && scene && camera) renderer.render(scene, camera);
}

function resetCamera() {
    if (controls.maxDistance <= 0.02) {
        camera.position.set(0, 0, 0.1);
        controls.target.set(0, 0, -1);
    } else {
        camera.position.set(0, 1.5, 5);
        controls.target.set(0, 0, -10);
    }
    controls.update();
    updateThreeStatus("🎯 Camera reset");
}

function initializeControls() {
    const reloadButton = document.getElementById("reloadSceneBtn");
    if (reloadButton) reloadButton.addEventListener("click", () => currentReportId && loadRoadView(currentReportId));

    const resetButton = document.getElementById("resetCameraBtn");
    if (resetButton) resetButton.addEventListener("click", resetCamera);
}

function resizeThreeViewer() {
    const container = document.getElementById("threeContainer");
    if (!container || !camera || !renderer) return;
    const width = container.clientWidth;
    const height = container.clientHeight;
    if (width === 0 || height === 0) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
}

function showLoadingOverlay(visible) {
    const overlay = document.getElementById("loadingOverlay");
    if (overlay) overlay.style.opacity = visible ? "1" : "0";
    if (overlay) overlay.style.pointerEvents = visible ? "auto" : "none";
}

function updateThreeStatus(message) {
    const status = document.getElementById("threeStatus");
    if (status) status.textContent = message;
    console.log("3D Status:", message);
}

window.addEventListener("beforeunload", () => {
    if (animationId) cancelAnimationFrame(animationId);
});