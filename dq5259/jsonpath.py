"""라벨 JSON에서 값을 꺼내는 최소 경로 문법.

    "info.time"                 -> 단일 값
    "annotation[].class_type"   -> 배열의 각 원소에서 값을 모은 리스트

항상 리스트를 반환한다. 경로가 없으면 [MISSING]을 돌려준다.
"""

MISSING = object()


def get(obj, path):
    nodes = [obj]
    for part in path.split("."):
        expand = part.endswith("[]")
        key = part[:-2] if expand else part
        nxt = []
        for node in nodes:
            if node is MISSING:
                nxt.append(MISSING)
                continue
            if key:
                node = node.get(key, MISSING) if isinstance(node, dict) else MISSING
            if expand:
                if isinstance(node, list):
                    nxt.extend(node)
                else:
                    nxt.append(MISSING)
            else:
                nxt.append(node)
        nodes = nxt
    return nodes


def is_null(value):
    """5259-2 완전성 측정에서 'null 값'으로 보는 기준."""
    if value is MISSING or value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def iter_strings(obj, prefix=""):
    """중첩 JSON의 모든 문자열 값을 (경로, 값)으로 순회한다."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_strings(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_strings(v, f"{prefix}[{i}]")
    elif isinstance(obj, str):
        yield prefix, obj
