// frontend/js/detection.js
let currentMode = "image";
let cameraStream = null;

function switchInput(mode) {
    currentMode = mode;
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    event.target.classList.add("active");
    
    const fileContainer = document.getElementById("file-input-container");
    const cameraContainer = document.getElementById("camera-container");
    const fileLabel = document.getElementById("file-label");
    const fileInput = document.getElementById("media-file");
    
    if (mode === "image") {
        fileContainer.style.display = "block";
        cameraContainer.style.display = "none";
        fileLabel.innerText = "Choose Road Image File";
        fileInput.accept = "image/*";
        stopCamera();
    } else if (mode === "video") {
        fileContainer.style.display = "block";
        cameraContainer.style.display = "none";
        fileLabel.innerText = "Choose Road Video Footage";
        fileInput.accept = "video/*";
        stopCamera();
    } else if (mode === "camera") {
        fileContainer.style.display = "none";
        cameraContainer.style.display = "block";
        startCamera();
    }
}

function startCamera() {
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            cameraStream = stream;
            document.getElementById("camera-stream").srcObject = stream;
        })
        .catch(err => alert("Camera access denied or unavailable: " + err));
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
}

function captureSnapshot() {
    const video = document.getElementById("camera-stream");
    const canvas = document.getElementById("snapshot-canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    canvas.toBlob(blob => {
        window.capturedBlob = new File([blob], "camera_capture.jpg", { type: "image/jpeg" });
        alert("Snapshot captured successfully! Ready for analysis.");
    }, "image/jpeg");
}

function toggleLocationInput(type) {
    const manualGroup = document.getElementById("manual-loc-group");
    if (type === "manual") {
        manualGroup.style.display = "block";
    } else {
        manualGroup.style.display = "none";
    }
}

document.getElementById("detection-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const locType = document.querySelector('input[name="loc_type"]:checked').value;
    let latitude = null;
    let longitude = null;
    let locationName = "Unknown";
    
    if (locType === "gps") {
        locationName = "Current GPS Location";
        // Attempt geolocation API
        if (navigator.geolocation) {
            try {
                const pos = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
                });
                latitude = pos.coords.latitude;
                longitude = pos.coords.longitude;
            } catch (err) {
                console.warn("GPS acquisition failed, proceeding with default coordinates.");
            }
        }
    } else if (locType === "manual") {
        locationName = document.getElementById("manual-location-name").value || "Manual Location";
        const latVal = document.getElementById("manual-lat").value;
        const lonVal = document.getElementById("manual-lon").value;
        if (latVal) latitude = parseFloat(latVal);
        if (lonVal) longitude = parseFloat(lonVal);
    }
    
    const formData = new FormData();
    if (latitude) formData.append("latitude", latitude);
    if (longitude) formData.append("longitude", longitude);
    formData.append("location_name", locationName);
    
    let endpoint = "http://localhost:8000/api/detect/image";
    if (currentMode === "camera") {
        if (!window.capturedBlob) {
            alert("Please capture a snapshot from the camera first!");
            return;
        }
        formData.append("file", window.capturedBlob);
    } else {
        const fileInput = document.getElementById("media-file");
        if (fileInput.files.length === 0) {
            alert("Please select a file to inspect!");
            return;
        }
        formData.append("file", fileInput.files[0]);
        if (currentMode === "video") {
            endpoint = "http://localhost:8000/api/detect/video";
        }
    }
    
    const submitBtn = e.target.querySelector("button[type='submit']");
    submitBtn.innerText = "Analyzing Frame via YOLOv8...";
    submitBtn.disabled = true;
    
    try {
        const response = await fetch(endpoint, {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        
        if (data.success) {
            document.getElementById("result-container").style.display = "block";
            document.getElementById("result-preview").src = `http://localhost:8000${data.result_url}`;
            
            if (currentMode === "video") {
                document.getElementById("res-count").innerText = data.analysis.total_potholes_detected;
                document.getElementById("res-conf").innerText = "80.0";
                document.getElementById("res-severity").innerText = "Processed Video Stream";
            } else {
                document.getElementById("res-count").innerText = data.analysis.pothole_count;
                document.getElementById("res-conf").innerText = data.analysis.confidence;
                document.getElementById("res-severity").innerText = data.analysis.severity;
            }
            document.getElementById("res-location").innerText = locationName;
        } else {
            alert("Detection execution failed.");
        }
    } catch (err) {
        console.error(err);
        alert("Server communication error.");
    } finally {
        submitBtn.innerText = "Analyze Road Condition";
        submitBtn.disabled = false;
    }
});