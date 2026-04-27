# ProctorX Model Notes

The backend defaults to `MODEL_WEIGHTS=yolo26n.pt` and falls back to `yolo11n.pt`.

For production accuracy, train a custom YOLO11-or-newer checkpoint with exactly these classes:

1. `person`
2. `phone`
3. `paper`

Keep students restricted to `person` detections only. Phone and paper detections are never converted into student identities.

Recommended dataset composition:

- Seated exam rooms from multiple camera angles.
- Walking and standing invigilators.
- Students passing paper sheets across desks.
- Students holding phones under desk, near face, and on desk.
- Normal non-cheating movement examples to reduce false positives.

After training, set:

```env
MODEL_WEIGHTS=models/runs/proctorx-yolo/weights/best.pt
```
