# 06. 시각화

의료시설 등 위경도 기반 시설 위치를 전국 점 지도로 그리는 공용 스크립트를 둡니다. 이동격차지수 choropleth·DRT 재배치 지도는 각각 `이동격차지수_3차자료/`, `src/04_drt_simulation/`, `outputs/figures/terrain/`에서 별도로 생성합니다.

## plot_facility_map.py

위경도가 있는 시설 위치 데이터(병원, 버스정류장 등)를 전국 점 지도로 그리는 재사용 스크립트입니다. 서울 제외 필터가 기본값입니다.

```bash
# 실제 데이터 없이 스크립트만 확인
python plot_facility_map.py --demo

# 실제 CSV로 실행 (건강보험심사평가원 병원정보서비스 등)
python plot_facility_map.py --csv data/raw/medical/hira_hospitals.csv \
    --title "의료시설은 어디에 있을까?" --source "2026.9 기준 · 건강보험심사평가원" \
    --out outputs/figures/medical/medical_map.png
```

Colab에서는 `google.colab.files.upload()`로 CSV를 올린 뒤 `plot_facility_map(파일명, title=...)`를 바로 호출하면 됩니다. 위경도·시도명 컬럼명이 다른 데이터셋(예: 다른 기관 CSV)이어도 흔한 컬럼명 후보를 자동으로 탐색합니다.
