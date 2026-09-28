// ==========================================================
// ROADGUARD AI
// DETECTION CONTROLLER
// ==========================================================


// ==========================================================
// STATE
// ==========================================================

let selectedImageFile = null;

let selectedVideoFile = null;

let cameraStream = null;

let mediaRecorder = null;

let recordedChunks = [];

let recordedVideoBlob = null;

let capturedImages = [];


// ==========================================================
// DOM READY
// ==========================================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        initializeDetectionPage();

    }
);


// ==========================================================
// INITIALIZE PAGE
// ==========================================================

function initializeDetectionPage() {

    initializeModeTabs();

    initializeImageUpload();

    initializeVideoUpload();

    initializeCamera();

    initializeClearButton();

}


// ==========================================================
// MODE TABS
// ==========================================================

function initializeModeTabs() {

    const buttons =
        document.querySelectorAll(".mode-btn");


    buttons.forEach(button => {

        button.addEventListener(
            "click",
            () => {

                const mode =
                    button.dataset.mode;


                document
                    .querySelectorAll(".mode-btn")
                    .forEach(btn => {

                        btn.classList.remove(
                            "active"
                        );

                    });


                button.classList.add(
                    "active"
                );


                document
                    .querySelectorAll(".detection-panel")
                    .forEach(panel => {

                        panel.classList.add(
                            "hidden"
                        );

                    });


                document
                    .getElementById(
                        `${mode}Mode`
                    )
                    .classList.remove(
                        "hidden"
                    );


                if (mode !== "camera") {

                    stopCamera();

                }

            }
        );

    });

}


// ==========================================================
// IMAGE UPLOAD
// ==========================================================

function initializeImageUpload() {

    const input =
        document.getElementById(
            "imageInput"
        );


    const selectButton =
        document.getElementById(
            "selectImageBtn"
        );


    const detectButton =
        document.getElementById(
            "detectImageBtn"
        );


    selectButton.addEventListener(
        "click",
        () => input.click()
    );


    input.addEventListener(
        "change",
        event => {

            const file =
                event.target.files[0];


            if (!file) return;


            selectedImageFile = file;


            showImagePreview(file);


            detectButton.disabled = false;

        }
    );


    detectButton.addEventListener(
        "click",
        async () => {

            if (!selectedImageFile) {

                alert(
                    "Please select an image first."
                );

                return;

            }


            await uploadAndProcess(
                selectedImageFile
            );

        }
    );

}


// ==========================================================
// IMAGE PREVIEW
// ==========================================================

function showImagePreview(file) {

    const container =
        document.getElementById(
            "imagePreviewContainer"
        );


    const preview =
        document.getElementById(
            "imagePreview"
        );


    preview.src =
        URL.createObjectURL(file);


    container.classList.remove(
        "hidden"
    );

}


// ==========================================================
// VIDEO UPLOAD
// ==========================================================

function initializeVideoUpload() {

    const input =
        document.getElementById(
            "videoInput"
        );


    const selectButton =
        document.getElementById(
            "selectVideoBtn"
        );


    const detectButton =
        document.getElementById(
            "detectVideoBtn"
        );


    selectButton.addEventListener(
        "click",
        () => input.click()
    );


    input.addEventListener(
        "change",
        event => {

            const file =
                event.target.files[0];


            if (!file) return;


            selectedVideoFile = file;


            showVideoPreview(file);


            detectButton.disabled = false;

        }
    );


    detectButton.addEventListener(
        "click",
        async () => {

            if (!selectedVideoFile) {

                alert(
                    "Please select a video first."
                );

                return;

            }


            await uploadAndProcess(
                selectedVideoFile
            );

        }
    );

}


// ==========================================================
// VIDEO PREVIEW
// ==========================================================

function showVideoPreview(file) {

    const container =
        document.getElementById(
            "videoPreviewContainer"
        );


    const preview =
        document.getElementById(
            "videoPreview"
        );


    preview.src =
        URL.createObjectURL(file);


    container.classList.remove(
        "hidden"
    );

}


// ==========================================================
// CAMERA INITIALIZATION
// ==========================================================

function initializeCamera() {

    const startButton =
        document.getElementById(
            "startCameraBtn"
        );


    const captureButton =
        document.getElementById(
            "captureImageBtn"
        );


    const startRecordingButton =
        document.getElementById(
            "startRecordingBtn"
        );


    const stopRecordingButton =
        document.getElementById(
            "stopRecordingBtn"
        );


    const stopCameraButton =
        document.getElementById(
            "stopCameraBtn"
        );


    const processVideoButton =
        document.getElementById(
            "processRecordedVideoBtn"
        );


    startButton.addEventListener(
        "click",
        startCamera
    );


    captureButton.addEventListener(
        "click",
        captureCameraImage
    );


    startRecordingButton.addEventListener(
        "click",
        startRecording
    );


    stopRecordingButton.addEventListener(
        "click",
        stopRecording
    );


    stopCameraButton.addEventListener(
        "click",
        stopCamera
    );


    processVideoButton.addEventListener(
        "click",
        async () => {

            if (!recordedVideoBlob) {

                alert(
                    "No recorded video available."
                );

                return;

            }


            const videoFile =
                new File(

                    [recordedVideoBlob],

                    `roadguard_recording_${Date.now()}.webm`,

                    {
                        type:
                            recordedVideoBlob.type ||
                            "video/webm"
                    }

                );


            await uploadAndProcess(
                videoFile
            );

        }
    );

}


