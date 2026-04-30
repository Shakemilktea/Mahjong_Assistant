from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter
from ultralytics import YOLO
import cv2

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

def remove_overlapping_boxes(boxes, iou_threshold=0.5):
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

def count_visible_tiles(detections, class_names):
    visible_counts = [0] * len(class_names)

    for detection in detections:
        tile_id = int(detection["cls"])
        if 0 <= tile_id < len(visible_counts):
            visible_counts[tile_id] += 1

    return visible_counts

# 偵測手牌(含吃碰槓)
def filter_hand_tiles(detections, x_threshold=0.125, y_threshold=0.8):
    hand_tiles = []
    for detection in detections:
        x1, y1, x2, y2 = detection["box"]
        cls = detection["cls"]

        # 假設手牌在畫面下方
        if y1 > (image_height * y_threshold) and x1 > (image_width * x_threshold):
            hand_tiles.append((int(cls), x1))
    return hand_tiles

def sort_tiles(hand_tiles, class_names):
    return [
        class_names[cls]
        for cls, _ in sorted(hand_tiles, key=lambda tile: tile[1])
    ]

def convert_hand(hand):
    man = ''
    pin = ''
    sou = ''
    honors = ''

    for tile in hand:
        if tile[0] == 'm':
            man += tile[1]
        elif tile[0] == 'p':
            pin += tile[1]
        elif tile[0] == 's':
            sou += tile[1]
        elif tile[0] == 'z':
            honors += tile[1]

    return TilesConverter.string_to_34_array(
        man=man, pin=pin, sou=sou, honors=honors
    )

def calculate_ukeire(after_discard, class_names, visible_counts=None):
    shanten = Shanten()
    tiles_34 = convert_hand(after_discard)
    base_shanten = shanten.calculate_shanten(tiles_34)

    if visible_counts is None:
        visible_counts = tiles_34

    ukeire_count = 0
    waits = []

    for tile_id, tile_name in enumerate(class_names):
        if visible_counts[tile_id] >= 4:
            continue

        test_tiles = tiles_34[:]
        test_tiles[tile_id] += 1

        if shanten.calculate_shanten(test_tiles) < base_shanten:
            remaining = 4 - visible_counts[tile_id]
            ukeire_count += remaining
            waits.append((tile_name, remaining))

    return ukeire_count, waits

def suggest_discard(hand, class_names, visible_counts=None):
    shanten = Shanten()
    if visible_counts is None:
        visible_counts = convert_hand(hand)

    candidates = []
    checked_tiles = set()

    for tile in hand:
        if tile in checked_tiles:
            continue
        checked_tiles.add(tile)

        test_hand = hand.copy()
        test_hand.remove(tile)

        tiles_34 = convert_hand(test_hand)
        score = shanten.calculate_shanten(tiles_34)
        ukeire_count, waits = calculate_ukeire(
            test_hand,
            class_names,
            visible_counts=visible_counts
        )

        candidates.append({
            "discard": tile,
            "shanten": score,
            "ukeire": ukeire_count,
            "waits": waits,
        })

    candidates.sort(key=lambda x: (x["shanten"], -x["ukeire"]))
    best_shanten = candidates[0]["shanten"]
    best_ukeire = candidates[0]["ukeire"]
    best_candidates = [
        candidate
        for candidate in candidates
        if candidate["shanten"] == best_shanten
        and candidate["ukeire"] == best_ukeire
    ]
    return best_candidates, candidates

def waiting_tiles(sorted_tiles, class_names, visible_counts=None):
    shanten = Shanten()
    tiles_34 = convert_hand(sorted_tiles)
    base_shanten = shanten.calculate_shanten(tiles_34)
    if visible_counts is None:
        visible_counts = tiles_34

    waits = []
    for tile_id, tile_name in enumerate(class_names):
        if visible_counts[tile_id] >= 4:
            continue

        test_tiles = tiles_34[:]
        test_tiles[tile_id] += 1

        if shanten.calculate_shanten(test_tiles) < base_shanten:
            remaining = 4 - visible_counts[tile_id]
            waits.append((tile_name, remaining))

    return waits


# ===== 設定 =====
image_dir = "MahjongSoul_screenshot/non_label/132824.png"     # 未標註圖片資料夾
img = cv2.imread(image_dir)
if img is None:
    raise FileNotFoundError(f"Cannot read image: {image_dir}")
image_height, image_width, _ = img.shape  # 高, 寬, 通道數
with open('classes.txt', 'r', encoding='utf-8') as file:
    class_names = [line.strip() for line in file.readlines()]
model = YOLO("runs/detect/best_train/weights/best.pt")

results = model.predict(
    source=image_dir,
    save=False,
    conf=0.5
)

# 偵測看的見的所有牌
filtered_tiles = [detection for r in results for detection in remove_overlapping_boxes(r.boxes)]
visible_counts = count_visible_tiles(filtered_tiles, class_names)

# 偵測手牌
hand_tiles = filter_hand_tiles(filtered_tiles)
sorted_tiles = sort_tiles(hand_tiles, class_names)

if len(sorted_tiles) == 14:
    best_candidates, candidates = suggest_discard(
        sorted_tiles,
        class_names,
        visible_counts=visible_counts
    )
    print("discard candidates:")
    for candidate in candidates:
        print(
            candidate["discard"],
            "shanten:", candidate["shanten"],
            "ukeire:", candidate["ukeire"],
            "waits:", candidate["waits"],
        )
    print("best discards:")
    for candidate in best_candidates:
        print(
            candidate["discard"],
            "shanten:", candidate["shanten"],
            "ukeire:", candidate["ukeire"],
            "waits:", candidate["waits"],
        )
elif len(sorted_tiles) == 13:
    print("waiting tiles:")
    print(waiting_tiles(sorted_tiles, class_names, visible_counts=visible_counts))
else:
    print("Sorted tiles = %d, detected failed." % len(sorted_tiles))