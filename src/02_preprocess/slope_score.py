# -*- coding: utf-8 -*-
"""GEDTM30 DEM(맨땅 기준 DTM, 30m)으로 읍면동별 평균 경사도(지형장벽 취약점수)를 만든다.

원자료
------
- DEM: GEDTM30 (Global Ensemble Digital Terrain Model), OpenGeoHub Foundation
  https://zenodo.org/records/14900181 (DOI: 10.5281/zenodo.14900180)
  실제 클립 다운로드: https://opentopography.s3.sdsc.edu/raster/GEDTM30/GEDTM30_be/...
  (globaldemportal.github.io에서 "글로벌 앙상블 ML 지형(~30m)" + Type=DTM 선택해 다운로드)
- 읍면동 경계: admdongkor (vuski/admdongkor, admdongkor.vw-lab.com)
  형식 GeoJSON, 좌표계 EPSG:4326, 경계단위 읍면동으로 다운로드

방법
----
1) DEM은 원래 위경도(도) 좌표계라, 그대로 경사도를 계산하면 위도에 따라 오차가 생긴다.
   미터 단위 좌표계(EPSG:5179, 한국 표준)로 재투영한 뒤 계산해야 정확하다.
2) 경사도는 GDAL의 gdaldem(커맨드라인 도구)으로 계산한다 — 파이썬 GIS 라이브러리(richdem 등)
   보다 설치가 안정적이고, Horn's algorithm 기반의 표준적인 경사도 계산을 그대로 쓴다.
3) 읍면동 경계 폴리곤을 슬로프 래스터와 같은 좌표계로 맞추고, rasterstats로 폴리곤별
   평균·최대 경사도를 집계한다(zonal statistics).
4) 평균 경사도를 min-max 정규화해 0~1의 "지형장벽_취약점수"로 만든다(높을수록 험함) —
   기존 이동격차지수·의료접근성 점수와 같은 방향으로 맞췄다.
5) 서울 포함 전국 읍면동을 대상으로 계산한다 — 서울 제외 여부는 다른 지표와 합칠 때
   최종적으로 결정한다(이 스크립트 단독으로는 필터링하지 않음).

Colab 사용법
-----------
    DEM_PATH = "GEDTM30_clip.tif"          # DEM 클립 다운로드 결과
    EMD_GEOJSON_PATH = "emd_20260701.geojson"  # admdongkor 다운로드 결과
    result = build_slope_score(DEM_PATH, EMD_GEOJSON_PATH)
"""

import subprocess

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import geopandas as gpd
from rasterstats import zonal_stats

TARGET_CRS = "EPSG:5179"  # 미터 단위, 한국 표준 좌표계


def _reproject_dem(dem_path: str, out_path: str) -> tuple[str, float | None]:
    with rasterio.open(dem_path) as src:
        nodata = src.nodata
        transform, width, height = calculate_default_transform(
            src.crs, TARGET_CRS, src.width, src.height, *src.bounds
        )
        profile = src.profile.copy()
        profile.update(crs=TARGET_CRS, transform=transform, width=width, height=height)

        with rasterio.open(out_path, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=TARGET_CRS,
                resampling=Resampling.bilinear,
                src_nodata=nodata,
                dst_nodata=nodata,
            )
    return out_path, nodata


def _compute_slope(reproj_dem_path: str, slope_path: str) -> tuple[str, float | None]:
    result = subprocess.run(
        ["gdaldem", "slope", reproj_dem_path, slope_path, "-compute_edges"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gdaldem slope 실패: {result.stderr}")
    with rasterio.open(slope_path) as src:
        slope_nodata = src.nodata
    return slope_path, slope_nodata


def _make_key(row) -> str:
    parts = [row["sidonm"]]
    if row.get("sggnm") and str(row["sggnm"]) != "None":
        parts.append(row["sggnm"])
    parts.append(row["emdnm"])
    return " ".join(parts)


def build_slope_score(
    dem_path: str,
    emd_geojson_path: str,
    reproj_dem_path: str = "GEDTM30_5179.tif",
    slope_path: str = "slope_degrees.tif",
    save_path: str | None = "slope_score.csv",
):
    print("1/3 DEM 재투영 중 (EPSG:5179)...")
    reproj_dem_path, nodata = _reproject_dem(dem_path, reproj_dem_path)
    print(f"   완료: {reproj_dem_path}")

    print("2/3 경사도 계산 중 (gdaldem)...")
    slope_path, slope_nodata = _compute_slope(reproj_dem_path, slope_path)
    print(f"   완료: {slope_path}")

    print("3/3 읍면동별 평균 경사도 집계 중...")
    gdf = gpd.read_file(emd_geojson_path).to_crs(TARGET_CRS)
    stats = zonal_stats(gdf.geometry, slope_path, stats=["mean", "max", "count"], nodata=slope_nodata)

    gdf["평균경사도"] = [s["mean"] for s in stats]
    gdf["최대경사도"] = [s["max"] for s in stats]
    gdf["픽셀수"] = [s["count"] for s in stats]
    gdf["읍면_key"] = gdf.apply(_make_key, axis=1)

    valid_mean = gdf["평균경사도"].dropna()
    gdf["지형장벽_취약점수"] = (gdf["평균경사도"] - valid_mean.min()) / (valid_mean.max() - valid_mean.min())

    result = gdf[["읍면_key", "sidonm", "sggnm", "emdnm", "area", "평균경사도", "최대경사도", "지형장벽_취약점수"]].copy()
    result = result.sort_values("지형장벽_취약점수", ascending=False).reset_index(drop=True)

    if save_path:
        result.to_csv(save_path, index=False, encoding="utf-8-sig")
        print(f"저장 완료: {save_path} ({len(result)}개 읍면동)")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dem", required=True, help="GEDTM30 클립 GeoTIFF 경로")
    parser.add_argument("--emd", required=True, help="읍면동 경계 GeoJSON 경로")
    parser.add_argument("--out", default="data/processed/slope_score.csv")
    args = parser.parse_args()

    out = build_slope_score(args.dem, args.emd, save_path=args.out)
    print(out.head(15).to_string())
