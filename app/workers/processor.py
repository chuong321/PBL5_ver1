"""
Processor - Multiprocessing Architecture (PRIMARY & SECONDARY)
================================================================================
Tien trinh 1 (PRIMARY): Chay YOLO1 de phan loai 38 loai rac
Tien trinh 2 (SECONDARY): Chay YOLO2 de xac nhan co nuoc/khong nuoc

Giao thuc giao tiep:
  PRIMARY -> Queue (intermediate) -> SECONDARY

Co che ket hop (2 tien trinh hoat dong song song):
  1. Co chat long + trong luong > nguong => Co nuoc
  2. Khong chat long + trong luong <= nguong => Khong nuoc
  3. Model bao khong nuoc nhung trong luong > nguong => Co nuoc (do nuoc day chai)
  4. Model bao co chat long nhung trong luong < nguong => Co nuoc (nguong qua cao)
================================================================================
"""

import os
import multiprocessing as mp
import queue
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime

from app.core.config import (
    MODEL_PATH,
    MODEL_SECONDARY_PATH,
    MAX_QUEUE_SIZE,
    WEIGHT_THRESHOLD,
    YOLO1_CONF,
    YOLO1_IMGSZ,
    YOLO1_DEVICE,
    YOLO2_CONF,
    YOLO2_IMGSZ,
    YOLO2_DEVICE,
    PRIMARY_PROCESS_WORKERS,
    SECONDARY_PROCESS_WORKERS,
)


