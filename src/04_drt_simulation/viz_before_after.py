# -*- coding: utf-8 -*-
"""경기도 DRT 재배치 시뮬레이션 — 전(현재 임의배치) vs 후(이동격차지수 기준) 지도 시각화.
저장소 루트에서 실행: python src/04_drt_simulation/viz_before_after.py"""
import os

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
GEOJSON = f"{REPO}/이동격차지수_3차자료/drt_boundary_mapping/경기도_분석경계_DRT연결.geojson"
RESULT = f"{HERE}/경기도_재배치_시뮬레이션_결과.csv"
OUT_PNG = f"{HERE}/경기도_재배치_전후비교_지도.png"

for f in fm.fontManager.ttflist:
    if "Nanum" in f.name or "Noto Sans CJK" in f.name or "Malgun" in f.name:
        plt.rcParams["font.family"] = f.name
        break
plt.rcParams["axes.unicode_minus"] = False

gdf = gpd.read_file(GEOJSON)[["읍면_key", "sggnm", "emdnm", "geometry"]]
result = pd.read_csv(RESULT)
gdf = gdf.merge(result[["읍면_key", "재배치_대수", "현재_귀속대수"]], on="읍면_key", how="left")
gdf["재배치_대수"] = gdf["재배치_대수"].fillna(0).astype(int)
gdf["현재_귀속대수"] = gdf["현재_귀속대수"].fillna(0)

gdf_proj = gdf.to_crs(5179)
gdf_proj["centroid"] = gdf_proj.geometry.centroid

fig, axes = plt.subplots(1, 2, figsize=(19, 11))

# ---- 왼쪽: 재배치 전(현재 귀속대수, 326대 중 307대 귀속) ----
ax = axes[0]
gdf_proj.plot(ax=ax, color="#eef1f4", edgecolor="#c9ced4", linewidth=0.4)
cur = gdf_proj[gdf_proj["현재_귀속대수"] > 0]
# 크기/색 모두 대수에 비례(연속값이라 버킷팅)
bins = [(0, 2, "#a8c5f0", 40, "1~2대"), (2, 5, "#5b8fd6", 70, "2~5대"), (5, 10, "#2f5597", 110, "5~10대"), (10, 999, "#0b2b5c", 160, "10대 이상")]
for lo, hi, color, size, label in bins:
    sub = cur[(cur["현재_귀속대수"] > lo) & (cur["현재_귀속대수"] <= hi)]
    pts = sub["centroid"]
    ax.scatter(pts.x, pts.y, s=size, color=color, edgecolor="white", linewidth=0.6, zorder=3, label=f"{label} ({len(sub)}개)")
ax.set_title(f"재배치 전 — 현재(경기교통공사 공식) 배치\n귀속 성공 {cur['현재_귀속대수'].sum():.0f}대 / 총 326대, {len(cur)}개 읍면동", fontsize=13, pad=12)
ax.legend(loc="lower left", frameon=True, fontsize=9, title="현재 귀속대수")
ax.set_axis_off()

# ---- 오른쪽: 재배치 후(이동격차지수 기준 최대잉여법) ----
ax = axes[1]
gdf_proj.plot(ax=ax, color="#eef1f4", edgecolor="#c9ced4", linewidth=0.4)
colors = {1: "#2f6fed", 2: "#e0532c"}
for n in [1, 2]:
    sub = gdf_proj[gdf_proj["재배치_대수"] == n]
    pts = sub["centroid"]
    ax.scatter(pts.x, pts.y, s=46 if n == 1 else 90, color=colors[n], edgecolor="white", linewidth=0.6, zorder=3, label=f"재배치 {n}대 ({len(sub)}개)")
ax.set_title(f"재배치 후 — 이동격차지수 기준 최대잉여법\n326대 중 {(gdf_proj['재배치_대수']>0).sum()}개 읍면동에 배정", fontsize=13, pad=12)
ax.legend(loc="lower left", frameon=True, fontsize=9, title="재배치 대수")
ax.set_axis_off()

fig.suptitle("경기도 DRT 재배치 시뮬레이션 — 전(현재 임의배치) vs 후(이동격차지수 기준)", fontsize=16, y=0.99)
caption = ("왼쪽: 현재(경기교통공사 공식) 임의배치 — 신도시·규제샌드박스 지역에 쏠림.   "
           "오른쪽: 이동격차지수 기준 재배치 — 도 전역(특히 외곽 농산촌)으로 고르게 분산")
fig.text(0.5, 0.01, caption, ha="center", va="bottom", fontsize=11, color="#333333")
plt.tight_layout(rect=[0, 0.03, 1, 0.96])
plt.savefig(OUT_PNG, dpi=170, bbox_inches="tight")
print("저장:", OUT_PNG)
