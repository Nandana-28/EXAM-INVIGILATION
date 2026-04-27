from __future__ import annotations

from math import sqrt

from backend.ml.types import BBox


def area(box: BBox) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def center(box: BBox) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = area((ix1, iy1, ix2, iy2))
    union = area(a) + area(b) - inter
    if union <= 0:
        return 0.0
    return inter / union


def contains_or_overlaps(person_box: BBox, object_box: BBox, min_overlap: float = 0.10) -> bool:
    object_area = area(object_box)
    if object_area <= 0:
        return False
    px1, py1, px2, py2 = person_box
    ox1, oy1, ox2, oy2 = object_box
    ix1, iy1 = max(px1, ox1), max(py1, oy1)
    ix2, iy2 = min(px2, ox2), min(py2, oy2)
    overlap = area((ix1, iy1, ix2, iy2)) / object_area
    return overlap >= min_overlap


def distance(a: BBox, b: BBox) -> float:
    ax, ay = center(a)
    bx, by = center(b)
    return sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def union_box(a: BBox, b: BBox) -> BBox:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def between(box: BBox, left: BBox, right: BBox, margin: float = 35.0) -> bool:
    cx, cy = center(box)
    lx, ly = center(left)
    rx, ry = center(right)
    min_x, max_x = sorted((lx, rx))
    min_y, max_y = sorted((ly, ry))
    return (min_x - margin) <= cx <= (max_x + margin) and (min_y - margin) <= cy <= (max_y + margin)


def height_width_ratio(box: BBox) -> float:
    x1, y1, x2, y2 = box
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    return height / width
