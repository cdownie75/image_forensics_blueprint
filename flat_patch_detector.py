import os
import cv2
import numpy as np
from PIL import Image
from receipt_cropper import save_flat_patch_overlay


def detect_flat_patches(image_path, patch_size=30, std_threshold=3.0):
    filename = os.path.basename(image_path)

    if "_overlay" in filename or "_cropped_debug" in filename:
        print(f"[SKIP] Skipping debug/overlay file: {filename}")
        return []

    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not load image from {image_path}")

    height, width = image.shape
    flat_patches = []

    for y in range(0, height - patch_size + 1, patch_size):
        for x in range(0, width - patch_size + 1, patch_size):
            patch = image[y:y+patch_size, x:x+patch_size]
            std_dev = np.std(patch)
            if std_dev < std_threshold:
                flat_patches.append({
                    "x": x,
                    "y": y,
                    "std_dev": float(std_dev)
                })

    # Generate overlay with suspicious patches
    overlay_image = cv2.imread(image_path)
    for patch in flat_patches:
        x, y = patch["x"], patch["y"]
        cv2.rectangle(overlay_image, (x, y), (x+patch_size, y+patch_size), (0, 0, 255), 2)

    # Save overlay image
    overlay_path = save_flat_patch_overlay(overlay_image, filename)

    # Return both patch data and overlay link summary
    return {
        "patches": flat_patches,
        "summary": {
            "suspicious_flat_regions": len(flat_patches) > 0,
            "overlay_image_url": f"/overlays/{os.path.basename(overlay_path)}"
        }
    }


def generate_overlay_image(image_path, patches, output_path, patch_size=40):
    image = Image.open(image_path).convert("RGB")
    overlay = image.copy()
    from PIL import ImageDraw
    draw = ImageDraw.Draw(overlay)

    for patch in patches:
        x, y = patch["x"], patch["y"]
        draw.rectangle([x, y, x+patch_size, y+patch_size], outline="red", width=2)

    overlay.save(output_path)


# Also define the missing save_flat_patch_overlay if not already in receipt_cropper.py
# This version is here for reference and to be added to receipt_cropper.py

def save_flat_patch_overlay(overlay_image, filename, overlay_dir="overlays"):
    os.makedirs(overlay_dir, exist_ok=True)
    overlay_filename = os.path.splitext(filename)[0] + "_overlay.jpg"
    overlay_path = os.path.join(overlay_dir, overlay_filename)
    cv2.imwrite(overlay_path, overlay_image)
    print(f"[OVERLAY SAVED] {overlay_path}")
    return overlay_path
