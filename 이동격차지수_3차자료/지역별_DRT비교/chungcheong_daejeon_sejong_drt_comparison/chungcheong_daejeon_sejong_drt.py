# -*- coding: utf-8 -*-
"""
충청(충북·충남)·대전·세종 — 이동격차지수 3차 결과 × DRT 현황 비교

순서 (사용자 지정):
1) 이동격차지수 3차 결과에서 충청남도/충청북도/대전광역시/세종특별자치시만 추출
2) DRT 현황 데이터의 지역명을 이동격차지수 읍면_key 표기에 맞춰 정규화
3) 시군구별로 읍면동 수가 많으면(>=20) 상위 10%(올림, 최소 2개),
   보통(10~19개)이면 상위 10개, 적으면(<10개) 상위 5개를 뽑아
   그 안에 DRT가 있는지 없는지 확인
"""
import math
import re
import pandas as pd
import openpyxl

INDEX_PATH = "/home/user/traffic-contest/이동격차지수_3차자료/gyeonggi_drt_comparison/전국_최종지수_재계산.csv"
DRT_PATH = "/home/user/traffic-contest/DRT_버스형_읍면동_검증본.xlsx"

TARGET_SIDO = ["충청남도", "충청북도", "대전광역시", "세종특별자치시"]

# ---------- 1) 이동격차지수 3차 결과에서 대상 지역만 추출 ----------
idx_df = pd.read_csv(INDEX_PATH)
region_df = idx_df[idx_df["sidonm"].isin(TARGET_SIDO)].copy()
print(f"[1단계] 전국 {len(idx_df)}개 읍면동 중 충청·대전·세종 {len(region_df)}개 추출")
print("  시군구 수:", region_df["sggnm"].nunique())
na_age = region_df["고령인구비율"].isna().sum()
if na_age:
    print(f"  (참고) 고령인구비율 결측 {na_age}건 — 이동격차지수 자체는 결측 아님(0 대체 반영돼 있음)")

# ---------- 2) DRT 현황 데이터 지역명을 읍면_key 표기에 맞춰 정규화 ----------
wb = openpyxl.load_workbook(DRT_PATH)
ws = wb["읍면동_DRT_상중"]
rows = list(ws.iter_rows(values_only=True))
header = rows[0]
idx_h = {h: i for i, h in enumerate(header)}
drt_rows = [r for r in rows[1:] if r[idx_h["권역"]] == "충청·대전·세종"]
drt_df = pd.DataFrame(drt_rows, columns=header)
print(f"\n[2단계] DRT 데이터(신뢰도 상/중) {len(drt_df)}건 정규화")

def normalize_sgg(sido, sgg):
    """이동격차지수 읍면_key의 sggnm 표기(공백 없음, 세종은 '세종시')에 맞춘다."""
    sgg = str(sgg).strip()
    if sido == "세종특별자치시":
        return "세종시"
    return sgg.replace(" ", "")  # "청주시 상당구" -> "청주시상당구"

drt_df["sggnm_정규화"] = drt_df.apply(lambda r: normalize_sgg(r["시도"], r["시군구"]), axis=1)
drt_df["읍면_key_정규화"] = drt_df["시도"] + " " + drt_df["sggnm_정규화"] + " " + drt_df["읍면동"]

# 매칭 확인
index_keys = set(region_df["읍면_key"])
drt_df["지수데이터_매칭"] = drt_df["읍면_key_정규화"].isin(index_keys)
unmatched = drt_df[~drt_df["지수데이터_매칭"]]
print(f"  정규화된 키로 매칭 성공: {drt_df['지수데이터_매칭'].sum()} / {len(drt_df)}")
if len(unmatched):
    print("  매칭 실패 건 (수작업 확인 필요):")
    for _, r in unmatched.iterrows():
        print("   ", r["읍면_key_정규화"], "<-", r["시도"], r["시군구"], r["읍면동"])

drt_eupmyeon_set = set(drt_df.loc[drt_df["지수데이터_매칭"], "읍면_key_정규화"])

# ---------- 3) 시군구별 상위권 추출 + DRT 유무 확인 ----------
def pick_top_n(n_total):
    if n_total >= 20:
        return max(2, math.ceil(n_total * 0.10)), "상위 10%(큰 지역)"
    elif n_total >= 10:
        return min(10, n_total), "상위 10개(보통 지역)"
    else:
        return min(5, n_total), "상위 5개(작은 지역)"

result_rows = []
summary_rows = []
for (sido, sgg), g in region_df.groupby(["sidonm", "sggnm"], sort=False):
    g = g.sort_values("이동격차지수", ascending=False).reset_index(drop=True)
    n_total = len(g)
    n_pick, rule = pick_top_n(n_total)
    top = g.head(n_pick).copy()
    top["읍면동_총수"] = n_total
    top["선정규칙"] = rule
    top["선정개수"] = n_pick
    top["순위"] = range(1, len(top) + 1)
    top["DRT_있음"] = top["읍면_key"].isin(drt_eupmyeon_set)
    result_rows.append(top)

    n_drt = top["DRT_있음"].sum()
    summary_rows.append({
        "시도": sido, "시군구": sgg, "읍면동_총수": n_total,
        "선정규칙": rule, "선정개수": n_pick,
        "상위권_DRT있음": n_drt, "상위권_DRT없음": n_pick - n_drt,
        "DRT_커버율": round(n_drt / n_pick, 3) if n_pick else None,
    })

result_df = pd.concat(result_rows, ignore_index=True)
summary_df = pd.DataFrame(summary_rows).sort_values(["시도", "시군구"]).reset_index(drop=True)

print(f"\n[3단계] 시군구 {len(summary_df)}개 처리 완료")
print(summary_df.to_string(index=False))

out_cols = ["시도", "시군구", "읍면동_총수", "선정규칙", "순위", "emdnm", "이동격차지수", "DRT_있음"]
result_df = result_df.rename(columns={"sidonm": "시도", "sggnm": "시군구"})
result_out = result_df[["시도", "시군구", "읍면동_총수", "선정규칙", "순위", "emdnm", "이동격차지수", "DRT_있음"]]

result_out.to_csv("/tmp/claude-0/-home-user-traffic-contest/a259b5de-5bf0-52dd-bbef-4fd9bfa53513/scratchpad/충청대전세종_상위권_DRT비교.csv", index=False, encoding="utf-8-sig")
summary_df.to_csv("/tmp/claude-0/-home-user-traffic-contest/a259b5de-5bf0-52dd-bbef-4fd9bfa53513/scratchpad/충청대전세종_시군구요약.csv", index=False, encoding="utf-8-sig")
print("\n저장 완료")

no_drt = result_df[~result_df["DRT_있음"]]
print(f"\n[주목] 상위권인데 DRT 없는 읍면동: {len(no_drt)}개")
print(no_drt[["시도","시군구","emdnm","이동격차지수"]].sort_values("이동격차지수", ascending=False).to_string(index=False))
