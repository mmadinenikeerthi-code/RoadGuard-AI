import csv
import io
import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ReportModel
from backend.schemas import ReportResponse, ReportSummary

PROJECT_ROOT = Path(__file__).resolve().parents[2]
THREE_D_DATA_DIR = PROJECT_ROOT / "results" / "3d_data"

router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"]
)


@router.get("", response_model=List[ReportResponse])
@router.get("/", response_model=List[ReportResponse])
def list_reports(db: Session = Depends(get_db)):
    return db.query(ReportModel).order_by(ReportModel.created_at.desc()).all()


@router.get("/summary", response_model=ReportSummary)
def get_reports_summary(db: Session = Depends(get_db)):
    reports = db.query(ReportModel).all()

    total_reports = len(reports)
    total_potholes = sum(r.pothole_count or 0 for r in reports)

    low = sum(1 for r in reports if r.severity == "LOW")
    moderate = sum(1 for r in reports if r.severity == "MODERATE")
    high = sum(1 for r in reports if r.severity == "HIGH")
    critical = sum(1 for r in reports if r.severity == "CRITICAL")

    return {
        "total_reports": total_reports,
        "total_potholes": total_potholes,
        "low_severity": low,
        "moderate_severity": moderate,
        "high_severity": high,
        "critical_severity": critical
    }


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportModel).filter(ReportModel.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report record not found.")
    return report


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportModel).filter(ReportModel.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report record not found.")

    db.delete(report)
    db.commit()
    return None


# ==========================================================
# REPORT DOWNLOADS (CSV & PDF)
# ==========================================================

def _load_report_detections(report_id: int):
    three_d_file = THREE_D_DATA_DIR / f"report_{report_id}.json"
    if three_d_file.exists():
        try:
            with open(three_d_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


@router.get("/{report_id}/download/csv")
def download_report_csv(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportModel).filter(ReportModel.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report record not found.")

    det_data = _load_report_detections(report_id)
    raw_potholes = det_data.get("unique_potholes") or det_data.get("detections") or []

    output = io.StringIO()
    writer = csv.writer(output)

    # Header section
    writer.writerow(["ROADGUARD AI - ROAD INSPECTION AUDIT REPORT"])
    writer.writerow(["Report ID", report.id])
    writer.writerow(["Created At", str(report.created_at or "")])
    writer.writerow(["Location Name", report.location_name or "Unknown Location"])
    writer.writerow(["Latitude", report.latitude if report.latitude is not None else "N/A"])
    writer.writerow(["Longitude", report.longitude if report.longitude is not None else "N/A"])
    writer.writerow(["Media Type", str(report.media_type or "").upper()])
    writer.writerow(["Media Path", str(report.media_path or "")])
    writer.writerow(["Result Path", str(report.result_path or "")])
    writer.writerow(["Pothole Count", report.pothole_count or 0])
    writer.writerow(["Overall Severity", str(report.severity or "LOW").upper()])
    writer.writerow(["Confidence Score", f"{round(float(report.confidence or 0) * 100, 2)}%"])
    writer.writerow([])

    # Detections table
    writer.writerow([
        "Pothole #",
        "Track/Detection ID",
        "Severity",
        "Confidence",
        "Center X (px)",
        "Center Y (px)",
        "Width",
        "Height",
        "Position 3D X",
        "Position 3D Y",
        "Position 3D Z",
    ])

    for idx, p in enumerate(raw_potholes):
        track_id = p.get("track_id") or p.get("id") or (p.get("source_track_ids", ["N/A"])[0] if p.get("source_track_ids") else "N/A")
        sev = str(p.get("severity") or report.severity or "LOW").upper()
        conf = round(float(p.get("confidence") or p.get("average_confidence") or report.confidence or 0) * 100, 2)
        center_dict = p.get("center") or {}
        center_norm = p.get("center_normalized") or {}
        cx = p.get("center_x") if p.get("center_x") is not None else (center_dict.get("x") if isinstance(center_dict, dict) else center_norm.get("x", ""))
        cy = p.get("center_y") if p.get("center_y") is not None else (center_dict.get("y") if isinstance(center_dict, dict) else center_norm.get("y", ""))
        avg_box = p.get("average_box") or {}
        w = p.get("width") if p.get("width") is not None else avg_box.get("width", "")
        h = p.get("height") if p.get("height") is not None else avg_box.get("height", "")
        pos3d = p.get("position_3d")
        px, py, pz = "", "", ""
        if isinstance(pos3d, dict):
            px, py, pz = pos3d.get("x", ""), pos3d.get("y", ""), pos3d.get("z", "")
        elif isinstance(pos3d, (list, tuple)) and len(pos3d) >= 3:
            px, py, pz = pos3d[0], pos3d[1], pos3d[2]

        writer.writerow([idx + 1, track_id, sev, f"{conf}%", cx, cy, w, h, px, py, pz])

    filename = f"RoadGuard_Report_{report_id}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{report_id}/download/pdf")
def download_report_pdf(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportModel).filter(ReportModel.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report record not found.")

    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    det_data = _load_report_detections(report_id)
    raw_potholes = det_data.get("unique_potholes") or det_data.get("detections") or []

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#0f172a'))
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, textColor=colors.HexColor('#64748b'))
    section_style = ParagraphStyle('SectionStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#1e293b'))
    meta_label = ParagraphStyle('MetaLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#475569'))
    meta_val = ParagraphStyle('MetaVal', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor('#0f172a'))
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#1e293b'))
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#1e293b'))
    th_style = ParagraphStyle('THStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#ffffff'))

    story = [
        Paragraph("RoadGuard AI - Infrastructure Inspection Audit Report", title_style),
        Paragraph("Automated AI Pothole Detection & Spatial Road Monitoring System", subtitle_style),
        Spacer(1, 14),
        Paragraph("Report Summary", section_style),
        Spacer(1, 6),
    ]

    lat_str = f"{report.latitude:.5f}" if report.latitude is not None else "N/A"
    lon_str = f"{report.longitude:.5f}" if report.longitude is not None else "N/A"
    conf_pct = f"{round(float(report.confidence or 0) * 100, 1)}%"

    summary_table_data = [
        [Paragraph("Report ID:", meta_label), Paragraph(f"#{report.id}", meta_val), Paragraph("Total Potholes:", meta_label), Paragraph(str(report.pothole_count or len(raw_potholes)), meta_val)],
        [Paragraph("Location Name:", meta_label), Paragraph(report.location_name or "Unknown Location", meta_val), Paragraph("Overall Severity:", meta_label), Paragraph(str(report.severity or "LOW").upper(), meta_val)],
        [Paragraph("Coordinates:", meta_label), Paragraph(f"{lat_str}, {lon_str}", meta_val), Paragraph("Model Confidence:", meta_label), Paragraph(conf_pct, meta_val)],
        [Paragraph("Media Type:", meta_label), Paragraph(str(report.media_type or "").upper(), meta_val), Paragraph("Recorded Timestamp:", meta_label), Paragraph(str(report.created_at or "N/A"), meta_val)],
    ]

    sum_table = Table(summary_table_data, colWidths=[100, 170, 100, 170])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph(f"Defect Telemetry Breakdown ({len(raw_potholes)} Detected Objects)", section_style))
    story.append(Spacer(1, 6))

    det_table_data = [
        [
            Paragraph("Item", th_style),
            Paragraph("Detection ID", th_style),
            Paragraph("Severity", th_style),
            Paragraph("Confidence", th_style),
            Paragraph("2D Center", th_style),
            Paragraph("3D Position (x, y, z)", th_style),
        ]
    ]

    rows_to_show = raw_potholes[:60]
    for idx, p in enumerate(rows_to_show):
        track_id = p.get("track_id") or p.get("id") or (p.get("source_track_ids", ["N/A"])[0] if p.get("source_track_ids") else f"P-{idx+1}")
        sev = str(p.get("severity") or report.severity or "LOW").upper()
        conf = f"{round(float(p.get('confidence') or p.get('average_confidence') or report.confidence or 0) * 100, 1)}%"
        center_dict = p.get("center") or {}
        center_norm = p.get("center_normalized") or {}
        cx = p.get("center_x") if p.get("center_x") is not None else (center_dict.get("x") if isinstance(center_dict, dict) else center_norm.get("x", ""))
        cy = p.get("center_y") if p.get("center_y") is not None else (center_dict.get("y") if isinstance(center_dict, dict) else center_norm.get("y", ""))
        center_str = f"({cx:.1f}, {cy:.1f})" if isinstance(cx, (int, float)) and isinstance(cy, (int, float)) else "N/A"
        
        pos3d = p.get("position_3d")
        pos_str = "N/A"
        if isinstance(pos3d, dict):
            pos_str = f"({pos3d.get('x', 0):.2f}, {pos3d.get('y', 0):.2f}, {pos3d.get('z', 0):.2f})"
        elif isinstance(pos3d, (list, tuple)) and len(pos3d) >= 3:
            pos_str = f"({pos3d[0]:.2f}, {pos3d[1]:.2f}, {pos3d[2]:.2f})"

        det_table_data.append([
            Paragraph(f"#{idx+1}", cell_bold),
            Paragraph(str(track_id), cell_style),
            Paragraph(sev, cell_bold),
            Paragraph(conf, cell_style),
            Paragraph(center_str, cell_style),
            Paragraph(pos_str, cell_style),
        ])

    if not rows_to_show:
        det_table_data.append([
            Paragraph("-", cell_style),
            Paragraph("No individual pothole coordinates recorded", cell_style),
            Paragraph(str(report.severity or "LOW"), cell_style),
            Paragraph(conf_pct, cell_style),
            Paragraph("N/A", cell_style),
            Paragraph("N/A", cell_style),
        ])

    det_table = Table(det_table_data, colWidths=[35, 115, 80, 75, 105, 130])
    det_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
    ]))
    story.append(det_table)
    story.append(Spacer(1, 16))
    story.append(Paragraph("This document was generated automatically by RoadGuard AI Road Infrastructure Monitoring System.", subtitle_style))

    doc.build(story)

    filename = f"RoadGuard_Report_{report_id}.pdf"
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )