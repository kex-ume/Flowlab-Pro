"""Service-request import, DR-02 conformity assessment and report-cover output."""

from __future__ import annotations

from copy import copy
from datetime import date, datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4


RULE_CODE = "DR-02"
RULE_NAME = "Guarded Acceptance - Expanded Uncertainty"
RULE_FORMULA = "w = U; lower AL = lower TL + U; upper AL = upper TL - U"


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def _row_value(sheet, row: int, start_column: int = 2, end_column: int = 5) -> str:
    values = []
    for column in range(start_column, end_column + 1):
        value = _text(sheet.cell(row, column).value)
        if value:
            values.append(value)
    return " ".join(dict.fromkeys(values)).strip()


def _answer(sheet, row: int, label_cell: str = "A", start_column: int = 2) -> str:
    label_value = _text(sheet[f"{label_cell}{row}"].value)
    if ":" in label_value:
        inline = label_value.split(":", 1)[1].strip(" _")
        if inline:
            return inline
    return _row_value(sheet, row, start_column)


def _inline_answer(value: Any) -> str:
    text = _text(value)
    if ":" not in text:
        return ""
    answer = text.split(":", 1)[1].strip(" _")
    return "" if answer.lower() in {"", "yes/no", "y/n"} else answer


def _cell_answer(sheet, label_cell: str, *answer_cells: str, other_cell: str | None = None) -> str:
    """Read one form field without leaking adjacent labels into its value."""
    inline = _inline_answer(sheet[label_cell].value)
    candidates = [inline]
    for coordinate in answer_cells:
        value = _text(sheet[coordinate].value)
        if value and not value.rstrip().endswith(":") and "please specify" not in value.lower():
            candidates.append(value)
    if other_cell:
        other = _inline_answer(sheet[other_cell].value)
        if other and other.lower() not in {"n/a", "na", "none"}:
            candidates.append(other)
    return next((value for value in candidates if value), "")


def _yes(value: Any) -> bool:
    return _text(value).lower() in {"yes", "y", "true", "1", "required", "accepted"}


def parse_tolerance(value: str) -> tuple[float | None, float | None, str]:
    """Parse common symmetric or lower/upper percentage acceptance-limit text."""
    text = _text(value).replace("−", "-").replace("–", "-")
    numbers = [float(item) for item in re.findall(r"[-+]?\d+(?:\.\d+)?", text)]
    unit = "%" if "%" in text or "percent" in text.lower() else ""
    if not numbers:
        return None, None, unit
    if "±" in text or "+/-" in text or "+-" in text or len(numbers) == 1:
        limit = abs(numbers[0])
        return -limit, limit, unit
    if len(numbers) >= 2:
        return min(numbers[0], numbers[1]), max(numbers[0], numbers[1]), unit
    return None, None, unit


def parse_flow_range(value: str) -> tuple[float | None, float | None, str]:
    """Extract the first two range values and their displayed flow unit."""
    text = _text(value).replace("–", "-").replace("−", "-")
    numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))]
    unit_match = re.search(
        r"(m(?:³|3)\s*/\s*(?:s|min|h|hr|day)|l\s*/?\s*(?:s|min|h|hr|day|pm)|kg\s*/\s*(?:s|min|h|hr)|(?:us\s*)?gpm|bpd)",
        text, re.I,
    )
    raw_unit = re.sub(r"\s+", "", unit_match.group(1)).lower() if unit_match else ""
    aliases = {"lpm":"L/min", "l/min":"L/min", "m3/h":"m³/h", "m3/hr":"m³/h",
        "m³/hr":"m³/h", "m³/h":"m³/h", "kg/s":"kg/s", "kg/min":"kg/min", "bpd":"BPD"}
    unit = aliases.get(raw_unit, unit_match.group(1).strip() if unit_match else "")
    if len(numbers) < 2:
        return None, None, unit
    return min(numbers), max(numbers), unit


