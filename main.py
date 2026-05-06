from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter
from ultralytics import YOLO
import ctypes
import cv2
import mss
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk

TILE_IMAGE_DIR = "MahjongSoul_screenshot/mahjong_template"
TILE_IMAGE_SIZE = (23, 30)
GAME_WINDOW_TITLE_KEYWORDS = ("雀魂", "MahjongSoul")
ANALYZE_INTERVAL_MS = 500
UI_HIGHT = 250
UI_WIDTH = 1000
UI_BG = "#050505"
UI_FG = "#f4f4f5"
UI_MUTED_FG = "#a1a1aa"
UI_FONT = ("Microsoft JhengHei", 16)
UI_SMALL_FONT = ("Microsoft JhengHei", 12)
TILE_CELL_WIDTH = 28
TILE_CELL_HEIGHT = 48
TILE_CELL_PADX = 1

user32 = ctypes.windll.user32

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]

def find_window_by_title(keywords):
    matches = []

    def enum_callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True

        title_length = user32.GetWindowTextLengthW(hwnd)
        if title_length == 0:
            return True

        buffer = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(hwnd, buffer, title_length + 1)
        title = buffer.value

        if any(keyword.lower() in title.lower() for keyword in keywords):
            matches.append(hwnd)

        return True

    enum_windows_proc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_void_p,
        ctypes.c_void_p
    )
    user32.EnumWindows(enum_windows_proc(enum_callback), 0)
    return matches[0] if matches else None

def get_window_capture_region(hwnd):
    if user32.IsIconic(hwnd):
        return None

    client_rect = RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(client_rect)):
        return None

    top_left = POINT(client_rect.left, client_rect.top)
    bottom_right = POINT(client_rect.right, client_rect.bottom)
    user32.ClientToScreen(hwnd, ctypes.byref(top_left))
    user32.ClientToScreen(hwnd, ctypes.byref(bottom_right))

    width = bottom_right.x - top_left.x
    height = bottom_right.y - top_left.y
    if width <= 0 or height <= 0:
        return None

    return {
        "left": top_left.x,
        "top": top_left.y,
        "width": width,
        "height": height,
    }

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
def filter_hand_tiles(detections, x_threshold=0.125, y_threshold=0.75):
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

    ukeire_count = 0
    waits = []
    for tile_id, tile_name in enumerate(class_names):
        if visible_counts[tile_id] >= 4:
            continue

        test_tiles = tiles_34[:]
        test_tiles[tile_id] += 1

        if shanten.calculate_shanten(test_tiles) < base_shanten:
            remaining = 4 - visible_counts[tile_id]
            waits.append((tile_name, remaining))
            ukeire_count += remaining

    return waits, ukeire_count

def screenshot_screen():
    with mss.MSS() as sct:
        hwnd = find_window_by_title(GAME_WINDOW_TITLE_KEYWORDS)
        if hwnd and user32.IsIconic(hwnd):
            return None

        monitor = get_window_capture_region(hwnd) if hwnd else None
        if monitor is None:
            monitor = sct.monitors[1]

        img = np.array(sct.grab(monitor))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def load_tile_images(class_names):
    tile_images = {}
    for tile_name in class_names:
        image_path = f"{TILE_IMAGE_DIR}/{tile_name}.png"
        image = Image.open(image_path)
        image = image.resize(TILE_IMAGE_SIZE, Image.Resampling.LANCZOS)
        tile_images[tile_name] = ImageTk.PhotoImage(image)
    return tile_images

def clear_result_frame():
    for child in result_frame.winfo_children():
        child.destroy()

def make_recommendation_key(discard_tiles=None, waits=None, ukeire=None, candidate_rows=None, status=None):
    if status:
        return ("status", status)

    if candidate_rows:
        return (
            "candidates",
            tuple(
                (
                    candidate["discard"],
                    tuple(candidate["waits"]),
                    candidate["ukeire"],
                )
                for candidate in candidate_rows
            ),
        )

    return (
        "single",
        tuple(discard_tiles or []),
        tuple(waits or []),
        ukeire,
    )

def add_tile(parent, tile_name):
    image = tile_images.get(tile_name)
    if image is None:
        tk.Label(parent, text=tile_name, font=UI_FONT, bg=UI_BG, fg=UI_FG).pack(side="left", padx=3)
        return

    tk.Label(parent, image=image, bg=UI_BG).pack(side="left", padx=3)

def add_tile_cell(parent, tile_name, count=None):
    cell = tk.Frame(parent, bg=UI_BG, width=TILE_CELL_WIDTH, height=TILE_CELL_HEIGHT)
    cell.pack(side="left", padx=TILE_CELL_PADX)
    cell.pack_propagate(False)

    image = tile_images.get(tile_name)
    if image is None:
        tk.Label(cell, text=tile_name, font=UI_SMALL_FONT, bg=UI_BG, fg=UI_FG).pack(side="top", fill="x")
    else:
        tk.Label(cell, image=image, bg=UI_BG).pack(side="top")

    count_text = f"x{count}" if count is not None else ""
    tk.Label(cell, text=count_text, font=UI_SMALL_FONT, bg=UI_BG, fg=UI_MUTED_FG).pack(side="top", fill="x")

