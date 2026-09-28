# ==========================================================
# backend/services/photogrammetry_service.py
# ROADGUARD AI - PHOTOGRAMMETRY / 3D RECONSTRUCTION SERVICE
# ==========================================================
#
# SERVICE LAYER ONLY - this module exposes plain functions.
# The HTTP endpoints live in backend/routers/photogrammetry.py.
#
# PRIMARY PIPELINE
#
#   Video
#      ↓
#   evenly sampled frames
#      ↓
#   COLMAP SIFT feature extraction
#      ↓
#   COLMAP sequential matching
#      ↓
#   COLMAP Mapper / Structure-from-Motion
#      ↓
#   actual reconstructed 3D points
#      ↓
#   PCA orientation
#      ↓
#   Delaunay surface generation
#      ↓
#   roadguard-road.ply
#      ↓
#   existing Three.js PLYLoader
#
# CPU / NO-CUDA MODE
#
# This RoadGuard implementation intentionally uses COLMAP sparse
# reconstruction only.
#
# It does NOT invoke PatchMatch Stereo / dense MVS because the
# current machine is using the no-CUDA / Intel graphics setup.
#
# COLMAP mode:
#
#   SIFT
#   Sequential Matcher
#   Mapper
#   Model Converter
#   reconstructed sparse 3D points
#   Delaunay surface
#
# IMPORTANT:
#
# When COLMAP is the active engine, the old synthetic rectangular
# road fallback is DISABLED.
#
# If COLMAP cannot produce usable geometry, reconstruction fails
# instead of silently generating the unwanted rectangular road.
#
# Legacy OpenCV mode remains available by explicitly setting:
#
#   ROADGUARD_PHOTOGRAMMETRY_ENGINE=opencv
#
# ==========================================================


import json
import math
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.config import BASE_DIR


# ==========================================================
# DIRECTORIES
# ==========================================================

RESULTS_DIR = BASE_DIR / "results"

PHOTOGRAMMETRY_DIR = RESULTS_DIR / "photogrammetry"

THREE_D_DATA_DIR = RESULTS_DIR / "3d_data"

MESH_FILENAME = "roadguard-road.ply"

POINTCLOUD_FILENAME = "roadguard-points.ply"

METADATA_FILENAME = "roadguard_3d.json"


# ==========================================================
# PHOTOGRAMMETRY ENGINE STATUS
# ==========================================================
#
# COLMAP is now the default engine.
#
# Resolution order:
#
# 1. ROADGUARD_COLMAP_PATH
# 2. colmap available on PATH
# 3. expected Windows no-CUDA installation
#
# Example:
#
#   $env:ROADGUARD_COLMAP_PATH="C:\...\colmap.exe"
#
# Engine selection:
#
#   ROADGUARD_PHOTOGRAMMETRY_ENGINE=colmap
#   ROADGUARD_PHOTOGRAMMETRY_ENGINE=opencv
#
# ==========================================================


def _resolve_colmap_executable() -> Optional[str]:
    """
    Resolve the COLMAP executable.

    Priority:
        1. ROADGUARD_COLMAP_PATH
        2. colmap available on PATH
        3. common RoadGuard Windows no-CUDA installation path
    """

    configured = (
        os.getenv("ROADGUARD_COLMAP_PATH") or ""
    ).strip()

    if configured:

        candidate = Path(configured)

        if candidate.exists() and candidate.is_file():
            return str(candidate)

    path_candidate = shutil.which("colmap")

    if path_candidate:
        return path_candidate

    windows_candidates = [
        Path.home()
        / "Downloads"
        / "colmap-x64-windows-nocuda"
        / "bin"
        / "colmap.exe",

        Path.home()
        / "Downloads"
        / "COLMAP"
        / "bin"
        / "colmap.exe",

        Path("C:/Program Files/COLMAP/bin/colmap.exe"),

        Path("C:/Program Files/COLMAP/colmap.exe"),

        Path("C:/Program Files (x86)/COLMAP/bin/colmap.exe"),

        Path("C:/Program Files (x86)/COLMAP/colmap.exe"),
    ]

    for candidate in windows_candidates:

        if candidate.exists() and candidate.is_file():
            return str(candidate)

    return None


def get_engine_status() -> Dict[str, Any]:
    """
    Return configured and available photogrammetry engine status.
    """

    configured_engine = (
        os.getenv(
            "ROADGUARD_PHOTOGRAMMETRY_ENGINE",
            "colmap",
        )
        or "colmap"
    ).strip().lower()

    if configured_engine not in {"opencv", "colmap"}:
        configured_engine = "colmap"

    colmap_path = _resolve_colmap_executable()

    colmap_available = colmap_path is not None

    if configured_engine == "colmap" and colmap_available:

        active_engine = "colmap"

    elif configured_engine == "opencv":

        active_engine = "opencv"

    else:

        # Keep API operational when COLMAP is not found.
        #
        # IMPORTANT:
        # process_report_photogrammetry() will explicitly reject
        # silent fallback when COLMAP was requested but unavailable.
        active_engine = "opencv"

    return {
        "configured_engine": configured_engine,
        "active_engine": active_engine,
        "opencv_available": True,
        "colmap_available": colmap_available,
        "colmap_path": colmap_path,
        "colmap_requested": configured_engine == "colmap",
        "fallback_to_opencv": (
            configured_engine == "colmap"
            and not colmap_available
        ),
    }


# ==========================================================
# TUNING
# ==========================================================

MAX_SAMPLED_FRAMES = 40

FRAME_WIDTH_FOR_MATCHING = 960

ORB_FEATURE_COUNT = 3000

LOWE_RATIO = 0.75

MIN_PAIR_MATCHES = 25

MAX_CLOUD_POINTS = 40000

# Legacy OpenCV road dimensions.
#
# These are retained only for explicit OpenCV fallback mode.
ROAD_WIDTH_METERS = 12.0

ROAD_LENGTH_METERS = 60.0

GRID_COLUMNS = 48

GRID_ROWS = 132

# frontend/js/roadguard-3d.js rescales every mesh to this size.
VIEWER_TARGET_SIZE = 100.0

BASE_ASPHALT_RGB = (96, 100, 106)

POTHOLE_RGB = {
    "LOW": (34, 197, 94),
    "MODERATE": (245, 158, 11),
    "HIGH": (249, 115, 22),
    "CRITICAL": (239, 68, 68),
}

SEVERITY_LEVELS = (
    "LOW",
    "MODERATE",
    "HIGH",
    "CRITICAL",
)

# COLMAP sparse reconstruction.
COLMAP_MAX_FRAMES = 40

# Minimum sparse points required by the COLMAP display mesh.
COLMAP_MIN_POINTS = 30

# Maximum points used for Delaunay.
MAX_MESH_POINTS = 5000


# ==========================================================
# SMALL HELPERS
# ==========================================================


def safe_float(
    value,
    default: float = 0.0,
) -> float:

    try:

        return float(value)

    except (ValueError, TypeError):

        return default


def clamp_value(
    value: float,
    minimum: float,
    maximum: float,
) -> float:

    return min(
        max(value, minimum),
        maximum,
    )


def normalize_severity(severity) -> str:
    """
    Accept both the API wording and Streamlit demo wording.
    """

    text = str(
        severity or ""
    ).strip().upper()

    if text in SEVERITY_LEVELS:
        return text

    legacy = {
        "MINOR": "LOW",
        "MEDIUM": "MODERATE",
        "SEVERE": "CRITICAL",
        "CRITICAL": "CRITICAL",
    }

    return legacy.get(
        text,
        "LOW",
    )


def rgb_to_hex(
    rgb: Sequence[int],
) -> str:

    return "#{:02x}{:02x}{:02x}".format(
        int(
            clamp_value(
                rgb[0],
                0,
                255,
            )
        ),
        int(
            clamp_value(
                rgb[1],
                0,
                255,
            )
        ),
        int(
            clamp_value(
                rgb[2],
                0,
                255,
            )
        ),
    )


def utc_now_iso() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


# ==========================================================
# WORKSPACE PATHS
# ==========================================================


def get_report_workspace(
    report_id: int,
) -> Path:

    return (
        PHOTOGRAMMETRY_DIR
        / f"report_{report_id}"
    )


def get_frames_dir(
    report_id: int,
) -> Path:

    return (
        get_report_workspace(report_id)
        / "frames"
    )


def get_mesh_path(
    report_id: int,
) -> Path:

    return (
        get_report_workspace(report_id)
        / MESH_FILENAME
    )


def get_pointcloud_path(
    report_id: int,
) -> Path:

    return (
        get_report_workspace(report_id)
        / POINTCLOUD_FILENAME
    )


def get_metadata_path(
    report_id: int,
) -> Path:

    return (
        get_report_workspace(report_id)
        / METADATA_FILENAME
    )


def ensure_workspace(
    report_id: int,
) -> Path:

    for directory in (
        get_report_workspace(report_id),
        get_frames_dir(report_id),
        get_mesh_path(report_id).parent,
    ):

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    return get_report_workspace(report_id)


# ==========================================================
# OPTIONAL OPENCV / NUMPY
#
# Imported lazily on purpose.
# ==========================================================


def _import_cv():

    try:

        import cv2
        import numpy as np

    except ImportError as error:

        raise RuntimeError(
            "OpenCV and NumPy are required for 3D reconstruction. "
            "Install them with: "
            "python -m pip install opencv-python-headless numpy"
        ) from error

    return cv2, np


# ==========================================================
# STEP 1 - FRAME SAMPLING
# ==========================================================


def extract_frames(
    video_path,
    frames_dir,
    max_frames: int = MAX_SAMPLED_FRAMES,
) -> List[Path]:
    """
    Save an evenly spaced set of frames and return their paths.
    """

    cv2, _np = _import_cv()

    frames_dir = Path(frames_dir)

    frames_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Remove old sampled frames so a new reconstruction cannot
    # accidentally reuse stale images.
    for old_frame in frames_dir.glob("*.jpg"):

        try:
            old_frame.unlink()
        except OSError:
            pass

    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():

        raise ValueError(
            f"Could not open video: {video_path}"
        )

    try:

        total_frames = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
            or 0
        )

    except (TypeError, ValueError):

        total_frames = 0

    step = (
        max(
            1,
            total_frames // max_frames,
        )
        if total_frames > 0
        else 5
    )

    saved_paths: List[Path] = []

    index = 0

    guard = 0

    while (
        len(saved_paths) < max_frames
        and guard < (max_frames * 4)
    ):

        guard += 1

        capture.set(
            cv2.CAP_PROP_POS_FRAMES,
            index,
        )

        ok, frame = capture.read()

        if not ok:
            break

        frame_path = (
            frames_dir
            / f"frame_{len(saved_paths):04d}.jpg"
        )

        cv2.imwrite(
            str(frame_path),
            frame,
        )

        saved_paths.append(
            frame_path
        )

        index += step

        if (
            total_frames > 0
            and index >= total_frames
        ):

            break

    capture.release()

    return saved_paths