// ==========================================================
// START CAMERA
// ==========================================================

async function startCamera() {

    try {

        cameraStream =
            await navigator
                .mediaDevices
                .getUserMedia({

                    video: {
                        facingMode: {
                            ideal: "environment"
                        }
                    },

                    audio: false

                });


        const video =
            document.getElementById(
                "cameraVideo"
            );


        video.srcObject =
            cameraStream;


        document
            .getElementById(
                "cameraPlaceholder"
            )
            .style.display =
            "none";


        document
            .getElementById(
                "captureImageBtn"
            )
            .disabled =
            false;


        document
            .getElementById(
                "startRecordingBtn"
            )
            .disabled =
            false;


        document
            .getElementById(
                "stopCameraBtn"
            )
            .disabled =
            false;


        updateRecordingStatus(
            "📹 Camera is active"
        );

    }

    catch (error) {

        console.error(error);


        updateRecordingStatus(
            "❌ Camera permission denied or camera unavailable"
        );

    }

}


// ==========================================================
// CAPTURE IMAGE
// ==========================================================

function captureCameraImage() {

    if (!cameraStream) return;


    const video =
        document.getElementById(
            "cameraVideo"
        );


    const canvas =
        document.getElementById(
            "cameraCanvas"
        );


    canvas.width =
        video.videoWidth;


    canvas.height =
        video.videoHeight;


    const context =
        canvas.getContext("2d");


    context.drawImage(

        video,

        0,

        0,

        canvas.width,

        canvas.height

    );


    canvas.toBlob(
        blob => {

            if (!blob) return;


            const file =
                new File(

                    [blob],

                    `road_capture_${Date.now()}.jpg`,

                    {
                        type: "image/jpeg"
                    }

                );


            capturedImages.push(file);


            displayCapturedImage(
                blob,
                file
            );


        },

        "image/jpeg",

        0.95
    );

}


// ==========================================================
// DISPLAY CAPTURED IMAGE
// ==========================================================

function displayCapturedImage(
    blob,
    file
) {

    const section =
        document.getElementById(
            "capturedImagesSection"
        );


    const gallery =
        document.getElementById(
            "capturedImages"
        );


    section.classList.remove(
        "hidden"
    );


    const card =
        document.createElement("div");


    card.className =
        "captured-image-card";


    const image =
        document.createElement("img");


    image.src =
        URL.createObjectURL(blob);


    const button =
        document.createElement("button");


    button.className =
        "primary-btn";


    button.textContent =
        "🔍 Detect";


    button.addEventListener(
        "click",
        async () => {

            await uploadAndProcess(
                file
            );

        }
    );


    card.appendChild(image);

    card.appendChild(button);


    gallery.appendChild(card);

}


// ==========================================================
// START RECORDING
// ==========================================================

function startRecording() {

    if (!cameraStream) return;


    recordedChunks = [];


    mediaRecorder =
        new MediaRecorder(
            cameraStream
        );


    mediaRecorder.addEventListener(
        "dataavailable",
        event => {

            if (
                event.data &&
                event.data.size > 0
            ) {

                recordedChunks.push(
                    event.data
                );

            }

        }
    );


    mediaRecorder.addEventListener(
        "stop",
        createRecordedVideo
    );


    mediaRecorder.start();


    document
        .getElementById(
            "startRecordingBtn"
        )
        .disabled =
        true;


    document
        .getElementById(
            "stopRecordingBtn"
        )
        .disabled =
        false;


    updateRecordingStatus(
        "🔴 Recording in progress..."
    );

}


// ==========================================================
// STOP RECORDING
// ==========================================================

function stopRecording() {

    if (
        mediaRecorder &&
        mediaRecorder.state !== "inactive"
    ) {

        mediaRecorder.stop();

    }

}


// ==========================================================
// CREATE RECORDED VIDEO
// ==========================================================

function createRecordedVideo() {

    recordedVideoBlob =
        new Blob(

            recordedChunks,

            {
                type:
                    mediaRecorder.mimeType ||
                    "video/webm"
            }

        );


    const video =
        document.getElementById(
            "recordedVideo"
        );


    video.src =
        URL.createObjectURL(
            recordedVideoBlob
        );


    document
        .getElementById(
            "recordedVideoSection"
        )
        .classList.remove(
            "hidden"
        );


    document
        .getElementById(
            "startRecordingBtn"
        )
        .disabled =
        false;


    document
        .getElementById(
            "stopRecordingBtn"
        )
        .disabled =
        true;


    updateRecordingStatus(
        "✅ Recording completed"
    );

}


// ==========================================================
// STOP CAMERA
// ==========================================================

