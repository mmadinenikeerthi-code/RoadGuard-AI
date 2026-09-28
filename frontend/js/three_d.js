// ==========================================================
// ROADGUARD AI — PROFESSIONAL 3D ROAD VIEW
// frontend/js/three_d.js
// ==========================================================

import * as THREE from "https://esm.sh/three@0.160.0";

import {
    OrbitControls
} from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";

import {
    PLYLoader
} from "https://esm.sh/three@0.160.0/examples/jsm/loaders/PLYLoader.js";


let scene;
let camera;
let renderer;
let controls;

let potholeGroup;
let reconstructionGroup;

let raycaster;
let mouse;

let currentReportId = null;
let currentSceneData = null;

let animationId;


// ==========================================================
// INITIALIZE
// ==========================================================

document.addEventListener(
    "DOMContentLoaded",
    initializeThreeViewer
);


async function initializeThreeViewer() {

    try {

        createThreeScene();

        initializeControls();

        animate();

        await loadReportList();

    } catch (error) {

        console.error(
            "3D initialization error:",
            error
        );

        updateThreeStatus(
            `Failed to initialize: ${error.message}`
        );
    }
}


// ==========================================================
// THREE SCENE
// ==========================================================

function createThreeScene() {

    const container =
        document.getElementById(
            "threeContainer"
        );

    if (!container) {

        throw new Error(
            "threeContainer not found"
        );
    }


    scene = new THREE.Scene();

    scene.background =
        new THREE.Color(
            0x07111f
        );


    const width =
        container.clientWidth || 900;

    const height =
        container.clientHeight || 600;


    camera =
        new THREE.PerspectiveCamera(
            55,
            width / height,
            0.1,
            2000
        );


    camera.position.set(
        0,
        5,
        16
    );


    renderer =
        new THREE.WebGLRenderer({
            antialias: true,
            alpha: false,
        });


    renderer.setSize(
        width,
        height
    );

    renderer.setPixelRatio(
        Math.min(
            window.devicePixelRatio,
            2
        )
    );

    renderer.shadowMap.enabled = true;

    renderer.shadowMap.type =
        THREE.PCFSoftShadowMap;


    container.appendChild(
        renderer.domElement
    );


    controls =
        new OrbitControls(
            camera,
            renderer.domElement
        );

    controls.enableDamping = true;

    controls.dampingFactor = 0.08;

    controls.enablePan = true;

    controls.minDistance = 2;

    controls.maxDistance = 100;

    controls.target.set(
        0,
        0,
        -10
    );


    potholeGroup =
        new THREE.Group();

    potholeGroup.name =
        "potholeGroup";

    scene.add(
        potholeGroup
    );


    reconstructionGroup =
        new THREE.Group();

    reconstructionGroup.name =
        "reconstructionGroup";

    scene.add(
        reconstructionGroup
    );


    raycaster =
        new THREE.Raycaster();

    mouse =
        new THREE.Vector2();


    renderer.domElement.addEventListener(
        "click",
        onSceneClick
    );


    window.addEventListener(
        "resize",
        resizeThreeViewer
    );
}


// ==========================================================
// REPORT LIST
// ==========================================================

async function loadReportList() {

    try {

        const response =
            await fetch(
                `${API_ENDPOINTS.base}/3d/reports-list`
            );

        if (!response.ok) {

            throw new Error(
                `Server error: ${response.status}`
            );
        }


        const data =
            await response.json();


        const selector =
            document.getElementById(
                "reportSelector"
            );


        selector.innerHTML = "";


        (
            data.reports || []
        ).forEach(
            report => {

                const option =
                    document.createElement(
                        "option"
                    );

                option.value =
                    report.id;

                option.textContent =
                    `#${report.id} — ` +
                    `${report.media_type} — ` +
                    `${report.pothole_count} potholes`;

                selector.appendChild(
                    option
                );
            }
        );


        selector.addEventListener(
            "change",
            () => {
                loadRoadView(
                    selector.value
                );
            }
        );


        if (
            data.reports &&
            data.reports.length
        ) {

            /*
             * Deep-linking support:
             *
             *     three_d.html?report_id=17
             *
             * Falls back to the newest report when no (or an
             * unknown) report_id is supplied.
             */
            const requestedReportId =
                new URLSearchParams(
                    window.location.search
                ).get("report_id");


            const requestedReport =
                requestedReportId
                    ? data.reports.find(
                        report =>
                            String(report.id) ===
                            String(requestedReportId)
                    )
                    : null;


            const targetReport =
                requestedReport ||
                data.reports[0];


            selector.value =
                targetReport.id;


            await loadRoadView(
                targetReport.id
            );

        } else {

            updateThreeStatus(
                "No reports available yet."
            );
        }

    } catch (error) {

        console.error(
            error
        );

        updateThreeStatus(
            error.message
        );
    }
}


