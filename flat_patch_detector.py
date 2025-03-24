
import cv2
import numpy as np
from PIL import Image

def detect_flat_patches(image_path, patch_size=40, std_threshold=2.0):
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
    
    return flat_patches

def generate_overlay_image(image_path, patches, output_path, patch_size=40):
    image = Image.open(image_path).convert("RGB")
    overlay = image.copy()
    from PIL import ImageDraw
    draw = ImageDraw.Draw(overlay)

    for patch in patches:
        x, y = patch["x"], patch["y"]
        draw.rectangle([x, y, x+patch_size, y+patch_size], outline="red", width=2)

    overlay.save(output_path)
