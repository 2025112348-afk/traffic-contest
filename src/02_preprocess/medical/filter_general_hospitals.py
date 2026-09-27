# -*- coding: utf-8 -*-
"""HIRA 병원정보서비스 CSV에서 종합병원·상급종합병원만 추려 CSV로 저장하고,
그 위치를 지도로 시각화한다 (src/06_visualize/plot_facility_map.py 재사용).

배경: 의료접근성 지수의 2차의료(종합병원) 축을 시각적으로 따로 확인하려면,
전체 병·의원 지도(medical_map.png)와는 별도로 "중증치료가 가능한 병원"만
걸러낸 위치가 필요하다. clCdNm(종별명) 컬럼으로 필터링한다.

Colab 사용법:
    from filter_general_hospitals import build_general_hospital_subset
    build_general_hospital_subset("hira_hospitals.csv")

로컬 실행:
    python filter_general_hospitals.py --csv data/raw/medical/hira_hospitals.csv
"""

import sys
from pathlib import Path

import pandas as pd

try:
    from plot_facility_map import plot_facility_map  # Colab: 같은 폴더에 파일을 올려둔 경우
except ImportError:
    # 로컬에서 repo 구조 그대로 실행하는 경우 (src/06_visualize/plot_facility_map.py)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "06_visualize"))
    from plot_facility_map import plot_facility_map

# 주의: HIRA 원자료의 clCdNm 표기는 "상급종합병원"이 아니라 "상급종합"이다
# (df["clCdNm"].value_counts()로 실제 표기 확인 후 반영함).
TARGET_TIERS = ["종합병원", "상급종합"]


def build_general_hospital_subset(
    csv_path: str,
    out_csv: str = "data/processed/medical/hira_general_hospitals.csv",
    out_png: str = "outputs/figures/medical/general_hospital_map.png",
    tier_col: str = "clCdNm",
):
    df = pd.read_csv(csv_path)
    subset = df[df[tier_col].isin(TARGET_TIERS)].copy()
    print(f"{'+'.join(TARGET_TIERS)} {len(subset)}개 (전체 {len(df)}개 중)")

    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    subset.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"CSV 저장 완료: {out_csv}")

    plot_facility_map(
        out_csv,
        title="종합병원은 어디에 있을까?",
        source_note="건강보험심사평가원",
        out_path=out_png,
    )
    return subset


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="data/raw/medical/hira_hospitals.csv", help="HIRA 병원정보 CSV 경로")
    parser.add_argument("--out-csv", default="data/processed/medical/hira_general_hospitals.csv")
    parser.add_argument("--out-png", default="outputs/figures/medical/general_hospital_map.png")
    args = parser.parse_args()

    build_general_hospital_subset(args.csv, out_csv=args.out_csv, out_png=args.out_png)
