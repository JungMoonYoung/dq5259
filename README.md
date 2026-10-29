# DQ-5259 · ISO/IEC 5259 기반 AI 학습데이터 품질 평가 도구

> 표준을 번역하며 공부하고, 진단 도구를 시험하며 적용해 보니,
> ML 학습데이터에 꼭 필요한 품질 평가가 비어 있어서 직접 만들었다.

## 배경

1. **학습**: ISO/IEC 5259-2·3·5(분석·ML용 데이터 품질) 국문 번역에 참여하며 측정값(Part 2)·관리 절차(Part 3)·거버넌스(Part 5) 체계를 익혔다.
2. **적용**: 데이터 품질 진단 솔루션 시험 업무에서 범용 진단(구문·참조·메타·파일명·통계)을 11종 포맷 시험 데이터로 검증했다.
3. **발견**: 5259-2와 대조하면, 범용 진단은 일반 데이터 품질(ISO/IEC 25024 계열)에 집중한다. 5259-2가 **ML용으로 새로 정의한 특성**(균형·다양성·식별가능성·유사성)은 다루지 않는다.
4. **구현**: 그 빈 곳을 5259-2 측정값으로 직접 구현하고, 5259-3 6.3.9항의 확인 검토 절차대로 판정·기록하는 도구를 만들었다.

## 표준 조항 ↔ 구현

| 5259 조항 | 요구 내용 | 구현 |
|---|---|---|
| 5259-3 6.3.9 | 측정값 식별 | `runner.select()` 데이터 유형별 적용/미적용 + 사유 |
| 5259-3 6.3.9 b | 기준값 문서화 | YAML 설정의 `threshold`·`direction` |
| 5259-3 6.3.9 d, e | 사용 측정값·기준값 기록 | 보고서 + `runs/run_*.json` 실행 이력 |
| 5259-2 6장 | 측정 함수 | `dq5259/measures/` — QM ID별 함수 |
| 5259-2 8장 | 데이터 품질 보고 | 시험성적서 형식 HTML 보고서, 결함 CSV |

## 측정값

**사전 점검** — 평가 가능한 상태인지 확인 (범용 진단 영역이라 최소 구현)

| ID | 측정값 | 측정 함수 | 기본 기준 |
|---|---|---|---|
| Com-ML-5 | 라벨 완전성 | X = A/B (A: 라벨 없거나 불완전한 샘플, B: 전체 샘플) | ≤ 0.01 |
| Com-ML-3 | 특성 완전성 | X = A/B (특성별 null 아닌 항목 / 전체 항목), 최솟값 | ≥ 0.99 |
| Con-ML-1 | 레코드 일관성 | X = A/B (A: 중복 레코드, B: 전체 레코드), SHA-1 | ≤ 0.01 |

**본 평가** — ML 전용 품질 특성 (5259-2 6.5절)

| ID | 측정값 | 측정 함수 | 기본 기준 |
|---|---|---|---|
| Bal-ML-3 | 범주 간 균형 | X = A/B (A: 평균 범주 크기, B: 평균과의 최대 절대 차이) | ≥ 0.5 |
| Bal-ML-8 | 라벨 분포 균형 | X = JSD(실제 분포, 균일 분포), 밑 2 | ≤ 0.3 |
| Bal-ML-1 | 밝기 균형 | X = A/B (A: 평균 밝기, B: 최대 절대 차이) | 정보 제공 |
| Bal-ML-7 | 라벨 비율 균형 | X = 두 그룹 간 라벨 L 비율 차이의 최댓값 | ≤ 0.1 |
| Div-ML-3 | 범주 크기 다양성 | X = A/B (A: 기준 미만 범주 수, B: 전체 범주 수) | ≤ 0.2 |
| Idn-ML-1 | 식별가능성 비율 | X = A/B (A: 단독·결합으로 식별 가능한 레코드, B: 전체) | = 0 |
| Sim-ML-1 | 샘플 유사성 | X = 1 − B/A (A: 샘플 수, B: 군집 수) | 정보 제공 |

