# 01. 데이터 수집

API로 받아야 하는 원자료(현재는 병원 좌표)를 수집하는 스크립트를 둡니다. TAGO 버스노선정보·GTFS·OD·자동차등록대수·인구 등 나머지 데이터는 각 제공처에서 직접 다운로드하며, 출처·접근 방법은 `data/README.md`에 정리되어 있습니다.

주제별 하위폴더(`medical/` 등)로 나눠서 저장합니다.

## medical/fetch_hira_hospitals.py

건강보험심사평가원 병원정보서비스는 파일 다운로드가 아니라 Open API 방식이라, 이 스크립트가 페이지네이션하며 전국 병·의원(명칭·주소·경도·위도)을 모아 CSV로 저장합니다. `src/06_visualize/plot_facility_map.py`의 입력 데이터로 바로 쓸 수 있습니다.

```bash
python fetch_hira_hospitals.py --service-key "본인의_디코딩_인증키" --out data/raw/medical/hira_hospitals.csv
```

⚠️ 인증키는 data.go.kr 활용신청으로 발급받은 개인 키입니다. 코드나 커밋에 절대 하드코딩하지 말고, 실행할 때 인자로만 넘기세요.
