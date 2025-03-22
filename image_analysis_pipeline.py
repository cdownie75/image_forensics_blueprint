import os
import json
from PIL import Image, ExifTags
import cv2

def analyze_metadata(image_path):
    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()
            if not exif_data:
                return {}
            return {
                ExifTags.TAGS.get(tag): value
                for tag, value in exif_data.items()
                if tag in ExifTags.TAGS
            }
    except Exception as e:
        return {"error": str(e)}

def detect_edges(image_path):
    try:
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            return {"error": "Could not load image."}
        edges = cv2.Canny(image, 100, 200)
        return {"edges_detected": True, "shape": edges.shape}
    except Exception as e:
        return {"error": str(e)}

def detect_manipulation(image_path):
    meta = analyze_metadata(image_path)
    edges = detect_edges(image_path)
    anomalies = {
        "Missing DateTime": "DateTime" not in meta,
        "Strange Orientation": meta.get("Orientation", 1) not in [1, 6, 8],
    }
    return {
        "Metadata": meta,
        "EdgeDetection": edges,
        "Metadata_Anomalies": anomalies
    }, any(anomalies.values())

def process_directory(folder, output_report="forensic_reports.json"):
    reports = []
    for filename in os.listdir(folder):
        path = os.path.join(folder, filename)
        if os.path.isfile(path):
            findings, flagged = detect_manipulation(path)
            reports.append({
                "filename": filename,
                "flagged": flagged,
                "findings": findings
            })
    with open(output_report, "w") as f:
        json.dump({"reports": reports}, f, indent=2)