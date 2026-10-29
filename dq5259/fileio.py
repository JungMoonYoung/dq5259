"""원천·라벨 파일 읽기. 실패해도 예외를 던지지 않고 사유를 돌려준다 (NFR-04)."""

import hashlib
import json
import wave

from PIL import Image

ENCODINGS = ("utf-8", "utf-8-sig", "cp949")


def read_json(path):
    """(데이터, 오류사유) 튜플. JSONL은 첫 줄만 레코드로 쓰지 않고 리스트로 돌려준다."""
    raw = path.read_bytes()
    if not raw.strip():
        return None, "빈 파일"
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        try:
            if path.suffix.lower() == ".jsonl":
                return [json.loads(line) for line in text.splitlines() if line.strip()], None
            return json.loads(text), None
        except json.JSONDecodeError as e:
            return None, f"JSON 구문 오류 (line {e.lineno}, col {e.colno})"
    return None, "인코딩 판별 실패 (utf-8/cp949 아님)"


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(img, size=8):
    """차이 해시(dHash). 비슷한 이미지는 비트가 비슷하다 — Sim-ML-1 군집화에 사용."""
    small = img.convert("L").resize((size + 1, size), Image.Resampling.BILINEAR)
    px = list(small.tobytes())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (left > right)
    return bits


def image_meta(path):
    """실제 해상도·평균 밝기·dHash. 실패 시 (None, 사유)."""
    try:
        with Image.open(path) as img:
            img.load()
            width, height = img.size
            gray = img.convert("L")
            gray.thumbnail((128, 128))
            px = list(gray.tobytes())
            brightness = sum(px) / len(px)
            return {"width": width, "height": height,
                    "brightness": brightness, "dhash": dhash(img)}, None
    except Exception as e:  # 손상 이미지는 종류가 다양해 한 번에 받는다
        return None, f"이미지 읽기 실패 ({type(e).__name__})"


def audio_meta(path):
    try:
        with wave.open(str(path), "rb") as w:
            frames, rate = w.getnframes(), w.getframerate()
            return {"sample_rate": rate, "channels": w.getnchannels(),
                    "duration": frames / rate if rate else 0.0}, None
    except Exception as e:
        return None, f"음성 읽기 실패 ({type(e).__name__})"
