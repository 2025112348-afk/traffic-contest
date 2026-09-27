# -*- coding: utf-8 -*-
"""KOSIS 농림어업총조사 지역조사 "의료시설 소재지 및 소요시간별 행정리 수"
원자료를 읍/면 단위 의료접근성 점수로 변환한다.

Colab 사용법:
    from google.colab import files
    uploaded = files.upload()   # 101_DT_1AR20116_....csv 선택
    df = build_medical_access_score(list(uploaded.keys())[0])
    df.head(20)

원자료 컬럼 구조 (시설 6종 × 9구간이 반복됨):
    {시설명}:행정리내 / 읍·면내 / 읍면외_10분미만 / 10~19 / 20~29 /
    30~39 / 40~49 / 50~59 / 60분이상
→ 컬럼명 자체에서 구간 경계가 안 잘리므로, ":행정리내"가 나오는 지점을
  기준으로 9개씩 끊어서 "이번 블록은 어느 시설이다"를 인식한다.

점수화 방법
-----------
1) 구간 대표값(분) 매핑 — 각 구간을 하나의 숫자로 근사한다.
   행정리내=0, 읍면내=7(정확한 분 단위가 표에 없어 10분미만과 행정리내
   사이 값으로 가정 — 팀 내에서 다르게 잡고 싶으면 BUCKET_MINUTES만 바꾸면 됨),
   10분미만=8, 10~19=15, 20~29=25, 30~39=35, 40~49=45, 50~59=55, 60분이상=70
   (open-ended 구간이라 다소 보수적으로 70분으로 근사)
2) 읍/면별 가중평균 소요시간 = Σ(구간 대표값 × 그 구간에 속하는 행정리 수) / 총행정리수
   → 마을 하나하나의 실제 값이 아니라, 그 읍/면 안에서 "평균적으로 얼마나
     걸리는가"를 근사한 값이다.
3) 심각도 보조지표 = 20분 이상 걸리는 행정리 비율 (20~29~60분이상 구간 합 / 총행정리수)
   → 평균값이 완화시켜버리는 "많이 늦는 소수"를 따로 보여주기 위함.
4) 시설을 "수술·중증 치료가 중심이냐"를 기준으로 1차/2차로 나눈다
   (의료법 제3조 의료기관 종별 기준 — 종합병원만 100병상 이상 +
   필수 진료과목별 전속전문의를 법적으로 요구하는 유일한 등급이다).
   - TIER1_CLEAR (동네의료, 1차 취급): 약국, 보건진료소, 보건소(지소포함),
     일반병·의원, 한방병·의원, 치과병·의원
     → 일반병원(30~99병상)은 입원은 가능해도 종합병원 같은 필수과목·중증
       요건이 없어 시골에서는 사실상 "입원 가능한 동네 의원" 역할을 한다.
       한방병원·치과병원도 수술·중증 중심이 아니라는 점은 동일하다. KOSIS
       원자료도 종합병원만 별도 컬럼으로 떼어놓고 나머지는 "병·의원"으로
       묶어놨다는 점이 이 구분과 일치한다.
   - TIER2_CLEAR (대형병원, 2차 취급): 종합병원
     → 의료법상 유일하게 중증·수술 중심 요건이 명시된 등급.
   ※ 다른 기준(예: 일반병·의원만 다시 뺀다)으로 바꾸고 싶으면
     TIER1_CLEAR/TIER2_CLEAR 리스트만 수정하면 전체가 다시 계산된다.
5) TIER1_CLEAR 각 시설의 가중평균 소요시간을 단순평균해 "1차의료_평균소요분"을
   만들고, TIER2_CLEAR(종합병원)가 원자료에 있으면 같은 방식으로
   "2차의료_평균소요분"도 만든다. 각각 min-max 정규화해 0~1의
   "1차의료_취약점수" / "2차의료_취약점수"(높을수록 나쁨)로 변환한다 —
   기존 이동격차지수(팀원 노트북)의 점수 방향과 동일하게 맞췄다.
   ※ 종합병원 컬럼이 없는 CSV로 돌리면 2차 점수는 자동으로 건너뛴다
     (전체 시설을 포함해 다시 받은 CSV가 있어야 2차 점수까지 나온다).
6) 1차·2차 점수를 "의료시설_취약점수" 하나로 합친다(0.4×1차 + 0.6×2차,
   2차 비중을 더 높게 — 종합병원 부재가 더 심각한 문제라는 판단).
   숫자는 예시이며 팀에서 정확한 비율을 정하면 됨(코드 상단 add_tier_score
   호출 다음 줄의 W1, W2만 바꾸면 전체가 다시 계산된다).
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 구간 대표값(분) — 필요하면 여기 값만 바꾸면 전체 점수가 다시 계산된다.
BUCKET_MINUTES = {
    "행정리내": 0,
    "읍면내": 7,
    "10분미만": 8,
    "10~19": 15,
    "20~29": 25,
    "30~39": 35,
    "40~49": 45,
    "50~59": 55,
    "60이상": 70,
}
BUCKET_ORDER = list(BUCKET_MINUTES.keys())

# "수술·중증 치료 중심이냐"로 1차/2차를 나눈다 — 종합병원만 법적으로
# 중증 요건이 명시돼 있고, 나머지는 규모와 무관하게 동네의료로 취급.
TIER1_CLEAR = ["약국", "보건진료소", "보건소", "일반병의원", "한방병의원", "치과병의원"]
TIER2_CLEAR = ["종합병원"]

SIDO_NAMES = {
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시",
    "세종특별자치시", "경기도", "강원특별자치도", "충청북도", "충청남도", "전북특별자치도",
    "전라남도", "경상북도", "경상남도", "제주특별자치도",
}
SIDO_ALIASES = {"강원도": "강원특별자치도", "전라북도": "전북특별자치도"}
NON_REGION = {"전국", "동부", "읍부", "면부"}

FACILITY_NAME_MAP = {
    "약국(약방포함)": "약국",
    "보건진료소": "보건진료소",
    "보건소(지소포함)": "보건소",
    "한방병?의원": "한방병의원",
    "일반병?의원": "일반병의원",
    "치과병?의원": "치과병의원",
    "종합병원": "종합병원",
}


def _load_csv_robust(path: str) -> pd.DataFrame:
    for enc in ["cp949", "euc-kr", "utf-8-sig"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩 실패: {path}")


def _parse_facility_blocks(columns: list[str]):
    """컬럼 목록을 (시설명, {구간명: 컬럼명}) 블록 리스트로 쪼갠다."""
    blocks = []
    cur_facility = None
    cur_bucket_idx = 0
    for col in columns:
        base = re.sub(r"\.\d+$", "", col)  # pandas가 붙인 중복 접미사(.1, .2 ...) 제거
        if ":행정리내" in base:
            raw_name = base.split(":")[0]
            cur_facility = FACILITY_NAME_MAP.get(raw_name, raw_name)
            blocks.append({"facility": cur_facility, "cols": {}})
            cur_bucket_idx = 0
        if cur_facility is None:
            continue
        bucket = BUCKET_ORDER[cur_bucket_idx]
        blocks[-1]["cols"][bucket] = col
        cur_bucket_idx += 1
    return blocks


def _build_eupmyeon_key(raw_names: pd.Series):
    """행 순서를 따라가며 시도->시군구->읍/면 계층을 추적해서,
    실제 '읍' 또는 '면' 개별 행에만 '시도 시군구 읍/면' 키를 붙인다.
    (전국/읍부/면부/시도합계/시군구합계 행은 None → 이후 groupby에서 제외됨)"""
    keys = []
    cur_sido, cur_sigungu = None, None
    for raw in raw_names:
        name = "" if pd.isna(raw) else str(raw).strip()
        if not name or name in NON_REGION:
            keys.append(None)
            continue
        canon = SIDO_ALIASES.get(name, name)
        if canon in SIDO_NAMES:
            cur_sido, cur_sigungu = canon, None
            keys.append(None)
            continue
        if name.endswith(("읍", "면")):
            keys.append(f"{cur_sido} {cur_sigungu} {name}" if cur_sigungu else f"{cur_sido} {name}")
            continue
        if name.endswith(("시", "군", "구")):
            cur_sigungu = name
            keys.append(None)
            continue
        keys.append(None)
    return keys


def build_medical_access_score(csv_path: str, save_path: str | None = "data/processed/medical/medical_access_score.csv"):
    df = _load_csv_robust(csv_path)
    if "시점" in df.columns:
        print("시점(연도):", df["시점"].dropna().unique())

    meta_cols = ["행정구역별", "시점", "총행정리수[행정리]"]
    facility_cols = [c for c in df.columns if c not in meta_cols and not c.startswith("Unnamed")]
    blocks = _parse_facility_blocks(facility_cols)

    df["읍면_key"] = _build_eupmyeon_key(df["행정구역별"])
    base = df[df["읍면_key"].notna()].copy()
    print(f"원본 {len(df)}행 중 읍/면 개별 행 {len(base)}개 추출")

    total_ri = pd.to_numeric(
        base["총행정리수[행정리]"].astype(str).str.replace("-", "0"), errors="coerce"
    )

    result = base[["읍면_key"]].copy()
    result["총행정리수"] = total_ri

    for block in blocks:
        facility = block["facility"]
        counts = {}
        for bucket, col in block["cols"].items():
            counts[bucket] = pd.to_numeric(
                base[col].astype(str).str.replace("-", "0"), errors="coerce"
            ).fillna(0)

        # 정합성 체크: 구간 합이 총행정리수와 얼추 맞는지 (원자료 오류 조기 발견용)
        bucket_sum = sum(counts.values())
        mismatch = (bucket_sum - total_ri).abs() > 1
        if mismatch.any():
            n_bad = mismatch.sum()
            print(f"[주의] {facility}: {n_bad}개 읍/면에서 구간 합≠총행정리수 (원자료 확인 필요)")

        weighted_minutes = sum(counts[b] * BUCKET_MINUTES[b] for b in BUCKET_ORDER)
        avg_minutes = weighted_minutes / bucket_sum.replace(0, np.nan)

        over20 = sum(counts[b] for b in ["20~29", "30~39", "40~49", "50~59", "60이상"])
        ratio_over20 = over20 / bucket_sum.replace(0, np.nan)

        result[f"{facility}_평균소요분"] = avg_minutes
        result[f"{facility}_20분이상비율"] = ratio_over20

    present_facilities = {block["facility"] for block in blocks}

    def minmax(s):
        return (s - s.min()) / (s.max() - s.min())

    def add_tier_score(tier_name: str, facilities: list[str]):
        have = [f for f in facilities if f in present_facilities]
        missing = [f for f in facilities if f not in present_facilities]
        if missing:
            print(f"[알림] {tier_name}: 원자료에 없어서 건너뜀 → {missing}")
        if not have:
            return
        cols = [f"{f}_평균소요분" for f in have]
        result[f"{tier_name}_평균소요분"] = result[cols].mean(axis=1)
        result[f"{tier_name}_취약점수"] = minmax(result[f"{tier_name}_평균소요분"])

    add_tier_score("1차의료", TIER1_CLEAR)
    add_tier_score("2차의료", TIER2_CLEAR)

    # 6) 1차·2차를 하나의 "의료시설_취약점수"로 합친다. 2차(종합병원)는 원자료에
    #    없으면 건너뛰므로, 둘 다 있을 때만 합성 점수를 만든다.
    #    가중치(0.4/0.6)는 예시값 — 종합병원 접근성을 더 급한 문제로 볼지는
    #    팀 논의로 정하고, 여기 숫자만 바꾸면 전체가 다시 계산된다.
    if "1차의료_취약점수" in result.columns and "2차의료_취약점수" in result.columns:
        W1, W2 = 0.4, 0.6
        result["의료시설_취약점수"] = W1 * result["1차의료_취약점수"] + W2 * result["2차의료_취약점수"]

    sort_col = "의료시설_취약점수" if "의료시설_취약점수" in result.columns else (
        "1차의료_취약점수" if "1차의료_취약점수" in result.columns else result.columns[-1]
    )
    result = result.sort_values(sort_col, ascending=False).reset_index(drop=True)

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(save_path, index=False, encoding="utf-8-sig")
        print(f"저장 완료: {save_path} ({len(result)}개 읍/면)")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="KOSIS 원자료 CSV 경로")
    parser.add_argument("--out", default="data/processed/medical/medical_access_score.csv")
    args = parser.parse_args()

    out = build_medical_access_score(args.csv, save_path=args.out)
    print(out.head(20).to_string())
