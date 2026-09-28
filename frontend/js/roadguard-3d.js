// frontend/js/roadguard-3d.js

import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js";

import { OrbitControls } from
    "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/controls/OrbitControls.js";

import { PLYLoader } from
    "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/loaders/PLYLoader.js";


const params = new URLSearchParams(
    window.location.search
);

const reportId =
    params.get("report_id");


/*
   Report used by the viewer.
   Defaults to report 21 (the report exposed by the unified
   sidebar link: /3d?report_id=21).
*/

const DEFAULT_REPORT_ID = "21";


const activeReportId =
    reportId || DEFAULT_REPORT_ID;


const container =
    document.getElementById("roadguard-3d") ||
    document.getElementById("three-container");


const statusElement =
    document.getElementById("3d-status") ||
    document.getElementById("loading");


const potholePanel =
    document.getElementById("pothole-list");


if (!container) {

    console.error(
        "RoadGuard 3D container not found."
    );

    throw new Error(
        "3D container missing"
    );
}


if (!reportId) {

    /*
       The unified sidebar links to /3d?report_id=21.
       When the query string has no report_id we fall back to
       report 21 so the real COLMAP / photogrammetry
       reconstruction is still loaded instead of an empty view.
    */

    console.info(
        "RoadGuard 3D: no report_id supplied - " +
        "loading the default report " +
        DEFAULT_REPORT_ID
    );
}


// ============================================================
// SCENE
// ============================================================

const scene =
    new THREE.Scene();

scene.background =
    new THREE.Color(
        0x080b10
    );


// ============================================================
// CAMERA
// ============================================================

const camera =
    new THREE.PerspectiveCamera(
        55,
        container.clientWidth /
            container.clientHeight,
        0.01,
        100000
    );

camera.position.set(
    0,
    5,
    15
);


// ============================================================
// RENDERER
// ============================================================

const renderer =
    new THREE.WebGLRenderer({
        antialias: true,
        powerPreference: "high-performance"
    });

renderer.setPixelRatio(
    Math.min(
        window.devicePixelRatio,
        2
    )
);

renderer.setSize(
    container.clientWidth,
    container.clientHeight
);

renderer.shadowMap.enabled = true;

container.appendChild(
    renderer.domElement
);


// ============================================================
// CONTROLS
// ============================================================

const controls =
    new OrbitControls(
        camera,
        renderer.domElement
    );

controls.enableDamping = true;

controls.dampingFactor = 0.06;

controls.screenSpacePanning = true;

controls.minDistance = 0.5;

controls.maxDistance = 5000;

controls.target.set(
    0,
    0,
    0
);


// ============================================================
// LIGHTING
// ============================================================

const ambientLight =
    new THREE.HemisphereLight(
        0xffffff,
        0x202020,
        2.2
    );

scene.add(
    ambientLight
);


const directionalLight =
    new THREE.DirectionalLight(
        0xffffff,
        3
    );

directionalLight.position.set(
    20,
    40,
    20
);

directionalLight.castShadow = true;

scene.add(
    directionalLight
);


// ============================================================
// VIEWER CONTENT
//
// The viewer shows ONLY the real RoadGuard reconstruction that
// is loaded from the COLMAP / photogrammetry PLY files above.
// No procedural road (PlaneGeometry / BoxGeometry / GridHelper)
// is created.
// ============================================================


// ============================================================
// GROUPS
// ============================================================

const roadGroup =
    new THREE.Group();

scene.add(
    roadGroup
);


const potholeGroup =
    new THREE.Group();

scene.add(
    potholeGroup
);


// ============================================================
// LOAD 3D ROAD
// ============================================================

