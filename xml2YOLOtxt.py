import os
import xml.etree.ElementTree as ET

# open
with open('classes.txt', 'r', encoding='utf-8') as file:
    classes = [line.strip() for line in file.readlines()]

def convert(xml_file, output_txt):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    size = root.find('size')
    w_img = int(size.find('width').text)
    h_img = int(size.find('height').text)

    with open(output_txt, "w") as f:
        for obj in root.findall('object'):
            name = obj.find('name').text

            if name not in classes:
                raise ValueError(f"[Error] file {xml_file} name {name} not in classes.")

            cls_id = classes.index(name)

            xmlbox = obj.find('bndbox')
            xmin = float(xmlbox.find('xmin').text)
            xmax = float(xmlbox.find('xmax').text)
            ymin = float(xmlbox.find('ymin').text)
            ymax = float(xmlbox.find('ymax').text)

            x_center = (xmin + xmax) / 2 / w_img
            y_center = (ymin + ymax) / 2 / h_img
            width = (xmax - xmin) / w_img
            height = (ymax - ymin) / h_img

            f.write(f"{cls_id} {x_center} {y_center} {width} {height}\n")


# 批次轉換
xml_folder = "./MahjongSoul_screenshot/in_game_screenshot"

for file in os.listdir(xml_folder):
    if file.endswith(".xml"):
        xml_path = os.path.join(xml_folder, file)
        txt_path = os.path.join(xml_folder, file.replace(".xml", ".txt"))

        convert(xml_path, txt_path)

xml_folder = "./MahjongSoul_screenshot/mahjong"

for file in os.listdir(xml_folder):
    if file.endswith(".xml"):
        xml_path = os.path.join(xml_folder, file)
        txt_path = os.path.join(xml_folder, file.replace(".xml", ".txt"))

        convert(xml_path, txt_path)