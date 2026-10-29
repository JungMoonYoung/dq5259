"""결함을 의도적으로 심은 합성 데이터셋 생성 (SRS AT-01).

공개 데이터의 라벨 구조(배송로봇 비도로 운행 / 감정 자유대화)를 본뜬 가짜 데이터에
개수를 정확히 아는 결함을 넣고, 정답을 samples/<이름>_expected.json으로 남긴다.

    python tools/make_synthetic.py            # samples/ 아래 생성
"""

import json
import random
import shutil
import struct
import wave
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "samples"

ROBOT_CLASSES = ["sidewalk", "vegetation", "building", "road", "obstacle", "pedestrian", "vehicle", "bicycle"]
# 범주 쏠림: sidewalk·vegetation이 대부분, bicycle은 매우 적게
CLASS_WEIGHTS = [30, 25, 15, 10, 8, 6, 4, 0.5]


def robot_image(rng, dark, size=(320, 180)):
    img = Image.new("RGB", size, tuple(rng.randint(20, 60) if dark else rng.randint(120, 230) for _ in range(3)))
    d = ImageDraw.Draw(img)
    for _ in range(rng.randint(6, 12)):
        x0, y0 = rng.randint(0, 300), rng.randint(0, 160)
        x1, y1 = x0 + rng.randint(10, 120), y0 + rng.randint(10, 80)
        hi = 90 if dark else 255
        d.rectangle([x0, y0, x1, y1], fill=tuple(rng.randint(0, hi) for _ in range(3)))
    return img


def robot_label(rng, name, time, objects, weather="sunny", extra_info=None):
    info = {"filename": f"{name}.jpg", "location": "bucheon", "case": "sidewalk", "time": time,
            "season": "autumn", "weather": weather, "device_type": "wheel-based", "sensor_id": "cam02"}
    info.update(extra_info or {})
    return {
        "annotation_add": {"imgWidth": 320, "imgHeight": 180, "class_count": len(set(objects))},
        "annotation": [{"annotation_id": rng.randint(10**6, 10**7), "class_type": c,
                        "box": {"top": 0, "left": 0, "width": 10, "height": 10}} for c in objects],
        "info": info,
    }


def make_robot(rng):
    root = OUT / "robot"
    if root.exists():
        shutil.rmtree(root)
    src, lab = root / "01.원천데이터", root / "02.라벨링데이터"
    src.mkdir(parents=True)
    lab.mkdir(parents=True)
    exp = {"samples": 0, "com_ml_5": 0, "con_ml_1": 0, "com_ml_3_weather_null": 0,
           "idn_direct": 0, "read_failures": 0, "class_counts": {}, "night": 0,
           "resolutions": {}, "con_ml_2_inconsistent_pairs": []}

    def put(name, objects, time="day", dark=False, weather="sunny", extra=None, write_label=True, image=None,
            size=(320, 180)):
        img = image or robot_image(rng, dark, size)
        img.save(src / f"{name}.jpg", quality=90)
        res = f"{img.size[0]}×{img.size[1]}"
        exp["resolutions"][res] = exp["resolutions"].get(res, 0) + 1
        if write_label:
            (lab / f"{name}.json").write_text(json.dumps(robot_label(rng, name, time, objects, weather, extra),
                                                         ensure_ascii=False, indent=1), encoding="utf-8")
            for c in objects:
                exp["class_counts"][c] = exp["class_counts"].get(c, 0) + 1
        exp["samples"] += 1
        return img

    base_images, base_objs = [], []
    for i in range(40):
        night = i >= 34  # 6장만 야간 → 밝기·시간대 쏠림
        objs = rng.choices(ROBOT_CLASSES, CLASS_WEIGHTS, k=rng.randint(3, 7))
        if night:
            objs += ["pedestrian"] * 3  # 야간에 보행자 비율이 높게 → Bal-ML-7 그룹 편향
        weather = "" if i in (5, 12) else "sunny"  # 필수 특성 누락 2건
        if i in (5, 12):
            exp["com_ml_3_weather_null"] += 1
        extra = {"memo": "현장 담당 010-2481-7735"} if i == 20 else None  # 직접식별자 1건
        if i == 20:
            exp["idn_direct"] += 1
        exp["night"] += night
        size = (640, 360) if i in (30, 31) else (320, 180)  # 고해상도 2장 → Bal-ML-2
        base_images.append(put(f"BT_SYN_{i:03d}", objs, "night" if night else "day", night, weather, extra, size=size))
        base_objs.append(set(objs))

    # 원천만 있고 라벨 없음 3건
    for i in range(3):
        put(f"BT_SYN_NOLABEL_{i}", [], write_label=False)
        exp["com_ml_5"] += 1
    # 라벨은 있으나 annotation이 비어 있음 1건
    put("BT_SYN_EMPTY", [])
    exp["com_ml_5"] += 1
    # 완전히 같은 이미지 2건 (원본 0번·1번 복사) → 중복(Con-ML-1)
    # 라벨은 원본과 다르게 → 유사 이미지 라벨 불일치(Con-ML-2)
    for i in range(2):
        put(f"BT_SYN_DUP_{i}", ["sidewalk"], image=base_images[i])
        exp["con_ml_1"] += 1
        if base_objs[i] != {"sidewalk"}:
            exp["con_ml_2_inconsistent_pairs"].append([f"BT_SYN_{i:03d}", f"BT_SYN_DUP_{i}"])
    # 손상 파일: 깨진 JPG(라벨 있음) 1건 + 빈 JSON(원천 있음) 1건
    (src / "BT_SYN_BROKEN.jpg").write_bytes(b"\xff\xd8\xff\xe0 not really a jpeg")
    (lab / "BT_SYN_BROKEN.json").write_text(json.dumps(robot_label(rng, "BT_SYN_BROKEN", "day", ["road"])), encoding="utf-8")
    exp["class_counts"]["road"] = exp["class_counts"].get("road", 0) + 1
    robot_image(rng, False).save(src / "BT_SYN_EMPTYJSON.jpg")
    exp["resolutions"]["320×180"] += 1
    (lab / "BT_SYN_EMPTYJSON.json").write_bytes(b"")
    exp["samples"] += 2
    exp["read_failures"] += 2
    exp["com_ml_5"] += 1  # 빈 JSON = 라벨 읽기 실패 → 불완전 라벨
    (OUT / f"{root.name}_expected.json").write_text(json.dumps(exp, ensure_ascii=False, indent=1), encoding="utf-8")
    return exp