async function loadRoadMesh() {

    const loader =
        new PLYLoader();

    /*
       Real RoadGuard reconstruction sources, tried in order:

       1. existing backend result path
          results/photogrammetry/report_<id>/roadguard-road.ply
       2. existing photogrammetry mesh API
          /api/photogrammetry/mesh/<id>
    */

    const candidateUrls = [

        `/results/photogrammetry/report_${activeReportId}/roadguard-road.ply`,

        `/api/photogrammetry/mesh/${activeReportId}`

    ];

    try {

        if (statusElement) {

            statusElement.textContent =
                "Loading COLMAP reconstruction...";
        }

        let geometry = null;

        for (const modelUrl of candidateUrls) {

            console.log(
                "RoadGuard COLMAP PLY:",
                modelUrl
            );

            try {

                geometry =
                    await loader.loadAsync(
                        modelUrl
                    );

                break;

            } catch (loadError) {

                console.warn(
                    "PLY source unavailable:",
                    modelUrl,
                    loadError
                );
            }
        }

        if (!geometry) {

            throw new Error(
                "No RoadGuard PLY reconstruction available"
            );
        }

        console.log(
            "COLMAP PLY loaded successfully"
        );

        console.log(
            "Vertices:",
            geometry.attributes.position
                ? geometry.attributes.position.count
                : 0
        );

        console.log(
            "Has faces:",
            geometry.index !== null
        );

        // =====================================================
        // DETERMINE PLY TYPE
        // =====================================================

        const hasFaces =
            geometry.index !== null &&
            geometry.index.count >= 3;

        let roadObject;

        // =====================================================
        // COLMAP POINT CLOUD
        // =====================================================

        if (!hasFaces) {

            /*
               COLMAP sparse point cloud.

               The point size is scaled with the model below so the
               real reconstruction is clearly visible instead of
               rendering as sub-pixel dots.
            */

            const pointSize = 1.1;

            const pointMaterial =
                new THREE.PointsMaterial({

                    size: pointSize,

                    vertexColors:
                        geometry.hasAttribute(
                            "color"
                        ),

                    sizeAttenuation: true

                });

            roadObject =
                new THREE.Points(
                    geometry,
                    pointMaterial
                );

            console.log(
                "ROADGUARD 3D NEW VERSION LOADED",
                geometry.attributes.position.count,
                "points"
            );

        }

        // =====================================================
        // COLMAP MESH
        // =====================================================

        else {

            geometry.computeVertexNormals();

            const material =
                new THREE.MeshStandardMaterial({

                    vertexColors:
                        geometry.hasAttribute(
                            "color"
                        ),

                    roughness: 0.8,

                    metalness: 0.05,

                    side:
                        THREE.DoubleSide

                });

            roadObject =
                new THREE.Mesh(
                    geometry,
                    material
                );

            roadObject.castShadow = true;

            roadObject.receiveShadow = true;

            console.log(
                "Rendering COLMAP mesh"
            );
        }

        roadGroup.add(
            roadObject
        );


        // =====================================================
        // CENTER COLMAP MODEL
        // =====================================================

        geometry.computeBoundingBox();

        const box =
            geometry.boundingBox;

        if (box) {

            const center =
                new THREE.Vector3();

            box.getCenter(
                center
            );

            roadObject.position.sub(
                center
            );

            const size =
                new THREE.Vector3();

            box.getSize(
                size
            );

            const maxDimension =
                Math.max(
                    size.x,
                    size.y,
                    size.z
                );

            console.log(
                "COLMAP dimensions:",
                size.x,
                size.y,
                size.z
            );

            if (
                maxDimension > 0
            ) {

                const targetSize = 100;

                const scale =
                    targetSize /
                    maxDimension;

                roadObject.scale.setScalar(
                    scale
                );


                /*
                   Keep the point cloud readable after the model is
                   rescaled to the viewer target size.
                */

                if (
                    roadObject.isPoints &&
                    roadObject.material
                ) {

                    roadObject.material.size =
                        targetSize * 0.012;

                    roadObject.material.needsUpdate =
                        true;
                }

                console.log(
                    "COLMAP scale:",
                    scale
                );
            }
        }


        // =====================================================
        // FRAME CAMERA
        // =====================================================

        frameObject(
            roadObject
        );


        if (statusElement) {

            statusElement.textContent =
                "COLMAP 3D reconstruction loaded";

            /*
               Hide the loading overlay so the real reconstruction
               is actually visible.
            */

            statusElement.classList.add(
                "hidden"
            );
        }

    }

    catch (error) {

        console.error(
            "COLMAP reconstruction failed:",
            error
        );

        if (statusElement) {

            statusElement.textContent =
                "COLMAP reconstruction unavailable";

            statusElement.classList.add(
                "hidden"
            );
        }
    }
}


