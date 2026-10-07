# -*- coding: utf-8 -*-
"""충청·대전·세종 467개 읍면동을 시군구 구분 없이 통째로 풀에 놓고,
이동격차지수 상위/하위 구간별 DRT 보유율을 비교한다 (양성 검증)."""
import math
import pandas as pd
import openpyxl
from scipy import stats

INDEX_PATH = "/home/user/traffic-contest/이동격차지수_3차자료/gyeonggi_drt_comparison/전국_최종지수_재계산.csv"
DRT_PATH = "/home/user/traffic-contest/DRT_버스형_읍면동_검증본.xlsx"
TARGET_SIDO = ["충청남도", "충청북도", "대전광역시", "세종특별자치시"]

idx_df = pd.read_csv(INDEX_PATH)
region_df = idx_df[idx_df["sidonm"].isin(TARGET_SIDO)].copy()

wb = openpyxl.load_workbook(DRT_PATH)
ws = wb["읍면동_DRT_상중"]
rows = list(ws.iter_rows(values_only=True))
header = rows[0]
idx_h = {h: i for i, h in enumerate(header)}
drt_rows = [r for r in rows[1:] if r[idx_h["권역"]] == "충청·대전·세종"]
drt_df = pd.DataFrame(drt_rows, columns=header)

def normalize_sgg(sido, sgg):
    sgg = str(sgg).strip()
    if sido == "세종특별자치시":
        return "세종시"
    return sgg.replace(" ", "")

drt_df["읍면_key_정규화"] = drt_df["시도"] + " " + drt_df.apply(lambda r: normalize_sgg(r["시도"], r["시군구"]), axis=1) + " " + drt_df["읍면동"]
drt_set = set(drt_df["읍면_key_정규화"])

region_df["DRT_있음"] = region_df["읍면_key"].isin(drt_set)
region_df = region_df.sort_values("이동격차지수", ascending=False).reset_index(drop=True)
n = len(region_df)
print(f"전체 읍면동: {n}개 (충청남도+충청북도+대전광역시+세종특별자치시, 시군구 구분 없이 하나의 풀)")
print(f"전체 DRT 보유율: {region_df['DRT_있음'].mean():.1%} ({region_df['DRT_있음'].sum()}개)\n")

print(f"{'구간':10s} {'표본수':>6s} {'DRT있음':>8s} {'보유율':>8s}")
for pct in [10, 20, 30]:
    k = math.ceil(n * pct / 100)
    top = region_df.head(k)
    bottom = region_df.tail(k)
    top_rate = top["DRT_있음"].mean()
    bottom_rate = bottom["DRT_있음"].mean()
    print(f"상위 {pct:>2d}% {k:>6d} {top['DRT_있음'].sum():>8d} {top_rate:>7.1%}")
    print(f"하위 {pct:>2d}% {k:>6d} {bottom['DRT_있음'].sum():>8d} {bottom_rate:>7.1%}")
    ratio = (top_rate / bottom_rate) if bottom_rate > 0 else float('inf')
    print(f"  -> 상위/하위 배율: {ratio:.1f}배\n")

# 전체 상관계수 (이동격차지수 연속값 vs DRT유무 이진값 -> point-biserial correlation)
corr, pval = stats.pointbiserialr(region_df["DRT_있음"].astype(int), region_df["이동격차지수"])
print(f"전체 467개 기준 point-biserial 상관계수: r={corr:.3f}, p={pval:.4f}")
print("(r이 양수이고 유의하면: 이동격차지수가 높을수록 DRT 보유 확률도 유의하게 높다는 뜻)")

region_df[["읍면_key","sidonm","sggnm","emdnm","이동격차지수","DRT_있음"]].to_csv(
    "/tmp/claude-0/-home-user-traffic-contest/a259b5de-5bf0-52dd-bbef-4fd9bfa53513/scratchpad/충청대전세종_전체467_DRT유무.csv",
    index=False, encoding="utf-8-sig")
print("\n저장 완료: 충청대전세종_전체467_DRT유무.csv")
