"""Database-backed GUM uncertainty workflow used by the FlowLab Pro web UI."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
import json
from math import inf, sqrt
from statistics import mean, stdev

from app.modules.uncertainty.engine import GUMEngine, TypeAProcessor, UncertaintyInput


CALCULATION_TYPES = {
    "mutGrav": ("MUT · Gravimetric", "Gravimetric Method", False),
    "mutCor": ("MUT · Coriolis Master Meter", "Coriolis Comparison Method", False),
    "cmcGrav": ("CMC · Gravimetric", "Gravimetric Method", True),
    "cmcCor": ("CMC · Coriolis Master Meter", "Coriolis Comparison Method", True),
}

SOURCE_TEMPLATES = {
    "mutGrav": ("Weighing system calibration", "Weighing resolution", "Timer calibration",
        "Timer resolution", "Diverter timing", "Density", "Temperature", "Pressure",
        "Buoyancy", "Evaporation", "Leakage", "Flow stability", "Reproducibility"),
    "cmcGrav": ("Weighing system calibration", "Weighing resolution", "Timer calibration",
        "Timer resolution", "Diverter timing", "Density", "Temperature", "Pressure",
        "Buoyancy", "Evaporation", "Leakage", "Flow stability", "Reproducibility"),
    "mutCor": ("Master-meter calibration", "Correction curve", "Resolution", "Drift",
        "Zero stability", "Repeatability", "Reproducibility", "Temperature effect",
        "Pressure effect", "Synchronization", "DAQ", "Pulse counting", "Installation",
        "Density compensation"),
    "cmcCor": ("Master-meter calibration", "Correction curve", "Resolution", "Drift",
        "Zero stability", "Repeatability", "Reproducibility", "Temperature effect",
        "Pressure effect", "Synchronization", "DAQ", "Pulse counting", "Installation",
        "Density compensation"),
}


def hydrate_job_metadata(connection, payload):
    job_id = payload.get("jobId")
    row = connection.execute("""SELECT j.id,j.job_number,j.job_title,j.status,c.customer_name,
        COALESCE(p.project_number,''),COALESCE(p.project_name,''),j.mut_description,
        COALESCE(j.mut_asset_id,e.asset_number,''),COALESCE(j.mut_serial_number,e.serial_number,''),
        COALESCE(j.manufacturer,e.manufacturer,''),COALESCE(j.model_number,e.model,''),
        j.meter_type,j.flow_min,j.flow_max,j.flow_unit,j.fluid_medium,j.calibration_quantity,
        j.engineer_operator,m.method_name,COALESCE(j.flow_point_count,1)
        FROM calibration_jobs j LEFT JOIN customers c ON c.id=j.customer_id
        LEFT JOIN laboratory_equipment e ON e.id=j.equipment_id
        LEFT JOIN calibration_methods m ON m.id=j.method_id
        LEFT JOIN project_jobs pj ON pj.job_id=j.id LEFT JOIN projects p ON p.id=pj.project_id
        WHERE j.id=? AND j.is_deleted=0""", (job_id,)).fetchone()
    if not row:
        raise ValueError("Select an available Job before calculating.")
    if row[3] == "Completed":
        raise ValueError("Job Completed: this Job has already been completed and is locked. Request HOD authorization from the Job record.")
    expected = "mutGrav" if "gravimetric" in (row[19] or "").lower() else \
        "mutCor" if "coriolis" in (row[19] or "").lower() else None
    if expected and payload.get("calculationType") != expected:
        raise ValueError(f"The selected Job uses {row[19]}; open the matching MUT calculation type.")
    payload.update(jobNumber=row[1], jobTitle=row[2] or "", jobStatus=row[3], customer=row[4] or "",
        projectNumber=row[5], projectName=row[6], mut=row[7] or "", mutAssetId=row[8],
        serialNumber=row[9], manufacturer=row[10], model=row[11], meterType=row[12] or "",
        rangeMin=row[13], rangeMax=row[14], rangeUnit=row[15] or "", fluid=row[16] or "",
        quantity=row[17] or payload.get("quantity") or "mass", analyst=row[18] or payload.get("analyst") or "",
        jobMethod=row[19] or "", flowPointCount=max(1, int(row[20] or 1)))
    return row


def equipment_rows(connection):
    return connection.execute("""SELECT e.id,e.asset_number,e.equipment_name,
        COALESCE(e.serial_number,''),COALESCE(e.manufacturer,''),COALESCE(e.model,''),
        ec.operating_range_min,ec.operating_range_max,COALESCE(ec.operating_unit,''),
        e.last_calibration_date,e.next_calibration_date,e.status,e.is_active,
        p.id,p.certificate_number,p.standard_uncertainty,p.expanded_uncertainty,
        p.coverage_factor,COALESCE(p.resolution,ec.resolution),p.drift,
        COALESCE(p.certificate_path,e.certificate_path),COALESCE(ec.accuracy_class,''),
        COALESCE(p.source_name,e.equipment_name || ' calibration uncertainty'),
        COALESCE(p.uncertainty_unit,ec.operating_unit,''),COALESCE(p.evaluation_basis,''),
        COALESCE(p.distribution,''),p.divisor,COALESCE(p.sensitivity,1),p.degrees_of_freedom,
        COALESCE(p.version,''),(SELECT ch.id FROM calibration_history ch WHERE ch.equipment_id=e.id
            AND ch.status='Approved' AND ch.is_deleted=0 ORDER BY ch.calibration_date DESC,ch.id DESC LIMIT 1)
        FROM laboratory_equipment e
        LEFT JOIN equipment_capabilities ec ON ec.equipment_id=e.id
        LEFT JOIN uncertainty_profiles p ON p.equipment_id=e.id AND p.is_active=1
        WHERE e.is_active=1 AND e.is_reference_standard=1
          AND e.record_status='Approved' AND p.id IS NOT NULL
          AND TRIM(COALESCE(p.uncertainty_unit,''))<>''
          AND p.evaluation_basis IN ('standard','expanded')
          AND p.divisor IS NOT NULL AND p.sensitivity IS NOT NULL
        ORDER BY e.equipment_name""").fetchall()


def equipment_dict(row):
    keys = ("id", "asset_number", "name", "serial_number", "manufacturer", "model",
        "range_min", "range_max", "range_unit", "calibration_date", "due_date", "status",
        "is_active", "profile_id", "certificate_number", "standard_uncertainty",
        "expanded_uncertainty", "coverage_factor", "resolution", "drift",
        "certificate_path", "accuracy", "source_name", "uncertainty_unit",
        "evaluation_basis", "distribution", "divisor", "sensitivity",
        "degrees_of_freedom", "version", "calibration_record_id")
    equipment = dict(zip(keys, row))
    basis = equipment.get("evaluation_basis") or (
        "expanded" if equipment.get("expanded_uncertainty") is not None else "standard")
    value = (equipment.get("expanded_uncertainty") if basis == "expanded"
        else equipment.get("standard_uncertainty"))
    divisor = equipment.get("divisor") or (
        equipment.get("coverage_factor") if basis == "expanded" else 1)
    equipment["source_properties"] = {"calibration_uncertainty": {
        "name": equipment.get("source_name"), "value": value,
        "unit": equipment.get("uncertainty_unit"), "basis": basis,
        "distribution": (equipment.get("distribution") or "Normal").lower(),
        "certK": equipment.get("coverage_factor") if basis == "expanded" else None,
        "divisor": divisor, "standardUncertainty": equipment.get("standard_uncertainty"),
        "contribution": ((equipment.get("standard_uncertainty") or 0) *
            (equipment.get("sensitivity") or 1)),
        "sensitivity": equipment.get("sensitivity") or 1,
        "dof": equipment.get("degrees_of_freedom"),
        "evidence": equipment.get("certificate_number") or equipment.get("certificate_path"),
    }}
    return equipment


def _number(value, label, required=True):
    if value in (None, ""):
        if required:
            raise ValueError(f"{label}: enter a value.")
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label}: enter a valid number.") from error


def _equipment_source(connection, source, nominal_flow):
    equipment_id = source.get("equipmentId")
    if not equipment_id:
        return None
    row = connection.execute("""SELECT e.id,e.asset_number,e.equipment_name,
        e.next_calibration_date,e.status,e.is_active,e.certificate_path,
        ec.operating_range_min,ec.operating_range_max,ec.operating_unit,
        COALESCE(CAST(ec.accuracy_value AS TEXT),ec.accuracy_class),ec.resolution,p.certificate_number,p.standard_uncertainty,
        p.expanded_uncertainty,p.coverage_factor,p.resolution,p.drift,p.version,p.certificate_path
        ,ec.tolerance,(SELECT ch.id FROM calibration_history ch WHERE ch.equipment_id=e.id
            AND ch.is_deleted=0 ORDER BY ch.calibration_date DESC,ch.id DESC LIMIT 1)
        ,p.source_name,p.uncertainty_unit,p.evaluation_basis,p.distribution,p.divisor,
        p.sensitivity,p.degrees_of_freedom
        FROM laboratory_equipment e
        LEFT JOIN equipment_capabilities ec ON ec.equipment_id=e.id
        LEFT JOIN uncertainty_profiles p ON p.equipment_id=e.id AND p.is_active=1
        WHERE e.id=?""", (equipment_id,)).fetchone()
    if not row or not row[5] or str(row[4]).lower() != "active":
        raise ValueError(f"{source.get('name')}: selected equipment is inactive.")
    if row[13] is None and row[14] is None:
        raise ValueError(f"{row[1]} {row[2]}: no approved active uncertainty profile is available.")
    due = row[3]
    if not due:
        raise ValueError(f"{row[1]} {row[2]}: calibration due date is missing.")
    if due < date.today().isoformat():
        formatted = datetime.strptime(due, "%Y-%m-%d").strftime("%d %B %Y")
        raise ValueError(f"{row[2]} {row[1]} calibration expired on {formatted}.")
    certificate = row[12] or row[6] or row[19]
    if not certificate:
        raise ValueError(f"{row[1]} {row[2]}: a calibration certificate is required.")
    if row[7] is not None and row[8] is not None and not row[7] <= nominal_flow <= row[8]:
        raise ValueError(f"{row[1]} {row[2]} is outside its valid range at {nominal_flow:g} {row[9] or ''}.")
    prop = source.get("equipmentProperty", "calibration_uncertainty")
    values = {
        "calibration_uncertainty": (
            row[14] if (row[24] or '').lower() == "expanded" else row[13],
            row[24] or ("standard" if row[13] is not None else "expanded"),
            row[15] if (row[24] or '').lower() == "expanded" else None),
        "resolution": (row[16] if row[16] is not None else row[11], "resolution", None),
        "accuracy": (row[10], "limit", None),
        "tolerance": (row[20], "limit", None),
        "drift": (row[17], "standard", None),
    }
    if prop == "other":
        return {"evidence": certificate, "equipmentAsset": row[1], "equipmentId": row[0],
            "equipmentVersion": row[18], "calibrationRecordId": row[21]}
    value, basis, certificate_k = values.get(prop, (None, None, None))
    if prop == "accuracy" and isinstance(value, str):
        try:
            value = float(value.strip().rstrip("%"))
        except ValueError:
            value = None
    if value is None:
        raise ValueError(f"{row[1]} {row[2]}: {prop.replace('_', ' ')} is missing.")
    return {"name":row[22] or source.get("name"),"value": value, "basis": basis,
        "unit":row[23] or source.get("unit"),"distribution":row[25] or source.get("distribution"),
        "divisor":row[26],"sensitivity":row[27] if row[27] is not None else source.get("sensitivity"),
        "dof":row[28] if row[28] is not None else source.get("dof"),"certK": certificate_k,
        "evidence": certificate, "equipmentAsset": row[1], "equipmentId": row[0],
        "equipmentVersion": row[18], "calibrationRecordId": row[21]}


def _standardize_source(connection, source, nominal_flow):
    equipment = _equipment_source(connection, source, nominal_flow)
    if equipment:
        source = source | equipment
    name = (source.get("name") or "").strip()
    if not name:
        raise ValueError("Uncertainty source: enter a source name.")
    value = _number(source.get("value"), name)
    unit = (source.get("unit") or "").strip()
    if not unit:
        raise ValueError(f"{name}: select the unit of the entered uncertainty.")
    basis = (source.get("basis") or "").lower()
    if not basis:
        raise ValueError(f"{name}: select the evaluation basis.")
    distribution = (source.get("distribution") or "").lower()
    cert_k = _number(source.get("certK"), f"{name} certificate k", False)
    if basis == "standard":
        divisor, distribution_name = 1.0, "Normal"
    elif basis == "expanded":
        if not cert_k or cert_k <= 0:
            raise ValueError(f"{name}: enter the certificate coverage factor k.")
        divisor, distribution_name = cert_k, "Normal"
    elif basis == "resolution":
        divisor, distribution_name = sqrt(12), "Rectangular"
    elif basis == "limit":
        divisors = {"rectangular": sqrt(3), "triangular": sqrt(6), "u-shaped": sqrt(2)}
        if distribution not in divisors:
            raise ValueError(f"{name}: select Rectangular, Triangular, or U-shaped distribution.")
        divisor, distribution_name = divisors[distribution], distribution.title()
    else:
        raise ValueError(f"{name}: evaluation basis is not supported.")
    sensitivity = _number(source.get("sensitivity"), f"{name} sensitivity coefficient")
    dof = _number(source.get("dof"), f"{name} degrees of freedom", False)
    return UncertaintyInput(name, source.get("sourceType", "B"),
        "Equipment Register" if equipment else "Calculation record", value, unit,
        basis.title(), distribution_name, divisor, sensitivity,
        degrees_of_freedom=dof, equipment_id=str(source.get("equipmentId")) if source.get("equipmentId") else None,
        flow_point=nominal_flow, evidence=source.get("evidence") or None,
        source_version=source.get("equipmentVersion"), notes=source.get("notes") or None,
        calibration_record_id=source.get("calibrationRecordId"))


def calculate_payload(connection, payload):
    calculation_type = payload.get("calculationType")
    if calculation_type not in CALCULATION_TYPES:
        raise ValueError("Select one of the four supported calculation types.")
    type_label, method, is_cmc = CALCULATION_TYPES[calculation_type]
    job_row = None
    if not is_cmc:
        job_row = hydrate_job_metadata(connection, payload)
    quantity = payload.get("quantity", "mass")
    points = payload.get("points") or []
    if not points:
        raise ValueError("Add at least one flow point.")
    if job_row and not payload.get("pointOnly") and len(points) != max(1, int(job_row[20] or 1)):
        raise ValueError(
            f"This Job requires {max(1, int(job_row[20] or 1))} flow points; "
            f"the calculation currently contains {len(points)}.")
    calculated_points = []
    for index, point in enumerate(points, 1):
        nominal = _number(point.get("nominalFlow"), f"Flow point {index}")
        unit = (point.get("flowUnit") or "").strip()
        if not unit:
            raise ValueError(f"Flow point {index}: select a flow unit.")
        observations, errors = [], []
        for run_index, run in enumerate(point.get("runs") or [], 1):
            if calculation_type in {"mutGrav", "cmcGrav"}:
                evaluated = GUMEngine.gravimetric_run(
                    _number(run.get("mass"), f"Run {run_index} collected mass"),
                    _number(run.get("time"), f"Run {run_index} collection time"),
                    _number(run.get("mut"), f"Run {run_index} MUT indication"),
                    quantity, _number(run.get("density"), f"Run {run_index} density", quantity == "volume"),
                    point.get("densityUnit") or "kg/m³", unit)
            else:
                correction = _number(run.get("correction"), f"Run {run_index} master correction")
                evaluated = GUMEngine.coriolis_run(
                    _number(run.get("master"), f"Run {run_index} master indication"),
                    correction, _number(run.get("mut"), f"Run {run_index} MUT indication"),
                    run.get("correctionBasis"))
            observations.append(run | evaluated)
            errors.append(evaluated["error_percent"])
        if len(errors) < 2:
            raise ValueError(f"Flow point {index}: enter at least two repeated observations.")
        type_a, statistics = TypeAProcessor.from_observations(
            "Repeatability of calibration result", errors, "%", nominal,
            "Retained error observations; component repeatability diagnostics are not added separately")
        diagnostic_fields = (
            (("Collected mass", "mass", "kg"), ("Collection time", "time", "s"),
             ("Density / specific volume", "density", point.get("densityUnit") or "kg/m³"))
            if calculation_type in {"mutGrav", "cmcGrav"} else
            (("Master indication", "master", unit), ("Master correction", "correction", "fraction"))
        ) + (("Reference flow", "reference_flow", unit), ("MUT indication", "mut", unit),
             ("Calibration error", "error_percent", "%"))
        repeatability_diagnostics = []
        for label, key, diagnostic_unit in diagnostic_fields:
            values = [float(observation[key]) for observation in observations
                if observation.get(key) not in (None, "")]
            if not values:
                continue
            average = mean(values)
            sample_deviation = stdev(values) if len(values) > 1 else None
            standard_uncertainty = sample_deviation / sqrt(len(values)) if sample_deviation is not None else None
            repeatability_diagnostics.append({
                "quantity": label, "unit": diagnostic_unit, "n": len(values), "mean": average,
                "standard_deviation": sample_deviation, "standard_uncertainty": standard_uncertainty,
                "relative_standard_uncertainty": (abs(standard_uncertainty / average) * 100
                    if standard_uncertainty is not None and average != 0 else None),
                "treatment": ("Included as the Type A budget source" if key == "error_percent"
                    else "Diagnostic only — captured in result repeatability")})
        sources = [type_a]
        for source in point.get("sources") or []:
            if source.get("included", True):
                sources.append(_standardize_source(connection, source, nominal))
        result = GUMEngine.calculate(sources, point.get("correlations") or (),
            point.get("coverageMode", "auto"),
            _number(point.get("manualK"), "Manual coverage factor", False),
            _number(point.get("coverageProb", 95), "Coverage probability"), nominal)
        if is_cmc:
            expression = point.get("cmcExpression")
            if expression not in {"point", "constant", "a_plus_bq", "rss"}:
                raise ValueError(f"Flow point {index}: select the CMC expression.")
            if expression != "point":
                coefficient_a = _number(point.get("cmcA"), f"Flow point {index} CMC coefficient A")
                if coefficient_a < 0:
                    raise ValueError(f"Flow point {index}: CMC coefficient A must not be negative.")
                if expression in {"a_plus_bq", "rss"}:
                    coefficient_b = _number(point.get("cmcB"), f"Flow point {index} CMC coefficient B")
                    if coefficient_b < 0:
                        raise ValueError(f"Flow point {index}: CMC coefficient B must not be negative.")
        calculated_points.append({
            "index": index - 1, "label": point.get("label") or f"Point {index}",
            "nominalFlow": nominal, "flowUnit": unit, "observations": observations,
            "statistics": statistics, "repeatabilityDiagnostics": repeatability_diagnostics,
            "result": result.snapshot(),
            "cmcExpression": point.get("cmcExpression"), "cmcA": point.get("cmcA"),
            "cmcB": point.get("cmcB"), "referenceTemperature": point.get("refTemp"),
            "referencePressure": point.get("refPressure"),
            "densityUnit": point.get("densityUnit") or "kg/m³"})
    comparison = [] if is_cmc else _compare_with_approved_cmc(connection, method, calculated_points)
    return {"calculationType": calculation_type, "calculationTypeLabel": type_label,
        "method": method, "isCmc": is_cmc, "points": calculated_points,
        "cmcComparison": comparison, "calculatedAt": datetime.now().isoformat(timespec="seconds")}


def _expression_value(point, flow):
    expression = point.get("cmcExpression")
    budget_value = point.get("result", {}).get("expanded_uncertainty")
    if expression == "point":
        return budget_value if float(point.get("nominalFlow")) == float(flow) else None
    a = _number(point.get("cmcA"), "CMC coefficient A")
    if expression == "constant":
        return a
    b = _number(point.get("cmcB"), "CMC coefficient B")
    if float(flow) == 0:
        return None
    if expression == "a_plus_bq":
        return a + b / float(flow)
    if expression == "rss":
        return sqrt(a ** 2 + (b / float(flow)) ** 2)
    return None


def _compare_with_approved_cmc(connection, method, mut_points):
    row = connection.execute("""SELECT id,revision,snapshot_json FROM cmc_revisions
        WHERE method_name=? AND status='Approved' ORDER BY revision DESC LIMIT 1""", (method,)).fetchone()
    if not row:
        return []
    snapshot = json.loads(row[2]).get("backendResult", {})
    cmc_points = snapshot.get("points", [])
    comparisons = []
    for point in mut_points:
        applicable = next((value for candidate in cmc_points
            if (value := _expression_value(candidate, point["nominalFlow"])) is not None), None)
        mut_value = point["result"]["expanded_uncertainty"]
        comparisons.append({"flowPoint": point["nominalFlow"], "flowUnit": point["flowUnit"],
            "mutUncertainty": mut_value, "applicableCmc": applicable,
            "reportableUncertainty": max(mut_value, applicable) if applicable is not None else None,
            "status": ("Calculated uncertainty is below the laboratory CMC — review required."
                       if applicable is not None and mut_value < applicable else
                       "Complete" if applicable is not None else "No applicable approved CMC"),
            "cmcRecordId": row[0], "cmcRevision": row[1]})
    return comparisons


def calculation_uid(connection):
    prefix = datetime.now().strftime("UB-%Y%m%d")
    count = connection.execute("SELECT COUNT(*) FROM uncertainty_calculations WHERE calculation_uid LIKE ?",
        (prefix + "%",)).fetchone()[0]
    return f"{prefix}-{count + 1:04d}"


def save_calculation(connection, payload, result, actor):
    job_id = payload.get("jobId")
    if not job_id:
        raise ValueError("Select an existing job and MUT before saving.")
    hydrate_job_metadata(connection, payload)
    existing_id = payload.get("recordId")
    if existing_id:
        existing = connection.execute("SELECT status,revision,calculation_uid,calculated_by FROM uncertainty_calculations WHERE id=?", (existing_id,)).fetchone()
        if not existing:
            raise ValueError("Calculation record was not found.")
        if existing[0] == "Approved":
            raise ValueError("Approved calculations are locked. Create a revision to make changes.")
        if existing[0] in {"Draft","Reverted"} and existing[3] != actor:
            raise ValueError("This unfinished uncertainty draft belongs to another user.")
        calculation_id, revision, uid = int(existing_id), existing[1], existing[2]
        connection.execute("DELETE FROM uncertainty_flow_points WHERE calculation_id=?", (calculation_id,))
        connection.execute("DELETE FROM uncertainty_sources WHERE calculation_id=?", (calculation_id,))
        connection.execute("""UPDATE uncertainty_calculations SET calculation_type=?,method_name=?,
            quantity=?,fluid=?,analyst=?,snapshot_json=?,calculation_version='flp-gum-2.0',
            combined_standard_uncertainty=?,coverage_factor=?,expanded_uncertainty=?,
            calculated_by=?,last_edited_by=?,calculated_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (result["calculationTypeLabel"], result["method"], payload.get("quantity"), payload.get("fluid"),
             payload.get("analyst") or actor, json.dumps(payload | {"backendResult": result}),
             result["points"][-1]["result"]["combined_standard_uncertainty"],
             result["points"][-1]["result"]["coverage_factor"],
             result["points"][-1]["result"]["expanded_uncertainty"], actor, actor, calculation_id))
    else:
        unfinished = connection.execute("""SELECT id,calculation_uid FROM uncertainty_calculations
            WHERE job_id=? AND calculation_type=? AND status IN ('Draft','Reverted') AND calculated_by=?
            ORDER BY updated_at DESC,id DESC LIMIT 1""", (job_id, result["calculationTypeLabel"],actor)).fetchone()
        if unfinished:
            raise ValueError(f"Draft {unfinished[1]} already exists for this Job and method. Continue it from Records.")
        revision = connection.execute("SELECT COALESCE(MAX(revision),0)+1 FROM uncertainty_calculations WHERE job_id=?", (job_id,)).fetchone()[0]
        requested_uid = str(payload.get("calculationId") or "").strip()
        uid = requested_uid if requested_uid.startswith("UB-") and not connection.execute(
            "SELECT 1 FROM uncertainty_calculations WHERE calculation_uid=?", (requested_uid,)).fetchone() else calculation_uid(connection)
        last = result["points"][-1]["result"]
        calculation_id = connection.execute("""INSERT INTO uncertainty_calculations
            (job_id,revision,status,calculation_uid,calculation_type,method_name,quantity,fluid,
             analyst,final_job_rule,combined_standard_uncertainty,coverage_factor,expanded_uncertainty,
             calculation_version,snapshot_json,calculated_by,created_by,last_edited_by,calculated_at,updated_at)
            VALUES (?,?, 'Draft',?,?,?,?,?,?,'Multiple flow points',?,?,?,'flp-gum-2.0',?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""",
            (job_id, revision, uid, result["calculationTypeLabel"], result["method"], payload.get("quantity"),
             payload.get("fluid"), payload.get("analyst") or actor, last["combined_standard_uncertainty"],
             last["coverage_factor"], last["expanded_uncertainty"],
             json.dumps(payload | {"backendResult": result}), actor, actor, actor)).lastrowid
    _save_children(connection, calculation_id, payload, result, actor)
    return {"id": calculation_id, "calculationId": uid, "revision": revision, "status": "Draft"}


