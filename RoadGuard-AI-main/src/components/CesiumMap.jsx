import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import * as Cesium from "cesium";

const CesiumMap = forwardRef(function CesiumMap(_props, ref) {
    const containerRef = useRef(null);
    const viewerRef = useRef(null);
    const searchMarkerRef = useRef(null);
    const routeEntitiesRef = useRef([]);

    useEffect(() => {
        let viewer;
        let cancelled = false;

        async function initialize() {
            const token = import.meta.env.VITE_CESIUM_ION_TOKEN;
            if (token && token !== "YOUR_CESIUM_ION_TOKEN") {
                Cesium.Ion.defaultAccessToken = token;
            }

            viewer = new Cesium.Viewer(containerRef.current, {
                animation: false,
                timeline: false,
                baseLayerPicker: true,
                geocoder: false,
                homeButton: true,
                sceneModePicker: true,
                navigationHelpButton: true,
                infoBox: true,
                selectionIndicator: true
            });
            viewerRef.current = viewer;

            try {
                // Uses Cesium World Terrain if an ion token is configured.
                if (token && token !== "YOUR_CESIUM_ION_TOKEN") {
                    viewer.scene.globe.depthTestAgainstTerrain = true;
                    const terrain = await Cesium.createWorldTerrainAsync();
                    if (!cancelled) viewer.terrainProvider = terrain;
                }
            } catch (e) {
                console.warn("Terrain could not be loaded; using the default globe.", e);
            }

            // Initial view centred on Bengaluru; replace with your existing map setup if needed.
            viewer.camera.flyTo({
                destination: Cesium.Cartesian3.fromDegrees(77.5946, 12.9716, 18000),
                duration: 1.2
            });
        }

        initialize();

        return () => {
            cancelled = true;
            if (viewer && !viewer.isDestroyed()) viewer.destroy();
            viewerRef.current = null;
        };
    }, []);

    useImperativeHandle(ref, () => ({
        showLocation(location) {
            const viewer = viewerRef.current;
            if (!viewer || viewer.isDestroyed()) return;
            if (searchMarkerRef.current) viewer.entities.remove(searchMarkerRef.current);

            searchMarkerRef.current = viewer.entities.add({
                name: location.label || "Searched location",
                position: Cesium.Cartesian3.fromDegrees(location.lon, location.lat),
                point: {
                    pixelSize: 13,
                    color: Cesium.Color.fromCssColorString("#22c55e"),
                    outlineColor: Cesium.Color.WHITE,
                    outlineWidth: 3,
                    heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
                },
                label: {
                    text: location.label || "Searched location",
                    font: "14px sans-serif",
                    fillColor: Cesium.Color.WHITE,
                    outlineColor: Cesium.Color.BLACK,
                    outlineWidth: 3,
                    style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                    pixelOffset: new Cesium.Cartesian2(0, -22),
                    disableDepthTestDistance: Number.POSITIVE_INFINITY
                }
            });

            viewer.camera.flyTo({
                destination: Cesium.Cartesian3.fromDegrees(location.lon, location.lat, 4500),
                duration: 1.4
            });
        },

        showRoute(coordinates, start, end) {
            const viewer = viewerRef.current;
            if (!viewer || viewer.isDestroyed()) return;
            routeEntitiesRef.current.forEach((entity) => viewer.entities.remove(entity));
            routeEntitiesRef.current = [];

            const positions = coordinates.map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat, 8));
            const routeLine = viewer.entities.add({
                name: "Road route",
                polyline: {
                    positions,
                    width: 7,
                    material: new Cesium.PolylineGlowMaterialProperty({
                        glowPower: 0.18,
                        color: Cesium.Color.fromCssColorString("#38bdf8")
                    }),
                    clampToGround: true
                }
            });
            const startPin = viewer.entities.add({
                name: "Start",
                position: Cesium.Cartesian3.fromDegrees(start.lon, start.lat),
                point: { pixelSize: 12, color: Cesium.Color.LIME, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
                label: { text: "START", font: "bold 12px sans-serif", pixelOffset: new Cesium.Cartesian2(0, -18), fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE }
            });
            const endPin = viewer.entities.add({
                name: "Destination",
                position: Cesium.Cartesian3.fromDegrees(end.lon, end.lat),
                point: { pixelSize: 12, color: Cesium.Color.RED, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
                label: { text: "DESTINATION", font: "bold 12px sans-serif", pixelOffset: new Cesium.Cartesian2(0, -18), fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE }
            });
            routeEntitiesRef.current = [routeLine, startPin, endPin];
            viewer.flyTo(routeEntitiesRef.current, { duration: 1.5 });
        }
    }), []);

    return <div ref={containerRef} className="cesium-container" />;
});

export default CesiumMap;