// ==========================================================
// LOAD ROAD VIEW
// ==========================================================

async function loadRoadView(
    reportId
) {

    if (
        reportId === undefined ||
        reportId === null ||
        reportId === ""
    ) {

        showError(
            "No report selected."
        );

        return;
    }


    currentReportId =
        reportId;

    showLoadingOverlay(
        true
    );

    setStatusBar(
        `Loading 3D data for report #${reportId}…`,
        false
    );


    try {

        const response =
            await fetch(
                `${API_ENDPOINTS.base}/3d/road-view/${reportId}`
            );


        /*
         * Read the body as text first so an empty response or a
         * non-JSON error page cannot throw an opaque
         * "Unexpected end of JSON input".
         */
        const rawBody =
            await response.text();


        let data = null;


        if (rawBody) {

            try {

                data = JSON.parse(
                    rawBody
                );

            } catch (parseError) {

                throw new Error(
                    `Invalid JSON from `
                    + `/3d/road-view/${reportId} `
                    + `(HTTP ${response.status}).`
                );
            }
        }


        if (!response.ok) {

            const detail =
                data &&
                (data.detail || data.message);


            throw new Error(
                detail
                    ? `HTTP ${response.status}: ${detail}`
                    : `HTTP ${response.status} from `
                    + `/3d/road-view/${reportId}.`
            );
        }


        if (!data) {

            throw new Error(
                `Empty response from `
                + `/3d/road-view/${reportId}.`
            );
        }


        currentSceneData =
            data;


        updateSummary(
            data
        );


        clearWorld();


        /*
         * TRUE 360 MEDIA
         */
        if (
            data.viewer &&
            data.viewer.is_360
        ) {

            updateModeBadge(
                "360 PANORAMA",
                true
            );

            await buildPanoramaMode(
                data.report.media_path
            );

        }

        /*
         * REAL RECONSTRUCTION
         */
        else if (
            data.viewer &&
            data.viewer.reconstruction_available
        ) {

            updateModeBadge(
                "3D RECONSTRUCTION",
                true
            );

            await buildReconstructionMode(
                data.reconstruction
            );

        }

        /*
         * FALLBACK
         */
        else {

            updateModeBadge(
                "3D ROAD VIEW",
                false
            );

            buildFallbackRoad();
        }


        renderPotholeMarkers(
            data.potholes || []
        );


        reportLoadOutcome(
            data
        );


    } catch (error) {

        showError(
            `Could not load 3D data for report `
            + `#${reportId}: ${error.message}`
        );

    } finally {

        showLoadingOverlay(
            false
        );
    }
}


/**
 * Describe what actually loaded, including what is missing.
 *
 * Nothing is invented here: the numbers come from the report
 * row and the "warnings" list produced by the backend.
 */
