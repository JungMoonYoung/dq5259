"""FR-01 프로파일링: 파일 목록화, 라벨-원천 쌍 매칭, 메타 추출, 실패 기록."""

from dataclasses import dataclass, field
from pathlib import Path

from . import fileio


@dataclass
class Sample:
    key: str
    label_path: Path | None = None
    source_path: Path | None = None
    label: dict | None = None
    label_error: str | None = None
    source_meta: dict | None = None
    source_error: str | None = None
    source_hash: str | None = None


@dataclass
class Profile:
    root: Path
    samples: list[Sample] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)

    @property
    def paired(self):
        return [s for s in self.samples if s.label_path and s.source_path]

    @property
    def labeled(self):
        return [s for s in self.samples if s.label is not None]

    def summary(self):
        n = len(self.samples)
        return {
            "samples": n,
            "label_files": sum(1 for s in self.samples if s.label_path),
            "source_files": sum(1 for s in self.samples if s.source_path),
            "paired": len(self.paired),
            "label_only": sum(1 for s in self.samples if s.label_path and not s.source_path),
            "source_only": sum(1 for s in self.samples if s.source_path and not s.label_path),
            "read_failures": len(self.failures),
        }


def build(cfg, progress=None):
    ds = cfg["dataset"]
    root = Path(ds["root"])
    if not root.is_dir():
        raise FileNotFoundError(f"데이터셋 폴더가 없습니다: {root} — 설정의 dataset.root를 확인하세요")

    label_ext = {e.lower() for e in ds["label_ext"]}
    source_ext = {e.lower() for e in ds["source_ext"]}
    suffix = ds.get("label_suffix") or ""
    by_key = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in label_ext:
            key = p.stem[:-len(suffix)] if suffix and p.stem.endswith(suffix) else p.stem
            by_key.setdefault(key, Sample(key)).label_path = p
        elif ext in source_ext:
            by_key.setdefault(p.stem, Sample(p.stem)).source_path = p

    prof = Profile(root, list(by_key.values()))
    read_meta = fileio.image_meta if ds["type"] == "image" else fileio.audio_meta
    total = len(prof.samples)
    for i, s in enumerate(prof.samples, 1):
        if s.label_path:
            s.label, s.label_error = fileio.read_json(s.label_path)
            if s.label_error:
                prof.failures.append({"file": str(s.label_path.relative_to(root)),
                                      "kind": "라벨", "reason": s.label_error})
        if s.source_path:
            s.source_hash = fileio.sha1(s.source_path)
            s.source_meta, s.source_error = read_meta(s.source_path)
            if s.source_error:
                prof.failures.append({"file": str(s.source_path.relative_to(root)),
                                      "kind": "원천", "reason": s.source_error})
        if progress:
            progress(i, total)
    return prof