def parse_service_request(upload) -> dict[str, Any]:
    """Read the supplied EATL service-request workbook without changing it."""
    from openpyxl import load_workbook

    upload.stream.seek(0)
    raw = upload.stream.read()
    upload.stream.seek(0)
    workbook = load_workbook(io.BytesIO(raw), data_only=True, read_only=False)
    sheet = workbook["REQUEST"] if "REQUEST" in workbook.sheetnames else workbook[workbook.sheetnames[0]]

    acceptance = _cell_answer(sheet, "A34", "D34")
    lower, upper, unit = parse_tolerance(acceptance)
    footer = _text(sheet["D66"].value)
    revision_match = re.search(r"(?:rev(?:ision)?\s*)?([0-9A-Za-z.-]+)", footer, re.I)
    request_number = _cell_answer(sheet, "A64", "A65")
    requested_range = _cell_answer(sheet, "A31", "D31")
    flow_min, flow_max, flow_unit = parse_flow_range(requested_range)
    result = {
        "request_number": request_number,
        "revision": revision_match.group(1) if revision_match else footer,
        "request_date": _inline_answer(sheet["E8"].value),
        "company_name": _cell_answer(sheet, "A8", "B8"),
        "meter_end_user": _cell_answer(sheet, "A9", "B9"),
        "address": _cell_answer(sheet, "A10", "B10"),
        "city": _cell_answer(sheet, "A11", "B11"),
        "state": _inline_answer(sheet["D11"].value),
        "country": _inline_answer(sheet["E11"].value),
        "meter_type": _cell_answer(sheet, "A13", "C13", other_cell="D13"),
        "communication_mode": _cell_answer(sheet, "A14", "C14", other_cell="D14"),
        "meter_size": _cell_answer(sheet, "A15", "C15", other_cell="D15"),
        "serial_number": _cell_answer(sheet, "A16", "C16"),
        "flange_class": _cell_answer(sheet, "A17", "C17", other_cell="D17"),
        "manufacturer": _cell_answer(sheet, "A18", "C18"),
        "model_number": _inline_answer(sheet["D18"].value) or _text(sheet["E18"].value),
        "maximum_flowrate": _cell_answer(sheet, "A20", "C20"),
        "flow_point_count": _integer(_cell_answer(sheet, "A21", "C21")),
        "run_count": _integer(_inline_answer(sheet["D21"].value) or _text(sheet["E21"].value)),
        "meter_use": _cell_answer(sheet, "A22", "C22", other_cell="D22"),
        "witness_required": _cell_answer(sheet, "A23", "C23"),
        "service_type": _cell_answer(sheet, "A25", "C25"),
        "service_description": _inline_answer(sheet["A28"].value),
        "requested_procedure": _cell_answer(sheet, "A30", "D30"),
        "requested_flow_range": requested_range,
        "flow_min": flow_min,
        "flow_max": flow_max,
        "flow_unit": flow_unit,
        "conformity_required": _yes(_cell_answer(sheet, "A32", "D32")),
        "decision_rule_code": _cell_answer(sheet, "A33", "D33"),
        "acceptance_limits": acceptance,
        "lower_tolerance": lower,
        "upper_tolerance": upper,
        "tolerance_unit": unit,
        "contact_name": _inline_answer(sheet["A36"].value),
        "contact_phone": _inline_answer(sheet["C36"].value),
        "contact_email": _inline_answer(sheet["D36"].value),
        "file_hash": hashlib.sha256(raw).hexdigest(),
        "original_filename": Path(upload.filename or "service-request.xlsx").name,
    }
    return result


def _integer(value: Any) -> int | None:
    match = re.search(r"\d+", _text(value))
    return int(match.group()) if match else None


def next_assessment_uid(connection) -> str:
    prefix = f"CA-{date.today().year}-"
    count = connection.execute(
        "SELECT COUNT(*) FROM conformity_assessments WHERE assessment_uid LIKE ?", (prefix + "%",)
    ).fetchone()[0]
    return f"{prefix}{count + 1:04d}"