function reportLoadOutcome(
    data
) {

    const loadedMarkers =
        (data.potholes || []).length;


    const recordedPotholes =
        (data.report && data.report.pothole_count) || 0;


    const markerSource =
        (data.metadata && data.metadata.marker_source) || "none";


    let message =
        `${loadedMarkers} pothole marker(s) shown`;


    if (
        recordedPotholes > 0 &&
        loadedMarkers === 0
    ) {

        message +=
            ` — report #${data.report.id} records `
            + `${recordedPotholes} pothole(s), but no `
            + `per-pothole 3D geometry is available for it.`;

    } else if (
        markerSource === "detections" &&
        loadedMarkers !== recordedPotholes
    ) {

        /*
         * Older reports store per-frame samples only, so the
         * scene shows raw detections rather than one marker per
         * deduplicated pothole. Say so instead of implying the
         * recorded count is wrong.
         */
        message +=
            ` — these are per-frame detections; report `
            + `#${data.report.id} records `
            + `${recordedPotholes} distinct pothole(s).`;
    }


    if (
        data.warnings &&
        data.warnings.length
    ) {

        message +=
            " " +
            data.warnings.join(" ");
    }


    setStatusBar(
        message,
        false
    );


    console.log(
        "3D: road view loaded",
        data
    );
}


// ==========================================================
// REAL RECONSTRUCTION
// ==========================================================

async function buildReconstructionMode(
    reconstruction
) {

    clearReconstruction();


    const loader =
        new PLYLoader();


    const meshURL =
        reconstruction &&
        reconstruction.mesh_url;


    const pointURL =
        reconstruction &&
        reconstruction.pointcloud_url;


    if (meshURL) {

        updateThreeStatus(
            "Loading reconstructed road geometry..."
        );


        try {

            const geometry =
                await loader.loadAsync(
                    meshURL
                );


            /*
             * COLMAP sparse reconstructions contain vertices but
             * no triangle faces. Those must be drawn as points;
             * a THREE.Mesh would connect unrelated vertices with
             * meaningless triangles and render as garbage.
             */
            const hasFaces =
                geometry.index !== null &&
                geometry.index.count >= 3;


            let roadObject;


            if (hasFaces) {

                geometry.computeVertexNormals();


                const material =
                    new THREE.MeshStandardMaterial({
                        vertexColors:
                            geometry.hasAttribute(
                                "color"
                            ),

                        roughness: 0.88,

                        metalness: 0.02,

                        side:
                            THREE.DoubleSide,
                    });


                roadObject =
                    new THREE.Mesh(
                        geometry,
                        material
                    );

                roadObject.castShadow = true;

                roadObject.receiveShadow = true;

            } else {

                const material =
                    new THREE.PointsMaterial({
                        size: 0.35,

                        sizeAttenuation: true,

                        vertexColors:
                            geometry.hasAttribute(
                                "color"
                            ),
                    });


                roadObject =
                    new THREE.Points(
                        geometry,
                        material
                    );
            }


            roadObject.name =
                "roadReconstruction";


            normalizeObject(
                roadObject
            );


            reconstructionGroup.add(
                roadObject
            );


            fitCameraToObject(
                roadObject
            );


            updateThreeStatus(
                hasFaces
                    ? "Reconstructed road mesh loaded."
                    : "Reconstructed point cloud loaded "
                      + `(${geometry.attributes.position.count} points).`
            );


            return;


        } catch (error) {

            console.warn(
                "Reconstruction geometry loading failed:",
                error
            );
        }
    }


    if (pointURL) {

        updateThreeStatus(
            "Loading reconstructed point cloud..."
        );


        try {

            const geometry =
                await loader.loadAsync(
                    pointURL
                );


            const material =
                new THREE.PointsMaterial({
                    size: 0.035,

                    vertexColors:
                        geometry.hasAttribute(
                            "color"
                        ),
                });


            const points =
                new THREE.Points(
                    geometry,
                    material
                );


            points.name =
                "roadPointCloud";


            normalizeObject(
                points
            );


            reconstructionGroup.add(
                points
            );


            fitCameraToObject(
                points
            );


            updateThreeStatus(
                "Reconstructed point cloud loaded."
            );


            return;


        } catch (error) {

            console.warn(
                "Point cloud loading failed:",
                error
            );
        }
    }


    buildFallbackRoad();

    updateThreeStatus(
        "Reconstruction unavailable — showing 3D road view."
    );
}


