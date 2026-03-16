import math
import os
from typing import Optional, Tuple, Iterable, Union, List
import cv2
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

from image_helpers import ImageLike, Image, _to_bgr

Number = Union[int, float]
Rect = Tuple[Number, Number, Number, Number]


def _coord_to_px(v: Number, total: int) -> int:
    if isinstance(v, float) and 0.0 < v <= 1.0:
        return int(round(v * total))
    return int(round(v))


def _resolve_region(region: Optional[Rect], w: int, h: int) -> Tuple[int, int, int, int]:
    if not region:
        return 0, 0, w, h
    x1 = max(0, min(_coord_to_px(region[0], w), w))
    y1 = max(0, min(_coord_to_px(region[1], h), h))
    x2 = max(0, min(_coord_to_px(region[2], w), w))
    y2 = max(0, min(_coord_to_px(region[3], h), h))
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return x1, y1, x2, y2


def _rotate(img: np.ndarray, angle: float, interp=cv2.INTER_LINEAR, border_val=(0, 0, 0)):
    (h, w) = img.shape[:2]
    c = (w / 2.0, h / 2.0)
    M = cv2.getRotationMatrix2D(c, angle, 1.0)
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    nw = int(np.ceil(h * sin + w * cos))
    nh = int(np.ceil(h * cos + w * sin))
    M[0, 2] += (nw / 2) - c[0]
    M[1, 2] += (nh / 2) - c[1]
    return cv2.warpAffine(img, M, (nw, nh), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=border_val)


def _resize(img: np.ndarray, scale: float, interp=cv2.INTER_LINEAR):
    h, w = img.shape[:2]
    return cv2.resize(img, (max(1, int(round(w * scale))), max(1, int(round(h * scale)))), interpolation=interp)


def _build_white_ignoring_mask(bgr: np.ndarray, white_thresh=240, sat_thresh=25) -> np.ndarray:
    mask1 = ~((bgr[:, :, 0] >= white_thresh) & (bgr[:, :, 1] >= white_thresh) & (bgr[:, :, 2] >= white_thresh))
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask2 = hsv[:, :, 1] > sat_thresh
    mask = (mask1 & mask2).astype(np.uint8) * 255
    if mask.mean() < 5:
        mask = (mask1.astype(np.uint8)) * 255
    return mask


def _load_template_and_mask(tpl, force_ignore_white=True, white_thresh=240, sat_thresh=25):
    if tpl.ndim == 2:
        return cv2.cvtColor(tpl, cv2.COLOR_GRAY2BGR), None

    if tpl.shape[2] == 4:
        bgr = tpl[:, :, :3]
        alpha = tpl[:, :, 3]
        mask = (alpha > 0).astype(np.uint8) * 255
        if force_ignore_white:
            mask2 = _build_white_ignoring_mask(bgr, white_thresh, sat_thresh)
            mask = cv2.bitwise_and(mask, mask2)
        return bgr, mask

    bgr = tpl[:, :, :3]
    if force_ignore_white:
        mask = _build_white_ignoring_mask(bgr, white_thresh, sat_thresh)
    else:
        mask = _build_white_ignoring_mask(bgr, white_thresh=250, sat_thresh=0)
    return bgr, mask


