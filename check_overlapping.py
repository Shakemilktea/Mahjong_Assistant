import os
import xml.etree.ElementTree as ET

# ===== 參數 =====
xml_root_dir = "MahjongSoul_screenshot/non_label"
iou_threshold = 0.3   # IoU 超過這個值就視為「重疊過多」


def compute_iou(box1, box2):
    # box: (xmin, ymin, xmax, ymax)
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2

    # 交集
    inter_xmin = max(x1_min, x2_min)
    inter_ymin = max(y1_min, y2_min)
    inter_xmax = min(x1_max, x2_max)
    inter_ymax = min(y1_max, y2_max)

    inter_w = max(0, inter_xmax - inter_xmin)
    inter_h = max(0, inter_ymax - inter_ymin)
    inter_area = inter_w * inter_h

    # 面積
    area1 = (x1_max - x1_min) * (y1_max - y1_min)
    area2 = (x2_max - x2_min) * (y2_max - y2_min)

    union_area = area1 + area2 - inter_area

    if union_area == 0:
        return 0

    return inter_area / union_area


def process_xml(xml_path, iou_threshold):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    objects = []

    # 收集 bbox
    for obj in root.findall("object"):
        name = obj.find("name").text
        bndbox = obj.find("bndbox")

        if bndbox is not None:
            xmin = int(bndbox.find("xmin").text)
            ymin = int(bndbox.find("ymin").text)
            xmax = int(bndbox.find("xmax").text)
            ymax = int(bndbox.find("ymax").text)

            objects.append((name, (xmin, ymin, xmax, ymax)))

    results = []

    # 兩兩比較
    for i in range(len(objects)):
        for j in range(i + 1, len(objects)):
            name1, box1 = objects[i]
            name2, box2 = objects[j]

            iou = compute_iou(box1, box2)

            if iou > iou_threshold:
                results.append((name1, box1, name2, box2, iou))

    return results


# ===== 主程式 =====
for root_dir, _, files in os.walk(xml_root_dir):
    for file in files:
        if file.endswith(".xml"):
            xml_path = os.path.join(root_dir, file)

            results = process_xml(xml_path, iou_threshold)

            if results:
                print(f"\n[Overlap Found] {xml_path}")
                for name1, box1, name2, box2, iou in results:
                    print(f"  {name1} {box1}")
                    print(f"  {name2} {box2}")
                    print(f"  IoU = {iou:.3f}")
                    print("-" * 40)