def save_partial_draft(connection, payload, actor):
    calculation_type = payload.get("calculationType")
    if calculation_type not in CALCULATION_TYPES:
        raise ValueError("Select a supported uncertainty calculation before saving the draft.")
    if CALCULATION_TYPES[calculation_type][2]:
        method = CALCULATION_TYPES[calculation_type][1]; existing_id = payload.get("recordId")
        snapshot = json.dumps(payload, separators=(",", ":"))
        if existing_id:
            existing = connection.execute("SELECT status,revision,created_by FROM cmc_revisions WHERE id=?",
                (existing_id,)).fetchone()
            if not existing or existing[0] not in {"Draft", "Reverted"}:
                raise ValueError("Only a Draft or Reverted CMC record can be automatically saved.")
            if existing[2] != actor:
                raise ValueError("This unfinished CMC draft belongs to another user.")
            connection.execute("""UPDATE cmc_revisions SET snapshot_json=?,reason=?,calculated_at=CURRENT_TIMESTAMP
                WHERE id=?""", (snapshot, payload.get("reason") or "In-progress capability calculation", existing_id))
            return {"id": existing_id, "calculationId": f"CMC-{method[:3].upper()}-{existing[1]:03d}",
                "revision": existing[1], "status": existing[0], "createdBy": existing[2], "isCmc": True}
        unfinished = connection.execute("""SELECT id,revision,created_by,status FROM cmc_revisions
            WHERE method_name=? AND status IN ('Draft','Reverted') AND created_by=?
            ORDER BY id DESC LIMIT 1""", (method,actor)).fetchone()
        if unfinished:
            return {"id": unfinished[0], "calculationId": f"CMC-{method[:3].upper()}-{unfinished[1]:03d}",
                "revision": unfinished[1], "status": unfinished[3], "createdBy": unfinished[2],
                "isCmc": True, "existing": True}
        revision = connection.execute("SELECT COALESCE(MAX(revision),0)+1 FROM cmc_revisions WHERE method_name=?",
            (method,)).fetchone()[0]
        record_id = connection.execute("""INSERT INTO cmc_revisions
            (method_name,revision,status,reason,calculation_version,snapshot_json,created_by,calculated_at)
            VALUES (?,?,'Draft',?,'flp-gum-2.0',?,?,CURRENT_TIMESTAMP)""",
            (method, revision, payload.get("reason") or "In-progress capability calculation", snapshot, actor)).lastrowid
        return {"id": record_id, "calculationId": f"CMC-{method[:3].upper()}-{revision:03d}",
            "revision": revision, "status": "Draft", "createdBy": actor, "isCmc": True}
    if not payload.get("jobId"):
        raise ValueError("Select a Job before the draft can be saved.")
    hydrate_job_metadata(connection, payload)
    job_id = int(payload["jobId"]); existing_id = payload.get("recordId")
    snapshot = json.dumps(payload, separators=(",", ":"))
    if existing_id:
        existing = connection.execute("""SELECT status,calculation_uid,revision,calculated_by
            FROM uncertainty_calculations WHERE id=? AND job_id=?""", (existing_id, job_id)).fetchone()
        if not existing or existing[0] not in {"Draft", "Reverted"}:
            raise ValueError("Only a Draft or Reverted uncertainty record can be automatically saved.")
        if existing[3] != actor:
            raise ValueError("This unfinished uncertainty draft belongs to another user.")
        connection.execute("""UPDATE uncertainty_calculations SET calculation_type=?,method_name=?,
            quantity=?,fluid=?,analyst=?,snapshot_json=?,last_edited_by=?,updated_at=CURRENT_TIMESTAMP
            WHERE id=?""", (calculation_type, CALCULATION_TYPES[calculation_type][1],
            payload.get("quantity", "mass"), payload.get("fluid"), payload.get("analyst"),
            snapshot, actor, existing_id))
        return {"id": existing_id, "calculationId": existing[1], "revision": existing[2],
            "status": existing[0], "createdBy": existing[3]}
    unfinished = connection.execute("""SELECT id,calculation_uid,revision,calculated_by,status
        FROM uncertainty_calculations WHERE job_id=? AND calculation_type=?
        AND status IN ('Draft','Reverted') AND calculated_by=?
        ORDER BY updated_at DESC,id DESC LIMIT 1""",
        (job_id, calculation_type,actor)).fetchone()
    if unfinished:
        return {"id": unfinished[0], "calculationId": unfinished[1], "revision": unfinished[2],
            "status": unfinished[4], "createdBy": unfinished[3], "existing": True}
    revision = connection.execute("SELECT COALESCE(MAX(revision),0)+1 FROM uncertainty_calculations WHERE job_id=?",
        (job_id,)).fetchone()[0]
    uid = calculation_uid(connection)
    calculation_id = connection.execute("""INSERT INTO uncertainty_calculations
        (job_id,revision,status,calculation_uid,calculation_type,method_name,quantity,fluid,analyst,
         calculation_version,snapshot_json,calculated_by,created_by,last_edited_by,calculated_at,updated_at)
        VALUES (?,?,'Draft',?,?,?,?,?,?,'flp-gum-2.0',?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""",
        (job_id, revision, uid, calculation_type, CALCULATION_TYPES[calculation_type][1],
         payload.get("quantity", "mass"), payload.get("fluid"), payload.get("analyst"),
         snapshot, actor, actor, actor)).lastrowid
    return {"id": calculation_id, "calculationId": uid, "revision": revision,
        "status": "Draft", "createdBy": actor}


