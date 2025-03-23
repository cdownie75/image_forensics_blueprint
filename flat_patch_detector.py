
import cv2
import numpy as np
from PIL import Image

def detect_flat_patches(image_path, patch_size=40, std_threshold=5):
    """
    Detects flat patches in an image based on pixel intensity variance.
    Returns a list of flagged patch regions.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    height, width = img.shape
    flagged_patches = []

    for y in range(0, height - patch_size, patch_size):
        for x in range(0, width - patch_size, patch_size):
            patch = img[y:y + patch_size, x:x + patch_size]
            std_dev = np.std(patch)
            if std_dev < std_threshold:
                flagged_patches.append({
                    "x": x,
                    "y": y,
                    "std_dev": float(std_dev)
                })

    return flagged_patches

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python flat_patch_detector.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    results = detect_flat_patches(image_path)
    print(f"Found {len(results)} flat patches:")
    for r in results:
        print(r)