// ============================================================
// FRAME CAMERA
// ============================================================

function frameObject(
    object
) {

    const box =
        new THREE.Box3()
            .setFromObject(
                object
            );

    const center =
        new THREE.Vector3();

    box.getCenter(
        center
    );

    const size =
        new THREE.Vector3();

    box.getSize(
        size
    );

    const maxSize =
        Math.max(
            size.x,
            size.y,
            size.z
        );

    const distance =
        maxSize * 1.4;

    camera.position.set(
        center.x,
        center.y +
            maxSize * 0.25,
        center.z +
            distance
    );

    controls.target.copy(
        center
    );

    controls.update();
}


// ============================================================
// CREATE POTHOLE MARKER
// ============================================================

function createPotholeMarker(
    pothole,
    index
) {

    if (
        !pothole.position_3d
    ) {
        return;
    }

    const position =
        pothole.position_3d;

    const marker =
        new THREE.Mesh(
            new THREE.SphereGeometry(
                0.25,
                24,
                24
            ),
            new THREE.MeshBasicMaterial({
                color:
                    pothole.severity ===
                    "CRITICAL"
                        ? 0xff2222
                        :
                    pothole.severity ===
                    "HIGH"
                        ? 0xff6611
                        :
                    pothole.severity ===
                    "MODERATE"
                        ? 0xffcc00
                        :
                        0x22cc66
            })
        );


    marker.position.set(
        position[0],
        position[1] + 0.15,
        position[2]
    );


    marker.userData = {
        pothole,
        index
    };


    potholeGroup.add(
        marker
    );


    // Vertical indicator
    const line =
        new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(
                    position[0],
                    position[1],
                    position[2]
                ),

                new THREE.Vector3(
                    position[0],
                    position[1] + 2,
                    position[2]
                )
            ]),
            new THREE.LineBasicMaterial({
                color: 0xffffff
            })
        );

    potholeGroup.add(
        line
    );
}


// ============================================================
// LOAD POTHOLE DATA
// ============================================================

async function loadPotholeMetadata() {

    try {

        const response =
            await fetch(
                `/api/photogrammetry/metadata/${activeReportId}`
            );

        if (!response.ok) {

            throw new Error(
                "Metadata unavailable"
            );
        }

        const data =
            await response.json();

        const potholes =
            data.potholes || [];


        /*
           Presentation only: surface the reconstruction summary
           that the photogrammetry API already returns.
        */

        updateSummaryMetrics(
            data,
            potholes
        );


        potholes.forEach(
            (pothole, index) => {

                createPotholeMarker(
                    pothole,
                    index
                );
            }
        );


        updatePotholePanel(
            potholes
        );


    } catch (error) {

        console.error(
            "Failed to load pothole metadata:",
            error
        );
    }
}


// ============================================================
// UI PANEL
// ============================================================

function updatePotholePanel(
    potholes
) {

    if (!potholePanel) {
        return;
    }

    potholePanel.innerHTML = "";


    if (!potholes.length) {

        potholePanel.innerHTML =
            `
            <div class="pothole-empty">
                No mapped potholes available.
            </div>
            `;

        return;
    }


    potholes.forEach(
        (pothole, index) => {

            const card =
                document.createElement(
                    "div"
                );

            card.className =
                "pothole-card";


            const confidence =
                pothole.confidence != null
                    ? `${(
                        pothole.confidence * 100
                    ).toFixed(1)}%`
                    : "N/A";


            card.innerHTML =
                `
                <div>
                    <strong>
                        Pothole ${index + 1}
                    </strong>
                </div>

                <div>
                    Severity:
                    ${pothole.severity || "UNKNOWN"}
                </div>

                <div>
                    Confidence:
                    ${confidence}
                </div>
                `;


            potholePanel.appendChild(
                card
            );
        }
    );
}