// ==========================================================
// FALLBACK ROAD
// ==========================================================

function buildFallbackRoad() {

    scene.background =
        new THREE.Color(
            0x07111f
        );


    const ambient =
        new THREE.HemisphereLight(
            0xffffff,
            0x223344,
            1.8
        );

    scene.add(
        ambient
    );


    const directional =
        new THREE.DirectionalLight(
            0xffffff,
            2
        );

    directional.position.set(
        10,
        20,
        10
    );

    directional.castShadow =
        true;

    scene.add(
        directional
    );


    const roadGeometry =
        new THREE.PlaneGeometry(
            20,
            60,
            40,
            120
        );


    const roadMaterial =
        new THREE.MeshStandardMaterial({
            color: 0x252b32,
            roughness: 0.94,
            metalness: 0.0,
        });


    const road =
        new THREE.Mesh(
            roadGeometry,
            roadMaterial
        );


    road.rotation.x =
        -Math.PI / 2;


    road.position.set(
        0,
        -0.5,
        -25
    );


    road.name =
        "fallbackRoad";


    road.receiveShadow =
        true;


    reconstructionGroup.add(
        road
    );


    /*
     * Lane markings
     */

    const lineMaterial =
        new THREE.MeshBasicMaterial({
            color: 0xe5e7eb
        });


    [-3.3, 3.3].forEach(
        x => {

            const lineGeometry =
                new THREE.PlaneGeometry(
                    0.08,
                    60
                );

            const line =
                new THREE.Mesh(
                    lineGeometry,
                    lineMaterial
                );

            line.rotation.x =
                -Math.PI / 2;

            line.position.set(
                x,
                -0.48,
                -25
            );

            reconstructionGroup.add(
                line
            );
        }
    );


    camera.position.set(
        0,
        4.5,
        15
    );


    controls.target.set(
        0,
        0,
        -15
    );


    controls.update();
}


// ==========================================================
// PANORAMA
// ==========================================================

async function buildPanoramaMode(
    imagePath
) {

    const geometry =
        new THREE.SphereGeometry(
            50,
            60,
            40
        );


    geometry.scale(
        -1,
        1,
        1
    );


    const texture =
        await new THREE.TextureLoader()
            .loadAsync(
                `${API_ENDPOINTS.base}/results/${imagePath}`
            );


    texture.colorSpace =
        THREE.SRGBColorSpace;


    const material =
        new THREE.MeshBasicMaterial({
            map: texture
        });


    const sphere =
        new THREE.Mesh(
            geometry,
            material
        );


    sphere.name =
        "panoramaSphere";


    scene.add(
        sphere
    );


    camera.position.set(
        0,
        0,
        0.1
    );


    controls.minDistance =
        0.01;

    controls.maxDistance =
        0.01;

    controls.target.set(
        0,
        0,
        -1
    );

    controls.update();
}


// ==========================================================
// NORMALIZE RECONSTRUCTION
// ==========================================================

function normalizeObject(
    object
) {

    const box =
        new THREE.Box3()
            .setFromObject(
                object
            );


    const center =
        box.getCenter(
            new THREE.Vector3()
        );


    const size =
        box.getSize(
            new THREE.Vector3()
        );


    const maxDimension =
        Math.max(
            size.x,
            size.y,
            size.z
        );


    if (
        !Number.isFinite(
            maxDimension
        ) ||
        maxDimension <= 0
    ) {

        return;
    }


    const scale =
        20 / maxDimension;


    object.scale.setScalar(
        scale
    );


    object.position.sub(
        center.multiplyScalar(
            scale
        )
    );
}


// ==========================================================
// FIT CAMERA
// ==========================================================

