# -*- coding: utf-8 -*-
"""
경기도 DRT 재배치 시뮬레이션
"샌드박스 임의배치 267대" vs "이동격차지수 기준 재배치 267대"

배분 단위: 읍면동(602개)
배분 방법: 최대잉여법(Largest Remainder Method) — 표준 의석배분(apportionment) 알고리즘

현재 배치(읍면동 단위 귀속) 출처:
- 1차 소스: 가연 `이동격차지수_3차자료/drt_boundary_mapping/경기도_경계기준_DRT비교.csv`의
  "운행구역에 읍면동 명시"(확인) 53개 — data/raw/경기도_똑버스_운행현황.csv 공식 46개
  운행구역을 admdongkor 602개 경계와 신중하게 대조한 결과(운행구역 명칭과 읍면동 명칭이
  정확히 일치하는 것만 확인 처리).
- 2차 보강: 은규가 만든 경기도_DRT_종합.xlsx(318행 전국 DRT 데이터셋 기반)와 교차검증해
  2건을 추가함(admdongkor 602개 목록에 실존함을 직접 대조로 확인, 318행 데이터셋에
  뉴스 출처도 있음) — 평택시 고덕동(고덕국제신도시 15대), 파주시 교하동(운정신도시·
  교하지구 15대). 나머지 7건(고양시 덕은동·향동동, 안산시 목내동·성곡동·원시동,
  안양시 안양9동, 의정부시 민락동)은 admdongkor 602개 실제 행정동 목록에 없는 표기로
  확인되어 기각함(예: 안양시만안구는 안양1~7동까지만 존재, 안양9동은 없음).

자세한 비교 과정은 같은 폴더의 `경기도_DRT_재배치_기록.md`를 참고.
"""
import pandas as pd
import numpy as np

BOUNDARY_PATH = "이동격차지수_3차자료/drt_boundary_mapping/경기도_경계기준_DRT비교.csv"
OFFICIAL_PATH = "data/raw/경기도_똑버스_운행현황.csv"
TOTAL_N = 267  # 경기도 똑버스 실제 총 운행대수(현재 샌드박스 등으로 임의배치된 현황)

VERIFIED_ADDITIONS = [
    ("경기도 평택시 고덕동", "고덕국제신도시"),
    ("경기도 파주시 교하동", "운정신도시·교하지구"),
]


def largest_remainder(weights: pd.Series, total: int) -> pd.Series:
    """이동격차지수 비례로 total대를 정수로 나눈다(표준 의석배분 알고리즘).
    1) 이상적인 실수 몫 = weights / sum(weights) * total
    2) 내림한 정수를 우선 배정
    3) 남은 대수만큼, 소수점 잉여(실수 몫 - 내림값)가 큰 지역부터 1대씩 추가 배정
    이 방법이 "원래 비율에서 가장 적게 벗어나는 정수해"를 보장한다.
    """
    share = weights / weights.sum() * total
    floor_alloc = np.floor(share).astype(int)
    remainder = share - floor_alloc
    n_remaining = total - floor_alloc.sum()
    add_idx = remainder.sort_values(ascending=False).index[:n_remaining]
    alloc = floor_alloc.copy()
    alloc.loc[add_idx] += 1
    assert alloc.sum() == total
    return alloc


def build_current_allocation(boundary: pd.DataFrame, official: pd.DataFrame) -> pd.Series:
    """55개 확인된 읍면동에 현재 운행대수를 귀속시킨다.
    한 운행구역에 여러 읍면동이 확인되면 그 구역 운행대수를 확인된 읍면동 수로 균등 배분한다."""
    zone_vehicle_map = official.set_index("운행구역")["운행대수_숫자"].to_dict()

    confirmed = boundary[boundary["DRT대조결과"] == "운행구역에 읍면동 명시"].copy()

    add_rows = []
    for key, zone in VERIFIED_ADDITIONS:
        row = boundary[boundary["읍면_key"] == key].iloc[0].copy()
        row["DRT대조결과"] = "운행구역에 읍면동 명시(은규 318행 데이터셋 교차검증으로 추가)"
        row["일치_운행구역"] = zone
        add_rows.append(row)
    confirmed = pd.concat([confirmed, pd.DataFrame(add_rows)], ignore_index=True)

    confirmed["_zones"] = confirmed["일치_운행구역"].str.split(" / ")
    exploded = confirmed.explode("_zones").rename(columns={"_zones": "zone"})
    exploded["zone"] = exploded["zone"].str.strip()
    exploded["_zone_count"] = exploded.groupby("zone")["emdnm"].transform("count")

    def lookup_zone_vehicle(zone_name):
        if zone_name in zone_vehicle_map:
            return zone_vehicle_map[zone_name]
        for k, v in zone_vehicle_map.items():
            if zone_name.replace(" ", "") == k.replace(" ", ""):
                return v
        return None

    exploded["_zone_vehicle_total"] = exploded["zone"].apply(lookup_zone_vehicle)
    exploded = exploded.dropna(subset=["_zone_vehicle_total"])
    exploded["_귀속대수"] = exploded["_zone_vehicle_total"] / exploded["_zone_count"]
    return exploded.groupby("읍면_key")["_귀속대수"].sum().rename("현재_귀속대수")


def run(boundary_path: str = BOUNDARY_PATH, official_path: str = OFFICIAL_PATH, total_n: int = TOTAL_N):
    boundary = pd.read_csv(boundary_path)
    official = pd.read_csv(official_path)
    official = official[official["지자체"] != "계"].copy()
    official["운행대수_숫자"] = official["운행대수"].str.replace("대", "").astype(int)
    assert official["운행대수_숫자"].sum() == total_n

    current_alloc = build_current_allocation(boundary, official)

    boundary = boundary.sort_values("이동격차지수", ascending=False).reset_index(drop=True)
    boundary["재배치_대수"] = largest_remainder(boundary["이동격차지수"], total_n).values

    result = boundary.merge(current_alloc, on="읍면_key", how="left")
    result["현재_귀속대수"] = result["현재_귀속대수"].fillna(0)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", default=BOUNDARY_PATH)
    parser.add_argument("--official", default=OFFICIAL_PATH)
    parser.add_argument("--total", type=int, default=TOTAL_N)
    parser.add_argument("--out", default="경기도_재배치_시뮬레이션_결과.csv")
    args = parser.parse_args()

    result = run(args.boundary, args.official, args.total)
    out_cols = ["읍면_key", "sidonm", "sggnm", "emdnm", "이동격차지수", "재배치_대수", "현재_귀속대수", "DRT대조결과"]
    result[out_cols].to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {args.out} ({len(result)}개 읍면동)")