def _save_children(connection, calculation_id, payload, result, actor):
    result_by_index = {point["index"]: point for point in result["points"]}
    for index, point in enumerate(payload["points"]):
        computed = result_by_index[index]
        point_id = connection.execute("""INSERT INTO uncertainty_flow_points
            (calculation_id,point_order,label,nominal_flow,flow_unit,reference_temperature,
             reference_pressure,coverage_mode,coverage_probability,manual_coverage_factor,
             cmc_expression,cmc_coefficient_a,cmc_coefficient_b)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (calculation_id, index, computed["label"],
            computed["nominalFlow"], computed["flowUnit"], point.get("refTemp"), point.get("refPressure"),
            point.get("coverageMode", "auto"), point.get("coverageProb", 95), point.get("manualK"),
            point.get("cmcExpression"), point.get("cmcA"), point.get("cmcB"))).lastrowid
        for run_index, run in enumerate(computed["observations"], 1):
            connection.execute("""INSERT INTO uncertainty_observations
                (flow_point_id,run_number,collected_mass,collection_time,density,density_unit,mut_indication,
                 master_equipment_id,master_indication,master_correction,correction_basis,
                 reference_flow,error_percent) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (point_id, run_index, run.get("mass"), run.get("time"), run.get("density"),
                 point.get("densityUnit") or "kg/m³", run.get("mut"),
                 run.get("masterEquipmentId"), run.get("master"), run.get("correction"),
                 run.get("correctionBasis"), run["reference_flow"], run["error_percent"]))
        result_snapshot = computed["result"]
        stats = computed["statistics"]
        connection.execute("""INSERT INTO uncertainty_point_results
            (flow_point_id,observation_count,mean_error,sample_standard_deviation,
             type_a_standard_uncertainty,combined_standard_uncertainty,effective_degrees_of_freedom,
             coverage_factor,expanded_uncertainty,result_json) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (point_id, stats["n"], stats["mean"], stats["standard_deviation"], stats["standard_uncertainty"],
             result_snapshot["combined_standard_uncertainty"], result_snapshot["effective_degrees_of_freedom"],
             result_snapshot["coverage_factor"], result_snapshot["expanded_uncertainty"], json.dumps(result_snapshot)))
        for component in result_snapshot["components"]:
            source = component["input"]
            equipment_id = int(source["equipment_id"]) if source.get("equipment_id") else None
            connection.execute("""INSERT INTO uncertainty_sources
                (calculation_id,flow_point,source_name,source_type,source_origin,equipment_id,calibration_record_id,input_value,
                 unit,uncertainty_input_type,distribution,divisor,standard_uncertainty,
                 sensitivity_coefficient,contribution,contribution_percent,degrees_of_freedom,
                 source_status,evidence_path,observations_json,source_version,notes,added_by)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (calculation_id,
                 computed["nominalFlow"], source["source"], source["source_type"], source["source_origin"],
                 equipment_id, source.get("calibration_record_id"), source["input_value"], source["unit"], source["uncertainty_input_type"],
                 source["distribution"], source["divisor"], component["standard_uncertainty"],
                 source["sensitivity_coefficient"], component["contribution"], component["contribution_percent"],
                 source["degrees_of_freedom"], source["source_status"], source["evidence"],
                 json.dumps(computed["observations"]) if source["source_type"] == "A" else None,
                 source["source_version"], source["notes"], actor))
        for correlation in point.get("correlations") or []:
            connection.execute("""INSERT INTO uncertainty_correlations
                (flow_point_id,source_i,source_j,coefficient,justification) VALUES (?,?,?,?,?)""",
                (point_id, correlation.get("source_i") or correlation.get("a"),
                 correlation.get("source_j") or correlation.get("b"),
                 correlation.get("coefficient", correlation.get("r")), correlation.get("justification", "")))