def _canny_edges(img_bgr: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    lo = 50
    hi = 150
    e = cv2.Canny(g, lo, hi)
    return e


def _find_green_hint(bgr: np.ndarray, target=(93, 189, 93), tol: int = 12, min_area: int = 30):
    lower = np.array([max(0, target[0] - tol), max(0, target[1] - tol), max(0, target[2] - tol)], dtype=np.uint8)
    upper = np.array([min(255, target[0] + tol), min(255, target[1] + tol), min(255, target[2] + tol)], dtype=np.uint8)
    mask = cv2.inRange(bgr, lower, upper)

    if mask is None or mask.sum() == 0:
        return None, None, None

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return None, None, None

    best_idx = -1
    best_area = 0
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area and area > best_area:
            best_area = area
            best_idx = i

    if best_idx == -1:
        return None, None, None

    cx, cy = centroids[best_idx]
    return int(round(cx)), int(round(cy)), mask


def _eval_angle_worker(roi: np.ndarray, roi_edges: np.ndarray, tpl_bgr: np.ndarray, tpl_mask: Optional[np.ndarray], ang: float, scales: np.ndarray):
    try:
        try:
            cv2.setNumThreads(1)
        except Exception:
            pass

        tpl_rot = _rotate(tpl_bgr, ang, interp=cv2.INTER_LINEAR)
        mask_rot = _rotate(tpl_mask, ang, interp=cv2.INTER_NEAREST, border_val=0) if tpl_mask is not None else None

        rh, rw = roi.shape[:2]
        best = (-1.0, None, None, ang, 1.0)

        for sc in scales:
            tpl_rs = _resize(tpl_rot, float(sc), interp=cv2.INTER_LINEAR)
            mask_rs = _resize(mask_rot, float(sc), interp=cv2.INTER_NEAREST) if mask_rot is not None else None

            th, tw = tpl_rs.shape[:2]
            if th > rh or tw > rw or th < 3 or tw < 3:
                continue

            if mask_rs is not None:
                res1 = cv2.matchTemplate(roi, tpl_rs, cv2.TM_CCORR_NORMED, mask=mask_rs)
            else:
                res1 = cv2.matchTemplate(roi, tpl_rs, cv2.TM_CCORR_NORMED)
            _, max_val1, _, max_loc1 = cv2.minMaxLoc(res1)

            tpl_edges = _canny_edges(tpl_rs)
            res2 = cv2.matchTemplate(roi_edges, tpl_edges, cv2.TM_CCOEFF_NORMED)
            _, max_val2, _, max_loc2 = cv2.minMaxLoc(res2)

            if max_val1 >= max_val2:
                score, loc = float(max_val1), max_loc1
            else:
                score, loc = float(max_val2), max_loc2

            if score > best[0]:
                best = (score, loc, (th, tw), ang, float(sc))

        return best
    except Exception:
        return (-1.0, None, None, ang, 1.0)


def _search_roi(roi: np.ndarray, tpl_bgr: np.ndarray, tpl_mask: Optional[np.ndarray], threshold: float, angles: Iterable[float], scales: np.ndarray, parallel: bool, max_workers: Optional[int] = None):
    roi_edges = _canny_edges(roi)

    best_score = -1.0
    best_loc = None
    best_tpl_hw = None
    best_ang = 0.0
    best_sc = 1.0

    angle_list = list(angles)

    if parallel and len(angle_list) > 1:
        if max_workers is None or max_workers <= 0:
            max_workers = os.cpu_count() or 4
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_eval_angle_worker, roi, roi_edges, tpl_bgr, tpl_mask, float(ang), scales) for ang in angle_list]
            for fut in as_completed(futures):
                score, loc, tpl_hw, ang, sc = fut.result()
                if score > best_score:
                    best_score, best_loc, best_tpl_hw, best_ang, best_sc = score, loc, tpl_hw, ang, sc
    else:
        for ang in angle_list:
            score, loc, tpl_hw, _, sc = _eval_angle_worker(roi, roi_edges, tpl_bgr, tpl_mask, float(ang), scales)
            if score > best_score:
                best_score, best_loc, best_tpl_hw, best_ang, best_sc = score, loc, tpl_hw, float(ang), sc

    if best_score < threshold or best_loc is None or best_tpl_hw is None:
        return None

    return best_score, best_loc, best_tpl_hw, best_ang, best_sc