def calculate_dr02_point(error: float, uncertainty: float, lower: float, upper: float) -> dict[str, Any]:
    error, uncertainty, lower, upper = map(float, (error, uncertainty, lower, upper))
    if uncertainty < 0:
        raise ValueError("Expanded uncertainty cannot be negative.")
    if lower >= upper:
        raise ValueError("Lower tolerance must be less than upper tolerance.")
    lower_acceptance = lower + uncertainty
    upper_acceptance = upper - uncertainty
    passed = lower_acceptance <= upper_acceptance and lower_acceptance <= error <= upper_acceptance
    if passed:
        rationale = "The reported error is within the guarded acceptance interval."
    elif lower <= error <= upper:
        rationale = "The result is within the specification limit but does not meet the guarded acceptance criterion."
    else:
        rationale = "The reported error is outside the specification limit and guarded acceptance interval."
    return {
        "lower_acceptance": lower_acceptance,
        "upper_acceptance": upper_acceptance,
        "decision": "PASS" if passed else "FAIL",
        "rationale": rationale,
    }


def approved_uncertainty_points(connection, job_id: int, calculation_id: int | None = None):
    if calculation_id:
        calculation = connection.execute(
            """SELECT id,calculation_uid,revision,snapshot_json,approved_by,approved_at
               FROM uncertainty_calculations WHERE id=? AND job_id=? AND status='Approved'""",
            (calculation_id, job_id),
        ).fetchone()
    else:
        calculation = connection.execute(
            """SELECT id,calculation_uid,revision,snapshot_json,approved_by,approved_at
               FROM uncertainty_calculations WHERE job_id=? AND status='Approved'
               ORDER BY revision DESC,approved_at DESC,id DESC LIMIT 1""",
            (job_id,),
        ).fetchone()
    if not calculation:
        raise ValueError("Select a Job with an approved uncertainty calculation.")
    points = connection.execute(
        """SELECT fp.id,fp.point_order,fp.nominal_flow,fp.flow_unit,
                  pr.mean_error,pr.expanded_uncertainty
           FROM uncertainty_flow_points fp
           JOIN uncertainty_point_results pr ON pr.flow_point_id=fp.id
           WHERE fp.calculation_id=? ORDER BY fp.point_order""",
        (calculation[0],),
    ).fetchall()
    if not points:
        raise ValueError("The approved uncertainty calculation has no calculated flow-point results.")
    for point in points:
        if point[4] is None or point[5] is None:
            raise ValueError("Every selected flow point requires an approved error and expanded uncertainty.")
    return calculation, points


