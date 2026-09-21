# 01. 데이터 수집

농림어업총조사, KTDB 가구통행실태조사, 생활이동데이터, 인구총조사, DEM/경사도, 한국교통안전공단 배출량 통계를 내려받는 스크립트를 둡니다. 각 스크립트는 `data/README.md`에 정리된 출처·신청 절차를 따릅니다.

## fetch_hira_hospitals.py

건강보험심사평가원 병원정보서비스는 파일 다운로드가 아니라 Open API 방식이라, 이 스크립트가 페이지네이션하며 전국 병·의원(명칭·주소·경도·위도)을 모아 CSV로 저장합니다. `src/06_visualize/plot_facility_map.py`의 입력 데이터로 바로 쓸 수 있습니다.

```bash
python fetch_hira_hospitals.py --service-key "본인의_디코딩_인증키" --out data/raw/hira_hospitals.csv
```

⚠️ 인증키는 data.go.kr 활용신청으로 발급받은 개인 키입니다. 코드나 커밋에 절대 하드코딩하지 말고, 실행할 때 인자로만 넘기세요.