def add_candidate_row(discard_tile=None, waits=None, ukeire=None):
    row_frame = tk.Frame(result_frame, bg=UI_BG)
    row_frame.pack(side="top", fill="x", padx=10, pady=6, anchor="w")

    if discard_tile:
        tk.Label(row_frame, text="切", font=UI_FONT, bg=UI_BG, fg=UI_FG).pack(side="left", padx=(0, 4), pady=(0, 14))
        add_tile_cell(row_frame, discard_tile)

    tk.Label(row_frame, text="摸", font=UI_FONT, bg=UI_BG, fg=UI_FG).pack(side="left", padx=(0, 4), pady=(0, 14))

    if waits:
        for tile_name, remaining in waits:
            add_tile_cell(row_frame, tile_name, count=remaining)
    else:
        empty_frame = tk.Frame(row_frame, bg=UI_BG, width=TILE_CELL_WIDTH, height=TILE_CELL_HEIGHT)
        empty_frame.pack(side="left", padx=TILE_CELL_PADX)
        empty_frame.pack_propagate(False)
        tk.Label(empty_frame, text="無", font=UI_FONT, bg=UI_BG, fg=UI_MUTED_FG).pack(expand=True)

    if ukeire is not None:
        tk.Label(row_frame, text=f"{ukeire}張", font=UI_FONT, bg=UI_BG, fg=UI_FG).pack(side="left", padx=(0, 8), pady=(0, 14))

def show_recommendation(discard_tiles=None, waits=None, ukeire=None, candidate_rows=None, status=None):
    global last_recommendation_key
    recommendation_key = make_recommendation_key(
        discard_tiles=discard_tiles,
        waits=waits,
        ukeire=ukeire,
        candidate_rows=candidate_rows,
        status=status,
    )
    if recommendation_key == last_recommendation_key:
        return

    last_recommendation_key = recommendation_key
    clear_result_frame()

    if status:
        tk.Label(result_frame, text=status, font=("Microsoft JhengHei", 18), bg=UI_BG, fg=UI_FG).pack(side="left", padx=12)
        return

    if candidate_rows:
        for candidate in candidate_rows:
            add_candidate_row(
                discard_tile=candidate["discard"],
                waits=candidate["waits"],
                ukeire=candidate["ukeire"],
            )
        return

    discard_tiles = discard_tiles or []
    if discard_tiles:
        for discard_tile in discard_tiles:
            add_candidate_row(discard_tile=discard_tile, waits=waits, ukeire=ukeire)
    else:
        add_candidate_row(waits=waits, ukeire=ukeire)

def analyze_screen():
    try:
        frame = screenshot_screen()
        if frame is None:
            show_recommendation(status="遊戲視窗已最小化，等待還原...")
            return

        global image_height, image_width
        image_height, image_width, _ = frame.shape

        results = model.predict(
            source=frame,
            save=False,
            conf=0.5,
            verbose=False
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
            show_recommendation(candidate_rows=best_candidates)
        elif len(sorted_tiles) == 13:
            wait, ukeire_count = waiting_tiles(sorted_tiles, class_names, visible_counts=visible_counts)
            show_recommendation(
                waits=wait,
                ukeire=ukeire_count,
            )
        else:
            show_recommendation(status="偵測到 %d 張，請確認畫面" % len(sorted_tiles))
    except Exception as exc:
        show_recommendation(status="截圖或辨識失敗，等待下一次重試: %s" % exc)
    finally:
        # 500 ms 後再執行一次 analyze_screen
        root.after(ANALYZE_INTERVAL_MS, analyze_screen)

# ===== 設定 =====
# image_dir = "MahjongSoul_screenshot/non_label/04162322.png"     # 未標註圖片資料夾
# img = cv2.imread(image_dir)
# if img is None:
#     raise FileNotFoundError(f"Cannot read image: {image_dir}")
# image_height, image_width, _ = img.shape  # 高, 寬, 通道數
with open('classes.txt', 'r', encoding='utf-8') as file:
    class_names = [line.strip() for line in file.readlines()]
model = YOLO("runs/detect/best_train/weights/best.pt")

# 主程式
root = tk.Tk()
root.attributes("-topmost", True)
root.geometry(f"{UI_WIDTH}x{UI_HIGHT}+0+0")

result_frame = tk.Frame(root, bg=UI_BG)
result_frame.pack(fill="both", expand=True)

last_recommendation_key = None
tile_images = load_tile_images(class_names)
show_recommendation(status="偵測中...")

analyze_screen()
root.mainloop()
