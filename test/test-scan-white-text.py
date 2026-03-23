import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
import pytesseract

image_path = os.path.join(os.path.dirname(__file__), "images", "image.png")
img = cv2.imread(image_path)
if img is None:
    print("ERROR: Could not load image")
    sys.exit(1)

print(f"Image size: {img.shape}")
print("=" * 70)

# Expected text from the image (what we can see):
expected_lines = [
    "Kill HP Bonus", "140.0",
    "Critical Damage Rate", "10.00%",
    "Excellent Damage Rate", "57.90%",
    "Defense Ignore Rate", "25.30%",
    "DMG Reduction", "69.23%",
    "Double Attack Rate", "16.06%",
    "DMG Reflection", "33.00%",
    "DMG Bonus", "49.00%",
    "DMG Absorption", "70.00%",
    "Max SD", "277576/277789",
    "SD Regen SPD (/3s)", "3.42%",
    "COMBO Energy Regen SPD", "150.20%",
    "PVP DMG Reduction", "5.79%",
]

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
kernel = np.ones((2, 2), np.uint8)

os.makedirs(os.path.join(os.path.dirname(__file__), "temp"), exist_ok=True)

variants = []

# --- Variant 1: gray_thresh_inv (invert for white text -> black text on white bg)
for thresh in [100, 120, 140, 150, 160, 180]:
    _, th = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY_INV)
    variants.append((f"gray_thresh_inv_t{thresh}", th))

# --- Variant 2: gray_thresh normal (white text stays white)
for thresh in [100, 140, 180]:
    _, th = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
    variants.append((f"gray_thresh_t{thresh}", th))

# --- Variant 3: CLAHE + threshold
for clip in [2.0, 3.0]:
    for thresh in [100, 140, 180]:
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(4, 4))
        enh = clahe.apply(gray)
        _, th = cv2.threshold(enh, thresh, 255, cv2.THRESH_BINARY_INV)
        variants.append((f"clahe_inv_c{clip}_t{thresh}", th))

# --- Variant 4: Otsu
_, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
variants.append(("otsu", otsu))

_, otsu_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
variants.append(("otsu_inv", otsu_inv))

# --- Variant 5: Adaptive threshold
adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
variants.append(("adaptive_inv", adapt))

adapt2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 5)
variants.append(("adaptive_mean_inv", adapt2))

# --- Variant 6: white_text (high value, low saturation in HSV)
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
# White text: low saturation, high value
mask = cv2.inRange(hsv, np.array([0, 0, 150]), np.array([180, 50, 255]))
mask_inv = 255 - mask  # black text on white bg
variants.append(("white_hsv", mask_inv))

mask2 = cv2.inRange(hsv, np.array([0, 0, 120]), np.array([180, 80, 255]))
mask2_inv = 255 - mask2
variants.append(("white_hsv_wide", mask2_inv))

# Test each variant with PSM 6 (block of text) at scale 2 and 3
best_score = 0
best_name = ""
best_text = ""

for name, binary in variants:
    for scale in [2, 3]:
        for psm in [6]:
            if scale > 1:
                scaled = cv2.resize(binary, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            else:
                scaled = binary

            text = pytesseract.image_to_string(scaled, config=f"--psm {psm}").strip()

            # Score: count how many expected items appear
            text_lower = text.lower()
            hits = sum(1 for e in expected_lines if e.lower() in text_lower)
            score = hits / len(expected_lines) * 100

            if score > 0 or "dmg" in text_lower or "kill" in text_lower:
                print(f"\n[{name}] psm={psm} scale={scale} => {score:.0f}% ({hits}/{len(expected_lines)})")
                print(f"  Text: {repr(text[:200])}")

            if score > best_score:
                best_score = score
                best_name = f"{name}_psm{psm}_s{scale}"
                best_text = text
                # Save the best binary image for inspection
                cv2.imwrite(os.path.join(os.path.dirname(__file__), "temp", f"best_{name}_s{scale}.png"), scaled)

print("\n" + "=" * 70)
print(f"BEST: {best_name} with {best_score:.0f}% match")
print(f"\nFull text output:")
print(best_text)
print("\n--- Hits check ---")
text_lower = best_text.lower()
for e in expected_lines:
    found = "OK" if e.lower() in text_lower else "MISS"
    print(f"  [{found}] {e}")