def save_cmc(connection, payload, result, actor):
    method = result["method"]
    existing_id = payload.get("recordId")
    if existing_id:
        existing = connection.execute("SELECT status,revision FROM cmc_revisions WHERE id=?", (existing_id,)).fetchone()
        if not existing:
            raise ValueError("CMC record was not found.")
        if existing[0] == "Approved":
            raise ValueError("Approved CMC records are locked. Create a revision to make changes.")
        connection.execute("""UPDATE cmc_revisions SET snapshot_json=?,coverage_factor=?,
            proposed_cmc=?,calculation_version='flp-gum-2.0',calculated_at=CURRENT_TIMESTAMP
            WHERE id=?""", (json.dumps(payload | {"backendResult": result}),
            result["points"][-1]["result"]["coverage_factor"],
            result["points"][-1]["result"]["expanded_uncertainty"], existing_id))
        return {"id": int(existing_id), "calculationId": f"CMC-{method[:3].upper()}-{existing[1]:03d}",
            "revision": existing[1], "status": "Draft", "isCmc": True}
    revision = connection.execute("SELECT COALESCE(MAX(revision),0)+1 FROM cmc_revisions WHERE method_name=?", (method,)).fetchone()[0]
    last = result["points"][-1]["result"]
    record_id = connection.execute("""INSERT INTO cmc_revisions
        (method_name,revision,status,reason,proposed_cmc,coverage_factor,calculation_version,
         snapshot_json,created_by,calculated_at) VALUES (?,?,'Draft',?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (method, revision, payload.get("reason") or "GUM uncertainty budget", last["expanded_uncertainty"],
         last["coverage_factor"], "flp-gum-2.0", json.dumps(payload | {"backendResult": result}), actor)).lastrowid
    return {"id": record_id, "calculationId": f"CMC-{method[:3].upper()}-{revision:03d}",
        "revision": revision, "status": "Draft", "isCmc": True}


def workflow(connection, record_type, record_id, action, actor, comment="",
             assigned_reviewer=None, assigned_approver=None, auto_approve=False):
    table = "cmc_revisions" if record_type == "cmc" else "uncertainty_calculations"
    creator_column = "created_by" if record_type == "cmc" else "calculated_by"
    row = connection.execute(
        f"SELECT status,{creator_column},reviewed_by,assigned_reviewer,assigned_approver FROM {table} WHERE id=?",
        (record_id,)).fetchone()
    if not row:
        raise ValueError("Calculation record was not found.")
    current = row[0]
    if action == "submit" and auto_approve:
        if current not in {"Draft", "Reverted"}:
            raise ValueError(f"Cannot submit a calculation with status {current}.")
        note = "Automatically approved under Chief Meteorologist authority."
        if record_type == "cmc":
            connection.execute(f"""UPDATE {table} SET status='Approved',submitted_at=CURRENT_TIMESTAMP,
                reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP,review_comment=?,hod_reviewer=?,
                approved_at=CURRENT_TIMESTAMP,approved_by=?,effective_at=CURRENT_TIMESTAMP,
                assigned_reviewer=NULL,assigned_approver=NULL WHERE id=?""",
                (actor,note,actor,actor,record_id))
        else:
            connection.execute(f"""UPDATE {table} SET status='Approved',submitted_at=CURRENT_TIMESTAMP,
                submitted_by=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP,review_comment=?,hod_reviewer=?,
                approved_at=CURRENT_TIMESTAMP,approved_by=?,assigned_reviewer=NULL,assigned_approver=NULL
                WHERE id=?""", (actor,actor,note,actor,actor,record_id))
        entity = "cmc_revision" if record_type == "cmc" else "uncertainty_calculation"
        connection.execute("""INSERT INTO approval_history
            (entity_type,entity_id,action,actor,notes) VALUES (?,?,?,?,?)""",
            (entity,record_id,"submit",actor,comment or None))
        connection.execute("""INSERT INTO approval_history
            (entity_type,entity_id,action,actor,notes) VALUES (?,?,?,?,?)""",
            (entity,record_id,"auto_approve",actor,note))
        return "Approved"
    if action == "submit" and (not assigned_reviewer or not assigned_approver):
        raise ValueError("Select both the Technical Reviewer and the final Approving Officer.")
    if action in {"review", "approve", "revert"} and row[1] == actor:
        raise ValueError("The creator cannot review or approve their own uncertainty record.")
    if action == "review" and row[3] and row[3] != actor:
        raise ValueError(f"This Technical Review is assigned to {row[3]}.")
    if action == "revert" and current == "Submitted for Review" and row[3] and row[3] != actor:
        raise ValueError(f"This Technical Review is assigned to {row[3]}.")
    if action in {"approve", "revert"} and current == "HOD Review" and row[4] and row[4] != actor:
        raise ValueError(f"Final approval is assigned to {row[4]}.")
    if action == "approve" and row[2] == actor:
        raise ValueError("The technical reviewer cannot also give final HOD approval.")
    transitions = {"submit": ({"Draft", "Reverted"}, "Submitted for Review"),
                   "review": ({"Submitted for Review"}, "HOD Review"),
                   "revert": ({"Submitted for Review", "HOD Review"}, "Reverted"),
                   "approve": ({"HOD Review"}, "Approved")}
    if action not in transitions or current not in transitions[action][0]:
        raise ValueError(f"Cannot {action} a calculation with status {current}.")
    if action == "revert" and not comment.strip():
        raise ValueError("A comment is required when reverting a calculation.")
    new_status = transitions[action][1]
    if action == "submit":
        if record_type == "cmc":
            connection.execute(f"""UPDATE {table} SET status=?,submitted_at=CURRENT_TIMESTAMP,
                reviewed_by=NULL,reviewed_at=NULL,review_comment=NULL,hod_reviewer=NULL,
                assigned_reviewer=?,assigned_approver=? WHERE id=?""",
                (new_status, assigned_reviewer, assigned_approver, record_id))
        else:
            connection.execute(f"""UPDATE {table} SET status=?,submitted_at=CURRENT_TIMESTAMP,
                submitted_by=?,reviewed_by=NULL,reviewed_at=NULL,review_comment=NULL,hod_reviewer=NULL,
                assigned_reviewer=?,assigned_approver=? WHERE id=?""",
                (new_status, actor, assigned_reviewer, assigned_approver, record_id))
    elif action == "review":
        connection.execute(f"""UPDATE {table} SET status=?,reviewed_at=CURRENT_TIMESTAMP,
            reviewed_by=?,review_comment=? WHERE id=?""", (new_status, actor, comment or None, record_id))
    elif action == "revert":
        reviewer_field = "hod_reviewer" if current == "HOD Review" else "reviewed_by"
        connection.execute(f"""UPDATE {table} SET status=?,{reviewer_field}=?,review_comment=?
            WHERE id=?""", (new_status, actor, comment, record_id))
    elif action == "approve":
        effective = ",effective_at=CURRENT_TIMESTAMP" if record_type == "cmc" else ""
        connection.execute(f"""UPDATE {table} SET status=?,hod_reviewer=?,approved_at=CURRENT_TIMESTAMP,
            approved_by=?{effective} WHERE id=?""", (new_status, actor, actor, record_id))
    connection.execute("""INSERT INTO approval_history
        (entity_type,entity_id,action,actor,notes) VALUES (?,?,?,?,?)""",
        ("cmc_revision" if record_type == "cmc" else "uncertainty_calculation", record_id,
         action, actor, comment or None))
    if action == "submit":
        connection.execute("""INSERT INTO workflow_tasks
            (entity_type,entity_id,task_type,status,submitted_by,assigned_to,notes)
            VALUES (?,?, 'Technical Review','Pending',?,?,?)""",
            ("cmc_revision" if record_type == "cmc" else "uncertainty_calculation", record_id,
             actor, assigned_reviewer, comment or None))
    elif action == "review":
        connection.execute("""UPDATE workflow_tasks SET status='Completed',reviewed_at=CURRENT_TIMESTAMP,
            decision=?,comment=? WHERE entity_type=? AND entity_id=? AND status='Pending'""",
            (new_status, comment or None, "cmc_revision" if record_type == "cmc" else "uncertainty_calculation", record_id))
        connection.execute("""INSERT INTO workflow_tasks
            (entity_type,entity_id,task_type,status,submitted_by,assigned_to,notes)
            VALUES (?,?, 'HOD Review','Pending',?,?,?)""",
            ("cmc_revision" if record_type == "cmc" else "uncertainty_calculation", record_id,
             actor, row[4], comment or None))
    elif action in {"approve", "revert"}:
        connection.execute("""UPDATE workflow_tasks SET status='Completed',reviewed_at=CURRENT_TIMESTAMP,
            decision=?,comment=? WHERE entity_type=? AND entity_id=? AND status='Pending'""",
            (new_status, comment or None, "cmc_revision" if record_type == "cmc" else "uncertainty_calculation", record_id))
    return new_status


def create_revision(connection, record_id, actor, reason):
    row = connection.execute("SELECT job_id,status,snapshot_json FROM uncertainty_calculations WHERE id=?", (record_id,)).fetchone()
    if not row or row[1] != "Approved":
        raise ValueError("Only an approved calculation can create a new revision.")
    if not str(reason or "").strip():
        raise ValueError("A reason for revision is required.")
    payload = json.loads(row[2]); payload.pop("backendResult", None); payload.pop("recordId", None)
    result = calculate_payload(connection, payload)
    saved = save_calculation(connection, payload, result, actor)
    connection.execute("UPDATE uncertainty_calculations SET parent_calculation_id=?,revision_reason=? WHERE id=?",
        (record_id, str(reason).strip(), saved["id"]))
    return saved


def create_cmc_revision(connection, record_id, actor, reason):
    row = connection.execute("SELECT status,snapshot_json FROM cmc_revisions WHERE id=?", (record_id,)).fetchone()
    if not row or row[0] != "Approved":
        raise ValueError("Only an approved CMC calculation can create a new revision.")
    if not str(reason or "").strip():
        raise ValueError("A reason for revision is required.")
    payload = json.loads(row[1]); payload.pop("backendResult", None); payload.pop("recordId", None)
    result = calculate_payload(connection, payload)
    payload["reason"] = str(reason).strip()
    return save_cmc(connection, payload, result, actor)


def record_payload(connection, record_id, record_type="calculation"):
    if record_type == "cmc":
        row = connection.execute("""SELECT id,revision,status,snapshot_json,created_by,reviewed_by,
            approved_by,approved_at,hod_reviewer,assigned_reviewer,assigned_approver
            FROM cmc_revisions WHERE id=?""", (record_id,)).fetchone()
    else:
        row = connection.execute("""SELECT id,revision,status,snapshot_json,calculation_uid,
            calculated_by,reviewed_by,approved_by,approved_at,hod_reviewer
            ,assigned_reviewer,assigned_approver
            FROM uncertainty_calculations WHERE id=?""", (record_id,)).fetchone()
    if not row:
        raise ValueError("Calculation record was not found.")
    payload = json.loads(row[3]); payload["recordId"] = row[0]; payload["revision"] = row[1]; payload["status"] = row[2]
    if record_type == "cmc":
        payload["createdBy"], payload["reviewedBy"] = row[4], row[5]
        payload["approvedBy"], payload["approvedAt"], payload["hodReviewer"] = row[6], row[7], row[8]
        payload["assignedReviewer"], payload["assignedApprover"] = row[9], row[10]
    else:
        payload["calculationId"] = row[4]
        payload["createdBy"], payload["reviewedBy"] = row[5], row[6]
        payload["approvedBy"], payload["approvedAt"], payload["hodReviewer"] = row[7], row[8], row[9]
        payload["assignedReviewer"], payload["assignedApprover"] = row[10], row[11]
    return payload


def pdf_report(payload):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen.canvas import Canvas
    stream = BytesIO(); canvas = Canvas(stream, pagesize=A4); width, height = A4
    margin = 42; y = height - margin
    def line(text, size=9, gap=14, bold=False, color="#263746"):
        nonlocal y
        if y < 58:
            canvas.showPage(); y = height - margin
        canvas.setFillColor(HexColor(color)); canvas.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        canvas.drawString(margin, y, str(text)[:118]); y -= gap
    def section(title):
        nonlocal y
        y -= 5; line(title.upper(), 10, 18, True, "#087b83")
    def number(value):
        try: return f"{float(value):.8g}"
        except (TypeError, ValueError): return ""
    canvas.setFillColor(HexColor("#123247")); canvas.rect(0, height - 78, width, 78, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1); canvas.setFont("Helvetica-Bold", 17)
    canvas.drawString(margin, height - 42, "FlowLab Pro - Measurement Uncertainty Report")
    canvas.setFont("Helvetica", 9); canvas.drawString(margin, height - 60, "Controlled approved record - read only")
    y = height - 100
    section("Record identification")
    line(f"Calculation ID: {payload.get('calculationId', '')}    Revision: {payload.get('revision', 1)}    Status: {payload.get('status', '')}")
    line(f"Job: {payload.get('jobNumber', '')}    Project: {payload.get('projectNumber', '')} {payload.get('projectName', '')}")
    line(f"Customer: {payload.get('customer', '')}    Analyst: {payload.get('analyst', '')}")
    line(f"MUT: {payload.get('mut', '')}    Asset: {payload.get('mutAssetId', '')}    Serial: {payload.get('serialNumber', '')}")
    line(f"Manufacturer: {payload.get('manufacturer', '')}    Model: {payload.get('model', '')}    Meter type: {payload.get('meterType', '')}")
    line(f"Range: {payload.get('rangeMin', '')} to {payload.get('rangeMax', '')} {payload.get('rangeUnit', '')}    Fluid: {payload.get('fluid', '')}")
    section("Method and applicable standards")
    line(f"Method: {CALCULATION_TYPES.get(payload.get('calculationType'), ('', '', False))[1]}")
    line("ISO/IEC 17025:2017 - General requirements for the competence of testing and calibration laboratories")
    line("JCGM 100:2008 - Evaluation of measurement data - Guide to the expression of uncertainty in measurement")
    line("ILAC P14:09/2020 - ILAC policy for measurement uncertainty in calibration")
    result = payload.get("backendResult", {})
    for point in result.get("points", []):
        section(f"Flow point - {point.get('label') or point.get('nominalFlow')}")
        line(f"Nominal flow: {number(point.get('nominalFlow'))} {point.get('flowUnit', '')}    Reference temperature: {point.get('referenceTemperature') or ''} C    Reference pressure: {point.get('referencePressure') or ''}")
        stats = point.get("statistics", {}); outcome = point.get("result", {})
        line(f"Type A: n={stats.get('n', '')}; mean={number(stats.get('mean'))} %; s={number(stats.get('standard_deviation'))} %; uA={number(stats.get('standard_uncertainty'))} %")
        line("Repeatability diagnostics (informational; not separately added to RSS)", 8, 13, True)
        for diagnostic in point.get("repeatabilityDiagnostics", []):
            line(f"{diagnostic.get('quantity','')}: mean={number(diagnostic.get('mean'))} {diagnostic.get('unit','')}; s={number(diagnostic.get('standard_deviation'))}; u={number(diagnostic.get('standard_uncertainty'))}; relative u={number(diagnostic.get('relative_standard_uncertainty'))}% - {diagnostic.get('treatment','')}", 7, 11)
        line("Run | Reference flow | MUT indication | Error (%)", 8, 13, True)
        for index, observation in enumerate(point.get("observations", []), 1):
            line(f"{index} | {number(observation.get('reference_flow'))} | {number(observation.get('mut'))} | {number(observation.get('error_percent'))}", 8, 12)
        line("Source | Type | Basis / distribution | Standard u | Sensitivity | Contribution | Share", 8, 13, True)
        for component in outcome.get("components", []):
            item = component.get("input", {})
            line(f"{item.get('source','')} | {item.get('source_type','')} | {item.get('uncertainty_input_type','')} / {item.get('distribution','')} | {number(component.get('standard_uncertainty'))} | {number(item.get('sensitivity_coefficient'))} | {number(component.get('contribution'))} | {number(component.get('contribution_percent'))}%", 8, 12)
        line(f"Combined standard uncertainty uc: {number(outcome.get('combined_standard_uncertainty'))} %", 9, 14, True)
        line(f"Effective degrees of freedom: {number(outcome.get('effective_degrees_of_freedom'))}    Coverage factor k: {number(outcome.get('coverage_factor'))}    Coverage probability: {number(outcome.get('coverage_probability'))}%")
        line(f"Expanded uncertainty U: {number(outcome.get('expanded_uncertainty'))} %", 10, 18, True, "#087b83")
    section("Review and approval")
    line(f"Technical reviewer: {payload.get('reviewedBy') or ''}")
    line(f"Approving officer: {payload.get('approvedBy') or payload.get('hodReviewer') or ''}")
    line(f"Approved at: {payload.get('approvedAt') or ''}")
    line("This report is generated from the locked approved calculation snapshot.", 8, 12, False, "#5b7185")
    canvas.save(); stream.seek(0); return stream
