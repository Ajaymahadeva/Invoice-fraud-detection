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
# TESSERACT CONFIG (USE YOUR ACTUAL PATH)
# =========================================================

TESSERACT_PATH = r"D:\project\tesseractmode\tesseract.exe"

try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    pytesseract.get_tesseract_version()
    logger.info(f"Tesseract configured successfully: {TESSERACT_PATH}")
except Exception as e:
    logger.error("Tesseract configuration failed")
    raise RuntimeError("Tesseract OCR not configured correctly")

# =========================================================
# CONSTANTS
# =========================================================

GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"

PROCESSED_JSON = "processed_invoices.json"
VENDOR_HISTORY_JSON = "vendor_history.json"

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
        # LOAD IMAGE
        # -------------------------
        image = Image.open(tmp_path).convert("RGB")
        img_np = np.array(image)
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)

        # -------------------------
        # OCR (SAFE)
        # -------------------------
        try:
            ocr_text = pytesseract.image_to_string(gray)
        except Exception:
            return {
                "status": "rejected",
                "reason": "OCR engine failed to read the image"
            }

        if not ocr_text or not ocr_text.strip():
            return {
                "status": "rejected",
                "reason": "No readable text found in image"
            }

        # -------------------------
        # INVOICE CHECK
        # -------------------------
        if not looks_like_invoice(ocr_text):
            return {
                "status": "rejected",
                "reason": "It is not an invoice image"
            }

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

        inv_no = fields["invoice_number"]
        amount = fields["amount_total"]
        tax_id = fields["tax_id"]

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

        risk_score = min(risk_score, 100)

        if risk_score > 60:
            risk_category = "High"
        elif risk_score >= 30:
            risk_category = "Medium"
        else:
            risk_category = "Low"

        save_json(PROCESSED_JSON, list(processed))
        save_json(VENDOR_HISTORY_JSON, history)

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

    except Exception as e:
        logger.error(traceback.format_exc())
        return {
            "status": "rejected",
            "reason": "Unexpected server error while processing image"
        }

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