// ============================================================
// RESIZE
// ============================================================

window.addEventListener(
    "resize",
    () => {

        const width =
            container.clientWidth;

        const height =
            container.clientHeight;


        camera.aspect =
            width / height;

        camera.updateProjectionMatrix();


        renderer.setSize(
            width,
            height
        );
    }
);


// ============================================================
// ANIMATION
// ============================================================

function animate() {

    requestAnimationFrame(
        animate
    );

    controls.update();

    renderer.render(
        scene,
        camera
    );
}


// ============================================================
// VIEWER CONTROLS
// (camera presets + focus buttons of the unified shell)
// ============================================================

function focusTarget() {

    if (potholeGroup.children.length) {
        return potholeGroup;
    }

    if (roadGroup.children.length) {
        return roadGroup;
    }

    return scene;
}


function setupViewerControls() {

    const perspectiveButton =
        document.getElementById("perspectiveBtn");

    const topButton =
        document.getElementById("topBtn");

    const resetButton =
        document.getElementById("resetBtn");

    const focusAllButton =
        document.getElementById("focusAllBtn");

    const focusSelectedButton =
        document.getElementById("focusSelectedBtn");


    function readBounds(object) {

        const box =
            new THREE.Box3()
                .setFromObject(object);

        const center =
            new THREE.Vector3();

        const size =
            new THREE.Vector3();

        box.getCenter(center);
        box.getSize(size);

        const maxSize =
            Math.max(
                size.x,
                size.y,
                size.z
            ) || 100;

        return {
            center,
            maxSize
        };
    }


    if (perspectiveButton) {

        perspectiveButton.addEventListener(
            "click",
            () => {

                const target =
                    focusTarget();

                const bounds =
                    readBounds(target);

                camera.position.set(
                    bounds.center.x + bounds.maxSize * 1.2,
                    bounds.center.y + bounds.maxSize * 0.9,
                    bounds.center.z + bounds.maxSize * 1.2
                );

                controls.target.copy(
                    bounds.center
                );

                controls.update();
            }
        );
    }


    if (topButton) {

        topButton.addEventListener(
            "click",
            () => {

                const target =
                    focusTarget();

                const bounds =
                    readBounds(target);

                camera.position.set(
                    bounds.center.x,
                    bounds.center.y + bounds.maxSize * 1.6,
                    bounds.center.z + 0.001
                );

                controls.target.copy(
                    bounds.center
                );

                controls.update();
            }
        );
    }


    if (resetButton) {

        resetButton.addEventListener(
            "click",
            () => {

                frameObject(
                    focusTarget()
                );
            }
        );
    }


    if (focusAllButton) {

        focusAllButton.addEventListener(
            "click",
            () => {

                frameObject(
                    focusTarget()
                );
            }
        );
    }


    if (focusSelectedButton) {

        focusSelectedButton.addEventListener(
            "click",
            () => {

                frameObject(
                    focusTarget()
                );
            }
        );
    }
}


// ============================================================
// SUMMARY METRICS
// (from the existing photogrammetry metadata API)
// ============================================================

function updateSummaryMetrics(
    data,
    potholes
) {

    const totalElement =
        document.getElementById("totalPotholes");

    const confidenceElement =
        document.getElementById("confidence");

    const conditionElement =
        document.getElementById("roadCondition");


    const total =

        data && data.pothole_count != null

            ? Number(data.pothole_count)

            : (potholes ? potholes.length : 0);


    if (totalElement) {

        totalElement.textContent =
            String(total);
    }


    const confidence =
        data && data.confidence != null
            ? Number(data.confidence)
            : NaN;


    if (confidenceElement) {

        confidenceElement.textContent =
            Number.isFinite(confidence)
                ? `${(confidence * 100).toFixed(1)}%`
                : "--";
    }


    if (conditionElement) {

        conditionElement.textContent =
            data && data.severity
                ? String(data.severity).toUpperCase()
                : "--";
    }
}


// ============================================================
// START
// ============================================================

setupViewerControls();

loadRoadMesh();

loadPotholeMetadata();

animate();