function fitCameraToObject(
    object
) {

    const box =
        new THREE.Box3()
            .setFromObject(
                object
            );


    const center =
        box.getCenter(
            new THREE.Vector3()
        );


    const size =
        box.getSize(
            new THREE.Vector3()
        );


    const maxSize =
        Math.max(
            size.x,
            size.y,
            size.z
        );


    const distance =
        Math.max(
            maxSize * 1.5,
            8
        );


    camera.position.set(
        center.x,
        center.y + distance * 0.55,
        center.z + distance
    );


    controls.target.copy(
        center
    );


    controls.minDistance =
        Math.max(
            1,
            maxSize * 0.05
        );


    controls.maxDistance =
        Math.max(
            50,
            maxSize * 5
        );


    controls.update();
}


// ==========================================================
// POTHOLE MARKERS
// ==========================================================

function renderPotholeMarkers(
    markers
) {

    clearPotholes();


    markers.forEach(
        marker => {

            const geometry =
                new THREE.SphereGeometry(
                    0.28,
                    24,
                    18
                );


            const color =
                getThreeColor(
                    marker.severity
                );


            const material =
                new THREE.MeshStandardMaterial({
                    color,
                    roughness: 0.45,
                    metalness: 0.05,
                    emissive: color,
                    emissiveIntensity: 0.18,
                });


            const mesh =
                new THREE.Mesh(
                    geometry,
                    material
                );


            /*
             * Detection coordinates are image-space,
             * so we deliberately map them into a visual
             * road coordinate system. This is NOT claimed
             * as measured physical depth.
             *
             * The 0..1000 input range is mapped onto the
             * same 20-unit box that normalizeObject() gives
             * the reconstructed geometry, so markers land on
             * the road surface instead of floating outside it.
             */

            const normalizedX =
                marker.center_x || 0;

            const normalizedY =
                marker.center_y || 0;


            const x =
                ((normalizedX % 1000) / 1000) * 20 - 10;


            const z =
                -(
                    ((normalizedY % 1000) / 1000) * 20 - 10
                );


            mesh.position.set(
                x,
                0.15,
                z
            );


            mesh.userData =
                marker;


            mesh.castShadow =
                true;


            potholeGroup.add(
                mesh
            );
        }
    );
}


// ==========================================================
// CLEAR
// ==========================================================

function clearPotholes() {

    while (
        potholeGroup.children.length
    ) {

        const object =
            potholeGroup.children[0];

        potholeGroup.remove(
            object
        );

        disposeObject(
            object
        );
    }
}


function clearReconstruction() {

    while (
        reconstructionGroup.children.length
    ) {

        const object =
            reconstructionGroup.children[0];

        reconstructionGroup.remove(
            object
        );

        disposeObject(
            object
        );
    }
}


function clearWorld() {

    clearPotholes();

    clearReconstruction();


    const panorama =
        scene.getObjectByName(
            "panoramaSphere"
        );


    if (panorama) {

        scene.remove(
            panorama
        );

        disposeObject(
            panorama
        );
    }


    scene.children
        .filter(
            child =>
                child.isLight
        )
        .forEach(
            light => {
                scene.remove(
                    light
                );
            }
        );
}


function disposeObject(
    object
) {

    if (
        object.geometry
    ) {

        object.geometry.dispose();
    }


    if (
        object.material
    ) {

        if (
            Array.isArray(
                object.material
            )
        ) {

            object.material.forEach(
                material =>
                    material.dispose()
            );

        } else {

            object.material.dispose();
        }
    }
}


// ==========================================================
// CLICK
// ==========================================================

function onSceneClick(
    event
) {

    const rect =
        renderer.domElement
            .getBoundingClientRect();


    mouse.x =
        (
            (event.clientX - rect.left)
            / rect.width
        ) * 2 - 1;


    mouse.y =
        -(
            (event.clientY - rect.top)
            / rect.height
        ) * 2 + 1;


    raycaster.setFromCamera(
        mouse,
        camera
    );


    const intersections =
        raycaster.intersectObjects(
            potholeGroup.children
        );


    if (
        intersections.length
    ) {

        showPotholeInfo(
            intersections[0]
                .object
                .userData
        );
    }
}


// ==========================================================
// INFO PANEL
// ==========================================================

