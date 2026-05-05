from ultralytics import YOLO

model = YOLO("yolov8n.pt")

model.train(
    data="mahjong.yaml",
    epochs=150,
    imgsz=960,
    batch=4,          # 小一點
    workers=0,        # 避免bug
    pretrained=True
)

# model = YOLO("runs/detect/best_train/weights/best.pt")
#
# model.train(
#     data="mahjong.yaml",
#     epochs=1,
#     imgsz=960,
#     batch=4,
#     workers=0,
#     lr0=0.001,
# )