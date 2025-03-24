import cv2
import numpy as np
from PIL import Image
import os

def crop_receipt_region(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image from {image_path}")

    print(f"[CROP] Original image shape: {img.shape}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 30, 150)

    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("No contours found")

    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    cropped = img[y:y+h, x:x+w]

    print(f"[CROP] Cropped image shape: {cropped.shape}")

    # Save a debug copy of the cropped image inside 'images/' folder
    base_filename = os.path.splitext(os.path.basename(image_path))[0]
    debug_path = os.path.join("images", base_filename + "_cropped_debug.jpg")
    os.makedirs("images", exist_ok=True)
    cv2.imwrite(debug_path, cropped)
    print(f"[CROP] Debug cropped image saved to {debug_path}")

    # Save cropped image to overwrite the original path
    pil_image = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
    pil_image.save(image_path)
    print(f"[CROP] Final cropped image saved to {image_path}")

def save_flat_patch_overlay(overlay_image, filename, overlay_dir="overlays"):
    os.makedirs(overlay_dir, exist_ok=True)
    overlay_filename = os.path.splitext(filename)[0] + "_overlay.jpg"
    overlay_path = os.path.join(overlay_dir, overlay_filename)
    cv2.imwrite(overlay_path, overlay_image)
    print(f"[OVERLAY SAVED] {overlay_path}")
    return overlay_path