def build_assessment(connection, job_id: int, calculation_id: int | None, lower: float, upper: float,
                     tolerance_unit: str, specification_reference: str, specification_revision: str,
                     specification_clause: str, rule_revision: str, actor: str) -> int:
    calculation, points = approved_uncertainty_points(connection, job_id, calculation_id)
    revision = connection.execute(
        "SELECT COALESCE(MAX(revision),0)+1 FROM conformity_assessments WHERE job_id=?", (job_id,)
    ).fetchone()[0]
    point_results = []
    for point in points:
        outcome = calculate_dr02_point(point[4], point[5], lower, upper)
        point_results.append({
            "flow_point_id": point[0], "point_order": point[1], "flow_value": point[2],
            "flow_unit": point[3], "error_percent": point[4], "expanded_uncertainty": point[5],
            "lower_tolerance": lower, "upper_tolerance": upper, **outcome,
        })
    overall = "PASS" if all(point["decision"] == "PASS" for point in point_results) else "FAIL"
    if overall == "PASS":
        statement = ("All reported calibration points conform to the specified requirement when the stated "
                     "expanded measurement uncertainty and Decision Rule DR-02 are applied.")
    else:
        statement = ("One or more reported calibration points did not meet the guarded acceptance criterion. "
                     "Refer to the calibration results for the decision at each flow point.")
    snapshot = {
        "rule": {"code": RULE_CODE, "name": RULE_NAME, "revision": rule_revision, "formula": RULE_FORMULA},
        "uncertainty": {"id": calculation[0], "uid": calculation[1], "revision": calculation[2],
                        "approved_by": calculation[4], "approved_at": calculation[5]},
        "specification": {"reference": specification_reference, "revision": specification_revision,
                          "clause": specification_clause, "lower": lower, "upper": upper,
                          "unit": tolerance_unit},
        "points": point_results, "overall_decision": overall, "statement": statement,
    }
    cursor = connection.execute(
        """INSERT INTO conformity_assessments
           (assessment_uid,job_id,uncertainty_calculation_id,revision,status,rule_code,rule_revision,
            specification_reference,specification_revision,specification_clause,lower_tolerance,
            upper_tolerance,tolerance_unit,overall_decision,statement_text,snapshot_json,created_by)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (next_assessment_uid(connection), job_id, calculation[0], revision, "Draft", RULE_CODE,
         rule_revision, specification_reference, specification_revision, specification_clause,
         lower, upper, tolerance_unit, overall, statement, json.dumps(snapshot), actor),
    )
    assessment_id = cursor.lastrowid
    connection.executemany(
        """INSERT INTO conformity_assessment_points
           (assessment_id,uncertainty_flow_point_id,point_order,flow_value,flow_unit,error_percent,
            expanded_uncertainty,lower_tolerance,upper_tolerance,lower_acceptance,upper_acceptance,
            decision,rationale) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(assessment_id, p["flow_point_id"], p["point_order"], p["flow_value"], p["flow_unit"],
          p["error_percent"], p["expanded_uncertainty"], p["lower_tolerance"], p["upper_tolerance"],
          p["lower_acceptance"], p["upper_acceptance"], p["decision"], p["rationale"])
         for p in point_results],
    )
    return assessment_id


def load_cover_data(connection, assessment_id: int) -> dict[str, Any]:
    row = connection.execute(
        """SELECT ca.id,ca.assessment_uid,ca.status,ca.rule_code,ca.rule_revision,
                  ca.specification_reference,ca.specification_revision,ca.specification_clause,
                  ca.lower_tolerance,ca.upper_tolerance,ca.tolerance_unit,ca.overall_decision,
                  ca.statement_text,ca.approved_by,ca.approved_at,j.id,j.job_number,j.job_title,
                  c.customer_name,j.mut_description,j.mut_serial_number,j.manufacturer,j.model_number,
                  j.meter_type,j.meter_size,j.flow_min,j.flow_max,j.flow_unit,j.fluid_medium,
                  m.method_name,uc.calculation_uid,uc.revision,uc.coverage_factor,
                  COALESCE(lsr.request_number,''),COALESCE(lsr.revision,''),COALESCE(lsr.address,''),
                  COALESCE(lsr.city,''),COALESCE(lsr.state,''),COALESCE(lsr.country,''),
                  COALESCE(lsr.request_date,''),COALESCE(lsr.file_path,'')
           FROM conformity_assessments ca JOIN calibration_jobs j ON j.id=ca.job_id
           LEFT JOIN customers c ON c.id=j.customer_id LEFT JOIN calibration_methods m ON m.id=j.method_id
           JOIN uncertainty_calculations uc ON uc.id=ca.uncertainty_calculation_id
           LEFT JOIN lab_service_requests lsr ON lsr.id=(SELECT id FROM lab_service_requests
               WHERE job_id=j.id ORDER BY id DESC LIMIT 1)
           WHERE ca.id=? AND ca.is_deleted=0""", (assessment_id,)
    ).fetchone()
    if not row:
        raise ValueError("Conformity assessment was not found.")
    points = connection.execute(
        """SELECT point_order,flow_value,flow_unit,error_percent,expanded_uncertainty,
                  lower_tolerance,upper_tolerance,lower_acceptance,upper_acceptance,decision,rationale
           FROM conformity_assessment_points WHERE assessment_id=? ORDER BY point_order""",
        (assessment_id,),
    ).fetchall()
    keys = ("assessment_id","assessment_uid","status","rule_code","rule_revision","specification_reference",
            "specification_revision","specification_clause","lower_tolerance","upper_tolerance","tolerance_unit",
            "overall_decision","statement_text","approved_by","approved_at","job_id","job_number","job_title",
            "customer_name","mut_description","mut_serial_number","manufacturer","model_number","meter_type",
            "meter_size","flow_min","flow_max","flow_unit","fluid_medium","method_name","calculation_uid",
            "calculation_revision","coverage_factor","service_request_number","service_request_revision","address",
            "city","state","country","request_date","service_request_path")
    data = dict(zip(keys, row))
    point_keys = ("point_order","flow_value","flow_unit","error_percent","expanded_uncertainty",
                  "lower_tolerance","upper_tolerance","lower_acceptance","upper_acceptance","decision","rationale")
    data["points"] = [dict(zip(point_keys, point)) for point in points]
    data["conformity_required"] = True
    return data