function showPotholeInfo(
    marker
) {

    const panel =
        document.getElementById(
            "potholeInfoPanel"
        );


    if (!panel) {
        return;
    }


    const location =
        marker.location;


    const locationText =
        location &&
        location.latitude !== undefined
            ? `${Number(location.latitude).toFixed(6)}, ${Number(location.longitude).toFixed(6)}`
            : "Location unavailable";


    panel.innerHTML = `
        <div class="pothole-info-card">
            <h4>Pothole #${marker.pothole_id}</h4>

            <p>
                <strong>Severity:</strong>
                ${marker.severity}
            </p>

            <p>
                <strong>Confidence:</strong>
                ${(Number(marker.confidence || 0) * 100).toFixed(0)}%
            </p>

            <p>
                <strong>Location:</strong>
                ${locationText}
            </p>
        </div>
    `;
}


// ==========================================================
// SUMMARY
// ==========================================================

function updateSummary(
    data
) {

    const total =
        document.getElementById(
            "totalObjects"
        );

    const format =
        document.getElementById(
            "mediaFormat"
        );


    if (total) {

        total.textContent =
            data.total_potholes || 0;
    }


    if (format) {

        format.textContent =
            data.report &&
            data.report.media_type
                ? data.report.media_type
                : "--";
    }
}


// ==========================================================
// MODE BADGE
// ==========================================================

function updateModeBadge(
    label,
    isReal
) {

    const badge =
        document.getElementById(
            "viewModeBadge"
        );


    if (!badge) {
        return;
    }


    badge.textContent =
        label;


    badge.className =
        "view-mode-badge " +
        (
            isReal
                ? "true-360"
                : "reconstruction"
        );
}


// ==========================================================
// COLORS
// ==========================================================

function getThreeColor(
    severity
) {

    const colors = {

        LOW: 0x22c55e,

        MODERATE: 0xf59e0b,

        HIGH: 0xf97316,

        CRITICAL: 0xef4444,
    };


    return (
        colors[
            String(
                severity || "LOW"
            ).toUpperCase()
        ] ||
        0x64748b
    );
}


// ==========================================================
// CONTROLS
// ==========================================================

function initializeControls() {

    const reload =
        document.getElementById(
            "reloadSceneBtn"
        );


    if (reload) {

        reload.addEventListener(
            "click",
            () => {

                if (
                    currentReportId
                ) {

                    loadRoadView(
                        currentReportId
                    );
                }
            }
        );
    }


    const reset =
        document.getElementById(
            "resetCameraBtn"
        );


    if (reset) {

        reset.addEventListener(
            "click",
            resetCamera
        );
    }


    /*
     * "Build 3D Model"
     *
     * Calls the registered endpoint:
     *
     *     POST /api/photogrammetry/reconstruct/<report_id>
     */
    const buildModel =
        document.getElementById(
            "runReconstructionBtn"
        );


    if (buildModel) {

        buildModel.addEventListener(
            "click",
            runPhotogrammetryReconstruction
        );
    }


    /*
     * "Open 3D Reconstruction"
     *
     * Opens the dedicated reconstruction viewer for the
     * currently selected report.
     */
    const openReconstruction =
        document.getElementById(
            "openPlyViewerBtn"
        );


    if (openReconstruction) {

        openReconstruction.addEventListener(
            "click",
            () => {

                if (!currentReportId) {

                    showError(
                        "Select a report before opening the "
                        + "reconstruction viewer."
                    );

                    return;
                }


                window.open(
                    `${API_ENDPOINTS.base}/3d-view`
                    + `?report_id=${currentReportId}`,
                    "_blank"
                );
            }
        );
    }
}


/**
 * Run photogrammetry for the selected report, then reload
 * the scene so the freshly built geometry is displayed.
 */