class PrimaryProcessor(mp.Process):
    """
    Tien trinh 1 (PRIMARY CLASSIFICATION)
    ========================================
    Chuyen trach: Phan loai 38 loai rac thai

    Input: Nhan anh tu main process qua queue
    Output: Gui ket qua (label, bounding_box) qua intermediate_queue

    Hoat dong:
    - Load YOLO1 model (best.pt)
    - Loop: Lay anh tu input_queue -> Inference -> Gui vao intermediate_queue
    - Neu label la "Chai nhua"/"Lon"/... -> Gui crop image vao secondary_queue
    """

    def __init__(
        self,
        input_queue: mp.Queue,
        intermediate_queue: mp.Queue,
        shutdown_event: mp.Event,
        worker_id: int = 0,
    ):
        super().__init__()
        self.daemon = False
        self.input_queue = input_queue
        self.intermediate_queue = intermediate_queue
        self.shutdown_event = shutdown_event
        self.worker_id = worker_id
        self.yolo_model = None
        self.labels_map = self._init_labels_map()

    def _init_labels_map(self) -> Dict[int, str]:
        """38 loai rac thai (dung de map class_id -> label)."""
        return {
            0: "plastic_bottle",
            1: "plastic_bag",
            2: "plastic_cup",
            3: "plastic_container",
            4: "paper_box",
            5: "paper_sheet",
            6: "cardboard",
            7: "newspaper",
            8: "aluminum_can",
            9: "steel_can",
            10: "glass_bottle",
            11: "glass_jar",
            12: "metal_can",
            13: "metal_wire",
            14: "textile_cloth",
            15: "textile_bag",
            16: "wood_piece",
            17: "wood_board",
            18: "ceramic_cup",
            19: "ceramic_plate",
            20: "leather_shoe",
            21: "leather_bag",
            22: "rubber_tire",
            23: "rubber_ball",
            24: "food_waste",
            25: "food_bottle",
            26: "organic_material",
            27: "electronic_device",
            28: "battery",
            29: "lightbulb",
            30: "metal_scrap",
            31: "plastic_film",
            32: "foam_material",
            33: "composite_material",
            34: "mixed_waste",
            35: "hazardous",
            36: "unknown",
            37: "misc",
        }

    def load_model(self) -> bool:
        """Load YOLO1 model."""
        try:
            if os.path.exists(MODEL_PATH):
                from ultralytics import YOLO

                self.yolo_model = YOLO(MODEL_PATH)
                print(f"[PRIMARY-{self.worker_id}] ✓ YOLO1 model loaded: {MODEL_PATH}")
                return True

            print(f"[PRIMARY-{self.worker_id}] ⚠ best.pt not found. Using dummy mode.")
            return False
        except Exception as exc:
            print(f"[PRIMARY-{self.worker_id}] ✗ Error loading YOLO1: {exc}")
            return False

    def perform_inference(self, image: np.ndarray) -> Tuple[str, float, Optional[np.ndarray]]:
        """
        Thuc hien YOLO1 inference.

        Args:
            image: OpenCV image (numpy array)

        Returns:
            Tuple: (label, confidence, crop_image_for_secondary)
        """
        try:
            if self.yolo_model is None:
                dummy_labels = list(self.labels_map.values())[:5]
                return (
                    np.random.choice(dummy_labels),
                    float(np.random.uniform(0.7, 0.99)),
                    image,
                )

            results = self.yolo_model(
                image,
                conf=YOLO1_CONF,
                imgsz=YOLO1_IMGSZ,
                verbose=False,
                device=YOLO1_DEVICE,
            )

            if results and len(results) > 0:
                result = results[0]

                if result.boxes is not None and len(result.boxes) > 0:
                    confidences = result.boxes.conf.cpu().numpy()
                    class_ids = result.boxes.cls.cpu().numpy().astype(int)
                    boxes = result.boxes.xyxy.cpu().numpy().astype(int)

                    max_idx = np.argmax(confidences)
                    confidence = float(confidences[max_idx])
                    class_id = int(class_ids[max_idx])
                    box = boxes[max_idx]

                    label = self.labels_map.get(class_id, f"unknown_{class_id}")

                    x1, y1, x2, y2 = box
                    crop_image = image[
                        max(0, y1) : min(image.shape[0], y2),
                        max(0, x1) : min(image.shape[1], x2),
                    ]

                    return label, confidence, crop_image

            return "no_detection", 0.0, image

        except Exception as exc:
            print(f"[PRIMARY-{self.worker_id}] ✗ Inference error: {exc}")
            return "error", 0.0, image

    def run(self) -> None:
        """Main loop cua PRIMARY process."""
        print(f"\n[PRIMARY-{self.worker_id}] Khoi dong tien trinh Primary Classification")

        if not self.load_model():
            print(f"[PRIMARY-{self.worker_id}] ✗ Khong the load model. Dung tien trinh.")
            return

        print(f"[PRIMARY-{self.worker_id}] ✓ San sang xu ly anh")

        while not self.shutdown_event.is_set():
            try:
                try:
                    item = self.input_queue.get(timeout=1)

                    if item is None:
                        break

                    batch_id, images, weights = item

                    print(
                        f"[PRIMARY-{self.worker_id}] 📸 Nhan batch #{batch_id} ({len(images)} anh)"
                    )

                    results = []
                    for idx, (image, weight) in enumerate(zip(images, weights)):
                        label, confidence, crop_image = self.perform_inference(image)

                        result = {
                            "batch_id": batch_id,
                            "image_idx": idx,
                            "label": label,
                            "confidence": confidence,
                            "crop_image": crop_image,
                            "weight_grams": weight,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        results.append(result)

                        print(
                            f"[PRIMARY-{self.worker_id}]   [{idx+1}/{len(images)}] {label} (conf={confidence:.2%})"
                        )

                    self.intermediate_queue.put(("primary_result", batch_id, results))
                    print(
                        f"[PRIMARY-{self.worker_id}] ✓ Batch #{batch_id} hoan thanh -> Intermediate Queue"
                    )

                except queue.Empty:
                    continue
                except Exception as exc:
                    print(f"[PRIMARY-{self.worker_id}] ✗ Error processing batch: {exc}")
                    continue

            except KeyboardInterrupt:
                print(f"[PRIMARY-{self.worker_id}] ⛔ Received interrupt signal")
                break

        print(f"[PRIMARY-{self.worker_id}] 🛑 Tien trinh PRIMARY dung")


class SecondaryProcessor(mp.Process):
    """
    Tien trinh 2 (SECONDARY VERIFICATION)
    ========================================
    Chuyen trach: Xac nhan co nuoc / khong nuoc ben trong chai/binh

    Input: Nhan crop image tu intermediate_queue (ket qua tu PRIMARY)
    Output: Gui ket qua final (label, confidence, has_liquid) qua result_queue

    Hoat dong:
    - Load YOLO2 model (lightweight - model_weights/secondary/best.pt)
    - Loop: Lay crop tu intermediate_queue -> Inference nuoc -> Gui vao result_queue
    - Ket hop voi weight_grams de xac dinh: CO NUOC hay KHONG NUOC

    Logic ket hop 4 truong hop:
      1. Model bao CO + weight > nguong => CO NUOC
      2. Model bao KHONG + weight <= nguong => KHONG NUOC
      3. Model bao KHONG + weight > nguong => CO NUOC
      4. Model bao CO + weight < nguong => CO NUOC
    """

    def __init__(
        self,
        intermediate_queue: mp.Queue,
        result_queue: mp.Queue,
        shutdown_event: mp.Event,
        worker_id: int = 0,
    ):
        super().__init__()
        self.daemon = False
        self.intermediate_queue = intermediate_queue
        self.result_queue = result_queue
        self.shutdown_event = shutdown_event
        self.worker_id = worker_id
        self.yolo_model = None

    def load_model(self) -> bool:
        """Load YOLO2 model."""
        try:
            if os.path.exists(MODEL_SECONDARY_PATH):
                from ultralytics import YOLO

                self.yolo_model = YOLO(MODEL_SECONDARY_PATH)
                print(
                    f"[SECONDARY-{self.worker_id}] ✓ YOLO2 model loaded: {MODEL_SECONDARY_PATH}"
                )
                return True

            print(
                f"[SECONDARY-{self.worker_id}] ⚠ Secondary model not found. Using dummy mode."
            )
            return False
        except Exception as exc:
            print(f"[SECONDARY-{self.worker_id}] ✗ Error loading YOLO2: {exc}")
            return False

    def detect_liquid(self, image: np.ndarray) -> Tuple[bool, float]:
        """
        Phat hien co chat long trong anh crop.

        Args:
            image: Crop image tu PRIMARY

        Returns:
            Tuple: (has_liquid: bool, confidence: float)
        """
        try:
            if self.yolo_model is None:
                has_liquid = bool(np.random.rand() > 0.5)
                return has_liquid, float(np.random.uniform(0.6, 0.95))

            results = self.yolo_model(
                image,
                conf=YOLO2_CONF,
                imgsz=YOLO2_IMGSZ,
                verbose=False,
                device=YOLO2_DEVICE,
            )

            if results and len(results) > 0:
                result = results[0]

                if result.boxes is not None and len(result.boxes) > 0:
                    has_liquid = True
                    confidence = float(result.boxes.conf.cpu().numpy().max())
                    return has_liquid, confidence

            return False, 0.0

        except Exception as exc:
            print(f"[SECONDARY-{self.worker_id}] ✗ Liquid detection error: {exc}")
            return False, 0.0

    def determine_has_liquid(
        self,
        model_detected: bool,
        model_conf: float,
        label: str,
        weight_grams: Optional[float],
    ) -> Tuple[str, float]:
        """
        Ket hop model output + weight de xac dinh FINAL: CO NUOC / KHONG NUOC.

        Args:
            model_detected: Model phat hien chat long
            model_conf: Do tin cay cua model
            label: Label tu PRIMARY (e.g., 'plastic_bottle')
            weight_grams: Trong luong (grams)

        Returns:
            Tuple: ('yes'/'no', final_confidence)
        """

        weight_threshold = WEIGHT_THRESHOLD.get(
            "bottle" if "bottle" in label.lower() else "default"
        )

        if weight_grams is None:
            return ("yes" if model_detected else "no", model_conf)

        if model_detected and weight_grams > weight_threshold:
            return ("yes", model_conf * 0.95)

        if not model_detected and weight_grams <= weight_threshold:
            return ("no", model_conf * 0.95)

        if not model_detected and weight_grams > weight_threshold:
            return ("yes", (1 - model_conf) * 0.85)

        return ("yes", model_conf * 0.80)

    def run(self) -> None:
        """Main loop cua SECONDARY process."""
        print(f"\n[SECONDARY-{self.worker_id}] Khoi dong tien trinh Secondary Verification")

        if not self.load_model():
            print(
                f"[SECONDARY-{self.worker_id}] ⚠ Khong the load YOLO2. Su dung weight-only logic."
            )

        print(f"[SECONDARY-{self.worker_id}] ✓ San sang xac nhan nuoc")

        while not self.shutdown_event.is_set():
            try:
                try:
                    msg_type, batch_id, primary_results = self.intermediate_queue.get(
                        timeout=1
                    )

                    if msg_type is None:
                        break

                    print(f"[SECONDARY-{self.worker_id}] 📊 Nhan batch #{batch_id} tu PRIMARY")

                    final_results = []
                    for primary_result in primary_results:
                        crop_image = primary_result["crop_image"]
                        label = primary_result["label"]
                        weight_grams = primary_result["weight_grams"]

                        model_detected, model_conf = self.detect_liquid(crop_image)
                        has_liquid, liquid_conf = self.determine_has_liquid(
                            model_detected, model_conf, label, weight_grams
                        )

                        final_result = {
                            "batch_id": batch_id,
                            "image_idx": primary_result["image_idx"],
                            "label": label,
                            "confidence": primary_result["confidence"],
                            "has_liquid": has_liquid,
                            "liquid_confidence": liquid_conf,
                            "weight_grams": weight_grams,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        final_results.append(final_result)

                        print(
                            f"[SECONDARY-{self.worker_id}]   → {label}: {has_liquid} (liquid_conf={liquid_conf:.2%})"
                        )

                    self.result_queue.put(("final_result", batch_id, final_results))
                    print(
                        f"[SECONDARY-{self.worker_id}] ✓ Batch #{batch_id} hoan thanh -> Result Queue"
                    )

                except queue.Empty:
                    continue
                except Exception as exc:
                    print(f"[SECONDARY-{self.worker_id}] ✗ Error processing batch: {exc}")
                    continue

            except KeyboardInterrupt:
                print(f"[SECONDARY-{self.worker_id}] ⛔ Received interrupt signal")
                break

        print(f"[SECONDARY-{self.worker_id}] 🛑 Tien trinh SECONDARY dung")


class ProcessorOrchestrator:
    """
    Orchestrator: Quan ly ca PRIMARY va SECONDARY processes
    =========================================================
    Chuyen trach: Khoi tao, quan ly cac tien trinh va giao tiep voi main app

    Giao thuc:
      Main App -> input_queue -> [PRIMARY] -> intermediate_queue -> [SECONDARY] -> result_queue -> Main App
    """

    def __init__(self):
        self.input_queue = mp.Queue(maxsize=MAX_QUEUE_SIZE)
        self.intermediate_queue = mp.Queue(maxsize=MAX_QUEUE_SIZE)
        self.result_queue = mp.Queue(maxsize=MAX_QUEUE_SIZE)
        self.shutdown_event = mp.Event()

        self.primary_processes = []
        self.secondary_processes = []
        self.is_running = False

    def start(self) -> None:
        """Khoi dong tat ca processes."""
        print("\n" + "=" * 80)
        print("🚀 MULTIPROCESSING ORCHESTRATOR - KHOI DONG")
        print("=" * 80)

        print("\n[ORCHESTRATOR] Khoi dong PRIMARY processes...")
        for i in range(PRIMARY_PROCESS_WORKERS):
            p = PrimaryProcessor(
                self.input_queue,
                self.intermediate_queue,
                self.shutdown_event,
                worker_id=i,
            )
            p.start()
            self.primary_processes.append(p)
            print(f"[ORCHESTRATOR] ✓ PRIMARY Worker-{i} started (PID: {p.pid})")

        print("\n[ORCHESTRATOR] Khoi dong SECONDARY processes...")
        for i in range(SECONDARY_PROCESS_WORKERS):
            p = SecondaryProcessor(
                self.intermediate_queue,
                self.result_queue,
                self.shutdown_event,
                worker_id=i,
            )
            p.start()
            self.secondary_processes.append(p)
            print(f"[ORCHESTRATOR] ✓ SECONDARY Worker-{i} started (PID: {p.pid})")

        self.is_running = True
        print("\n" + "=" * 80)
        print("✅ Tat ca processes da khoi dong thanh cong!")
        print("=" * 80 + "\n")

    def stop(self) -> None:
        """Dung tat ca processes."""
        print("\n" + "=" * 80)
        print("🛑 MULTIPROCESSING ORCHESTRATOR - DUNG")
        print("=" * 80)

        self.shutdown_event.set()

        self.input_queue.put(None)
        self.intermediate_queue.put((None, None, None))

        for p in self.primary_processes + self.secondary_processes:
            p.join(timeout=5)
            if p.is_alive():
                p.terminate()
                p.join()

        self.is_running = False
        print("✅ Tat ca processes da dung\n")

    def submit_batch(self, batch_id: int, images: list, weights: list = None) -> int:
        """
        Gui batch anh vao xu ly.

        Args:
            batch_id: ID cua batch (dung de track)
            images: List of OpenCV images
            weights: List of weights (grams) - neu None, dung default

        Returns:
            batch_id neu thanh cong, -1 neu loi
        """
        try:
            if not self.is_running:
                print("❌ Processor khong dang chay!")
                return -1

            if len(images) == 0:
                print("❌ Batch khong co anh")
                return -1

            if weights is None:
                weights = [50.0] * len(images)

            if len(weights) != len(images):
                print("❌ So luong weights khong khop so luong anh")
                return -1

            self.input_queue.put((batch_id, images, weights))
            print(f"[ORCHESTRATOR] 📥 Batch #{batch_id} da submit vao input_queue")
            return batch_id

        except Exception as exc:
            print(f"[ORCHESTRATOR] ✗ Error submitting batch: {exc}")
            return -1

    def get_result(self, timeout: float = None) -> Optional[Dict]:
        """
        Lay ket qua tu result_queue.

        Args:
            timeout: Timeout tinh bang giay

        Returns:
            Dict chua final result hoac None neu timeout
        """
        try:
            msg_type, batch_id, results = self.result_queue.get(timeout=timeout)

            if msg_type == "final_result":
                return {
                    "batch_id": batch_id,
                    "results": results,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except queue.Empty:
            return None
        except Exception as exc:
            print(f"[ORCHESTRATOR] ✗ Error getting result: {exc}")
            return None

    def get_queue_stats(self) -> Dict:
        """Lay thong ke ve cac queues."""
        return {
            "input_queue_size": self.input_queue.qsize(),
            "intermediate_queue_size": self.intermediate_queue.qsize(),
            "result_queue_size": self.result_queue.qsize(),
            "is_running": self.is_running,
            "primary_processes": len([p for p in self.primary_processes if p.is_alive()]),
            "secondary_processes": len([p for p in self.secondary_processes if p.is_alive()]),
        }


orchestrator = None


def init_orchestrator() -> ProcessorOrchestrator:
    """Khoi tao global orchestrator."""
    global orchestrator
    if orchestrator is None:
        orchestrator = ProcessorOrchestrator()
    return orchestrator


def start_orchestrator() -> None:
    """Khoi dong orchestrator."""
    global orchestrator
    orchestrator = init_orchestrator()
    orchestrator.start()


def stop_orchestrator() -> None:
    """Dung orchestrator."""
    global orchestrator
    if orchestrator is not None:
        orchestrator.stop()


def get_orchestrator() -> ProcessorOrchestrator:
    """Lay global orchestrator instance."""
    global orchestrator
    if orchestrator is None:
        raise RuntimeError("Orchestrator not initialized!")
    return orchestrator