def load_cover_data_without_conformity(connection, job_id: int) -> dict[str, Any]:
    """Load cover data for a Job where a conformity statement was not requested."""
    row = connection.execute(
        """SELECT j.id,j.job_number,j.job_title,c.customer_name,j.mut_description,
                  j.mut_serial_number,j.manufacturer,j.model_number,j.meter_type,j.meter_size,
                  j.flow_min,j.flow_max,j.flow_unit,j.fluid_medium,m.method_name,
                  uc.id,uc.calculation_uid,uc.revision,uc.coverage_factor,
                  COALESCE(lsr.request_number,''),COALESCE(lsr.revision,''),COALESCE(lsr.address,''),
                  COALESCE(lsr.city,''),COALESCE(lsr.state,''),COALESCE(lsr.country,''),
                  COALESCE(lsr.request_date,''),COALESCE(lsr.file_path,'')
           FROM calibration_jobs j
           LEFT JOIN customers c ON c.id=j.customer_id
           LEFT JOIN calibration_methods m ON m.id=j.method_id
           JOIN uncertainty_calculations uc ON uc.id=(SELECT id FROM uncertainty_calculations
               WHERE job_id=j.id AND status='Approved' ORDER BY revision DESC,approved_at DESC,id DESC LIMIT 1)
           LEFT JOIN lab_service_requests lsr ON lsr.id=(SELECT id FROM lab_service_requests
               WHERE job_id=j.id ORDER BY id DESC LIMIT 1)
           WHERE j.id=? AND j.is_deleted=0 AND COALESCE(j.conformity_required,0)=0""", (job_id,)
    ).fetchone()
    if not row:
        raise ValueError("This Job either requires a Decision Rule or has no approved uncertainty calculation.")
    keys = ("job_id","job_number","job_title","customer_name","mut_description","mut_serial_number",
            "manufacturer","model_number","meter_type","meter_size","flow_min","flow_max","flow_unit",
            "fluid_medium","method_name","uncertainty_calculation_id","calculation_uid","calculation_revision",
            "coverage_factor","service_request_number","service_request_revision","address","city","state",
            "country","request_date","service_request_path")
    data = dict(zip(keys, row))
    points = connection.execute(
        """SELECT fp.point_order,fp.nominal_flow,fp.flow_unit,pr.mean_error,pr.expanded_uncertainty
           FROM uncertainty_flow_points fp JOIN uncertainty_point_results pr ON pr.flow_point_id=fp.id
           WHERE fp.calculation_id=? ORDER BY fp.point_order""", (data["uncertainty_calculation_id"],)
    ).fetchall()
    data.update({"assessment_id": None, "assessment_uid": "NOT-REQUIRED", "status": "Approved",
        "rule_code": "N/A", "rule_revision": "", "specification_reference": "",
        "specification_revision": "", "specification_clause": "", "lower_tolerance": None,
        "upper_tolerance": None, "tolerance_unit": "", "overall_decision": "NOT REQUIRED",
        "statement_text": "A statement of conformity was not requested for this Job; no decision rule was applied.",
        "approved_by": "", "approved_at": "", "conformity_required": False})
    data["points"] = [{"point_order": p[0], "flow_value": p[1], "flow_unit": p[2],
        "error_percent": p[3], "expanded_uncertainty": p[4], "decision": "NOT APPLICABLE"} for p in points]
    return data


