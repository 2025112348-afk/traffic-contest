# -*- coding: utf-8 -*-
"""건강보험심사평가원 병원정보서비스 Open API를 페이지네이션하며 호출해
전국 병·의원 목록(명칭·주소·경도·위도 등)을 CSV로 모은다.

data.go.kr에서 이 데이터셋은 "파일 다운로드"가 아니라 API 방식이라,
브라우저에서 바로 받을 수 있는 버튼이 없다. 인증키(서비스키)로 여러 번
나눠서(pageNo) 요청해 전국 데이터를 모아야 한다.

Colab 사용법 (서비스키는 본인 Colab 안에서만 입력할 것 — 절대 채팅/깃허브에
붙여넣지 말 것):
    SERVICE_KEY = "본인의 디코딩(Decoding) 인증키"   # data.go.kr 마이페이지에서 확인
    df = fetch_all_hospitals(SERVICE_KEY)
    df.to_csv("hira_hospitals.csv", index=False, encoding="utf-8-sig")

주의: data.go.kr은 인증키를 "URL 인코딩"/"디코딩" 두 버전으로 준다.
requests 라이브러리는 params에 넣은 값을 자동으로 다시 인코딩하므로,
반드시 "디코딩(Decoding)" 키를 써야 한다 — 인코딩 키를 그대로 넣으면
이중 인코딩돼서 SERVICE_KEY_IS_NOT_REGISTERED_ERROR가 난다.
"""

import time

import pandas as pd
import requests

ENDPOINT = "http://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"


def fetch_all_hospitals(service_key: str, num_of_rows: int = 1000, sleep_sec: float = 0.2) -> pd.DataFrame:
    rows = []
    page_no = 1
    total_count = None

    while True:
        params = {
            "serviceKey": service_key,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            "_type": "json",
        }
        res = requests.get(ENDPOINT, params=params, timeout=30)
        res.raise_for_status()
        body = res.json()["response"]

        header = body["header"]
        if header["resultCode"] != "00":
            raise RuntimeError(f"API 오류: {header['resultCode']} {header['resultMsg']}")

        result = body["body"]
        if total_count is None:
            total_count = result["totalCount"]
            print(f"전체 {total_count}개 예상 (페이지당 {num_of_rows}개씩)")

        items = result.get("items")
        if not items:
            break
        page_rows = items["item"] if isinstance(items["item"], list) else [items["item"]]
        rows.extend(page_rows)
        print(f"  {page_no}페이지: 누적 {len(rows)}/{total_count}")

        if len(rows) >= total_count:
            break
        page_no += 1
        time.sleep(sleep_sec)  # 과도한 연속 호출 방지

    df = pd.DataFrame(rows)

    # 좌표 숫자형 변환 + 대한민국 영역 밖/결측 좌표 제거
    df["XPos"] = pd.to_numeric(df.get("XPos"), errors="coerce")
    df["YPos"] = pd.to_numeric(df.get("YPos"), errors="coerce")
    df = df.dropna(subset=["XPos", "YPos"])
    df = df[df["XPos"].between(124, 132) & df["YPos"].between(33, 39)]

    print(f"좌표 있는 병·의원 {len(df)}개 (전체 {total_count}개 중)")
    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service-key", required=True, help="data.go.kr 디코딩(Decoding) 인증키")
    parser.add_argument("--out", default="data/raw/medical/hira_hospitals.csv")
    args = parser.parse_args()

    out_df = fetch_all_hospitals(args.service_key)
    out_df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {args.out}")
