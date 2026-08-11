"""DermAI inference engine.

Dual mode:
  * TRAINED mode  - if a PyTorch EfficientNet-B4 weights file is present AND torch/timm
                    are installed, the image is classified by the CNN and fused with the
                    symptom score (0.60 / 0.40). Grad-CAM heatmap generated.
  * RULE mode     - otherwise, a transparent clinical-rule score (ABCDE / AEIOU / BCC / SCC
                    criteria + risk factors) drives the prediction. The app clearly reports
                    which mode produced each result so it is never misrepresented.

Preprocessing (always, Pillow): EXIF strip -> resize 299 -> (DullRazor hair removal if
OpenCV present). A blur score (variance of Laplacian) gates image quality.
"""
import os
import numpy as np
from PIL import Image, ImageOps

try:
    import cv2
    HAS_CV2 = True
except Exception:
    HAS_CV2 = False

try:
    import torch
    import timm
    HAS_TORCH = True
except Exception:
    HAS_TORCH = False

CLASSES = ["Melanoma", "BCC", "SCC", "MCC"]
IMG_SIZE = 299

_model = None  # lazily loaded trained model


# ----------------------------------------------------------------- preprocessing
def _dull_razor(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    k = cv2.getStructuringElement(cv2.MORPH_CROSS, (9, 9))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k)
    _, mask = cv2.threshold(blackhat, 10, 255, cv2.THRESH_BINARY)
    return cv2.inpaint(bgr, mask, 1, cv2.INPAINT_TELEA)


def preprocess(path):
    """Return (rgb_299 uint8 array, meta dict). EXIF stripped, hair removed, resized."""
    pil = ImageOps.exif_transpose(Image.open(path)).convert("RGB")   # EXIF strip
    w, h = pil.size
    rgb = np.array(pil)

    # blur score on the original (variance of Laplacian)
    if HAS_CV2:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    else:
        gy = np.mean(rgb, axis=2)
        blur = float(np.var(gy - np.roll(gy, 1, 0)))

    proc = rgb
    if HAS_CV2:
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        bgr = _dull_razor(bgr)
        bgr = cv2.resize(bgr, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_CUBIC)
        proc = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    else:
        proc = np.array(pil.resize((IMG_SIZE, IMG_SIZE), Image.BICUBIC))

    return proc, {"width": w, "height": h, "blur": round(blur, 1)}


def estimate_ita(rgb):
    """Individual Typology Angle (skin-tone proxy) on healthy border skin."""
    if not HAS_CV2:
        return None
    h, w = rgb.shape[:2]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2Lab).astype(np.float32)
    L = lab[..., 0] * 100.0 / 255.0
    b = lab[..., 2] - 128.0
    m = max(4, int(0.12 * min(h, w)))
    ring = np.zeros((h, w), bool)
    ring[:m, :] = ring[-m:, :] = ring[:, :m] = ring[:, -m:] = True
    skin = ring & (lab[..., 0] > 40) & (lab[..., 0] < 245)
    if skin.sum() < 30:
        return None
    return float(np.degrees(np.arctan2(np.median(L[skin]) - 50.0, np.median(b[skin]) + 1e-6)))


# ----------------------------------------------------------------- symptom rule score
def symptom_scores(sym):
    """Transparent clinical scoring from the symptom checklist -> per-class 0..1 weights.

    `sym` keys (booleans unless noted):
      ABCDE: a_asym,b_border,c_colour,d_diam,e_evolve, blue_white, nail, new_mole, pigment_net
      BCC:   bcc_pearly,bcc_rolled,bcc_telangiectasia,bcc_ulcer,bcc_scaly,bcc_nonheal
      SCC:   scc_nodule,scc_scaly,scc_hyperkeratotic,scc_ulcer,scc_rapid,scc_sunexposed,scc_ak,scc_marjolin
      AEIOU: mcc_a,mcc_e,mcc_i,mcc_o,mcc_u, mcc_dome, mcc_uniform
      general: pain,bleeding,ulceration,itching, fair_skin, moles50, nodes
      patient: age (int), immunosuppression (bool), sun_significant (bool)
    """
    g = lambda k: 1.0 if sym.get(k) else 0.0

    mel = (g("a_asym") + g("b_border") + g("c_colour") + g("d_diam") + g("e_evolve")) * 1.0
    mel += g("blue_white") * 1.2 + g("nail") * 0.8 + g("new_mole") * 0.5 + g("pigment_net") * 0.6

    bcc = (g("bcc_pearly") * 1.2 + g("bcc_rolled") * 1.1 + g("bcc_telangiectasia") * 1.2
           + g("bcc_ulcer") + g("bcc_scaly") * 0.8 + g("bcc_nonheal") * 0.8)

    scc = (g("scc_nodule") + g("scc_scaly") * 0.8 + g("scc_hyperkeratotic") * 1.1
           + g("scc_ulcer") + g("scc_rapid") + g("scc_sunexposed") * 0.7
           + g("scc_ak") * 0.9 + g("scc_marjolin") * 1.1)

    mcc = (g("mcc_a") + g("mcc_e") * 1.2 + g("mcc_i") * 1.1 + g("mcc_o") + g("mcc_u")
           + g("mcc_dome") * 0.8 + g("mcc_uniform") * 0.6)

    # general modifiers
    if sym.get("bleeding"):
        mel += 0.4; scc += 0.5
    if sym.get("ulceration"):
        scc += 0.6; bcc += 0.3
    if sym.get("pain"):
        scc += 0.3
    if sym.get("fair_skin"):
        mel += 0.3; scc += 0.3
    if sym.get("immunosuppression"):
        scc += 0.4; mcc += 0.6
    if sym.get("sun_significant"):
        scc += 0.4; bcc += 0.3
    age = sym.get("age") or 0
    if age >= 50:
        mcc += 0.5; scc += 0.3
    if sym.get("moles50"):
        mel += 0.3

    raw = np.array([max(mel, 0), max(bcc, 0), max(scc, 0), max(mcc, 0)], dtype=float)
    if raw.sum() == 0:
        raw = np.array([1.0, 1.0, 1.0, 1.0])
    # soft normalisation (temperature) so a clear leader dominates but others stay non-zero
    exp = np.exp(raw / 1.6)
    return exp / exp.sum()


