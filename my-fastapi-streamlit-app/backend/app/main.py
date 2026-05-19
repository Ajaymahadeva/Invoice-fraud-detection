from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import pytesseract
from PIL import Image
import cv2
import numpy as np
import os
import re
import json
import tempfile
import traceback
import math
import logging
from datetime import datetime

# =========================================================
# BASIC SETUP
# =========================================================

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Invoice Fraud Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# TESSERACT CONFIG (DYNAMIC PATH)
# =========================================================

# Resolve project root dynamically
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
TESSERACT_PATH = os.path.join(BASE_DIR, "tesseractmode", "tesseract.exe")

try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    pytesseract.get_tesseract_version()
    logger.info(f"Tesseract configured successfully: {TESSERACT_PATH}")
except Exception as e:
    logger.error(f"Tesseract configuration failed: {e}")
    logger.warning(
        "Continuing without configured Tesseract; OCR calls may fail. "
        "Set TESSERACT_PATH or install the tesseract executable to enable OCR."
    )

# =========================================================
# CONSTANTS & DATA DIRS
# =========================================================

GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

PROCESSED_JSON = os.path.join(DATA_DIR, "processed_invoices.json")
VENDOR_HISTORY_JSON = os.path.join(DATA_DIR, "vendor_history.json")
STATS_JSON = os.path.join(DATA_DIR, "stats.json")

# =========================================================
# UTIL FUNCTIONS
# =========================================================

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# =========================================================
# SIMPLE INVOICE TEXT CHECK
# =========================================================

def looks_like_invoice(text: str) -> bool:
    if not text:
        return False

    keywords = [
        "invoice", "bill", "total", "amount",
        "gst", "tax", "date", "invoice no"
    ]

    text_lower = text.lower()
    score = sum(1 for k in keywords if k in text_lower)

    return score >= 2

# =========================================================
# FIELD EXTRACTION
# =========================================================

def extract_invoice_fields(text: str):
    fields = {
        "invoice_number": None,
        "vendor_name": None,
        "amount_total": None,
        "invoice_date": None,
        "tax_id": None,
    }

    patterns = {
        "invoice_number": r"invoice\s*(no|number)?[:\-]?\s*([A-Za-z0-9\-]+)",
        "invoice_date": r"date[:\-]?\s*(\d{2}[-/]\d{2}[-/]\d{4})",
        "amount_total": r"(total|amount)\s*[:\-]?\s*([\d,]+\.\d{2})",
        "tax_id": r"(gstin|gst|tax id)[:\-]?\s*([A-Z0-9]{10,15})",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            fields[key] = match.groups()[-1]

    if fields["amount_total"]:
        try:
            fields["amount_total"] = float(fields["amount_total"].replace(",", ""))
        except Exception:
            fields["amount_total"] = None

    return fields

# =========================================================
# MAIN ENDPOINT
# =========================================================

@app.post("/analyze_invoice")
async def analyze_invoice(file: UploadFile = File(...)):
    tmp_path = None

    try:
        # -------------------------
        # SAVE TEMP IMAGE
        # -------------------------
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # -------------------------
        # LOAD IMAGE & PREPROCESS (OpenCV)
        # -------------------------
        image = Image.open(tmp_path).convert("RGB")
        img_np = np.array(image)
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        
        # Binarization and noise reduction to improve OCR accuracy
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        processed_img = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # -------------------------
        # OCR (SAFE)
        # -------------------------
        try:
            ocr_text = pytesseract.image_to_string(processed_img)
        except Exception:
            raise HTTPException(status_code=400, detail="OCR engine failed to read the image")

        if not ocr_text or not ocr_text.strip():
            raise HTTPException(status_code=400, detail="No readable text found in image. Please upload a clear document.")

        # -------------------------
        # INVOICE CHECK
        # -------------------------
        if not looks_like_invoice(ocr_text):
            raise HTTPException(status_code=400, detail="Document rejected: It does not appear to be a valid invoice based on its contents.")

        # -------------------------
        # EXTRACT FIELDS
        # -------------------------
        fields = extract_invoice_fields(ocr_text)

        # -------------------------
        # FRAUD RULES
        # -------------------------
        flags = []
        risk_score = 0

        processed = set(load_json(PROCESSED_JSON, []))
        history = load_json(VENDOR_HISTORY_JSON, {})
        stats = load_json(STATS_JSON, {"total_processed": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0})

        inv_no = fields["invoice_number"]
        amount = fields["amount_total"]
        tax_id = fields["tax_id"]
        inv_date_str = fields["invoice_date"]

        if not inv_no:
            flags.append("NO_INVOICE_NUMBER")
            risk_score += 30
        elif inv_no in processed:
            flags.append("DUPLICATE_INVOICE")
            risk_score += 30
        else:
            processed.add(inv_no)

        if not tax_id:
            flags.append("NO_TAX_ID")
            risk_score += 10
        elif not re.match(GSTIN_REGEX, tax_id):
            flags.append("INVALID_TAX_ID")
            risk_score += 30

        if amount is None:
            flags.append("NO_TOTAL_AMOUNT")
            risk_score += 10
        else:
            # Check for suspiciously round amounts
            if amount > 0 and amount % 1000 == 0:
                flags.append("SUSPICIOUS_ROUND_AMOUNT")
                risk_score += 15
                
        # Check for future dates
        if inv_date_str:
            try:
                # Try parsing standard formats like dd/mm/yyyy or dd-mm-yyyy
                date_format = "%d/%m/%Y" if "/" in inv_date_str else "%d-%m-%Y"
                inv_date = datetime.strptime(inv_date_str, date_format)
                if inv_date > datetime.now():
                    flags.append("FUTURE_DATE_DETECTED")
                    risk_score += 40
            except ValueError:
                flags.append("INVALID_DATE_FORMAT")
                risk_score += 10

        risk_score = min(risk_score, 100)

        if risk_score > 60:
            risk_category = "High"
            stats["high_risk"] += 1
        elif risk_score >= 30:
            risk_category = "Medium"
            stats["medium_risk"] += 1
        else:
            risk_category = "Low"
            stats["low_risk"] += 1

        stats["total_processed"] += 1

        save_json(PROCESSED_JSON, list(processed))
        save_json(VENDOR_HISTORY_JSON, history)
        save_json(STATS_JSON, stats)

        # -------------------------
        # FINAL RESPONSE
        # -------------------------
        return {
            "status": "success",
            "fields": fields,
            "flags": flags,
            "report_json": {
                "risk_category": risk_category,
                "risk_percentage": risk_score,
                "summary_of_anomalies": (
                    "Risk score calculated using rule-based analysis. "
                    "Detected issues: " + ", ".join(flags)
                ),
                "action_required": (
                    "Manual verification recommended"
                    if risk_category != "Low"
                    else "No immediate action required"
                )
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.format_exc())
        return {
            "status": "rejected",
            "reason": "Unexpected server error while processing image"
        }

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/stats")
async def get_stats():
    stats = load_json(STATS_JSON, {"total_processed": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0})
    return {"status": "success", "data": stats}

