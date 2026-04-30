from ultralytics import YOLO
import os
import xml.etree.ElementTree as ET

overlap_iou_threshold = 0.3


def compute_iou(box1, box2):
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2

    inter_xmin = max(x1_min, x2_min)
    inter_ymin = max(y1_min, y2_min)
    inter_xmax = min(x1_max, x2_max)
    inter_ymax = min(y1_max, y2_max)

    inter_w = max(0, inter_xmax - inter_xmin)
    inter_h = max(0, inter_ymax - inter_ymin)
    inter_area = inter_w * inter_h

    area1 = max(0, x1_max - x1_min) * max(0, y1_max - y1_min)
    area2 = max(0, x2_max - x2_min) * max(0, y2_max - y2_min)
    union_area = area1 + area2 - inter_area

    if union_area == 0:
        return 0

    return inter_area / union_area


def remove_overlapping_boxes(boxes, iou_threshold):
    detections = []
    for box, cls, conf in zip(boxes.xyxy, boxes.cls, boxes.conf):
        detections.append({
            "box": tuple(box.tolist()),
            "cls": int(cls),
            "conf": float(conf),
        })

    detections.sort(key=lambda detection: detection["conf"], reverse=True)

    kept = []
    for detection in detections:
        if all(
            compute_iou(detection["box"], kept_detection["box"]) <= iou_threshold
            for kept_detection in kept
        ):
            kept.append(detection)

    return kept

# ===== 設定 =====
image_dir = "MahjongSoul_screenshot/non_label/"     # 未標註圖片資料夾
with open('classes.txt', 'r', encoding='utf-8') as file:
    class_names = [line.strip() for line in file.readlines()]
model = YOLO("runs/detect/best_train/weights/best.pt")

results = model.predict(
    source=image_dir,
    save=False,
    conf=0.5
)

# ===== 產生 label =====
for r in results:
    img_path = r.path
    img_name = os.path.basename(img_path)
    base_name = os.path.splitext(img_name)[0]

    h, w = r.orig_shape

    # ===== XML 路徑 =====
    xml_path = os.path.join(image_dir, base_name + ".xml")

    # ===== 建立 XML =====
    annotation = ET.Element("annotation")

    ET.SubElement(annotation, "filename").text = img_name

    size = ET.SubElement(annotation, "size")
    ET.SubElement(size, "width").text = str(w)
    ET.SubElement(size, "height").text = str(h)
    ET.SubElement(size, "depth").text = "3"

    for detection in remove_overlapping_boxes(r.boxes, overlap_iou_threshold):
        x1, y1, x2, y2 = detection["box"]
        cls = detection["cls"]

        # ===== XML format =====
        obj = ET.SubElement(annotation, "object")
        ET.SubElement(obj, "name").text = class_names[cls]

        bndbox = ET.SubElement(obj, "bndbox")
        ET.SubElement(bndbox, "xmin").text = str(int(x1))
        ET.SubElement(bndbox, "ymin").text = str(int(y1))
        ET.SubElement(bndbox, "xmax").text = str(int(x2))
        ET.SubElement(bndbox, "ymax").text = str(int(y2))

    # ===== 儲存 XML =====
    tree = ET.ElementTree(annotation)
    tree.write(xml_path)

print("✅ Auto labeling 完成")
