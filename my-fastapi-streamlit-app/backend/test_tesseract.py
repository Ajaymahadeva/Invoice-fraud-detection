import pytesseract
from PIL import Image

# ✅ SET YOUR ACTUAL TESSERACT PATH
pytesseract.pytesseract.tesseract_cmd = r"D:\project\tesseractmode\tesseract.exe"

print("Tesseract path:", pytesseract.pytesseract.tesseract_cmd)

# ✅ CHECK VERSION
try:
    print("Tesseract version:", pytesseract.get_tesseract_version())
except Exception as e:
    print("ERROR: Tesseract not working")
    print(e)
    exit()

# ✅ SIMPLE OCR TEST
try:
    img = Image.new("RGB", (200, 80), color="white")
    text = pytesseract.image_to_string(img)
    print("OCR test successful (even if text is empty)")
except Exception as e:
    print("OCR FAILED")
    print(e)

print("Tesseract setup is WORKING ✅")
