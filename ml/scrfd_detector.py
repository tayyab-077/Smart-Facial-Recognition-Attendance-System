# ml/scrfd_detector.py
# ------------------------------------

# What it does: loads the SCRFD ONNX, runs inference, merges multi‑scale outputs,
# decodes boxes + 5 keypoints, filters by score, runs NMS, and returns box/landmark results scaled to the original image.

# --------------------------------------------

# ml/scrfd_detector.py
"""
Production-ready SCRFD ONNX wrapper with decoding, scaling and NMS.

Place model at: <project_root>/ml/models/scrfd_2.5g_bnkps.onnx
Usage:
    from ml.scrfd_detector import SCRFDDetector
    det = SCRFDDetector()
    results = det.detect(img, conf_threshold=0.45, iou_thresh=0.4)
    # results: list of {"box": (x,y,w,h), "score": float, "kps": [(x,y),...5]}
"""

from pathlib import Path
import numpy as np
import onnxruntime as ort
import cv2
from typing import List, Dict, Tuple

def _iou(boxA, boxB):
    # box: (x1,y1,x2,y2)
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    areaA = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
    areaB = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])
    denom = areaA + areaB - interArea
    return 0.0 if denom <= 0 else interArea / denom

def nms_boxes(boxes: List[Tuple[int,int,int,int,float]], iou_thresh: float = 0.4):
    """
    boxes: list of (x1,y1,x2,y2,score)
    returns list of boxes after NMS (same format)
    """
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: b[4], reverse=True)
    keep = []
    while boxes:
        cur = boxes.pop(0)
        keep.append(cur)
        boxes = [b for b in boxes if _iou((cur[0],cur[1],cur[2],cur[3]), (b[0],b[1],b[2],b[3])) < iou_thresh]
    return keep