function stopCamera() {

    if (!cameraStream) return;


    cameraStream
        .getTracks()
        .forEach(track => {

            track.stop();

        });


    cameraStream = null;


    document
        .getElementById(
            "cameraVideo"
        )
        .srcObject =
        null;


    document
        .getElementById(
            "cameraPlaceholder"
        )
        .style.display =
        "flex";


    document
        .getElementById(
            "captureImageBtn"
        )
        .disabled =
        true;


    document
        .getElementById(
            "startRecordingBtn"
        )
        .disabled =
        true;


    document
        .getElementById(
            "stopRecordingBtn"
        )
        .disabled =
        true;


    document
        .getElementById(
            "stopCameraBtn"
        )
        .disabled =
        true;


    updateRecordingStatus(
        "Camera stopped"
    );

}


// ==========================================================
// UPLOAD AND PROCESS
// ==========================================================

async function uploadAndProcess(file) {

    showProcessing(
        "Uploading media to RoadGuard AI..."
    );


    try {

        const formData =
            new FormData();


        /*
        IMPORTANT:

        If your FastAPI Swagger upload endpoint
        uses a different parameter name,
        change "file" below to that exact name.
        */

        formData.append(
            "file",
            file
        );


        const uploadResponse =
            await fetch(

                API_ENDPOINTS.detectionUpload,

                {
                    method: "POST",

                    body: formData
                }

            );


        const uploadData =
            await parseResponse(
                uploadResponse
            );


        if (!uploadResponse.ok) {

            throw new Error(

                uploadData.detail ||
                "Upload failed"

            );

        }


        console.log(
            "Upload Response:",
            uploadData
        );


        /*
        SUPPORT MULTIPLE BACKEND RESPONSE FORMATS
        */

        const reportId =

            uploadData.report_id ||

            uploadData.id ||

            uploadData.report?.id ||

            uploadData.data?.report_id ||

            uploadData.data?.id;


        if (!reportId) {

            hideProcessing();


            displayResult(
                uploadData
            );


            return;

        }


        showProcessing(
            "AI is analyzing potholes..."
        );


        const processResponse =
            await fetch(

                `${API_ENDPOINTS.detectionProcess}/${reportId}`,

                {
                    method: "POST"
                }

            );


        const processData =
            await parseResponse(
                processResponse
            );


        if (!processResponse.ok) {

            throw new Error(

                processData.detail ||
                "Detection processing failed"

            );

        }


        hideProcessing();


        displayResult(
            processData
        );


        console.log(
            "Detection Result:",
            processData
        );

    }

    catch (error) {

        console.error(
            "Detection Error:",
            error
        );


        hideProcessing();


        displayError(
            error.message
        );

    }

}


// ==========================================================
// PARSE RESPONSE
// ==========================================================

async function parseResponse(response) {

    const text =
        await response.text();


    try {

        return JSON.parse(text);

    }

    catch {

        return {
            detail: text
        };

    }

}


// ==========================================================
// PROCESSING UI
// ==========================================================

function showProcessing(message) {

    document
        .getElementById(
            "processingSection"
        )
        .classList.remove(
            "hidden"
        );


    document
        .getElementById(
            "processingMessage"
        )
        .textContent =
        message;

}


function hideProcessing() {

    document
        .getElementById(
            "processingSection"
        )
        .classList.add(
            "hidden"
        );

}


// ==========================================================
// DISPLAY RESULT
// ==========================================================

function displayResult(data) {

    const result =
        document.getElementById(
            "detectionResult"
        );


    result.classList.remove(
        "empty-result"
    );


    result.innerHTML = `

        <div class="result-success">

            <h3>
                ✅ Detection Completed Successfully
            </h3>

            <p>
                RoadGuard AI has completed
                the analysis.
            </p>

        </div>


        <pre class="result-json">${escapeHtml(
            JSON.stringify(
                data,
                null,
                2
            )
        )}</pre>

    `;

}


// ==========================================================
// DISPLAY ERROR
// ==========================================================

function displayError(message) {

    const result =
        document.getElementById(
            "detectionResult"
        );


    result.innerHTML = `

        <div class="result-error">

            <h3>
                ❌ Detection Failed
            </h3>

            <p>
                ${escapeHtml(message)}
            </p>

        </div>

    `;

}


// ==========================================================
// CLEAR RESULTS
// ==========================================================

function initializeClearButton() {

    const button =
        document.getElementById(
            "clearResultsBtn"
        );


    button.addEventListener(
        "click",
        () => {

            const result =
                document.getElementById(
                    "detectionResult"
                );


            result.className =
                "result-card empty-result";


            result.innerHTML = `

                <div class="empty-icon">
                    🔍
                </div>

                <h3>
                    No Detection Yet
                </h3>

                <p>
                    Upload media to begin detection.
                </p>

            `;

        }
    );

}


// ==========================================================
// STATUS
// ==========================================================

function updateRecordingStatus(message) {

    document
        .getElementById(
            "recordingStatus"
        )
        .textContent =
        message;

}


// ==========================================================
// ESCAPE HTML
// ==========================================================

function escapeHtml(text) {

    const div =
        document.createElement("div");


    div.textContent =
        text;


    return div.innerHTML;

}