def find_location_by_image(
    imageLike: ImageLike,
    pattern,
    region: Optional[Rect] = (605, 168, 1595, 953),
    threshold: float = 0.70,
    debug: bool = False,
    angles: Optional[Iterable[float]] = None,
    scale_range: Tuple[float, float] = (0.90, 1.10),
    scale_step: float = 0.05,
    force_ignore_white: bool = True,
    parallel: bool = True,
    max_workers: Optional[int] = 2,
    use_green_hint: bool = True,
    green_tol: int = 12,
    green_target: Tuple[int, int, int] = (93, 189, 93),
    green_window: int = 40,
) -> Optional[Tuple[int, int, float, float, float]]:
    img_full = _to_bgr(imageLike)
    if isinstance(imageLike, str):
        base, _ = os.path.splitext(imageLike)
    else:
        os.makedirs("temp", exist_ok=True)
        base = os.path.join("temp", "screenshot")
    H, W = img_full.shape[:2]
    x1, y1, x2, y2 = _resolve_region(region, W, H)
    roi_full = img_full[y1:y2, x1:x2].copy()

    tpl_bgr, tpl_mask = _load_template_and_mask(pattern, force_ignore_white=force_ignore_white)

    if angles is None:
        angles = list(range(0, 360, 5))
    else:
        angles = list(angles)
    scales = np.arange(scale_range[0], scale_range[1] + 1e-6, scale_step)

    debug_img = img_full.copy()

    if use_green_hint:
        hint_cx, hint_cy, hint_mask = _find_green_hint(roi_full, target=green_target, tol=green_tol, min_area=30)
        if hint_cx is not None:
            full_cx = x1 + hint_cx
            full_cy = y1 + hint_cy

            hw = max(4, green_window // 2)
            rx1 = max(0, full_cx - hw)
            ry1 = max(0, full_cy - hw)
            rx2 = min(W, full_cx + hw)
            ry2 = min(H, full_cy + hw)

            roi_local = img_full[ry1:ry2, rx1:rx2]

            local_angles = angles
            local_scales = scales

            res = _search_roi(roi_local, tpl_bgr, tpl_mask, threshold, local_angles, local_scales, parallel=False)
            if res is not None:
                best_score, best_loc, best_tpl_hw, best_ang, best_sc = res
                th, tw = best_tpl_hw
                tlx, tly = best_loc
                cx = rx1 + tlx + tw // 2
                cy = ry1 + tly + th // 2

                if debug:
                    cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.rectangle(debug_img, (rx1, ry1), (rx2, ry2), (255, 0, 255), 2)
                    cv2.circle(debug_img, (cx, cy), 6, (0, 255, 0), -1)
                    label = f"score={best_score:.3f} ang={best_ang:.1f}° scale={best_sc:.2f} [green]"
                    cv2.putText(debug_img, label, (cx + 10, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
                    cv2.imwrite(f"{base}_debug.png", debug_img)
                return int(cx), int(cy), float(best_score), float(best_ang), float(best_sc)

            if debug:
                cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.rectangle(debug_img, (rx1, ry1), (rx2, ry2), (255, 0, 255), 2)

    if debug:
        cv2.imwrite(f"{base}_debug.png", debug_img)
    return None


def is_coordinates_near(coor1: Tuple[float, float], coor2: Tuple[float, float], tolerance: float = 10.0, debug=False) -> Tuple[bool, float]:
    dx = coor1[0] - coor2[0]
    dy = coor1[1] - coor2[1]
    dist = math.hypot(dx, dy)
    return dist <= tolerance, dist


def find_color_to_image(
    img: ImageLike,
    target_rgbs: List[Tuple[int, int, int]],
    region: Optional[Tuple[int, int, int, int]] = None,
    tolerance: int = 10,
    ign: str = "",
    debug: bool = False,
) -> Optional[List[Tuple[int, int]]]:
    if debug:
        print(f"Finding colors {target_rgbs} in {img} with tolerance {tolerance}")
    img = _to_bgr(img)
    if img is None:
        raise FileNotFoundError(img)

    H, W = img.shape[:2]
    if region:
        x1, y1, x2, y2 = max(0, region[0]), max(0, region[1]), min(W, region[2]), min(H, region[3])
    else:
        x1, y1, x2, y2 = 0, 0, W, H

    roi = img[y1:y2, x1:x2]
    coords: List[Tuple[int, int]] = []

    for rgb in target_rgbs:
        target_bgr = (rgb[2], rgb[1], rgb[0])
        lower = np.array([max(0, c - tolerance) for c in target_bgr], dtype=np.uint8)
        upper = np.array([min(255, c + tolerance) for c in target_bgr], dtype=np.uint8)

        mask = cv2.inRange(roi, lower, upper)
        if mask.sum() == 0:
            continue

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if num_labels <= 1:
            continue

        best_idx = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        cx, cy = centroids[best_idx]
        coords.append((int(round(cx)) + x1, int(round(cy)) + y1))

    if not coords:
        return None

    if debug:
        out = img.copy()
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 2)
        for cx, cy in coords:
            cv2.circle(out, (cx, cy), 6, (0, 255, 0), -1)
        label = f"Colors={len(coords)} IGN={ign}"
        cv2.putText(out, label, (x1 + 10, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
        base, _ = os.path.splitext(img)
        dbg_path = f"{base}_color_debug.png"
        cv2.imwrite(dbg_path, out)

    return coords


def reorder_polygon_vertices(polygon: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if len(polygon) < 3:
        return polygon

    cx = sum(x for x, y in polygon) / len(polygon)
    cy = sum(y for x, y in polygon) / len(polygon)

    def angle_from_centroid(vertex):
        x, y = vertex
        return math.atan2(y - cy, x - cx)

    return sorted(polygon, key=angle_from_centroid)


def is_point_in_polygon(point: Tuple[int, int], polygon: List[Tuple[int, int]], auto_reorder: bool = True) -> bool:
    if len(polygon) < 3:
        return False

    if auto_reorder:
        polygon = reorder_polygon_vertices(polygon)

    x, y = point
    inside = False
    n = len(polygon)

    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        if xi == x and yi == y:
            return True

        if point_on_segment((xi, yi), (xj, yj), (x, y)):
            return True

        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside

        j = i

    return inside


def point_on_segment(p1: Tuple[int, int], p2: Tuple[int, int], p: Tuple[int, int]) -> bool:
    x1, y1 = p1
    x2, y2 = p2
    x, y = p

    cross_product = (y - y1) * (x2 - x1) - (x - x1) * (y2 - y1)
    if abs(cross_product) > 1e-10:
        return False

    return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)
