from celery import Celery
import pytesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
import cv2
import os
from PIL import Image

celery = Celery(
    "tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://red-cvfcd2popnds73b8snfg:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://red-cvfcd2popnds73b8snfg:6379/0")
)

def preprocess_image_for_ocr(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return "Could not load image."
    small = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    return gray

import shutil
import subprocess

print("[DEBUG] Tesseract binary found at:", shutil.which("tesseract"))
try:
    version = subprocess.check_output(["tesseract", "--version"])
    print("[DEBUG] Tesseract version:", version.decode().splitlines()[0])
except Exception as e:
    print("[DEBUG] Tesseract version check failed:", e)

@celery.task(name="ocr_task")
def run_ocr(image_path):
    try:
        print(f"[OCR] Task received for {image_path}")
        gray_image = preprocess_image_for_ocr(image_path)
        if isinstance(gray_image, str):
            print(f"[OCR] Preprocessing failed: {gray_image}")
            return gray_image
        print(f"[OCR] Preprocessing complete. Running Tesseract...")
        text = pytesseract.image_to_string(gray_image)
        print(f"[OCR] OCR complete. Extracted text length: {len(text.strip())} characters")
        return text.strip()
    except Exception as e:
        print(f"[OCR] Exception during OCR: {str(e)}")
        return f"Error during OCR: {str(e)}"
def run_ocr(image_path):
    try:
        print(f"[OCR] Starting OCR for {image_path}")
        gray_image = preprocess_image_for_ocr(image_path)
        if isinstance(gray_image, str):
            print(f"[OCR] Error in preprocessing: {gray_image}")
            return gray_image
        text = pytesseract.image_to_string(gray_image)
        print(f"[OCR] OCR complete for {image_path}")
        return text.strip()
    except Exception as e:
        print(f"[OCR] Exception during OCR: {str(e)}")
        return f"Error during OCR: {str(e)}"
