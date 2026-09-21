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
4) 핵심 3종(약국·보건소(지소포함)·일반병·의원)의 가중평균 소요시간을
   단순평균해 "1차의료_접근성(분)"을 만들고, min-max 정규화해
   0~1의 "의료접근성_취약점수"(높을수록 나쁨)로 변환한다 — 기존
   이동격차지수(팀원 노트북)의 점수 방향과 동일하게 맞췄다.
5) 한방병·의원 / 치과병·의원은 핵심 점수에 넣지 않고 별도 컬럼으로만
   남겨둔다 — 일상적 1차의료(내과·소아과 등)만큼 보편적 필수는 아니라고
   보되, 참고 지표로는 계속 계산해둔다(제외가 아니라 "보조" 취급).
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

# 핵심 3종(1차의료) — 접근성 점수의 주 변수. 한방/치과는 보조로만 계산.
CORE_FACILITIES = ["약국", "보건소", "일반병의원"]
SUPPLEMENTARY_FACILITIES = ["한방병의원", "치과병의원"]

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


def build_medical_access_score(csv_path: str, save_path: str | None = "data/processed/medical_access_score.csv"):
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

    # 핵심 3종(1차의료) 결합 점수
    core_cols = [f"{f}_평균소요분" for f in CORE_FACILITIES]
    result["1차의료_평균소요분"] = result[core_cols].mean(axis=1)

    def minmax(s):
        return (s - s.min()) / (s.max() - s.min())

    result["의료접근성_취약점수"] = minmax(result["1차의료_평균소요분"])  # 높을수록(1에 가까울수록) 접근성 나쁨

    result = result.sort_values("의료접근성_취약점수", ascending=False).reset_index(drop=True)

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(save_path, index=False, encoding="utf-8-sig")
        print(f"저장 완료: {save_path} ({len(result)}개 읍/면)")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="KOSIS 원자료 CSV 경로")
    parser.add_argument("--out", default="data/processed/medical_access_score.csv")
    args = parser.parse_args()

    out = build_medical_access_score(args.csv, save_path=args.out)
    print(out.head(20).to_string())
