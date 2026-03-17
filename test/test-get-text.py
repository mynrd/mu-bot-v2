import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import time
import glob
from learning_ocr_search_text import get_text

test_dir = os.path.dirname(__file__)
crop_dir = os.path.join(test_dir, "temp")
os.makedirs(crop_dir, exist_ok=True)

region = (880, 1, 1300, 47)

images_dir = os.path.join(test_dir, "images")
image_files = sorted(glob.glob(os.path.join(images_dir, "*.png")))

for image_path in image_files:
    name = os.path.splitext(os.path.basename(image_path))[0]
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Could not load {name}.png")
        continue

    # Save cropped region for visual inspection
    x1, y1, x2, y2 = region
    cropped = img[y1:y2, x1:x2]
    cv2.imwrite(os.path.join(crop_dir, f"{name}_cropped.png"), cropped)

    start = time.time()
    result = get_text(image_path, search="mynrd", region=region, debug=False)
    duration = time.time() - start
    found = "mynrd" in result
    status = "PASS" if found else "FAIL"
    print(f"{name}: [{status}] {duration:.3f}s")
    print()