### 구현 해석 (표준이 구체적 방법을 정하지 않은 부분)

- **Idn-ML-1**: '단독으로' 식별 → 직접식별자 13종 정규식(주민·외국인등록번호, 여권, 면허, 카드, 계좌, 건강보험, 휴대·일반전화, 이메일, 법인·사업자번호) + 이름 필드. '결합하여' 식별 → 준식별자 조합의 동일 집단이 k명 미만(k-익명성 위반).
- **Sim-ML-1**: 측정 함수 수식 대신 비고 7("샘플 수 = 군집 수이면 0")에 맞춰 X = 1 − B/A로 해석. 군집화는 이미지 dHash(64비트)의 해밍 거리 ≤ h를 같은 군집으로 묶는 방식(Union-Find).
- **Bal-ML-7**: 모든 라벨 L과 그룹 쌍 중 비율 차이가 가장 큰 값을 대표값으로 보고.
- **기준값**은 예시이며 사용 목적에 맞게 조정해야 한다 (5259-3 6.3.9 b). 목적에 따라 기준이 크게 달라지는 측정값은 판정하지 않고 정보만 제공한다.
- 5259-2가 ISO/IEC 25024를 참조만 하는 측정값(Con-ML-3 등)은 구현하지 않았다.

## 사용법

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 결함을 심은 합성 데이터 생성 + 진단
.venv\Scripts\python tools\make_synthetic.py
.venv\Scripts\python -m dq5259 configs\synthetic_robot.yaml --out runs\robot

# 화면
.venv\Scripts\streamlit run app.py
```

실제 데이터는 AI Hub에서 본인 계정으로 내려받아 `data/robot`, `data/emotion`에 둔다. 설정은 `configs/aihub_*.yaml`을 쓴다.
**AI Hub 데이터는 재배포가 금지되어 있어 저장소에 포함하지 않는다.**

### 설정에서 라벨 구조 지정

```yaml
fields:
  empty_check: annotation                 # 비어 있으면 불완전 라벨
  categories: annotation[].class_type     # 범주 라벨 ([]는 배열 펼치기)
  required: [info.time, info.weather]     # Com-ML-3 대상
  unit_items: Conversation[]              # Bal-ML-7 비교 단위
  unit_label: SpeakerEmotionCategory
  unit_group: ^{SpeakerNo}.Gender         # ^ = 루트 기준, {필드} = 항목 값으로 치환
  person_items: [Speaker1, Speaker2]      # Idn-ML-1 사람 정보
  quasi_identifiers: [Gender, Age, Residence, Occupation]
```

## 검증 (SRS 8장 인수 기준)

`pytest`로 9개 시험 통과.

| ID | 내용 |
|---|---|
| 단위 | A/B 역수·JSD를 손계산 값과 비교 |
| AT-01 | 결함 주입 합성 데이터: 라벨 누락 5, 중복 2, 필수값 누락 2, 개인정보 1, 준식별자 유일 2, 손상 파일 2, 야간 보행자 쏠림, 성별 감정 편향 → **측정 결과가 주입 수와 정확히 일치** |
| AT-02 | 빈 폴더, 라벨만 있는 폴더, 없는 경로 |
| AT-03 | 깨진 JPG, 깨진 JSON, cp949 인코딩 라벨 |
| AT-05 | 같은 설정 2회 실행 결과 동일 |

## 구조

```
dq5259/
  profile.py        라벨-원천 쌍 매칭, 메타 추출, 실패 기록
  measures/         QM 구현 (gate, balance, diversity, identifiability, similarity)
  runner.py         측정값 선택 → 판정 → 이력 저장
  report.py         HTML 보고서, 결함 CSV
app.py              Streamlit 화면
tools/make_synthetic.py   결함 주입 합성 데이터 생성기
configs/            합성·AI Hub 데이터 설정
tests/              인수 시험
```