class SCRFDDetector:
    def __init__(self, model_name: str = "scrfd_2.5g_bnkps.onnx", input_size: int = 640, providers=None):
        """
        model_name: filename placed under project_root/ml/models/
        input_size: SCRFD model input size (most ONNX scrfd models use 640)
        """
        base_dir = Path(__file__).resolve().parents[1]  # project_root
        model_path = base_dir / "ml" / "models" / model_name

        if not model_path.exists():
            raise FileNotFoundError(f"SCRFD model not found: {model_path}")

        providers = providers or ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(model_path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = int(input_size)
        # SCRFD typically uses three strides
        self.strides = [8, 16, 32]

    def _preprocess(self, img: np.ndarray):
        # Keep original width/height for scaling back later
        h0, w0 = img.shape[:2]
        resized = cv2.resize(img, (self.input_size, self.input_size))
        # convert BGR->RGB, CHW, float32
        rgb = resized[:, :, ::-1].astype(np.float32)
        blob = np.transpose(rgb, (2, 0, 1))[None, ...]
        return blob, (w0, h0)

    def _safe_get_outputs(self, raw_outputs):
        """
        Some SCRFD ONNX export orders outputs differently.
        We try to detect the pattern: 9 outputs: scores(3), boxes(3), kps(3).
        If not 9 outputs, we attempt a fallback grouping.
        """
        if len(raw_outputs) >= 9:
            # assume ordering: s0,s1,s2, b0,b1,b2, k0,k1,k2
            scores = [raw_outputs[0], raw_outputs[1], raw_outputs[2]]
            bboxes = [raw_outputs[3], raw_outputs[4], raw_outputs[5]]
            kps = [raw_outputs[6], raw_outputs[7], raw_outputs[8]]
        else:
            # fallback: split into thirds
            L = len(raw_outputs)
            third = max(1, L // 3)
            scores = raw_outputs[0:third]
            bboxes = raw_outputs[third:2*third]
            kps = raw_outputs[2*third:3*third]
            # if lengths mismatch, pad with empty arrays
            while len(scores) < 3: scores.append(np.zeros((0,1)))
            while len(bboxes) < 3: bboxes.append(np.zeros((0,4)))
            while len(kps) < 3: kps.append(np.zeros((0,10)))
        return scores, bboxes, kps

    def detect(self, img: np.ndarray, conf_threshold: float = 0.45, iou_thresh: float = 0.4) -> List[Dict]:
        """
        Run SCRFD detection on BGR image.
        Returns list of dicts: {"box": (x,y,w,h), "score": float, "kps": [(x,y)...5]}
        """
        if img is None:
            return []

        blob, (w0, h0) = self._preprocess(img)
        # run ONNX
        raw_outputs = self.session.run(None, {self.input_name: blob})
        scores_list, boxes_list, kps_list = self._safe_get_outputs(raw_outputs)

        proposals = []  # will hold tuples (x1,y1,x2,y2,score, kps_list)
        input_size = self.input_size

        # For each stride-level feature map
        for idx, stride in enumerate(self.strides):
            scores = scores_list[idx]    # shape (N,1)
            bboxes = boxes_list[idx]     # shape (N,4)
            kpss = kps_list[idx]         # shape (N,10)
            if scores is None or bboxes is None or kpss is None:
                continue

            # feature map dims for this stride (based on input_size)
            fm_h = input_size // stride
            fm_w = input_size // stride

            # Flatten possibility: ensure shapes are [fm_h*fm_w, ...]
            scores_flat = np.asarray(scores).reshape(-1)
            bboxes_flat = np.asarray(bboxes).reshape(-1, 4)
            kpss_flat = np.asarray(kpss).reshape(-1, 10)

            total = fm_h * fm_w
            # iterate positions
            for i in range(min(len(scores_flat), total)):
                score = float(scores_flat[i])
                if score < conf_threshold:
                    continue

                y = i // fm_w
                x = i % fm_w
                cx = (x + 0.5) * stride
                cy = (y + 0.5) * stride

                bbox = bboxes_flat[i]  # often [dx,dy, dw_log, dh_log] or normalized
                # decode width/height
                # if bbox values are very small (<3) we assume they are log-sizes as many SCRFD exports do
                if np.max(np.abs(bbox)) > 1.01:
                    # bbox interpreted as [dx, dy, w_log, h_log] in model-space
                    dx = float(bbox[0]) * stride
                    dy = float(bbox[1]) * stride
                    w = float(np.exp(bbox[2])) * stride
                    h = float(np.exp(bbox[3])) * stride
                    x1_model = cx + dx - w * 0.5
                    y1_model = cy + dy - h * 0.5
                else:
                    # bbox likely normalized (0..1) => scale to model space
                    x1_model = float(bbox[0]) * input_size
                    y1_model = float(bbox[1]) * input_size
                    x2_model = float(bbox[2]) * input_size
                    y2_model = float(bbox[3]) * input_size
                    w = x2_model - x1_model
                    h = y2_model - y1_model
                    x1_model = x1_model
                    y1_model = y1_model

                # scale to original image coordinates
                sx = w0 / input_size
                sy = h0 / input_size
                x1 = int(max(0, min(w0 - 1, round(x1_model * sx))))
                y1 = int(max(0, min(h0 - 1, round(y1_model * sy))))
                w_px = int(max(1, round(w * sx)))
                h_px = int(max(1, round(h * sy)))
                x2 = min(w0 - 1, x1 + w_px)
                y2 = min(h0 - 1, y1 + h_px)

                # decode landmarks: kpss typically gives offsets in model-space relative to grid or normalized
                kps_raw = kpss_flat[i]
                kps_pts = []
                # try two decodings: if values >1 assume model-space coords; else normalized
                if np.max(np.abs(kps_raw)) > 1.01:
                    # model-space: convert each (px,py) -> original
                    for j in range(0, 10, 2):
                        px_model = float(kps_raw[j])
                        py_model = float(kps_raw[j+1])
                        px = int(max(0, min(w0 - 1, round(px_model * sx))))
                        py = int(max(0, min(h0 - 1, round(py_model * sy))))
                        kps_pts.append((px, py))
                else:
                    # normalized 0..1
                    for j in range(0, 10, 2):
                        px_n = float(kps_raw[j])
                        py_n = float(kps_raw[j+1])
                        px = int(max(0, min(w0 - 1, round(px_n * w0))))
                        py = int(max(0, min(h0 - 1, round(py_n * h0))))
                        kps_pts.append((px, py))

                proposals.append((x1, y1, x2, y2, score, kps_pts))

        # Run NMS (convert to x1,y1,x2,y2,score)
        nms_in = [(x1, y1, x2, y2, s) for (x1, y1, x2, y2, s, kps) in proposals]
        kept = nms_boxes(nms_in, iou_thresh=iou_thresh)

        # build final results with associated kps (match by proximity)
        final = []
        for (x1, y1, x2, y2, score) in kept:
            # find nearest proposal's kps by center distance
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            best_kps = None
            best_dist = None
            for (px1, py1, px2, py2, s, kps) in proposals:
                pcx = (px1 + px2) / 2
                pcy = (py1 + py2) / 2
                d = (pcx - cx)**2 + (pcy - cy)**2
                if best_kps is None or d < best_dist:
                    best_dist = d
                    best_kps = kps
            final.append({
                "box": (int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                "score": float(score),
                "kps": best_kps or []
            })

        return final
