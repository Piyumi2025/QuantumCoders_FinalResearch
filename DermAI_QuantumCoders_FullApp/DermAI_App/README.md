# DermAI — Quantum Coders (Full-Stack Web App)

AI-assisted skin-cancer (Melanoma / BCC / SCC / MCC) classification & staging, with a Flask +
SQL backend wired to the existing UI. Every functional requirement is backed by a real database
record, real image preprocessing, real inference, and a real PDF report.

## Inference modes (important)
- **Clinical-rule mode** (default): predictions come from a transparent ABCDE / AEIOU / BCC / SCC
  rule engine + risk factors. Runs anywhere, no ML libraries needed. The UI clearly labels results
  as `CLINICAL-RULE MODE`.
- **Trained mode**: if you drop a trained `models_store/dermai_best.pth` (EfficientNet-B4) and install
  `torch` + `timm`, the image is classified by the CNN and fused with the symptom score (0.60 / 0.40),
  with a Grad-CAM heatmap. Results are labelled `TRAINED MODE`.

---

## 1. Quick start (SQLite — zero setup)

Requires **Python 3.10+**.

```bash
cd DermAI_App
python -m venv venv
# Windows:  venv\Scripts\activate
# macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**. Tables are created and demo users seeded automatically.

**Demo logins** (password for all: `Password@123`):
| Role   | Email             |
|--------|-------------------|
| Doctor | doctor@dermai.lk  |
| Doctor | kasun@dermai.lk   |
| Admin  | admin@dermai.lk   |

The **admin console** is not a button — it is a hidden endpoint. Visit
**http://localhost:5000/#admin** and sign in with the admin account.

---

## 2. Connect to your MySQL server

1. Install the driver:
   ```bash
   pip install PyMySQL
   ```
2. Create the database and a user on your MySQL server:
   ```sql
   CREATE DATABASE dermai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'dermai_user'@'%' IDENTIFIED BY 'StrongPass';
   GRANT ALL PRIVILEGES ON dermai.* TO 'dermai_user'@'%';
   FLUSH PRIVILEGES;
   ```
3. Point the app at it with the `DATABASE_URL` environment variable, then run:
   ```bash
   # macOS/Linux
   export DATABASE_URL="mysql+pymysql://dermai_user:StrongPass@localhost:3306/dermai"
   export SECRET_KEY="a-long-random-string"
   python app.py

   # Windows (PowerShell)
   $env:DATABASE_URL="mysql+pymysql://dermai_user:StrongPass@localhost:3306/dermai"
   $env:SECRET_KEY="a-long-random-string"
   python app.py
   ```
   On first run the app creates all tables in your MySQL database and seeds the demo users.

That is the only change needed — **no code edits**. (A `.env.example` is included for reference.)

### PostgreSQL (optional)
```bash
pip install psycopg2-binary
export DATABASE_URL="postgresql+psycopg2://dermai_user:StrongPass@localhost:5432/dermai"
```

---

## 3. Enable Trained mode (optional)
```bash
pip install torch timm
# place your trained weights at:
#   models_store/dermai_best.pth
```
Restart the app — `/health` will report `"mode":"trained"` and results switch to CNN + fusion + Grad-CAM.
Train the weights with the companion Kaggle notebooks (Objective 1 data prep + Objective 2 training).

---

## 4. Functional requirement → implementation map

| FR | Function | Endpoint / code |
|----|----------|-----------------|
| 1  | Register (validated) | `POST /api/auth/register` |
| 2  | Verify email & activate | `GET /verify/<token>`, `GET /api/auth/verify/<token>` |
| 3  | Sign in | `POST /api/auth/login` |
| 4  | Log out | `POST /api/auth/logout` |
| 5  | Manage account | `PUT /api/auth/account` |
| 6  | Admin manage users | `GET/POST/DELETE /api/admin/users…` |
| 7  | Enter & validate patient | `POST /api/patients` |
| 8  | Record symptoms | symptom vector in `POST /api/assess` |
| 9  | Upload image(s) | `POST /api/upload` |
| 10 | Validate image quality | blur / size / resolution checks in `upload` |
| 11 | Strip EXIF | `inference.preprocess()` (Pillow) |
| 12 | DullRazor hair removal | `inference._dull_razor()` (OpenCV) |
| 13 | Resize & normalize | `inference.preprocess()` → 299×299 |
| 14 | Load AI model | `inference._load_model()` |
| 15 | Classify type | `inference.analyze()` |
| 16 | Fuse symptom vector | `analyze()` fusion 0.60 / 0.40 |
| 17 | Predict stage | `inference._stage_from()` |
| 18 | Confidence & uncertainty | `analyze()` (<50% → uncertain) |
| 19 | Grad-CAM heatmap | `inference.make_heatmap()` |
| 20 | View report / records | `GET /api/report/<id>`, `GET /api/patients` |
| 21 | Download PDF | `GET /api/report/<id>/pdf` (ReportLab) |
| 22 | Disclaimer | every result card + PDF footer |

---

## 5. Project structure
```
DermAI_App/
├── app.py            # Flask factory, page routes, seeding
├── config.py         # DATABASE_URL / SQLite default / MySQL ready
├── extensions.py     # SQLAlchemy instance
├── models.py         # User, Patient, ImageAsset, Assessment, AuditLog
├── helpers.py        # session auth decorators
├── auth.py           # FR1–5 blueprint
├── api.py            # FR7–21 blueprint
├── admin.py          # FR6 blueprint
├── inference.py      # preprocessing + dual-mode inference + heatmap
├── report.py         # PDF generation
├── requirements.txt
├── .env.example
├── templates/index.html   # your UI (served)
├── static/css/style.css   # your styles
├── static/js/app.js       # UI ⇄ API wiring
├── uploads/          # runtime image + heatmap store
└── models_store/     # place dermai_best.pth here for Trained mode
```

## 6. Notes
- **Auth**: passwords hashed (Werkzeug PBKDF2). Sessions are cookie-based; set a strong `SECRET_KEY`
  in production and run behind HTTPS.
- **Email**: no SMTP server is bundled, so `register` returns the verification link and the UI
  auto-activates for the demo. Wire an SMTP provider in `auth.register` for production.
- **The elaborate result visuals** on the results screen are the original design; a **Live AI Result**
  card (real DB + model output) is injected at the top of the results and report, and the PDF is built
  entirely from real data.