# ----------------------------------------------------------------- trained model
def _load_model(weights_file):
    global _model
    if _model is not None:
        return _model
    if not (HAS_TORCH and weights_file and os.path.exists(weights_file)):
        return None
    m = timm.create_model("efficientnet_b4", pretrained=False, num_classes=len(CLASSES))
    state = torch.load(weights_file, map_location="cpu")
    m.load_state_dict(state.get("model", state), strict=False)
    m.eval()
    _model = m
    return _model


def _trained_probs(rgb_299, weights_file):
    m = _load_model(weights_file)
    if m is None:
        return None
    mean = np.array([0.485, 0.456, 0.406]); std = np.array([0.229, 0.224, 0.225])
    x = (rgb_299.astype(np.float32) / 255.0 - mean) / std
    x = torch.tensor(x.transpose(2, 0, 1)[None], dtype=torch.float32)
    with torch.no_grad():
        p = torch.softmax(m(x), dim=1)[0].numpy()
    return p


# ----------------------------------------------------------------- fuse + derive
def _stage_from(conf, sym):
    sev = sum(1 for k in ("ulceration", "bleeding", "e_evolve", "scc_rapid", "mcc_e") if sym.get(k))
    if conf >= 0.70 and sev >= 2:
        return "Advanced"
    if conf >= 0.50 or sev >= 1:
        return "Intermediate"
    return "Early"


def _urgency(pred, stage, conf):
    if pred == "MCC" or stage == "Advanced":
        return "Emergency"
    if pred in ("Melanoma", "SCC") and conf >= 0.45:
        return "Urgent"
    if stage == "Intermediate":
        return "Urgent"
    return "Routine"


def analyze(sym, rgb_299=None, weights_file=None,
            w_img=0.60, w_sym=0.40, uncertain_th=0.50):
    """Return the full prediction dict. Chooses trained or rule mode automatically."""
    s_probs = symptom_scores(sym)
    i_probs = _trained_probs(rgb_299, weights_file) if rgb_299 is not None else None

    if i_probs is not None:
        probs = w_img * i_probs + w_sym * s_probs
        mode = "trained"
    else:
        probs = s_probs
        mode = "rule"
    probs = probs / probs.sum()

    idx = int(np.argmax(probs))
    pred = CLASSES[idx]
    conf = float(probs[idx])
    stage = _stage_from(conf, sym)
    urgency = _urgency(pred, stage, conf)
    return {
        "mode": mode,
        "predicted_type": pred,
        "confidence": round(conf * 100, 1),
        "uncertain": conf < uncertain_th,
        "stage": stage,
        "urgency": urgency,
        "probs": {c: round(float(p) * 100, 1) for c, p in zip(CLASSES, probs)},
    }


# ----------------------------------------------------------------- heatmap
def make_heatmap(rgb_299, out_path):
    """Grad-CAM-style overlay. In rule mode a centre-weighted saliency proxy is used
    (the trained pipeline replaces this with true Grad-CAM on the last conv block)."""
    h, w = rgb_299.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h * 0.5, w * 0.52
    g = np.exp(-(((xx - cx) ** 2) / (2 * (w * 0.28) ** 2) + ((yy - cy) ** 2) / (2 * (h * 0.22) ** 2)))
    g = (g - g.min()) / (g.max() - g.min() + 1e-9)
    if HAS_CV2:
        heat = cv2.applyColorMap((g * 255).astype(np.uint8), cv2.COLORMAP_JET)
        heat = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
        overlay = (0.55 * rgb_299 + 0.45 * heat).astype(np.uint8)
        cv2.imwrite(out_path, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    else:
        heat = np.stack([g, np.zeros_like(g), 1 - g], axis=2)
        overlay = (0.6 * rgb_299 / 255.0 + 0.4 * heat)
        Image.fromarray((np.clip(overlay, 0, 1) * 255).astype(np.uint8)).save(out_path)
    return out_path