# ==========================================================
# COLMAP CPU SPARSE RECONSTRUCTION
# ==========================================================


def _run_colmap_command(
    colmap_path: str,
    arguments: Sequence[str],
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """
    Execute one COLMAP command.

    All output is captured and printed to the FastAPI terminal.

    CPU feature extraction and matching are explicitly selected.
    """

    command = [
        str(colmap_path)
    ] + [
        str(value)
        for value in arguments
    ]

    printable_command = " ".join(
        (
            f'"{value}"'
            if " " in value
            else value
        )
        for value in command
    )

    print(
        "\n[RoadGuard COLMAP] Running:\n"
        f"{printable_command}\n"
    )

    process = subprocess.run(
        command,
        cwd=(
            str(cwd)
            if cwd
            else None
        ),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )

    if process.stdout:

        print(
            "[RoadGuard COLMAP STDOUT]\n"
            + process.stdout[-12000:]
        )

    if process.stderr:

        print(
            "[RoadGuard COLMAP STDERR]\n"
            + process.stderr[-12000:]
        )

    if process.returncode != 0:

        raise RuntimeError(
            "COLMAP command failed.\n\n"
            f"Command:\n{printable_command}\n\n"
            f"Exit code: {process.returncode}\n\n"
            f"STDOUT:\n{process.stdout[-6000:]}\n\n"
            f"STDERR:\n{process.stderr[-10000:]}"
        )

    return process


def _prepare_colmap_images(
    frame_paths: Sequence[Path],
    images_dir: Path,
) -> List[Path]:
    """
    Copy RoadGuard sampled frames into the COLMAP image workspace.

    We copy rather than symlink so the pipeline also works on
    Windows installations where symlink permissions may be limited.
    """

    images_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    prepared: List[Path] = []

    for index, source in enumerate(
        frame_paths[:COLMAP_MAX_FRAMES]
    ):

        if not source.exists():
            continue

        destination = (
            images_dir
            / f"frame_{index:04d}.jpg"
        )

        shutil.copy2(
            source,
            destination,
        )

        prepared.append(
            destination
        )

    return prepared


def _find_colmap_sparse_model(
    sparse_dir: Path,
) -> Optional[Path]:
    """
    Find the first COLMAP sparse model generated by Mapper.
    """

    if not sparse_dir.exists():
        return None

    candidates = sorted(
        [
            path
            for path in sparse_dir.iterdir()
            if path.is_dir()
        ],
        key=lambda path: path.name,
    )

    for candidate in candidates:

        required_files = [
            candidate / "cameras.bin",
            candidate / "images.bin",
            candidate / "points3D.bin",
        ]

        if all(
            path.exists()
            for path in required_files
        ):

            return candidate

    return None


def _convert_colmap_model_to_text(
    colmap_path: str,
    sparse_model: Path,
    text_model: Path,
) -> None:
    """
    Convert COLMAP binary model into TXT.

    This allows RoadGuard to read the reconstructed point cloud
    without installing Python COLMAP bindings.
    """

    text_model.mkdir(
        parents=True,
        exist_ok=True,
    )

    _run_colmap_command(
        colmap_path,
        [
            "model_converter",
            "--input_path",
            str(sparse_model),
            "--output_path",
            str(text_model),
            "--output_type",
            "TXT",
        ],
        cwd=sparse_model.parent.parent,
    )


def _read_colmap_points3d(
    points_file: Path,
) -> Tuple[
    List[List[float]],
    List[List[int]],
]:
    """
    Read COLMAP points3D.txt.

    Format:

        POINT3D_ID X Y Z R G B ERROR ...
    """

    points: List[List[float]] = []

    colors: List[List[int]] = []

    if not points_file.exists():

        return points, colors

    with points_file.open(
        "r",
        encoding="utf-8",
        errors="replace",
    ) as file:

        for line in file:

            line = line.strip()

            if (
                not line
                or line.startswith("#")
            ):

                continue

            parts = line.split()

            if len(parts) < 7:
                continue

            try:

                x = float(parts[1])
                y = float(parts[2])
                z = float(parts[3])

                red = int(
                    float(parts[4])
                )

                green = int(
                    float(parts[5])
                )

                blue = int(
                    float(parts[6])
                )

            except (
                ValueError,
                IndexError,
            ):

                continue

            if not all(
                math.isfinite(value)
                for value in (
                    x,
                    y,
                    z,
                )
            ):

                continue

            points.append(
                [
                    round(x, 6),
                    round(y, 6),
                    round(z, 6),
                ]
            )

            colors.append(
                [
                    max(
                        0,
                        min(
                            255,
                            red,
                        ),
                    ),
                    max(
                        0,
                        min(
                            255,
                            green,
                        ),
                    ),
                    max(
                        0,
                        min(
                            255,
                            blue,
                        ),
                    ),
                ]
            )

    return points, colors


def _read_colmap_camera_centers(
    images_file: Path,
) -> List[List[float]]:
    """
    Read COLMAP camera poses from images.txt.

    COLMAP stores:

        IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME

    Camera center:

        C = -R^T t
    """

    try:

        import numpy as np

    except ImportError:

        return []

    centers: List[List[float]] = []

    if not images_file.exists():

        return centers

    with images_file.open(
        "r",
        encoding="utf-8",
        errors="replace",
    ) as file:

        lines = file.readlines()

    index = 0

    while index < len(lines):

        line = lines[index].strip()

        index += 1

        if (
            not line
            or line.startswith("#")
        ):

            continue

        parts = line.split()

        if len(parts) < 10:
            continue

        try:

            qw = float(parts[1])
            qx = float(parts[2])
            qy = float(parts[3])
            qz = float(parts[4])

            tx = float(parts[5])
            ty = float(parts[6])
            tz = float(parts[7])

        except (
            ValueError,
            IndexError,
        ):

            continue

        quaternion = np.array(
            [
                qw,
                qx,
                qy,
                qz,
            ],
            dtype=np.float64,
        )

        norm = float(
            np.linalg.norm(
                quaternion
            )
        )

        if norm <= 1e-12:
            continue

        qw, qx, qy, qz = (
            quaternion / norm
        )

        rotation = np.array(
            [
                [
                    1
                    - 2
                    * (
                        qy * qy
                        + qz * qz
                    ),
                    2
                    * (
                        qx * qy
                        - qz * qw
                    ),
                    2
                    * (
                        qx * qz
                        + qy * qw
                    ),
                ],
                [
                    2
                    * (
                        qx * qy
                        + qz * qw
                    ),
                    1
                    - 2
                    * (
                        qx * qx
                        + qz * qz
                    ),
                    2
                    * (
                        qy * qz
                        - qx * qw
                    ),
                ],
                [
                    2
                    * (
                        qx * qz
                        - qy * qw
                    ),
                    2
                    * (
                        qy * qz
                        + qx * qw
                    ),
                    1
                    - 2
                    * (
                        qx * qx
                        + qy * qy
                    ),
                ],
            ],
            dtype=np.float64,
        )

        translation = np.array(
            [
                [tx],
                [ty],
                [tz],
            ],
            dtype=np.float64,
        )

        center = (
            -rotation.T
            @ translation
        )

        centers.append(
            [
                round(
                    float(
                        center[0, 0]
                    ),
                    6,
                ),
                round(
                    float(
                        center[1, 0]
                    ),
                    6,
                ),
                round(
                    float(
                        center[2, 0]
                    ),
                    6,
                ),
            ]
        )

        # images.txt contains one POINTS2D line immediately after
        # each image header.
        if index < len(lines):

            index += 1

    return centers


def run_colmap_sparse_reconstruction(
    report_id: int,
    frame_paths: Sequence[Path],
) -> Dict[str, Any]:
    """
    Run CPU-compatible COLMAP sparse Structure-from-Motion.

    Pipeline:

        RoadGuard frames
            ↓
        SIFT feature extraction
            ↓
        sequential matching
            ↓
        COLMAP Mapper
            ↓
        sparse 3D reconstruction
            ↓
        model conversion
            ↓
        RoadGuard 3D point cloud
    """

    colmap_path = _resolve_colmap_executable()

    if not colmap_path:

        raise RuntimeError(
            "COLMAP executable was not found.\n"
            "Set ROADGUARD_COLMAP_PATH to the full path of "
            "colmap.exe."
        )

    workspace = (
        get_report_workspace(report_id)
        / "colmap"
    )

    images_dir = (
        workspace
        / "images"
    )

    database_path = (
        workspace
        / "database.db"
    )

    sparse_dir = (
        workspace
        / "sparse"
    )

    text_model = (
        workspace
        / "sparse_txt"
    )

    workspace.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------
    # Clean this report's COLMAP workspace.
    # ------------------------------------------------------

    if images_dir.exists():

        shutil.rmtree(
            images_dir
        )

    if database_path.exists():

        database_path.unlink()

    if sparse_dir.exists():

        shutil.rmtree(
            sparse_dir
        )

    if text_model.exists():

        shutil.rmtree(
            text_model
        )

    images_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------
    # Prepare images.
    # ------------------------------------------------------

    prepared_images = (
        _prepare_colmap_images(
            frame_paths,
            images_dir,
        )
    )

    if len(prepared_images) < 3:

        raise RuntimeError(
            "COLMAP requires at least 3 usable video frames."
        )

    print(
        "[RoadGuard COLMAP] "
        f"Prepared {len(prepared_images)} images."
    )

    # ------------------------------------------------------
    # 1. SIFT FEATURE EXTRACTION
    # ------------------------------------------------------

    _run_colmap_command(
        colmap_path,
        [
            "feature_extractor",
            "--database_path",
            str(database_path),
            "--image_path",
            str(images_dir),
            "--ImageReader.camera_model",
            "SIMPLE_RADIAL",
            "--ImageReader.single_camera",
            "1",
            "--FeatureExtraction.use_gpu",
            "0",
            "--FeatureExtraction.num_threads",
            "-1",
        ],
        cwd=workspace,
    )

    # ------------------------------------------------------
    # 2. SEQUENTIAL MATCHING
    #
    # Video frames naturally have temporal overlap.
    # ------------------------------------------------------

    _run_colmap_command(
        colmap_path,
        [
            "sequential_matcher",
            "--database_path",
            str(database_path),
            "--SequentialMatching.overlap",
            "10",
            "--SequentialMatching.quadratic_overlap",
            "1",
            "--FeatureMatching.use_gpu",
            "0",
            "--FeatureMatching.num_threads",
            "-1",
            "--SiftMatching.cross_check",
            "1",
        ],
        cwd=workspace,
    )

    # ------------------------------------------------------
    # 3. STRUCTURE FROM MOTION / MAPPER
    # ------------------------------------------------------

    sparse_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    _run_colmap_command(
        colmap_path,
        [
            "mapper",
            "--database_path",
            str(database_path),
            "--image_path",
            str(images_dir),
            "--output_path",
            str(sparse_dir),
            "--Mapper.num_threads",
            "-1",
        ],
        cwd=workspace,
    )

    sparse_model = (
        _find_colmap_sparse_model(
            sparse_dir
        )
    )

    if sparse_model is None:

        raise RuntimeError(
            "COLMAP Mapper did not produce a sparse model.\n"
            "The video may not have enough camera movement, "
            "texture, overlap, or stable visual features."
        )

    print(
        "[RoadGuard COLMAP] "
        f"Sparse model found: {sparse_model}"
    )

    # ------------------------------------------------------
    # 4. BINARY MODEL → TEXT
    # ------------------------------------------------------

    _convert_colmap_model_to_text(
        colmap_path,
        sparse_model,
        text_model,
    )

    points, colors = (
        _read_colmap_points3d(
            text_model
            / "points3D.txt"
        )
    )

    camera_centers = (
        _read_colmap_camera_centers(
            text_model
            / "images.txt"
        )
    )

    if len(points) < COLMAP_MIN_POINTS:

        raise RuntimeError(
            "COLMAP reconstructed too few 3D points.\n"
            f"Reconstructed points: {len(points)}\n"
            f"Minimum required: {COLMAP_MIN_POINTS}\n\n"
            "Try a video with stronger camera movement and "
            "more visible road texture."
        )

    print(
        "[RoadGuard COLMAP] "
        f"Reconstructed {len(points)} 3D points "
        f"from {len(camera_centers)} registered cameras."
    )

    return {
        "points": points,
        "colors": colors,
        "camera_centers": camera_centers,
        "method": "colmap_sift_sequential_sfm",
        "workspace": str(workspace),
        "sparse_model": str(sparse_model),
        "colmap_path": str(colmap_path),
        "images_registered": len(camera_centers),
        "images_prepared": len(prepared_images),
    }


# ==========================================================
# STEP 2a - LEGACY ORB FEATURE DETECTION
#
# Used only when ROADGUARD_PHOTOGRAMMETRY_ENGINE=opencv.
# ==========================================================


def detect_features(
    frame_paths: Sequence[Path],
) -> List[Dict[str, Any]]:
    """
    Return one feature record per usable frame.

    Legacy OpenCV path.
    """

    cv2, _np = _import_cv()

    orb = cv2.ORB_create(
        nfeatures=ORB_FEATURE_COUNT
    )

    features: List[
        Dict[str, Any]
    ] = []

    for frame_path in frame_paths:

        color = cv2.imread(
            str(frame_path),
            cv2.IMREAD_COLOR,
        )

        if color is None:
            continue

        height, width = (
            color.shape[:2]
        )

        if width > FRAME_WIDTH_FOR_MATCHING:

            scale = (
                FRAME_WIDTH_FOR_MATCHING
                / float(width)
            )

            color = cv2.resize(
                color,
                (
                    FRAME_WIDTH_FOR_MATCHING,
                    int(
                        round(
                            height * scale
                        )
                    ),
                ),
                interpolation=cv2.INTER_AREA,
            )

        gray = cv2.cvtColor(
            color,
            cv2.COLOR_BGR2GRAY,
        )

        keypoints, descriptors = (
            orb.detectAndCompute(
                gray,
                None,
            )
        )

        if (
            descriptors is None
            or len(keypoints)
            < MIN_PAIR_MATCHES
        ):

            continue

        features.append(
            {
                "keypoints": keypoints,
                "descriptors": descriptors,
                "color": color,
                "width": color.shape[1],
                "height": color.shape[0],
            }
        )

    return features


def _sample_color(
    color_image,
    pixel,
    width: int,
    height: int,
):

    x = int(
        clamp_value(
            float(pixel[0]),
            0,
            width - 1,
        )
    )

    y = int(
        clamp_value(
            float(pixel[1]),
            0,
            height - 1,
        )
    )

    blue, green, red = (
        color_image[y, x]
    )

    return (
        int(blue),
        int(green),
        int(red),
    )


# ==========================================================
# STEP 2b - LEGACY SPARSE STRUCTURE FROM MOTION
# ==========================================================


def sparse_reconstruction(
    features: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Legacy incremental two-view SfM.

    This is used only when the explicit OpenCV engine is selected.
    """

    cv2, np = _import_cv()

    if len(features) < 2:

        return {
            "points": [],
            "colors": [],
            "camera_centers": [],
            "method": "insufficient_frames",
        }

    matcher = cv2.BFMatcher(
        cv2.NORM_HAMMING,
        crossCheck=False,
    )

    reference = features[0]

    focal = (
        0.85
        * float(reference["width"])
    )

    camera_matrix = np.array(
        [
            [
                focal,
                0.0,
                reference["width"] / 2.0,
            ],
            [
                0.0,
                focal,
                reference["height"] / 2.0,
            ],
            [
                0.0,
                0.0,
                1.0,
            ],
        ],
        dtype=np.float64,
    )

    rotation_world = np.eye(
        3,
        dtype=np.float64,
    )

    translation_world = np.zeros(
        (3, 1),
        dtype=np.float64,
    )

    camera_centers: List[
        List[float]
    ] = [
        (
            -rotation_world.T
            @ translation_world
        ).ravel().tolist()
    ]

    world_points: List[
        List[float]
    ] = []

    world_colors: List[
        List[int]
    ] = []

    for index in range(
        len(features) - 1
    ):

        if (
            len(world_points)
            >= MAX_CLOUD_POINTS
        ):

            break

        frame_a = features[index]

        frame_b = features[
            index + 1
        ]

        matches = matcher.knnMatch(
            frame_a["descriptors"],
            frame_b["descriptors"],
            k=2,
        )

        good_matches = []

        for pair in matches:

            if len(pair) < 2:
                continue

            best, second = pair

            if (
                best.distance
                < LOWE_RATIO
                * second.distance
            ):

                good_matches.append(
                    best
                )

        if (
            len(good_matches)
            < MIN_PAIR_MATCHES
        ):

            continue

        points_a = np.float32(
            [
                frame_a[
                    "keypoints"
                ][
                    m.queryIdx
                ].pt
                for m in good_matches
            ]
        )

        points_b = np.float32(
            [
                frame_b[
                    "keypoints"
                ][
                    m.trainIdx
                ].pt
                for m in good_matches
            ]
        )

        essential, inlier_mask = (
            cv2.findEssentialMat(
                points_a,
                points_b,
                camera_matrix,
                method=cv2.RANSAC,
                prob=0.999,
                threshold=1.0,
            )
        )

        if essential is None:
            continue

        essential = np.asarray(
            essential,
            dtype=np.float64,
        ).reshape(
            3,
            3,
        )

        inlier_count = (
            int(
                inlier_mask.sum()
            )
            if inlier_mask is not None
            else len(good_matches)
        )

        if (
            inlier_count
            < MIN_PAIR_MATCHES
        ):

            continue

        (
            _retval,
            rotation_rel,
            translation_rel,
            _mask,
        ) = cv2.recoverPose(
            essential,
            points_a,
            points_b,
            camera_matrix,
        )

        projection_a = (
            camera_matrix
            @ np.hstack(
                (
                    np.eye(
                        3
                    ),
                    np.zeros(
                        (
                            3,
                            1,
                        )
                    ),
                )
            )
        )

        projection_b = (
            camera_matrix
            @ np.hstack(
                (
                    rotation_rel,
                    translation_rel,
                )
            )
        )

        homogeneous = (
            cv2.triangulatePoints(
                projection_a,
                projection_b,
                points_a.T,
                points_b.T,
            )
        )

        if (
            homogeneous.shape[1]
            == 0
        ):

            continue

        depths = (
            homogeneous[3]
        )

        valid = (
            np.abs(depths)
            > 1e-8
        )

        if not bool(
            np.any(valid)
        ):

            continue

        local_points = (
            homogeneous[:3, valid]
            / depths[valid]
        ).T

        in_front = (
            (
                local_points[:, 2]
                > 0.0
            )
            & np.isfinite(
                local_points
            ).all(axis=1)
            & (
                np.abs(
                    local_points
                )
                < 1e6
            ).all(axis=1)
        )

        local_points = (
            local_points[in_front]
        )

        if (
            local_points.shape[0]
            == 0
        ):

            continue

        transformed = (
            rotation_world
            @ local_points.T
        ).T + translation_world.ravel()

        keep = int(
            min(
                transformed.shape[0],
                MAX_CLOUD_POINTS
                - len(world_points),
            )
        )

        if keep <= 0:
            break

        transformed = (
            transformed[:keep]
        )

        source_pixels = (
            points_a[valid]
            [in_front]
            [:keep]
        )

        for point, pixel in zip(
            transformed,
            source_pixels,
        ):

            world_points.append(
                [
                    round(
                        float(point[0]),
                        5,
                    ),
                    round(
                        float(point[1]),
                        5,
                    ),
                    round(
                        float(point[2]),
                        5,
                    ),
                ]
            )

            blue, green, red = (
                _sample_color(
                    frame_a["color"],
                    pixel,
                    frame_a["width"],
                    frame_a["height"],
                )
            )

            world_colors.append(
                [
                    int(red),
                    int(green),
                    int(blue),
                ]
            )

        rotation_world = (
            rotation_world
            @ rotation_rel.T
        )

        translation_world = (
            translation_world
            - rotation_world
            @ translation_rel
        )

        camera_centers.append(
            (
                -rotation_world.T
                @ translation_world
            ).ravel().tolist()
        )

    method = (
        "opencv_sparse_sfm"
        if len(world_points) >= 1
        else "opencv_sparse_sfm_low_yield"
    )

    return {
        "points": world_points,
        "colors": world_colors,
        "camera_centers": camera_centers,
        "method": method,
    }


# ==========================================================
# STEP 3 - ASCII PLY WRITER
# ==========================================================


def write_ply(
    output_path,
    vertices: Sequence[
        Sequence[float]
    ],
    colors: Optional[
        Sequence[Sequence[int]]
    ] = None,
    faces: Optional[
        Sequence[Sequence[int]]
    ] = None,
    comments: Optional[
        Sequence[str]
    ] = None,
) -> Path:
    """
    Write an ASCII PLY file.

    A face list makes the result renderable as a THREE.Mesh.
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    vertex_list = list(
        vertices or []
    )

    face_list = list(
        faces or []
    )

    color_list = list(
        colors or []
    )

    has_colors = (
        bool(color_list)
        and len(color_list)
        == len(vertex_list)
    )

    lines = [
        "ply",
        "format ascii 1.0",
    ]

    for comment in (
        comments or []
    ):

        lines.append(
            f"comment {comment}"
        )

    lines.append(
        f"element vertex {len(vertex_list)}"
    )

    lines.append(
        "property float x"
    )

    lines.append(
        "property float y"
    )

    lines.append(
        "property float z"
    )

    if has_colors:

        lines.append(
            "property uchar red"
        )

        lines.append(
            "property uchar green"
        )

        lines.append(
            "property uchar blue"
        )

    if face_list:

        lines.append(
            f"element face {len(face_list)}"
        )

        lines.append(
            "property list uchar int vertex_indices"
        )

    lines.append(
        "end_header"
    )

    for index, vertex in enumerate(
        vertex_list
    ):

        parts = [
            f"{safe_float(vertex[0]):.5f}",
            f"{safe_float(vertex[1]):.5f}",
            f"{safe_float(vertex[2]):.5f}",
        ]

        if has_colors:

            red, green, blue = (
                color_list[index]
            )

            parts.append(
                str(
                    int(
                        clamp_value(
                            red,
                            0,
                            255,
                        )
                    )
                )
            )

            parts.append(
                str(
                    int(
                        clamp_value(
                            green,
                            0,
                            255,
                        )
                    )
                )
            )

            parts.append(
                str(
                    int(
                        clamp_value(
                            blue,
                            0,
                            255,
                        )
                    )
                )
            )

        lines.append(
            " ".join(parts)
        )

    for face in face_list:

        lines.append(
            "3 {} {} {}".format(
                int(face[0]),
                int(face[1]),
                int(face[2]),
            )
        )

    output_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return output_path


# ==========================================================
# STEP 4a - DETECTION NORMALISATION
# ==========================================================


def _detection_geometry(
    detection: Dict[str, Any],
    frame_width,
    frame_height,
    default_severity: str = "LOW",
):
    """
    Normalise one detection entry.
    """

    display_width = (
        safe_float(frame_width)
        or 1920.0
    )

    display_height = (
        safe_float(frame_height)
        or 1080.0
    )

    center = detection.get(
        "center"
    )

    if not isinstance(
        center,
        dict,
    ):

        center = {}

    bbox = detection.get(
        "bbox"
    )

    if not isinstance(
        bbox,
        dict,
    ):

        bbox = {}

    normalized = detection.get(
        "normalized"
    )

    if not isinstance(
        normalized,
        dict,
    ):

        normalized = {}

    center_x = safe_float(
        center.get(
            "x",
            detection.get(
                "center_x"
            ),
        )
    )

    center_y = safe_float(
        center.get(
            "y",
            detection.get(
                "center_y"
            ),
        )
    )

    box_width = safe_float(
        detection.get(
            "width"
        )
    )

    if box_width <= 0.0:

        box_width = max(
            0.0,
            safe_float(
                bbox.get(
                    "x2"
                )
            )
            - safe_float(
                bbox.get(
                    "x1"
                )
            ),
        )

    box_height = safe_float(
        detection.get(
            "height"
        )
    )

    if box_height <= 0.0:

        box_height = max(
            0.0,
            safe_float(
                bbox.get(
                    "y2"
                )
            )
            - safe_float(
                bbox.get(
                    "y1"
                )
            ),
        )

    area_ratio = safe_float(
        detection.get(
            "area_ratio"
        )
    )

    if area_ratio <= 0.0:

        area_ratio = (
            box_width
            * box_height
        ) / max(
            display_width
            * display_height,
            1.0,
        )

    normalized_x = (
        normalized.get(
            "x"
        )
    )

    if normalized_x is None:

        normalized_x = (
            center_x
            / max(
                display_width,
                1.0,
            )
        )

    normalized_y = (
        normalized.get(
            "y"
        )
    )

    if normalized_y is None:

        normalized_y = (
            center_y
            / max(
                display_height,
                1.0,
            )
        )

    return {
        "center_x": center_x,
        "center_y": center_y,
        "width": box_width,
        "height": box_height,
        "area_ratio": area_ratio,
        "normalized_x": clamp_value(
            safe_float(
                normalized_x
            ),
            0.0,
            1.0,
        ),
        "normalized_y": clamp_value(
            safe_float(
                normalized_y
            ),
            0.0,
            1.0,
        ),
        "display_width": display_width,
        "display_height": display_height,
        "confidence": safe_float(
            detection.get(
                "confidence"
            )
        ),
        "severity": normalize_severity(
            detection.get(
                "severity"
            )
            or default_severity
        ),
        "location_name": (
            detection.get(
                "location_name"
            )
            or "Unknown Location"
        ),
    }


# ==========================================================
# STEP 4b - DETECTION COLLAPSE
# ==========================================================


def _collapse_detections(
    detections: Sequence[Any],
) -> List[Dict[str, Any]]:
    """
    Reduce raw per-frame detections to one entry per physical
    pothole when track_id / id is available.
    """

    keyed: Dict[
        Any,
        Dict[str, Any]
    ] = {}

    anonymous: List[
        Dict[str, Any]
    ] = []

    for detection in (
        detections or []
    ):

        if not isinstance(
            detection,
            dict,
        ):

            continue

        key = detection.get(
            "track_id"
        )

        if key is None:

            key = detection.get(
                "id"
            )

        if key is None:

            anonymous.append(
                detection
            )

            continue

        previous = keyed.get(
            key
        )

        if previous is None:

            keyed[key] = detection

            continue

        if (
            safe_float(
                detection.get(
                    "area_ratio"
                )
            )
            >
            safe_float(
                previous.get(
                    "area_ratio"
                )
            )
        ):

            keyed[key] = detection

    ordered = list(
        keyed.values()
    )

    ordered.extend(
        anonymous
    )

    return ordered


# ==========================================================
# STEP 4c - LEGACY SYNTHETIC ROAD SURFACE
#
# IMPORTANT:
# This is retained only for explicit OpenCV mode.
#
# COLMAP mode never silently falls back here.
# ==========================================================


def build_road_surface(
    detections: Sequence[Any],
    frame_width: int = 0,
    frame_height: int = 0,
    default_severity: str = "LOW",
) -> Dict[str, Any]:
    """
    Legacy synthetic triangulated road heightfield.

    Used only when explicit OpenCV mode is selected and the
    reconstructed sparse cloud cannot produce a display surface.
    """

    specs = [
        _detection_geometry(
            detection,
            frame_width,
            frame_height,
            default_severity,
        )
        for detection in
        _collapse_detections(
            detections
        )
    ]

    columns = GRID_COLUMNS

    rows = GRID_ROWS

    road_width = ROAD_WIDTH_METERS

    road_length = ROAD_LENGTH_METERS

    potholes: List[
        Dict[str, Any]
    ] = []

    for index, spec in enumerate(
        specs
    ):

        radius = clamp_value(
            (
                spec["width"]
                / max(
                    spec[
                        "display_width"
                    ],
                    1.0,
                )
            )
            * road_width
            * 1.5,
            0.40,
            3.50,
        )

        depth = clamp_value(
            (
                spec["area_ratio"]
                ** 0.5
            )
            * 2.0,
            0.05,
            0.60,
        )

        center_x = (
            spec[
                "normalized_x"
            ]
            - 0.5
        ) * road_width

        center_z = (
            -(
                1.0
                - spec[
                    "normalized_y"
                ]
            )
            * road_length
        )

        potholes.append(
            {
                "id": index + 1,
                "label":
                    f"Pothole #{index + 1}",
                "severity":
                    spec["severity"],
                "confidence":
                    round(
                        clamp_value(
                            spec[
                                "confidence"
                            ],
                            0.0,
                            1.0,
                        ),
                        4,
                    ),
                "radius_m":
                    round(
                        radius,
                        3,
                    ),
                "depth_m":
                    round(
                        depth,
                        3,
                    ),
                "area_ratio":
                    round(
                        spec[
                            "area_ratio"
                        ],
                        6,
                    ),
                "location_name":
                    spec[
                        "location_name"
                    ],
                "mesh_position":
                    [
                        round(
                            center_x,
                            3,
                        ),
                        0.0,
                        round(
                            center_z,
                            3,
                        ),
                    ],
            }
        )

    vertices: List[
        Tuple[
            float,
            float,
            float,
        ]
    ] = []

    colors: List[
        Tuple[
            int,
            int,
            int,
        ]
    ] = []

    faces: List[
        Tuple[
            int,
            int,
            int,
        ]
    ] = []

    step_x = (
        road_width
        / columns
    )

    step_z = (
        road_length
        / rows
    )

    deepest = max(
        [
            pothole[
                "depth_m"
            ]
            for pothole
            in potholes
        ],
        default=0.0,
    )

    if deepest <= 0.0:

        deepest = 1.0

    for row in range(
        rows + 1
    ):

        z_value = (
            -row
            * step_z
        )

        for column in range(
            columns + 1
        ):

            x_value = (
                -road_width
                / 2.0
            ) + (
                column
                * step_x
            )

            depression = 0.0

            tint_rgb = (
                BASE_ASPHALT_RGB
            )

            tint_strength = 0.0

            for pothole in potholes:

                delta_x = (
                    x_value
                    - pothole[
                        "mesh_position"
                    ][0]
                )

                delta_z = (
                    z_value
                    - pothole[
                        "mesh_position"
                    ][2]
                )

                distance = (
                    (
                        delta_x ** 2
                    )
                    + (
                        delta_z ** 2
                    )
                ) ** 0.5

                if (
                    distance
                    >
                    (
                        pothole[
                            "radius_m"
                        ]
                        * 2.5
                    )
                ):

                    continue

                falloff = (
                    distance
                    / max(
                        pothole[
                            "radius_m"
                        ],
                        1e-6,
                    )
                )

                depth_here = (
                    pothole[
                        "depth_m"
                    ]
                    * math.exp(
                        -(falloff ** 2)
                    )
                )

                if (
                    depth_here
                    > depression
                ):

                    depression = (
                        depth_here
                    )

                    tint_rgb = (
                        POTHOLE_RGB[
                            pothole[
                                "severity"
                            ]
                        ]
                    )

                    tint_strength = (
                        clamp_value(
                            depth_here
                            / deepest,
                            0.0,
                            1.0,
                        )
                    )

            vertices.append(
                (
                    round(
                        x_value,
                        4,
                    ),
                    round(
                        -depression,
                        4,
                    ),
                    round(
                        z_value,
                        4,
                    ),
                )
            )

            blend = (
                0.55
                * tint_strength
            )

            red = (
                BASE_ASPHALT_RGB[0]
                * (1.0 - blend)
            ) + (
                tint_rgb[0]
                * blend
            )

            green = (
                BASE_ASPHALT_RGB[1]
                * (1.0 - blend)
            ) + (
                tint_rgb[1]
                * blend
            )

            blue = (
                BASE_ASPHALT_RGB[2]
                * (1.0 - blend)
            ) + (
                tint_rgb[2]
                * blend
            )

            shade = (
                1.0
                - (
                    depression
                    / deepest
                )
                * 0.35
            )

            colors.append(
                (
                    int(
                        clamp_value(
                            red * shade,
                            0,
                            255,
                        )
                    ),
                    int(
                        clamp_value(
                            green * shade,
                            0,
                            255,
                        )
                    ),
                    int(
                        clamp_value(
                            blue * shade,
                            0,
                            255,
                        )
                    ),
                )
            )

    stride = (
        columns + 1
    )

    for row in range(
        rows
    ):

        for column in range(
            columns
        ):

            top_left = (
                row
                * stride
                + column
            )

            top_right = (
                top_left + 1
            )

            bottom_left = (
                top_left
                + stride
            )

            bottom_right = (
                bottom_left + 1
            )

            faces.append(
                (
                    top_left,
                    bottom_left,
                    top_right,
                )
            )

            faces.append(
                (
                    top_right,
                    bottom_left,
                    bottom_right,
                )
            )

    x_values = [
        vertex[0]
        for vertex in vertices
    ]

    y_values = [
        vertex[1]
        for vertex in vertices
    ]

    z_values = [
        vertex[2]
        for vertex in vertices
    ]

    minimum = (
        min(x_values),
        min(y_values),
        min(z_values),
    )

    maximum = (
        max(x_values),
        max(y_values),
        max(z_values),
    )

    center = tuple(
        (
            minimum[i]
            + maximum[i]
        ) / 2.0
        for i in range(3)
    )

    dimensions = tuple(
        maximum[i]
        - minimum[i]
        for i in range(3)
    )

    max_dimension = max(
        dimensions
    )

    if max_dimension <= 0.0:

        max_dimension = 1.0

    scale = (
        VIEWER_TARGET_SIZE
        / max_dimension
    )

    for pothole in potholes:

        pothole[
            "position_mesh"
        ] = list(
            pothole[
                "mesh_position"
            ]
        )

        pothole[
            "position_3d"
        ] = [
            round(
                (
                    pothole[
                        "mesh_position"
                    ][i]
                    - center[i]
                )
                * scale,
                4,
            )
            for i in range(3)
        ]

        pothole[
            "color"
        ] = rgb_to_hex(
            POTHOLE_RGB[
                pothole[
                    "severity"
                ]
            ]
        )

    return {
        "vertices": vertices,
        "colors": colors,
        "faces": faces,
        "potholes": potholes,
        "stats": {
            "grid_columns":
                columns,
            "grid_rows":
                rows,
            "vertex_count":
                len(vertices),
            "face_count":
                len(faces),
            "road_width_m":
                road_width,
            "road_length_m":
                road_length,
            "center": [
                round(
                    value,
                    4,
                )
                for value
                in center
            ],
            "max_dimension":
                round(
                    max_dimension,
                    4,
                ),
            "viewer_scale":
                round(
                    scale,
                    6,
                ),
            "viewer_target_size":
                VIEWER_TARGET_SIZE,
        },
    }


# ==========================================================
# STEP 4d - RECONSTRUCTION-DERIVED ROAD MESH
# ==========================================================


def build_reconstructed_road_surface(
    reconstruction: Dict[str, Any],
    detections: Sequence[Any],
    frame_width: int = 0,
    frame_height: int = 0,
    default_severity: str = "LOW",
) -> Optional[Dict[str, Any]]:
    """
    Build the display mesh directly from reconstructed 3D points.

    For COLMAP:
        actual COLMAP sparse points
        ↓
        PCA orientation
        ↓
        2D Delaunay triangulation
        ↓
        triangular PLY mesh

    IMPORTANT:

    No rectangular road dimensions are invented here.

    The geometry comes from the actual reconstructed point cloud.
    """

    points = (
        reconstruction.get(
            "points"
        )
        or []
    )

    colors = (
        reconstruction.get(
            "colors"
        )
        or []
    )

    if len(points) < 30:

        return None

    try:

        _cv2, np = _import_cv()

    except Exception:

        return None

    try:

        point_array = np.asarray(
            points,
            dtype=np.float64,
        )

        if (
            point_array.ndim != 2
            or point_array.shape[1]
            != 3
        ):

            return None

        finite_mask = (
            np.isfinite(
                point_array
            ).all(axis=1)
        )

        point_array = (
            point_array[
                finite_mask
            ]
        )

        if len(point_array) < 30:

            return None

        color_array = np.asarray(
            colors,
            dtype=np.float64,
        )

        if (
            color_array.ndim != 2
            or color_array.shape[1]
            != 3
            or len(color_array)
            != len(points)
        ):

            color_array = np.tile(
                np.asarray(
                    BASE_ASPHALT_RGB,
                    dtype=np.float64,
                ),
                (
                    len(points),
                    1,
                ),
            )

        color_array = (
            color_array[
                finite_mask
            ]
        )

        # --------------------------------------------------
        # Remove extreme outliers.
        # --------------------------------------------------

        lower = np.percentile(
            point_array,
            1.5,
            axis=0,
        )

        upper = np.percentile(
            point_array,
            98.5,
            axis=0,
        )

        keep_mask = np.all(
            (
                point_array
                >= lower
            )
            & (
                point_array
                <= upper
            ),
            axis=1,
        )

        point_array = (
            point_array[
                keep_mask
            ]
        )

        color_array = (
            color_array[
                keep_mask
            ]
        )

        if len(point_array) < 30:

            return None

        # --------------------------------------------------
        # Bound Delaunay complexity.
        # --------------------------------------------------

        if (
            len(point_array)
            > MAX_MESH_POINTS
        ):

            sample_indices = (
                np.linspace(
                    0,
                    len(point_array)
                    - 1,
                    MAX_MESH_POINTS,
                    dtype=np.int64,
                )
            )

            point_array = (
                point_array[
                    sample_indices
                ]
            )

            color_array = (
                color_array[
                    sample_indices
                ]
            )

        # --------------------------------------------------
        # PCA
        #
        # The COLMAP coordinate system is arbitrary.
        # PCA gives us a stable local orientation.
        # --------------------------------------------------

        center = (
            point_array.mean(
                axis=0
            )
        )

        centered = (
            point_array
            - center
        )

        _u, singular_values, vt = (
            np.linalg.svd(
                centered,
                full_matrices=False,
            )
        )

        if (
            len(singular_values)
            < 3
        ):

            return None

        transformed = (
            centered
            @ vt.T
        )

        ranges = np.ptp(
            transformed,
            axis=0,
        )

        order = np.argsort(
            ranges
        )[::-1]

        horizontal_a = int(
            order[0]
        )

        horizontal_b = int(
            order[1]
        )

        height_axis = int(
            order[2]
        )

        x_values = (
            transformed[
                :,
                horizontal_a,
            ]
        )

        z_values = (
            transformed[
                :,
                horizontal_b,
            ]
        )

        y_values = (
            transformed[
                :,
                height_axis,
            ]
        )

        x_range = float(
            np.ptp(
                x_values
            )
        )

        z_range = float(
            np.ptp(
                z_values
            )
        )

        y_range = float(
            np.ptp(
                y_values
            )
        )

        # --------------------------------------------------
        # A usable road requires area in two dimensions.
        # --------------------------------------------------

        if (
            x_range
            <= 1e-6
            or z_range
            <= 1e-6
        ):

            return None

        if (
            x_range
            * z_range
            <= 1e-5
        ):

            return None

        # --------------------------------------------------
        # Orient the longer horizontal axis as road length.
        # --------------------------------------------------

        if x_range > z_range:

            mesh_x = x_values

            mesh_z = z_values

        else:

            mesh_x = z_values

            mesh_z = x_values

        mesh_x = (
            mesh_x.astype(
                np.float64
            )
        )

        mesh_z = (
            -mesh_z.astype(
                np.float64
            )
        )

        mesh_y = (
            y_values.astype(
                np.float64
            )
        )

        if y_range <= 1e-8:

            return None

        # --------------------------------------------------
        # Delaunay triangulation
        # --------------------------------------------------

        projected = np.column_stack(
            (
                mesh_x,
                mesh_z,
            )
        )

        min_x = float(
            np.min(mesh_x)
        )

        max_x = float(
            np.max(mesh_x)
        )

        min_z = float(
            np.min(mesh_z)
        )

        max_z = float(
            np.max(mesh_z)
        )

        if (
            max_x - min_x
            <= 1e-6
            or
            max_z - min_z
            <= 1e-6
        ):

            return None

        faces: List[
            Tuple[
                int,
                int,
                int,
            ]
        ] = []

        # --------------------------------------------------
        # Prefer SciPy.
        # --------------------------------------------------

        try:

            from scipy.spatial import Delaunay

            triangulation = (
                Delaunay(
                    projected
                )
            )

            simplices = (
                triangulation.simplices
            )

            for simplex in simplices:

                a, b, c = [
                    int(value)
                    for value
                    in simplex
                ]

                pa = projected[a]
                pb = projected[b]
                pc = projected[c]

                edge_ab = float(
                    np.linalg.norm(
                        pa - pb
                    )
                )

                edge_bc = float(
                    np.linalg.norm(
                        pb - pc
                    )
                )

                edge_ca = float(
                    np.linalg.norm(
                        pc - pa
                    )
                )

                if (
                    max(
                        edge_ab,
                        edge_bc,
                        edge_ca,
                    )
                    <= 0.0
                ):

                    continue

                faces.append(
                    (
                        a,
                        b,
                        c,
                    )
                )

        except Exception:

            # --------------------------------------------------
            # OpenCV fallback if SciPy is unavailable.
            # --------------------------------------------------

            try:

                canvas_size = 100000.0

                sx = (
                    canvas_size
                    / max(
                        max_x - min_x,
                        1e-9,
                    )
                )

                sz = (
                    canvas_size
                    / max(
                        max_z - min_z,
                        1e-9,
                    )
                )

                subdiv = (
                    _cv2.Subdiv2D(
                        (
                            0,
                            0,
                            int(
                                canvas_size
                            ),
                            int(
                                canvas_size
                            ),
                        )
                    )
                )

                for px, pz in projected:

                    qx = (
                        (
                            px - min_x
                        )
                        * sx
                        + 1.0
                    )

                    qz = (
                        (
                            pz - min_z
                        )
                        * sz
                        + 1.0
                    )

                    subdiv.insert(
                        (
                            float(qx),
                            float(qz),
                        )
                    )

                triangles = (
                    subdiv.getTriangleList()
                )

                lookup: Dict[
                    Tuple[int, int],
                    int,
                ] = {}

                for index, (
                    px,
                    pz,
                ) in enumerate(
                    projected
                ):

                    qx = int(
                        round(
                            (
                                px
                                - min_x
                            )
                            * sx
                            + 1.0
                        )
                    )

                    qz = int(
                        round(
                            (
                                pz
                                - min_z
                            )
                            * sz
                            + 1.0
                        )
                    )

                    lookup[
                        (
                            qx,
                            qz,
                        )
                    ] = index

                for triangle in triangles:

                    coords = [
                        (
                            float(
                                triangle[0]
                            ),
                            float(
                                triangle[1]
                            ),
                        ),
                        (
                            float(
                                triangle[2]
                            ),
                            float(
                                triangle[3]
                            ),
                        ),
                        (
                            float(
                                triangle[4]
                            ),
                            float(
                                triangle[5]
                            ),
                        ),
                    ]

                    indices = []

                    for qx, qz in coords:

                        ix = int(
                            round(qx)
                        )

                        iz = int(
                            round(qz)
                        )

                        direct = lookup.get(
                            (
                                ix,
                                iz,
                            )
                        )

                        if direct is None:

                            target = np.asarray(
                                [
                                    (
                                        qx / sx
                                    )
                                    + min_x,
                                    (
                                        qz / sz
                                    )
                                    + min_z,
                                ]
                            )

                            distances = (
                                np.sum(
                                    (
                                        projected
                                        - target
                                    )
                                    ** 2,
                                    axis=1,
                                )
                            )

                            direct = int(
                                np.argmin(
                                    distances
                                )
                            )

                        indices.append(
                            direct
                        )

                    if (
                        len(
                            set(
                                indices
                            )
                        )
                        == 3
                    ):

                        faces.append(
                            tuple(
                                indices
                            )
                        )

            except Exception:

                faces = []

        if len(faces) < 30:

            return None

        # --------------------------------------------------
        # Remove very long triangles that bridge gaps.
        # --------------------------------------------------

        edge_lengths = []

        for a, b, c in faces:

            pa = projected[a]
            pb = projected[b]
            pc = projected[c]

            edge_lengths.extend(
                [
                    float(
                        np.linalg.norm(
                            pa - pb
                        )
                    ),
                    float(
                        np.linalg.norm(
                            pb - pc
                        )
                    ),
                    float(
                        np.linalg.norm(
                            pc - pa
                        )
                    ),
                ]
            )

        if edge_lengths:

            edge_threshold = (
                float(
                    np.percentile(
                        edge_lengths,
                        97.0,
                    )
                )
                * 2.5
            )

            edge_threshold = max(
                edge_threshold,
                1e-6,
            )

            filtered_faces = []

            for a, b, c in faces:

                pa = projected[a]
                pb = projected[b]
                pc = projected[c]

                lengths = (
                    float(
                        np.linalg.norm(
                            pa - pb
                        )
                    ),
                    float(
                        np.linalg.norm(
                            pb - pc
                        )
                    ),
                    float(
                        np.linalg.norm(
                            pc - pa
                        )
                    ),
                )

                if (
                    max(lengths)
                    <= edge_threshold
                ):

                    filtered_faces.append(
                        (
                            a,
                            b,
                            c,
                        )
                    )

            faces = (
                filtered_faces
            )

        if len(faces) < 30:

            return None

        # --------------------------------------------------
        # Build PLY vertices.
        # --------------------------------------------------

        vertices: List[
            Tuple[
                float,
                float,
                float,
            ]
        ] = []

        vertex_colors: List[
            Tuple[
                int,
                int,
                int,
            ]
        ] = []

        for index in range(
            len(point_array)
        ):

            vertices.append(
                (
                    round(
                        float(
                            mesh_x[index]
                        ),
                        6,
                    ),
                    round(
                        float(
                            mesh_y[index]
                        ),
                        6,
                    ),
                    round(
                        float(
                            mesh_z[index]
                        ),
                        6,
                    ),
                )
            )

            rgb = (
                color_array[index]
            )

            vertex_colors.append(
                (
                    int(
                        clamp_value(
                            float(
                                rgb[0]
                            ),
                            0,
                            255,
                        )
                    ),
                    int(
                        clamp_value(
                            float(
                                rgb[1]
                            ),
                            0,
                            255,
                        )
                    ),
                    int(
                        clamp_value(
                            float(
                                rgb[2]
                            ),
                            0,
                            255,
                        )
                    ),
                )
            )

        # --------------------------------------------------
        # Pothole marker positions.
        #
        # These are approximate because YOLO gives 2D image
        # coordinates while this first COLMAP implementation
        # operates on the reconstructed 3D scene.
        #
        # The nearest reconstructed surface vertex is used.
        # --------------------------------------------------

        specs = [
            _detection_geometry(
                detection,
                frame_width,
                frame_height,
                default_severity,
            )
            for detection in
            _collapse_detections(
                detections
            )
        ]

        potholes: List[
            Dict[str, Any]
        ] = []

        x_min = float(
            np.min(mesh_x)
        )

        x_max = float(
            np.max(mesh_x)
        )

        z_min = float(
            np.min(mesh_z)
        )

        z_max = float(
            np.max(mesh_z)
        )

        for index, spec in enumerate(
            specs
        ):

            nx = spec[
                "normalized_x"
            ]

            ny = spec[
                "normalized_y"
            ]

            marker_x = (
                x_min
                + nx
                * (
                    x_max
                    - x_min
                )
            )

            marker_z = (
                z_max
                - ny
                * (
                    z_max
                    - z_min
                )
            )

            distances = (
                (
                    mesh_x
                    - marker_x
                ) ** 2
                +
                (
                    mesh_z
                    - marker_z
                ) ** 2
            )

            nearest_index = int(
                np.argmin(
                    distances
                )
            )

            marker_y = float(
                mesh_y[
                    nearest_index
                ]
            )

            potholes.append(
                {
                    "id":
                        index + 1,

                    "label":
                        f"Pothole #{index + 1}",

                    "severity":
                        spec[
                            "severity"
                        ],

                    "confidence":
                        round(
                            clamp_value(
                                spec[
                                    "confidence"
                                ],
                                0.0,
                                1.0,
                            ),
                            4,
                        ),

                    "radius_m":
                        round(
                            clamp_value(
                                (
                                    spec[
                                        "width"
                                    ]
                                    / max(
                                        spec[
                                            "display_width"
                                        ],
                                        1.0,
                                    )
                                )
                                * max(
                                    x_max
                                    - x_min,
                                    z_max
                                    - z_min,
                                )
                                * 1.5,
                                0.05,
                                max(
                                    x_max
                                    - x_min,
                                    z_max
                                    - z_min,
                                ),
                            ),
                            4,
                        ),

                    "depth_m":
                        round(
                            max(
                                0.01,
                                abs(
                                    marker_y
                                )
                                * 0.05,
                            ),
                            4,
                        ),

                    "area_ratio":
                        round(
                            spec[
                                "area_ratio"
                            ],
                            6,
                        ),

                    "location_name":
                        spec[
                            "location_name"
                        ],

                    "mesh_position":
                        [
                            round(
                                marker_x,
                                6,
                            ),
                            round(
                                marker_y,
                                6,
                            ),
                            round(
                                marker_z,
                                6,
                            ),
                        ],

                    "position_mapping":
                        "approximate_2d_to_3d",
                }
            )

        # --------------------------------------------------
        # Viewer transform.
        # --------------------------------------------------

        minimum = (
            float(
                np.min(mesh_x)
            ),
            float(
                np.min(mesh_y)
            ),
            float(
                np.min(mesh_z)
            ),
        )

        maximum = (
            float(
                np.max(mesh_x)
            ),
            float(
                np.max(mesh_y)
            ),
            float(
                np.max(mesh_z)
            ),
        )

        mesh_center = tuple(
            (
                minimum[i]
                + maximum[i]
            ) / 2.0
            for i in range(3)
        )

        dimensions = tuple(
            maximum[i]
            - minimum[i]
            for i in range(3)
        )

        max_dimension = max(
            dimensions
        )

        if max_dimension <= 0.0:

            return None

        viewer_scale = (
            VIEWER_TARGET_SIZE
            / max_dimension
        )

        for pothole in potholes:

            pothole[
                "position_mesh"
            ] = list(
                pothole[
                    "mesh_position"
                ]
            )

            pothole[
                "position_3d"
            ] = [
                round(
                    (
                        pothole[
                            "mesh_position"
                        ][i]
                        - mesh_center[i]
                    )
                    * viewer_scale,
                    4,
                )
                for i in range(3)
            ]

            pothole[
                "color"
            ] = rgb_to_hex(
                POTHOLE_RGB[
                    pothole[
                        "severity"
                    ]
                ]
            )

        geometry_source = (
            reconstruction.get(
                "method"
            )
            or "reconstructed_sfm"
        )

        return {
            "vertices":
                vertices,

            "colors":
                vertex_colors,

            "faces":
                faces,

            "potholes":
                potholes,

            "stats": {
                "geometry_source":
                    geometry_source,

                "grid_columns":
                    None,

                "grid_rows":
                    None,

                "vertex_count":
                    len(vertices),

                "face_count":
                    len(faces),

                "road_width_m":
                    round(
                        x_max
                        - x_min,
                        6,
                    ),

                "road_length_m":
                    round(
                        z_max
                        - z_min,
                        6,
                    ),

                "center":
                    [
                        round(
                            value,
                            6,
                        )
                        for value
                        in mesh_center
                    ],

                "max_dimension":
                    round(
                        max_dimension,
                        6,
                    ),

                "viewer_scale":
                    round(
                        viewer_scale,
                        6,
                    ),

                "viewer_target_size":
                    VIEWER_TARGET_SIZE,

                "pca_singular_values":
                    [
                        round(
                            float(value),
                            6,
                        )
                        for value
                        in singular_values
                    ],
            },
        }

    except Exception as error:

        print(
            "[RoadGuard Photogrammetry] "
            "Reconstruction-derived mesh failed: "
            f"{error}"
        )

        return None


# ==========================================================
# METADATA / STATUS READERS
# ==========================================================


def load_reconstruction_metadata(
    report_id: int,
) -> Optional[
    Dict[str, Any]
]:
    """
    Return stored roadguard_3d.json.
    """

    metadata_path = (
        get_metadata_path(
            report_id
        )
    )

    if not metadata_path.exists():

        return None

    try:

        with open(
            metadata_path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )

    except (
        OSError,
        ValueError,
    ) as error:

        print(
            "[RoadGuard Photogrammetry] "
            f"Could not read metadata for "
            f"report {report_id}: {error}"
        )

        return None


def get_reconstruction_metadata(
    report_id: int,
) -> Optional[
    Dict[str, Any]
]:

    return load_reconstruction_metadata(
        report_id
    )


def get_reconstruction_status(
    report_id: int,
) -> Dict[str, Any]:

    mesh_exists = (
        get_mesh_path(
            report_id
        ).exists()
    )

    metadata_exists = (
        get_metadata_path(
            report_id
        ).exists()
    )

    workspace_exists = (
        get_report_workspace(
            report_id
        ).exists()
    )

    if (
        mesh_exists
        and metadata_exists
    ):

        status = "completed"

    elif workspace_exists:

        status = (
            "processing_or_incomplete"
        )

    else:

        status = "not_started"

    return {
        "success": True,
        "report_id": report_id,
        "status": status,
        "workspace_exists":
            workspace_exists,
        "mesh_ready":
            mesh_exists,
        "metadata_ready":
            metadata_exists,
        "mesh_url": (
            f"/api/photogrammetry/mesh/"
            f"{report_id}"
            if mesh_exists
            else None
        ),
        "metadata_url": (
            f"/api/photogrammetry/metadata/"
            f"{report_id}"
            if metadata_exists
            else None
        ),
    }


# ==========================================================
# REPORT / MEDIA RESOLUTION
# ==========================================================


UPLOADS_DIR = (
    BASE_DIR / "uploads"
)

VIDEO_SUFFIXES = {
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
}


def _load_report(
    report_id: int,
    db,
):

    if db is None:

        return None

    try:

        from backend.models import (
            ReportModel
        )

    except ImportError:

        return None

    return (
        db.query(
            ReportModel
        )
        .filter(
            ReportModel.id
            == report_id
        )
        .first()
    )


def resolve_media_path(
    report,
    video_path=None,
) -> Path:
    """
    Locate the uploaded video/image on disk.
    """

    if video_path:

        candidate = Path(
            str(video_path)
        )

        if candidate.exists():

            return candidate

        if not candidate.is_absolute():

            candidate = (
                BASE_DIR
                / candidate
            )

            if candidate.exists():

                return candidate

    if report is None:

        raise FileNotFoundError(
            "The report is unknown and "
            "no explicit video_path was given."
        )

    raw_path = Path(
        str(
            report.media_path
        )
    )

    candidates = (
        [raw_path]
        if raw_path.is_absolute()
        else [
            BASE_DIR
            / raw_path
        ]
    )

    candidates.append(
        BASE_DIR
        / "uploads"
        / raw_path.name
    )

    for candidate in candidates:

        if candidate.exists():

            return candidate

    raise FileNotFoundError(
        "Uploaded media file was not found: "
        f"{report.media_path}"
    )


def _load_detection_metadata(
    report_id: int,
) -> Dict[str, Any]:
    """
    Read YOLO metadata written by detection_service.
    """

    candidates = [
        THREE_D_DATA_DIR
        / f"report_{report_id}.json",

        get_metadata_path(
            report_id
        ),
    ]

    for candidate in candidates:

        if not candidate.exists():

            continue

        try:

            with open(
                candidate,
                "r",
                encoding="utf-8",
            ) as file:

                return json.load(
                    file
                )

        except (
            OSError,
            ValueError,
        ) as error:

            print(
                "[RoadGuard Photogrammetry] "
                f"Skipping unreadable metadata "
                f"{candidate}: {error}"
            )

    return {}


def _media_dimensions(
    media_path: Path,
) -> Tuple[int, int]:
    """
    Return (width, height) of uploaded media.
    """

    cv2, _np = _import_cv()

    if media_path.suffix.lower() in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
    }:

        image = cv2.imread(
            str(media_path)
        )

        if image is None:

            return 0, 0

        height, width = (
            image.shape[:2]
        )

        return (
            int(width),
            int(height),
        )

    capture = cv2.VideoCapture(
        str(media_path)
    )

    if not capture.isOpened():

        return 0, 0

    width = int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
        or 0
    )

    height = int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
        or 0
    )

    capture.release()

    return (
        width,
        height,
    )


