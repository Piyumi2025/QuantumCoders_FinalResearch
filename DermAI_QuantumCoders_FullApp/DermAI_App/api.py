"""Core clinical API: patients, image upload/QC, assessment (inference), reports."""
import os
import json
import uuid
from flask import Blueprint, request, jsonify, current_app, send_file, abort
from werkzeug.utils import secure_filename
from extensions import db
from models import Patient, Assessment, ImageAsset, log
from helpers import current_user, client_ip, login_required
import inference
from report import build_report_pdf

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _ext_ok(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXT"]


# FR7 — Create/validate patient
@api_bp.post("/patients")
@login_required
def create_patient():
    u = current_user()
    d = request.get_json(force=True, silent=True) or {}
    try:
        age = int(d.get("age")) if d.get("age") not in (None, "") else None
    except ValueError:
        return jsonify(error="Age must be a number."), 400
    if age is not None and not (0 <= age <= 120):
        return jsonify(error="Age must be between 0 and 120."), 400
    if not d.get("gender") or not d.get("fitzpatrick"):
        return jsonify(error="Gender and skin type are required."), 400

    count = Patient.query.filter_by(doctor_id=u.id).count() + 1
    p = Patient(
        doctor_id=u.id, patient_code=f"PAT-{count:03d}",
        first_name=d.get("first_name"), last_name=d.get("last_name"),
        age=age, gender=d.get("gender"), nic=d.get("nic"), contact=d.get("contact"),
        address=d.get("address"), fitzpatrick=d.get("fitzpatrick"),
        lesion_location=d.get("lesion_location"),
        duration_weeks=int(d["duration_weeks"]) if str(d.get("duration_weeks", "")).isdigit() else None,
        growth_speed=d.get("growth_speed"), sun_exposure=d.get("sun_exposure"),
        immunosuppression=d.get("immunosuppression"), family_history=d.get("family_history"),
        prev_history=d.get("prev_history"), notes=d.get("notes"),
    )
    db.session.add(p)
    db.session.commit()
    log(u.id, "PATIENT", f"Created {p.patient_code}", client_ip())
    return jsonify(patient=p.to_dict()), 201


# FR20 (list) — patient records
@api_bp.get("/patients")
@login_required
def list_patients():
    u = current_user()
    rows = []
    for p in Patient.query.filter_by(doctor_id=u.id).order_by(Patient.id.desc()).all():
        last = (Assessment.query.filter_by(patient_id=p.id)
                .order_by(Assessment.id.desc()).first())
        rows.append({**p.to_dict(),
                     "last": last.to_dict() if last else None})
    return jsonify(patients=rows)


# FR9 + FR10 + FR11..FR13 — upload image, validate quality, preprocess
@api_bp.post("/upload")
@login_required
def upload():
    u = current_user()
    if "image" not in request.files:
        return jsonify(error="No image provided."), 400
    f = request.files["image"]
    if not f.filename or not _ext_ok(f.filename):
        return jsonify(error="Unsupported format. Use JPG/PNG/JPEG/TIFF."), 400

    raw = f.read()
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > current_app.config["MAX_IMAGE_MB"]:
        return jsonify(error=f"File too large ({size_mb:.1f} MB > "
                             f"{current_app.config['MAX_IMAGE_MB']} MB)."), 400

    up = current_app.config["UPLOAD_DIR"]
    os.makedirs(up, exist_ok=True)
    stored = os.path.join(up, f"{uuid.uuid4().hex}_{secure_filename(f.filename)}")
    with open(stored, "wb") as out:
        out.write(raw)

    # FR11-13: EXIF strip -> DullRazor -> resize/normalize + blur QC
    try:
        rgb, meta = inference.preprocess(stored)
    except Exception as e:
        os.remove(stored)
        return jsonify(error=f"Could not read image: {e}"), 400

    min_res = current_app.config["MIN_RESOLUTION"]
    blur_th = current_app.config["BLUR_THRESHOLD"]
    checks = {
        "format": True,
        "size": size_mb <= current_app.config["MAX_IMAGE_MB"],
        "resolution": meta["width"] >= min_res and meta["height"] >= min_res,
        "sharpness": meta["blur"] >= blur_th,
    }
    quality_pass = all(checks.values())

    img = ImageAsset(patient_id=None, filename=f.filename, stored_path=stored,
                     width=meta["width"], height=meta["height"], size_bytes=len(raw),
                     blur_score=meta["blur"], quality_pass=quality_pass)
    db.session.add(img)
    db.session.commit()
    log(u.id, "UPLOAD", f"Image {f.filename} ({meta['width']}x{meta['height']})", client_ip())
    return jsonify(image_id=img.id,
                   meta={"width": meta["width"], "height": meta["height"],
                         "size_mb": round(size_mb, 2), "blur": meta["blur"]},
                   checks=checks, quality_pass=quality_pass,
                   ita=inference.estimate_ita(rgb))


# FR8 + FR14..FR19 — run assessment (symptoms [+image] -> inference -> stage/urgency/heatmap)
@api_bp.post("/assess")
@login_required
def assess():
    u = current_user()
    d = request.get_json(force=True, silent=True) or {}
    sym = d.get("symptoms") or {}

    # resolve patient: existing id, or create from inline patient block
    patient = None
    if d.get("patient_id"):
        patient = Patient.query.filter_by(id=d["patient_id"], doctor_id=u.id).first()
    if patient is None and d.get("patient"):
        pd = d["patient"]
        count = Patient.query.filter_by(doctor_id=u.id).count() + 1
        patient = Patient(doctor_id=u.id, patient_code=f"PAT-{count:03d}",
                          first_name=pd.get("first_name"), last_name=pd.get("last_name"),
                          age=int(pd["age"]) if str(pd.get("age", "")).isdigit() else None,
                          gender=pd.get("gender"), fitzpatrick=pd.get("fitzpatrick"),
                          lesion_location=pd.get("lesion_location"),
                          duration_weeks=int(pd["duration_weeks"]) if str(pd.get("duration_weeks", "")).isdigit() else None,
                          growth_speed=pd.get("growth_speed"), notes=pd.get("notes"))
        db.session.add(patient)
        db.session.flush()
    if patient is None:
        return jsonify(error="A patient is required."), 400

    # merge patient-derived flags into the symptom dict
    sym.setdefault("age", patient.age or 0)

    cfg = current_app.config
    rgb = None
    img = None
    img_id = d.get("image_id")
    if not img_id:
        _ids = d.get("image_ids") or []
        if isinstance(_ids, list) and _ids:
            img_id = _ids[0]
    if img_id:
        img = ImageAsset.query.get(img_id)
        if img and os.path.exists(img.stored_path):
            try:
                rgb, _ = inference.preprocess(img.stored_path)
            except Exception:
                rgb = None

    result = inference.analyze(sym, rgb_299=rgb, weights_file=cfg["WEIGHTS_FILE"],
                               w_img=cfg["FUSION_IMAGE_WEIGHT"], w_sym=cfg["FUSION_SYMPTOM_WEIGHT"],
                               uncertain_th=cfg["UNCERTAIN_THRESHOLD"])

    a = Assessment(patient_id=patient.id, doctor_id=u.id,
                   symptom_json=json.dumps(sym),
                   predicted_type=result["predicted_type"], stage=result["stage"],
                   confidence=result["confidence"], urgency=result["urgency"],
                   uncertain=result["uncertain"], mode=result["mode"],
                   prob_mel=result["probs"]["Melanoma"], prob_bcc=result["probs"]["BCC"],
                   prob_scc=result["probs"]["SCC"], prob_mcc=result["probs"]["MCC"])
    db.session.add(a)
    db.session.flush()

    # heatmap (FR19)
    if rgb is not None:
        hp = os.path.join(cfg["UPLOAD_DIR"], f"heatmap_{a.id}.png")
        try:
            inference.make_heatmap(rgb, hp)
            a.heatmap_path = hp
        except Exception:
            pass
    if img is not None:
        img.assessment_id = a.id
        img.patient_id = patient.id
    db.session.commit()
    log(u.id, "ASSESSMENT", f"{patient.patient_code}: {result['predicted_type']} "
                            f"({result['confidence']}%, {result['mode']})", client_ip())

    return jsonify(assessment_id=a.id, patient=patient.to_dict(), **result,
                   has_heatmap=bool(a.heatmap_path))


@api_bp.get("/assess/<int:aid>")
@login_required
def get_assess(aid):
    a = Assessment.query.get_or_404(aid)
    return jsonify(assessment=a.to_dict(), patient=Patient.query.get(a.patient_id).to_dict())


@api_bp.get("/assess/<int:aid>/heatmap")
@login_required
def heatmap(aid):
    a = Assessment.query.get_or_404(aid)
    if not a.heatmap_path or not os.path.exists(a.heatmap_path):
        abort(404)
    return send_file(a.heatmap_path, mimetype="image/png")


# FR20 + FR21 — report view / PDF download
@api_bp.get("/report/<int:aid>")
@login_required
def report_json(aid):
    a = Assessment.query.get_or_404(aid)
    p = Patient.query.get(a.patient_id)
    return jsonify(assessment=a.to_dict(), patient=p.to_dict(),
                   symptoms=json.loads(a.symptom_json or "{}"))


@api_bp.get("/report/<int:aid>/pdf")
@login_required
def report_pdf(aid):
    u = current_user()
    a = Assessment.query.get_or_404(aid)
    p = Patient.query.get(a.patient_id)
    pdf = build_report_pdf(a, p, u, heatmap_path=a.heatmap_path)
    log(u.id, "REPORT", f"Downloaded PDF RPT-{a.id:05d}", client_ip())
    return send_file(pdf, mimetype="application/pdf", as_attachment=True,
                     download_name=f"DermAI_Report_{a.id:05d}.pdf")
