import os
import random
import shutil

def split_dataset(source_dir, output_dir, train_ratio=0.9):
    # 定義輸出資料夾
    img_train_dir = os.path.join(output_dir, "images/train")
    img_val_dir   = os.path.join(output_dir, "images/val")
    lbl_train_dir = os.path.join(output_dir, "labels/train")
    lbl_val_dir   = os.path.join(output_dir, "labels/val")

    # 建立資料夾
    os.makedirs(img_train_dir, exist_ok=True)
    os.makedirs(img_val_dir, exist_ok=True)
    os.makedirs(lbl_train_dir, exist_ok=True)
    os.makedirs(lbl_val_dir, exist_ok=True)

    # 取得所有 png
    png_files = [f for f in os.listdir(source_dir) if f.endswith(".png")]

    # 過濾掉沒有對應 txt 的檔案
    valid_files = []
    for png in png_files:
        txt = png.replace(".png", ".txt")
        if os.path.exists(os.path.join(source_dir, txt)):
            valid_files.append(png)
        else:
            print(f"[Warning] 找不到對應 txt: {png}")

    # 隨機打亂
    random.shuffle(valid_files)

    # 切分
    split_idx = int(len(valid_files) * train_ratio)
    train_files = valid_files[:split_idx]
    val_files = valid_files[split_idx:]

    print(f"Total: {len(valid_files)}")
    print(f"Train: {len(train_files)}")
    print(f"Val: {len(val_files)}")

    # 複製檔案
    def move_files(file_list, img_dst, lbl_dst):
        for png in file_list:
            txt = png.replace(".png", ".txt")

            src_img = os.path.join(source_dir, png)
            src_txt = os.path.join(source_dir, txt)

            dst_img = os.path.join(img_dst, png)
            dst_txt = os.path.join(lbl_dst, txt)

            shutil.copy2(src_img, dst_img)
            shutil.copy2(src_txt, dst_txt)

    move_files(train_files, img_train_dir, lbl_train_dir)
    move_files(val_files, img_val_dir, lbl_val_dir)

    print("✅ Done!")


# ===== 使用方式 =====
if __name__ == "__main__":
    output_dir = "MahjongSoul_screenshot/datasets/dataset/"  # 輸出資料夾
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
        os.makedirs(output_dir)

    # 讀取整張圖的
    source_dir = "MahjongSoul_screenshot/in_game_screenshot/"   # 原始資料夾
    train_ratio = 0.85
    split_dataset(source_dir, output_dir, train_ratio)

    # 讀取單張牌的
    source_dir = "MahjongSoul_screenshot/mahjong/"  # 原始資料夾
    train_ratio = 1
    split_dataset(source_dir, output_dir, train_ratio)