EMOTIONS = ["중립", "기쁨", "슬픔", "분노", "불안", "당황"]
COMMON_PEOPLE = [("남성", "20대", "서울/인천/경기", "학생"), ("여성", "20대", "서울/인천/경기", "학생"),
                 ("남성", "30대", "서울/인천/경기", "회사원"), ("여성", "30대", "서울/인천/경기", "회사원")]
RARE_PEOPLE = [("남성", "70대", "제주", "어업"), ("여성", "60대", "강원", "농업")]


def tiny_wav(rng, path, seconds=0.2, rate=16000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", rng.randint(-2000, 2000)) for _ in range(int(seconds * rate))))


def make_emotion(rng):
    root = OUT / "emotion"
    if root.exists():
        shutil.rmtree(root)
    src, lab = root / "01.원천데이터", root / "02.라벨링데이터"
    src.mkdir(parents=True)
    lab.mkdir(parents=True)
    exp = {"samples": 0, "idn_quasi_records": 0, "emotion_by_gender": {}, "con_ml_2": {"A": 2, "B": 4}}
    # 같은 문장에 다른 감정 라벨 주입 (Con-ML-2): "정말 고마워요" 3건 중 1건만 다름, "괜찮아요" 2건은 동일
    # → 비교 쌍 B = C(3,2) + C(2,2) = 4, 일치 쌍 A = 1 + 1 = 2
    forced = {0: ("정말 고마워요", "기쁨"), 1: ("정말 고마워요", "기쁨"), 2: ("정말 고마워요", "분노"),
              3: ("괜찮아요", "중립"), 4: ("괜찮아요", "중립")}

    people = []
    for i in range(30):
        g1 = COMMON_PEOPLE[i % 4]
        g2 = COMMON_PEOPLE[(i + 1) % 4]
        if i == 7:
            g1 = RARE_PEOPLE[0]
        if i == 19:
            g2 = RARE_PEOPLE[1]
        if i in (7, 19):
            exp["idn_quasi_records"] += 1
        people.append((g1, g2))

    for i, (p1, p2) in enumerate(people):
        name = f"EMO_SYN_{i:03d}"
        conv = []
        for t in range(10):
            spk = "Speaker1" if t % 2 == 0 else "Speaker2"
            gender = (p1 if spk == "Speaker1" else p2)[0]
            # 성별 편향 주입: 여성 화자는 '슬픔' 비율이 높게
            weights = [3, 2, 4, 1, 1, 1] if gender == "여성" else [4, 2, 1, 2, 1, 1]
            emo = rng.choices(EMOTIONS, weights)[0]
            text = f"합성 발화 {i}-{t}"
            if t == 0 and i in forced:
                text, emo = forced[i]
            exp["emotion_by_gender"].setdefault(gender, {}).setdefault(emo, 0)
            exp["emotion_by_gender"][gender][emo] += 1
            conv.append({"Text": text, "TextNo": f"{t + 1:06d}", "SpeakerNo": spk,
                         "SpeakerEmotionCategory": emo})

        def spk_obj(p, sid):
            return {"ID": sid, "Gender": p[0], "Age": p[1], "Residence": p[2], "Occupation": p[3]}

        label = {"File": {"FileName": name}, "Speaker1": spk_obj(p1, f"{1000 + 2 * i}"),
                 "Speaker2": spk_obj(p2, f"{1001 + 2 * i}"), "Conversation": conv}
        (lab / f"{name}.json").write_text(json.dumps(label, ensure_ascii=False, indent=1), encoding="utf-8")
        tiny_wav(rng, src / f"{name}.wav")
        exp["samples"] += 1
    (OUT / f"{root.name}_expected.json").write_text(json.dumps(exp, ensure_ascii=False, indent=1), encoding="utf-8")
    return exp


if __name__ == "__main__":
    rng = random.Random(5259)
    print("robot  :", make_robot(rng))
    print("emotion:", make_emotion(rng))
