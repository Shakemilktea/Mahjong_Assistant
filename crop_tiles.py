import os, shutil
import cv2
import xml.etree.ElementTree as ET

# ===== 設定 =====
img_dir = "MahjongSoul_screenshot/non_label"      # 圖片/xml資料夾
output_dir = "MahjongSoul_screenshot/datasets/mahjong_tiles"  # 輸出資料夾
if os.path.exists(output_dir):
    shutil.rmtree(output_dir)
    os.makedirs(output_dir)

os.makedirs(output_dir, exist_ok=True)
# ===== 主程式 =====
for xml_file in os.listdir(img_dir):
    if not xml_file.endswith(".xml"):
        continue

    xml_path = os.path.join(img_dir, xml_file)

    # 解析 XML
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 找圖片檔名
    filename = root.find("filename").text
    img_path = os.path.join(img_dir, filename)

    if not os.path.exists(img_path):
        print(f"[Warning] Image not found: {img_path}")
        continue

    img = cv2.imread(img_path)

    # 每個 object
    for i, obj in enumerate(root.findall("object")):
        class_name = obj.find("name").text

        bbox = obj.find("bndbox")
        xmin = int(float(bbox.find("xmin").text))
        ymin = int(float(bbox.find("ymin").text))
        xmax = int(float(bbox.find("xmax").text))
        ymax = int(float(bbox.find("ymax").text))

        # crop
        crop = img[ymin:ymax, xmin:xmax]

        # 建立 class 資料夾
        class_dir = os.path.join(output_dir, class_name)
        os.makedirs(class_dir, exist_ok=True)

        # 存檔（避免重名）
        save_name = f"{os.path.splitext(filename)[0]}_{i}.png"
        save_path = os.path.join(class_dir, save_name)
        print(save_path)

        success = cv2.imwrite(save_path, crop)

        if not success:
            print(f"[Error] Failed to save: {save_path}")

    print(f"Processed: {xml_file}")