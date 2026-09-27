# -*- coding: utf-8 -*-
"""HIRA 병원정보서비스(전국 요양기관 좌표)로 읍면동 단위 의료접근성을 다시 계산한다.

배경
----
KOSIS 농림어업총조사 기반 `medical_access_score.py`는 2020년 설문 자료이고
읍/면(농어촌)만 있어 도시 "동" 지역이 통째로 빠져 있다. HIRA 데이터는 전국
모든 요양기관 좌표(동 포함, 79,850개)를 담고 있어, 공간조인으로 "읍면동
대표점 → 최근접 병원까지의 직선거리"를 계산하면 전국 커버리지를 얻을 수 있다.

KOSIS 버전과 다른 점 (그대로 합치면 안 되는 이유)
--------------------------------------------
- KOSIS: "그 읍/면 안 행정리들의 평균 소요시간"(설문 기반, 분 단위)
  여기: "읍면동 대표점에서 최근접 병원까지의 직선거리"(좌표 기반, km 단위)
  → 단위·성격이 다른 별도 지표다. 최종 통합 때 같은 축으로 병합하려면
    두 점수 중 하나로 통일하거나(예: 동 지역은 이 HIRA 버전, 읍/면은
    KOSIS 버전 우선 사용), 재정규화 후 병행 비교하는 방식을 팀이 정해야 한다.
- 약국 데이터 없음: HIRA 병원정보서비스는 "요양기관(병·의원)"만 다루고
  약국은 별도 API(약국정보서비스)라, 이 버전의 1차의료에는 약국이 빠져 있다
  (KOSIS 버전 TIER1_CLEAR에는 약국이 포함돼 있었음 — 차이점 유의).

방법
----
1) 읍면동 폴리곤의 "대표점"(representative_point) — 중심점(centroid)과 달리
   해안·도서 지역처럼 모양이 복잡한 폴리곤에서도 폴리곤 내부에 반드시
   위치하는 점을 쓴다(centroid는 오목한 폴리곤에서 바다 위로 빠질 수 있음).
2) HIRA 요양기관을 "수술·중증 치료 중심이냐"로 1차/2차 분류
   (KOSIS 버전과 같은 기준 — 의료법 제3조):
   - 1차: 의원, 치과의원, 한의원, 보건진료소, 병원, 보건지소, 한방병원,
     치과병원, 보건소, 보건의료원, 조산원
   - 2차: 종합병원, 상급종합
   ※ 요양병원·정신병원은 특정 환자군 대상 시설이라 일반 접근성 지표에서
     제외했다(팀 논의로 포함시키고 싶으면 TIER1_HIRA에 추가하면 됨).
3) EPSG:5179(미터 단위)로 맞춘 뒤 geopandas의 sjoin_nearest로 "읍면동
   대표점 → 최근접 1차/2차 의료기관"까지의 직선거리(km)를 구한다.
   ※ 직선거리이며 실제 도로 이동거리가 아니다 — 버스정류장 공급축도
     같은 방식(직선거리)으로 계산됐다면 방법론이 일관되지만, 폴리곤
     내부 개수 세기(within) 방식이었다면 방법론 차이가 남는다(팀 확인 필요).
4) 각각 min-max 정규화(0~1, 높을수록 나쁨) 후, 1차·2차를 0.4/0.6 가중합해
   "의료시설_취약점수_HIRA"를 만든다 — KOSIS 버전과 같은 가중치를 썼다.

Colab 사용법
-----------
    result = build_medical_access_score_hira("hira_hospitals.csv", "emd_20260701.geojson")
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

TARGET_CRS = "EPSG:5179"

TIER1_HIRA = [
    "의원", "치과의원", "한의원", "보건진료소", "병원",
    "보건지소", "한방병원", "치과병원", "보건소", "보건의료원", "조산원",
]
TIER2_HIRA = ["종합병원", "상급종합"]


def _make_key(row) -> str:
    parts = [row["sidonm"]]
    if row.get("sggnm") and str(row["sggnm"]) != "None":
        parts.append(row["sggnm"])
    parts.append(row["emdnm"])
    return " ".join(parts)


def _nearest_distance_km(base_gdf: gpd.GeoDataFrame, target_gdf: gpd.GeoDataFrame) -> pd.Series:
    """base_gdf의 각 점에서 target_gdf 중 가장 가까운 점까지의 거리(km)를 구한다."""
    joined = gpd.sjoin_nearest(base_gdf, target_gdf, distance_col="_dist_m")
    # 동일 거리의 시설이 여러 개면 sjoin_nearest가 행을 복제하므로 하나만 남긴다.
    joined = joined[~joined.index.duplicated(keep="first")]
    return (joined["_dist_m"] / 1000.0).reindex(base_gdf.index)


def build_medical_access_score_hira(
    hira_csv_path: str,
    emd_geojson_path: str,
    save_path: str | None = "data/processed/medical/medical_access_score_hira.csv",
):
    hira = pd.read_csv(hira_csv_path)
    hira["XPos"] = pd.to_numeric(hira["XPos"], errors="coerce")
    hira["YPos"] = pd.to_numeric(hira["YPos"], errors="coerce")
    hira = hira.dropna(subset=["XPos", "YPos"])

    hira_gdf = gpd.GeoDataFrame(
        hira, geometry=gpd.points_from_xy(hira["XPos"], hira["YPos"]), crs="EPSG:4326"
    ).to_crs(TARGET_CRS)

    tier1 = hira_gdf[hira_gdf["clCdNm"].isin(TIER1_HIRA)]
    tier2 = hira_gdf[hira_gdf["clCdNm"].isin(TIER2_HIRA)]
    print(f"1차 의료기관 {len(tier1)}개, 2차(종합병원+상급종합) {len(tier2)}개")

    emd = gpd.read_file(emd_geojson_path).to_crs(TARGET_CRS)
    emd["읍면_key"] = emd.apply(_make_key, axis=1)

    centroids = emd.copy()
    centroids["geometry"] = centroids.geometry.representative_point()

    print("최근접 1차의료 거리 계산 중...")
    dist1 = _nearest_distance_km(centroids, tier1)
    print("최근접 2차의료 거리 계산 중...")
    dist2 = _nearest_distance_km(centroids, tier2)

    result = emd[["읍면_key", "sidonm", "sggnm", "emdnm"]].copy()
    result["1차의료_최근접거리_km"] = dist1.values
    result["2차의료_최근접거리_km"] = dist2.values

    def minmax(s):
        return (s - s.min()) / (s.max() - s.min())

    result["1차의료_취약점수_HIRA"] = minmax(result["1차의료_최근접거리_km"])
    result["2차의료_취약점수_HIRA"] = minmax(result["2차의료_최근접거리_km"])

    W1, W2 = 0.4, 0.6  # KOSIS 버전과 동일 가중치 — 바꾸려면 여기만 수정
    result["의료시설_취약점수_HIRA"] = (
        W1 * result["1차의료_취약점수_HIRA"] + W2 * result["2차의료_취약점수_HIRA"]
    )

    result = result.sort_values("의료시설_취약점수_HIRA", ascending=False).reset_index(drop=True)

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(save_path, index=False, encoding="utf-8-sig")
        print(f"저장 완료: {save_path} ({len(result)}개 읍면동)")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hira", default="data/raw/medical/hira_hospitals.csv")
    parser.add_argument("--emd", required=True, help="읍면동 경계 GeoJSON 경로")
    parser.add_argument("--out", default="data/processed/medical/medical_access_score_hira.csv")
    args = parser.parse_args()

    out = build_medical_access_score_hira(args.hira, args.emd, save_path=args.out)
    print(out.head(20).to_string())