def _report_directory() -> Path:
    target = Path("data/documents/generated-covers")
    target.mkdir(parents=True, exist_ok=True)
    return target


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_excel_cover(data: dict[str, Any], template_path: Path) -> Path:
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    if not template_path.is_file():
        raise ValueError("The controlled REPORT COVER.xlsx template is not configured.")
    workbook = load_workbook(template_path)
    sheet = workbook[workbook.sheetnames[0]]
    sheet["F4"] = data["job_number"]
    sheet["F5"] = date.today().strftime("%d-%m-%Y")
    sheet["I7"] = data["customer_name"] or ""
    sheet["I8"] = ", ".join(value for value in (data["address"], data["city"], data["state"], data["country"]) if value)
    sheet["I12"] = data["meter_type"] or ""
    sheet["I13"] = data["meter_size"] or ""
    sheet["I14"] = data["manufacturer"] or ""
    sheet["I15"] = data["model_number"] or ""
    sheet["I16"] = data["mut_serial_number"] or ""
    sheet["I18"] = f"{data['flow_min']} - {data['flow_max']} {data['flow_unit']}"
    sheet["I21"] = data["method_name"] or ""

    for merged in list(sheet.merged_cells.ranges):
        if merged.min_row <= 42 and merged.max_row >= 32:
            sheet.unmerge_cells(str(merged))
    for row in range(32, 43):
        for column in range(2, 16):
            sheet.cell(row, column).value = None
    dark = "123047"; light = "EAF2F5"; border = Side(style="thin", color="C9D7DF")
    sheet.merge_cells("B32:O32"); sheet["B32"] = "CALIBRATION RESULT AND CONFORMITY"
    sheet["B32"].font = Font(bold=True, color="FFFFFF", size=11)
    sheet["B32"].fill = PatternFill("solid", fgColor=dark); sheet["B32"].alignment = Alignment(vertical="center")
    headers = ("Flow point", "Error", "Expanded U", "MPE", "Acceptance limit", "Decision")
    starts = (2, 5, 7, 9, 11, 14); widths = (3, 2, 2, 2, 3, 2)
    for start, width, header in zip(starts, widths, headers):
        end = start + width - 1; sheet.merge_cells(start_row=33,start_column=start,end_row=33,end_column=end)
        cell=sheet.cell(33,start); cell.value=header; cell.font=Font(bold=True,color=dark,size=8)
        cell.fill=PatternFill("solid",fgColor=light); cell.alignment=Alignment(horizontal="center")
    visible_points = data["points"][:5]
    tolerance_unit = data["tolerance_unit"] or "%"
    for offset, point in enumerate(visible_points, 34):
        mpe = (f"{point['lower_tolerance']:.4g}{tolerance_unit} to {point['upper_tolerance']:.4g}{tolerance_unit}"
               if data.get("conformity_required") else "Not requested")
        acceptance = (f"{point['lower_acceptance']:.4g}{tolerance_unit} to {point['upper_acceptance']:.4g}{tolerance_unit}"
                      if data.get("conformity_required") else "Not applicable")
        values = (f"{point['flow_value']:g} {point['flow_unit']}", f"{point['error_percent']:+.4g}%",
                  f"{point['expanded_uncertainty']:.4g}%", mpe, acceptance, point["decision"])
        for start, width, value in zip(starts, widths, values):
            end=start+width-1; sheet.merge_cells(start_row=offset,start_column=start,end_row=offset,end_column=end)
            cell=sheet.cell(offset,start); cell.value=value; cell.alignment=Alignment(horizontal="center",vertical="center")
            cell.font=Font(bold=start==14,size=8,color="A52828" if value=="FAIL" else "123047")
    detail_row = 34 + len(visible_points)
    if len(data["points"]) > 5:
        sheet.merge_cells(start_row=detail_row,start_column=2,end_row=detail_row,end_column=15)
        sheet.cell(detail_row,2).value=f"{len(data['points']) - 5} additional points are retained in the approved conformity assessment."
        detail_row += 1
    sheet.merge_cells(start_row=detail_row,start_column=2,end_row=detail_row,end_column=5)
    sheet.cell(detail_row,2).value="Decision rule"
    sheet.merge_cells(start_row=detail_row,start_column=6,end_row=detail_row,end_column=15)
    sheet.cell(detail_row,6).value=(f"{data['rule_code']} Rev. {data['rule_revision'] or 'TBC'} - Guarded acceptance, w=U"
        if data.get("conformity_required") else "Not applicable - conformity statement not requested")
    detail_row += 1
    sheet.merge_cells(start_row=detail_row,start_column=2,end_row=detail_row,end_column=5)
    sheet.cell(detail_row,2).value="Statement"
    sheet.merge_cells(start_row=detail_row,start_column=6,end_row=min(42,detail_row+1),end_column=15)
    sheet.cell(detail_row,6).value=data["statement_text"]
    sheet.cell(detail_row,6).alignment=Alignment(wrap_text=True,vertical="top")
    for row in sheet.iter_rows(min_row=32,max_row=42,min_col=2,max_col=15):
        for cell in row:
            cell.border=Border(left=border,right=border,top=border,bottom=border)
            if cell.row > 32 and cell.font == Font(): cell.font=Font(size=8,color="123047")
    sheet.oddFooter.center.text = "Page &P of &N"
    output = _report_directory() / f"{data['job_number']}_{data['assessment_uid']}_cover.xlsx"
    workbook.save(output)
    return output


