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


def dhash(img, size=16):
    """차이 해시(dHash), size×size 비트를 bytes로 반환. 비슷한 이미지는 비트가 비슷하다.

    8×8(64비트)은 실제 거리 사진에서 '위는 하늘, 아래는 바닥' 구도만 같아도 같은 지문이 나와
    다른 장소 사진을 유사로 오판했다 (배송로봇 1만6천 장 실측: 다른 장소 오탐 16,838쌍).
    16×16(256비트)·거리 ≤ 24에서는 오탐 1쌍으로 줄어 기본값으로 쓴다.
    """
    small = img.convert("L").resize((size + 1, size), Image.Resampling.BILINEAR)
    px = small.tobytes()
    bits = bytearray(size * size // 8)
    for row in range(size):
        for col in range(size):
            k = row * size + col
            if px[row * (size + 1) + col] > px[row * (size + 1) + col + 1]:
                bits[k // 8] |= 0x80 >> (k % 8)
    return bytes(bits)


def image_meta(path):
    """실제 해상도·평균 밝기·dHash·8x8 썸네일(PCA 특징). 실패 시 (None, 사유)."""
    try:
        with Image.open(path) as img:
            width, height = img.size          # 원본 해상도 (draft 전에 기록)
            img.draft("RGB", (256, 256))      # JPEG은 축소 디코딩 — 1만 장 이상도 빠르게
            img.load()
            gray = img.convert("L")
            gray.thumbnail((128, 128))
            px = list(gray.tobytes())
            brightness = sum(px) / len(px)
            thumb = list(img.convert("L").resize((8, 8), Image.Resampling.BILINEAR).tobytes())
            return {"width": width, "height": height, "brightness": brightness,
                    "dhash": dhash(img), "thumb": thumb}, None
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