async function runPhotogrammetryReconstruction() {

    if (!currentReportId) {

        showError(
            "Select a report before building a 3D model."
        );

        return;
    }


    const confirmed =
        window.confirm(
            `Run photogrammetry reconstruction for report `
            + `#${currentReportId}?\n\n`
            + `This re-processes the stored video and can take `
            + `several minutes.`
        );


    if (!confirmed) {
        return;
    }


    showLoadingOverlay(
        true
    );

    updateThreeStatus(
        `Running photogrammetry for report #${currentReportId}…`
    );


    try {

        const response =
            await fetch(
                `${API_ENDPOINTS.photogrammetryReconstruct}/${currentReportId}`,
                {
                    method: "POST",
                }
            );


        const rawBody =
            await response.text();


        let payload = null;


        if (rawBody) {

            try {

                payload = JSON.parse(
                    rawBody
                );

            } catch (parseError) {

                payload = null;
            }
        }


        if (!response.ok) {

            const detail =
                payload &&
                (payload.detail || payload.message);


            throw new Error(
                detail
                    ? `HTTP ${response.status}: ${detail}`
                    : `HTTP ${response.status} from `
                    + `/api/photogrammetry/reconstruct/`
                    + `${currentReportId}.`
            );
        }


        updateThreeStatus(
            `Photogrammetry finished for report `
            + `#${currentReportId}. Reloading scene…`
        );


        await loadRoadView(
            currentReportId
        );


    } catch (error) {

        showError(
            `Build 3D Model failed for report `
            + `#${currentReportId}: ${error.message}`
        );


    } finally {

        showLoadingOverlay(
            false
        );
    }
}


function resetCamera() {

    camera.position.set(
        0,
        5,
        16
    );


    controls.target.set(
        0,
        0,
        -10
    );


    controls.update();


    updateThreeStatus(
        "Camera reset."
    );
}


// ==========================================================
// ANIMATION
// ==========================================================

function animate() {

    animationId =
        requestAnimationFrame(
            animate
        );


    if (controls) {

        controls.update();
    }


    if (
        renderer &&
        scene &&
        camera
    ) {

        renderer.render(
            scene,
            camera
        );
    }
}


// ==========================================================
// RESIZE
// ==========================================================

function resizeThreeViewer() {

    const container =
        document.getElementById(
            "threeContainer"
        );


    if (
        !container ||
        !camera ||
        !renderer
    ) {

        return;
    }


    const width =
        container.clientWidth;


    const height =
        container.clientHeight;


    if (
        !width ||
        !height
    ) {

        return;
    }


    camera.aspect =
        width / height;


    camera.updateProjectionMatrix();


    renderer.setSize(
        width,
        height
    );
}


// ==========================================================
// UI
// ==========================================================

function showLoadingOverlay(
    visible
) {

    const overlay =
        document.getElementById(
            "loadingOverlay"
        );


    if (!overlay) {
        return;
    }


    overlay.style.opacity =
        visible ? "1" : "0";


    overlay.style.pointerEvents =
        visible
            ? "auto"
            : "none";
}


function updateThreeStatus(
    message
) {

    const status =
        document.getElementById(
            "threeStatus"
        );


    if (status) {

        status.textContent =
            message;
    }


    /*
     * #threeStatus lives inside the loading overlay, so it is
     * hidden the moment the overlay fades out. Mirror every
     * message into the persistent status bar too.
     */
    setStatusBar(
        message,
        false
    );


    console.log(
        "3D:",
        message
    );
}


/**
 * Write to the status bar that sits outside the loading
 * overlay, so messages stay readable after loading finishes.
 */
function setStatusBar(
    message,
    isError
) {

    const bar =
        document.getElementById(
            "threeStatusBar"
        );


    if (!bar) {
        return;
    }


    bar.textContent =
        message;


    if (isError) {

        bar.classList.add(
            "error"
        );

    } else {

        bar.classList.remove(
            "error"
        );
    }
}


/**
 * Stop the spinner and surface a real, visible error.
 */
function showError(
    message
) {

    console.error(
        "3D error:",
        message
    );


    setStatusBar(
        message,
        true
    );


    const status =
        document.getElementById(
            "threeStatus"
        );


    if (status) {

        status.textContent =
            message;
    }
}


window.addEventListener(
    "beforeunload",
    () => {

        if (animationId) {

            cancelAnimationFrame(
                animationId
            );
        }
    }
);