def generate_pdf_cover(data: dict[str, Any]) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = _report_directory() / f"{data['job_number']}_{data['assessment_uid']}_cover.pdf"
    navy=colors.HexColor("#123047"); light=colors.HexColor("#EAF2F5"); line=colors.HexColor("#C9D7DF")
    styles=getSampleStyleSheet()
    cell=ParagraphStyle("coverCell",parent=styles["Normal"],fontName="Helvetica",fontSize=8,leading=10,textColor=navy)
    bold=ParagraphStyle("coverBold",parent=cell,fontName="Helvetica-Bold")
    title=ParagraphStyle("coverTitle",parent=bold,fontSize=16,leading=19,alignment=1)
    section_style=ParagraphStyle("coverSection",parent=bold,textColor=colors.white,fontSize=9)
    p=lambda value,style=cell: Paragraph(str(value or ""),style)
    def section(value):
        return Table([[p(value,section_style)]],colWidths=[174*mm],style=TableStyle([("BACKGROUND",(0,0),(-1,-1),navy),("LEFTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    def details(rows):
        return Table([[p(a,bold),p(b)] for a,b in rows],colWidths=[45*mm,129*mm],style=TableStyle([("GRID",(0,0),(-1,-1),.35,line),("BACKGROUND",(0,0),(0,-1),light),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    doc=SimpleDocTemplate(str(output),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=15*mm,bottomMargin=15*mm)
    story=[p("ENGINEERING AUTOMATION TECHNOLOGY LIMITED",title),p("METERING LABORATORY",ParagraphStyle("lab",parent=bold,alignment=1,textColor=colors.HexColor("#087F83"))),Spacer(1,4*mm),p("CERTIFICATE OF CALIBRATION",title),Spacer(1,4*mm),section("CERTIFICATE IDENTIFICATION"),details([
        ("Certificate / Job",data["job_number"]),("Assessment",f"{data['assessment_uid']} Rev. {data['calculation_revision']}"),("Date of issue",date.today().strftime("%d/%m/%Y")),("Service request",f"{data['service_request_number']} Rev. {data['service_request_revision']}"),
    ]),Spacer(1,2*mm),section("CUSTOMER AND INSTRUMENT"),details([
        ("Equipment owner",data["customer_name"]),("Address",", ".join(v for v in (data["address"],data["city"],data["state"],data["country"]) if v)),("Instrument",f"{data['meter_type']} - {data['mut_description']}"),("Manufacturer / model",f"{data['manufacturer']} / {data['model_number']}"),("Serial / size",f"{data['mut_serial_number']} / {data['meter_size']}"),("Flow range",f"{data['flow_min']} - {data['flow_max']} {data['flow_unit']}"),
    ]),Spacer(1,2*mm),section("CALIBRATION RESULT AND CONFORMITY")]
    point_rows=[[p(x,bold) for x in ("Flow point","Error","Expanded U","MPE","Acceptance limit","Decision")]]
    tolerance_unit = data["tolerance_unit"] or "%"
    for point in data["points"]:
        mpe = f"{point['lower_tolerance']:.4g}{tolerance_unit} to {point['upper_tolerance']:.4g}{tolerance_unit}" if data.get("conformity_required") else "Not requested"
        acceptance = f"{point['lower_acceptance']:.4g}{tolerance_unit} to {point['upper_acceptance']:.4g}{tolerance_unit}" if data.get("conformity_required") else "Not applicable"
        point_rows.append([p(f"{point['flow_value']:g} {point['flow_unit']}"),p(f"{point['error_percent']:+.4g}%"),p(f"{point['expanded_uncertainty']:.4g}%"),p(mpe),p(acceptance),p(point["decision"],bold)])
    story += [Table(point_rows,colWidths=[31*mm,22*mm,25*mm,32*mm,39*mm,25*mm],repeatRows=1,style=TableStyle([("GRID",(0,0),(-1,-1),.35,line),("BACKGROUND",(0,0),(-1,0),light),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)])),Spacer(1,2*mm),details([
        ("Specification",f"{data['specification_reference']} {data['specification_revision']} {data['specification_clause']}" if data.get("conformity_required") else "Conformity statement not requested"),("Uncertainty",f"Approved calculation {data['calculation_uid']} Rev. {data['calculation_revision']}; expanded uncertainty stated at each point."),("Decision rule",f"{data['rule_code']} Rev. {data['rule_revision'] or 'TBC'}. Guarded acceptance with w=U." if data.get("conformity_required") else "Not applicable"),("Statement",data["statement_text"]),("Overall conformity",data["overall_decision"]),("Approved by",f"{data['approved_by'] or ''} {data['approved_at'] or ''}"),
    ])]
    def footer(canvas, document):
        canvas.saveState(); canvas.setFont("Helvetica",7); canvas.setFillColor(colors.HexColor("#526A79")); canvas.drawString(18*mm,8*mm,"Generated by FlowLab Pro from approved controlled records"); canvas.drawRightString(192*mm,8*mm,f"Page {document.page}"); canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return output


def register_generated_cover(connection, data: dict[str, Any], output: Path, actor: str) -> int:
    digest = _file_digest(output)
    cursor = connection.execute(
        """INSERT INTO generated_report_covers
           (cover_uid,job_id,assessment_id,output_format,original_filename,file_path,file_hash,generated_by)
           VALUES (?,?,?,?,?,?,?,?)""",
        (f"COVER-{uuid4().hex[:12].upper()}",data["job_id"],data.get("assessment_id"),output.suffix[1:].upper(),
         output.name,str(output),digest,actor),
    )
    return cursor.lastrowid