# ==========================================================
# MAIN ENTRY POINT
# ==========================================================


def process_report_photogrammetry(
    report_id: int,
    db=None,
    video_path=None,
    detections: Optional[
        Sequence[Any]
    ] = None,
) -> Dict[str, Any]:
    """
    Run the full reconstruction pipeline.

    COLMAP mode:

        video
          ↓
        frames
          ↓
        COLMAP SIFT
          ↓
        sequential matcher
          ↓
        mapper
          ↓
        actual sparse 3D points
          ↓
        reconstructed Delaunay surface
          ↓
        roadguard-road.ply

    OpenCV mode:

        video
          ↓
        ORB
          ↓
        OpenCV SfM
          ↓
        reconstructed Delaunay surface
          ↓
        optional legacy synthetic fallback
    """

    report = _load_report(
        report_id,
        db,
    )

    media_path = resolve_media_path(
        report,
        video_path,
    )

    ensure_workspace(
        report_id
    )

    source_metadata = (
        _load_detection_metadata(
            report_id
        )
    )

    if detections is None:

        detections = (
            source_metadata.get(
                "unique_potholes"
            )
            or source_metadata.get(
                "detections"
            )
            or []
        )

    frame_width = int(
        safe_float(
            source_metadata.get(
                "frame_width"
            ),
            0.0,
        )
    )

    frame_height = int(
        safe_float(
            source_metadata.get(
                "frame_height"
            ),
            0.0,
        )
    )

    if (
        frame_width <= 0
        or frame_height <= 0
    ):

        measured_width, measured_height = (
            _media_dimensions(
                media_path
            )
        )

        frame_width = (
            frame_width
            or measured_width
        )

        frame_height = (
            frame_height
            or measured_height
        )

    # ======================================================
    # ENGINE SELECTION
    # ======================================================

    engine_status = (
        get_engine_status()
    )

    configured_engine = (
        engine_status[
            "configured_engine"
        ]
    )

    # ------------------------------------------------------
    # IMPORTANT:
    #
    # If COLMAP was requested but isn't available, do NOT
    # silently use OpenCV.
    #
    # This makes debugging much easier and prevents the
    # unwanted synthetic geometry from appearing.
    # ------------------------------------------------------

    if (
        configured_engine
        == "colmap"
        and not engine_status[
            "colmap_available"
        ]
    ):

        raise RuntimeError(
            "COLMAP was requested but the COLMAP executable "
            "was not found.\n\n"
            "Set ROADGUARD_COLMAP_PATH to the full path of "
            "colmap.exe, for example:\n\n"
            "C:\\Users\\madin\\Downloads\\"
            "colmap-x64-windows-nocuda\\bin\\colmap.exe"
        )

    # ======================================================
    # 1. SAMPLE VIDEO FRAMES
    # ======================================================

    print(
        "[RoadGuard Photogrammetry] "
        f"Sampling frames for report {report_id}..."
    )

    frame_paths = extract_frames(
        media_path,
        get_frames_dir(
            report_id
        ),
    )

    if len(frame_paths) < 3:

        raise RuntimeError(
            "Video did not provide enough usable frames "
            "for photogrammetry."
        )

    print(
        "[RoadGuard Photogrammetry] "
        f"Extracted {len(frame_paths)} frames."
    )

    # ======================================================
    # 2. RECONSTRUCTION
    # ======================================================

    if (
        configured_engine
        == "colmap"
    ):

        # --------------------------------------------------
        # REAL COLMAP PIPELINE
        # --------------------------------------------------

        print(
            "[RoadGuard Photogrammetry] "
            "=========================================="
        )

        print(
            "[RoadGuard Photogrammetry] "
            "COLMAP CPU SPARSE RECONSTRUCTION"
        )

        print(
            "[RoadGuard Photogrammetry] "
            f"Executable: "
            f"{engine_status['colmap_path']}"
        )

        print(
            "[RoadGuard Photogrammetry] "
            "=========================================="
        )

        reconstruction = (
            run_colmap_sparse_reconstruction(
                report_id,
                frame_paths,
            )
        )

        geometry_source = (
            "colmap_sparse_sfm_delaunay"
        )

        frames_with_features = (
            reconstruction.get(
                "images_registered",
                0,
            )
        )

    else:

        # --------------------------------------------------
        # EXPLICIT LEGACY OPENCV MODE
        # --------------------------------------------------

        print(
            "[RoadGuard Photogrammetry] "
            "Using explicit OpenCV reconstruction mode."
        )

        features = (
            detect_features(
                frame_paths
            )
        )

        reconstruction = (
            sparse_reconstruction(
                features
            )
        )

        geometry_source = (
            "opencv_sparse_sfm_delaunay"
        )

        frames_with_features = (
            len(features)
        )

    # ======================================================
    # 3. BUILD SURFACE FROM ACTUAL RECONSTRUCTED POINTS
    # ======================================================

    if configured_engine == "colmap":
        points = reconstruction.get("points") or []

        if not points:
            raise RuntimeError(
                "COLMAP completed, but no reconstructed 3D points were returned."
            )

        vertices = []
        colors = []

        for point in points:
            if isinstance(point, dict):
                x = safe_float(point.get("x"), 0.0)
                y = safe_float(point.get("y"), 0.0)
                z = safe_float(point.get("z"), 0.0)

                r = int(safe_float(point.get("r"), 180))
                g = int(safe_float(point.get("g"), 180))
                b = int(safe_float(point.get("b"), 180))
            else:
                x = safe_float(point[0], 0.0)
                y = safe_float(point[1], 0.0)
                z = safe_float(point[2], 0.0)

                r = int(safe_float(point[3], 180)) if len(point) > 3 else 180
                g = int(safe_float(point[4], 180)) if len(point) > 4 else 180
                b = int(safe_float(point[5], 180)) if len(point) > 5 else 180

            vertices.append((x, y, z))
            colors.append((r, g, b))

        surface = {
            "vertices": vertices,
            "colors": colors,
            "faces": [],
            "potholes": [],
            "stats": {
                "geometry_source": "colmap_sparse_point_cloud",
                "vertex_count": len(vertices),
                "face_count": 0,
                "road_width_m": 0.0,
                "road_length_m": 0.0,
            },
        }

        geometry_source = "colmap_sparse_point_cloud"

    else:
        surface = build_reconstructed_road_surface(
            reconstruction,
            detections,
            frame_width,
            frame_height,
            default_severity=normalize_severity(
                source_metadata.get("severity")
            ),
        )

    # ======================================================
    # IMPORTANT COLMAP RULE
    #
    # Never create the old rectangular road when COLMAP is
    # active.
    # ======================================================

    if (
        surface is None
        and configured_engine
        == "colmap"
    ):

        raise RuntimeError(
            "COLMAP produced a sparse reconstruction, "
            "but RoadGuard could not generate a triangulated "
            "surface from the actual reconstructed 3D points.\n\n"
            "The synthetic rectangular road fallback is "
            "disabled in COLMAP mode."
        )

    # ======================================================
    # LEGACY OPENCV FALLBACK ONLY
    # ======================================================

    if surface is None:

        surface = build_road_surface(
            detections,
            frame_width,
            frame_height,
            default_severity=
                normalize_severity(
                    source_metadata.get(
                        "severity"
                    )
                ),
        )

        geometry_source = (
            "synthetic_heightfield_fallback"
        )

    surface[
        "stats"
    ][
        "geometry_source"
    ] = geometry_source

    stats = surface[
        "stats"
    ]

    # ======================================================
    # 4. WRITE MESH
    # ======================================================

    mesh_path = write_ply(
        get_mesh_path(
            report_id
        ),
        surface[
            "vertices"
        ],
        surface[
            "colors"
        ],
        surface[
            "faces"
        ],
        comments=[
            (
                "RoadGuard AI reconstructed "
                f"road surface - report {report_id}"
            ),
            (
                f"geometry_source="
                f"{geometry_source}"
            ),
            (
                f"vertices="
                f"{stats['vertex_count']}"
            ),
            (
                f"faces="
                f"{stats['face_count']}"
            ),
            (
                f"road="
                f"{stats.get('road_width_m', 0.0)}"
                f"x"
                f"{stats.get('road_length_m', 0.0)}"
            ),
        ],
    )

    # ======================================================
    # 5. WRITE SPARSE POINT CLOUD
    # ======================================================

    pointcloud_path = None

    if reconstruction.get(
        "points"
    ):

        pointcloud_path = (
            write_ply(
                get_pointcloud_path(
                    report_id
                ),
                reconstruction[
                    "points"
                ],
                reconstruction[
                    "colors"
                ],
                None,
                comments=[
                    (
                        "RoadGuard AI "
                        "sparse reconstructed "
                        f"3D cloud - report "
                        f"{report_id}"
                    ),
                    (
                        f"points="
                        f"{len(reconstruction['points'])}"
                    ),
                    (
                        f"method="
                        f"{reconstruction['method']}"
                    ),
                ],
            )
        )

    # ======================================================
    # 6. SEVERITY / CONFIDENCE
    # ======================================================

    potholes = surface.get(
        "potholes", []
    )

    severity_candidates = [
        normalize_severity(
            source_metadata.get(
                "severity"
            )
        )
    ]

    severity_candidates.extend(
        pothole[
            "severity"
        ]
        for pothole in potholes
    )

    severity = max(
        severity_candidates,
        key=lambda value:
            SEVERITY_LEVELS.index(
                value
            ),
    )

    confidence = safe_float(
        source_metadata.get(
            "confidence"
        ),
        0.0,
    )

    if (
        confidence <= 0.0
        and potholes
    ):

        confidence = (
            sum(
                pothole[
                    "confidence"
                ]
                for pothole
                in potholes
            )
            / len(potholes)
        )

    pothole_count = len(
        potholes
    )

    if pothole_count == 0:

        pothole_count = int(
            safe_float(
                source_metadata.get(
                    "pothole_count"
                ),
                0.0,
            )
        )

    media_type = (
        "video"
        if media_path.suffix.lower()
        in VIDEO_SUFFIXES
        else "image"
    )

    # ======================================================
    # 7. METADATA
    # ======================================================

    payload = {
        "success": True,

        "report_id":
            report_id,

        "generated_at":
            utc_now_iso(),

        "method":
            geometry_source,

        "sfm_method":
            reconstruction[
                "method"
            ],

        "photogrammetry_engine":
            (
                "colmap"
                if configured_engine
                == "colmap"
                else "opencv"
            ),

        "colmap_path":
            engine_status.get(
                "colmap_path"
            ),

        "media": {
            "media_type":
                media_type,

            "path":
                str(
                    media_path
                ),

            "name":
                media_path.name,

            "frame_width":
                frame_width,

            "frame_height":
                frame_height,

            "format":
                source_metadata.get(
                    "media_format",
                    "forward_facing",
                ),
        },

        "reconstruction": {
            "frames_extracted":
                len(frame_paths),

            "frames_with_features":
                frames_with_features,

            "sparse_points":
                len(
                    reconstruction[
                        "points"
                    ]
                ),

            "camera_count":
                len(
                    reconstruction[
                        "camera_centers"
                    ]
                ),

            "registered_images":
                reconstruction.get(
                    "images_registered",
                    len(
                        reconstruction[
                            "camera_centers"
                        ]
                    ),
                ),

            "camera_poses":
                reconstruction[
                    "camera_centers"
                ],

            "workspace":
                reconstruction.get(
                    "workspace"
                ),

            "sparse_model":
                reconstruction.get(
                    "sparse_model"
                ),
        },

        "road":
            stats,

        "mesh": {
            "file":
                MESH_FILENAME,

            "relative_path":
                (
                    f"results/"
                    f"photogrammetry/"
                    f"report_{report_id}/"
                    f"dense/"
                    f"{MESH_FILENAME}"
                ),

            "url":
                (
                    f"/api/"
                    f"photogrammetry/"
                    f"mesh/"
                    f"{report_id}"
                ),
        },

        "pointcloud":
            (
                {
                    "file":
                        POINTCLOUD_FILENAME,

                    "relative_path":
                        (
                            f"results/"
                            f"photogrammetry/"
                            f"report_{report_id}/"
                            f"{POINTCLOUD_FILENAME}"
                        ),

                    "points":
                        len(
                            reconstruction[
                                "points"
                            ]
                        ),
                }
                if pointcloud_path
                else None
            ),

        "pothole_count":
            pothole_count,

        "severity":
            severity,

        "confidence":
            round(
                confidence,
                4,
            ),

        "potholes":
            potholes,
    }

    metadata_path = (
        get_metadata_path(
            report_id
        )
    )

    with open(
        metadata_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            indent=2,
        )

    # ======================================================
    # LOG
    # ======================================================

    print(
        "\n[RoadGuard Photogrammetry] "
        "=========================================="
    )

    print(
        "[RoadGuard Photogrammetry] "
        f"Report {report_id} reconstructed"
    )

    print(
        "[RoadGuard Photogrammetry] "
        f"Engine: {configured_engine}"
    )

    print(
        "[RoadGuard Photogrammetry] "
        f"Geometry: {geometry_source}"
    )

    print(
        "[RoadGuard Photogrammetry] "
        f"Vertices: {stats['vertex_count']}"
    )

    print(
        "[RoadGuard Photogrammetry] "
        f"Faces: {stats['face_count']}"
    )

    print(
        "[RoadGuard Photogrammetry] "
        f"Sparse points: "
        f"{len(reconstruction['points'])}"
    )

    print(
        "[RoadGuard Photogrammetry] "
        f"Cameras: "
        f"{len(reconstruction['camera_centers'])}"
    )

    print(
        "[RoadGuard Photogrammetry] "
        f"Potholes: {pothole_count}"
    )

    print(
        "[RoadGuard Photogrammetry] "
        f"Mesh: {mesh_path}"
    )

    print(
        "[RoadGuard Photogrammetry] "
        "==========================================\n"
    )

    # ======================================================
    # RETURN
    # ======================================================

    return {
        "report_id":
            report_id,

        "method":
            geometry_source,

        "sfm_method":
            reconstruction[
                "method"
            ],

        "photogrammetry_engine":
            configured_engine,

        "colmap_path":
            engine_status.get(
                "colmap_path"
            ),

        "frames_extracted":
            len(frame_paths),

        "frames_with_features":
            frames_with_features,

        "sparse_points":
            len(
                reconstruction[
                    "points"
                ]
            ),

        "camera_count":
            len(
                reconstruction[
                    "camera_centers"
                ]
            ),

        "vertex_count":
            stats[
                "vertex_count"
            ],

        "face_count":
            stats[
                "face_count"
            ],

        "pothole_count":
            pothole_count,

        "severity":
            severity,

        "confidence":
            round(
                confidence,
                4,
            ),

        "mesh_path":
            str(
                mesh_path
            ),

        "pointcloud_path":
            (
                str(
                    pointcloud_path
                )
                if pointcloud_path
                else None
            ),

        "metadata_path":
            str(
                metadata_path
            ),
    }


# ==========================================================
# ROUTER COMPATIBILITY - RECONSTRUCTED MESH
# ==========================================================


def get_reconstruction_mesh(
    report_id: int,
) -> Optional[str]:
    """
    Return reconstructed mesh path for a report.

    Compatibility helper used by the photogrammetry router.
    """

    mesh_path = get_mesh_path(
        report_id
    )

    if not mesh_path.exists():

        return None

    return str(
        mesh_path
    )