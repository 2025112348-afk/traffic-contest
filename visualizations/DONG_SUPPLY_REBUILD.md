# 10·14번 재집계 결과

CSV와 지도를 저장소의 2026-07-01 행정동 경계 3,558개로 통일했다. `traffic`은 원본 읽기에만 사용했고 결과는 `traffic-contest/visualizations`에 저장했다. 공통 키 `dong_code`는 경계의 10자리 `emdcd`이며 문자열로 읽는다. `province`, `sigungu`, `dong`도 포함한다.

## 결과 및 한계

- 10번 인구 매칭은 3,412개다. 기존 3,044개에 시도명 정규화로 368개가 추가됐다. 결측은 514개에서 146개로 줄었다(이름 중복 136개, 이름/기준시점 미대응 10개).
- 광주광역시·전라남도를 입력 경계의 전남광주통합특별시 표기로 맞추고 강원도·전라북도 별칭도 처리한다. 이는 해당 파일의 조인용 명칭 대응이며 행정개편의 공식성을 검증한 것은 아니다. 정규화 이후 원본·경계 양쪽에서 시도·동명 키가 유일할 때만 연결한다. 통합으로 같은 키가 되는 중복도 배제한다.
- 인구 원본에는 시군구·코드가 없다. 따라서 시군구 정규화나 시군구를 포함한 조인은 적용할 수 없다. 구를 상위 시로 합치는 변환도 적용하지 않았다. 공식 코드 대응표로 검증한 연결이 아니며, 이름이 같아도 경계가 동일하다고 보장할 수 없다. `population_status`, `population_source_line`, `population_source_province`에 근거를 남겼다. 정규화 매칭 상태는 `unique_normalized_province_dong_name_match`다.
- 인구는 2025년, 정류장·운행은 2025년 3월, 경계는 2026-07-01이다. 경계 속성의 이름·코드를 그대로 사용했다. 경계의 공식성 및 은구가 사용하는 버전과의 일치는 확인하지 않았다.
- 버스 정류장 213,625개 중 213,476개를 공간 매칭했다. 경계 밖 149개와 평일 운행량 3,653회는 제외했으며 감사 파일에 기록했다.
- 14번 평일 운행량 합계는 18,544,545회다. 배차간격 결측 정류장 4,456개도 운행량 집계에 포함했다.
- 정류장이 없는 행정동 13개도 보존했다. 정류장당 공급량은 분모가 0이면 결측이다.
- 14번 `per_10k`를 `departures_per_stop`으로 바꿨다. 예전 `BJCD`, `NAME`, 대표 정류장 POINT인 `geometry`는 새 CSV에서 사용하지 않는다.

## 원본과 좌표계

- 인구: `../traffic/연령_및_성별_인구_–_읍면동_20260921125950.csv`
- 운행: `../traffic/bus_supply/bus_data/processed/gtfs_stop_supply_2025.csv`
- 버스 정류장: `07_bus_stops_2025/bus_stops.csv` (기존 route_type 0·3·5 추출 결과)
- 경계: `../data/raw/terrain/emd_boundary_20260701.zip`

N3A 원본에는 시군구명 필드가 없어 이름 컬럼만 추가하는 방식 대신 새 경계로 공간 재집계했다. 경계 ZIP은 EPSG:5179라고 표기하지만 실제 좌표는 경도 124~132, 위도 33~39다. 지형 전처리 코드의 원본 설명도 EPSG:4326이다. EPSG:4326으로 지정한 뒤 EPSG:5179로 변환했고 원본 ZIP은 수정하지 않았다.

## 재실행과 검증

```powershell
python visualizations/refresh_10_14.py
```

원본 폴더는 `--source-root`로 변경한다. 위 명령은 두 CSV·지도와 감사 파일을 갱신한다. 중복 지역코드, 다중 공간 배정, 누락 좌표, 비정상 수치, 집계 정류장 수 및 운행량 보존을 검증한다. 이름 중복을 순서나 임의 인구 배분으로 해결하지 않는다.

감사 자료는 `dong_supply_audit/audit.json`, `unresolved_population_regions.csv`, `unmatched_source_population.csv`다. 남은 결측 146개를 해결하려면 시군구·행정동 코드가 있는 인구 원본과 기준시점 대응 자료가 필요하다.

고유코드가 있는 인구를 확보한 경우 `rebuild_dong_supply.py`를 사용할 수 있다. 인구 입력은 `dong_code,population,elderly`, 공급 입력은 `stop_id,day_type,departures,headway_min`, 좌표는 `stop_id,stop_lat,stop_lon`이다. 인구 코드 집합은 경계와 일치해야 하며 분석 대상 교통수단은 입력 단계에서 통일한다. 날짜는 실제 자료의 기준일로 지정한다.

```powershell
python visualizations/rebuild_dong_supply.py --boundary-crs EPSG:4326 --boundary-date 2026-07-01 --population population.csv --population-date 2025 --stops bus_stops.csv --supply bus_supply.csv --supply-date 2025-03
```

일반 코드의 기본 출력은 `rebuilt_dong_supply` 검토 폴더다. 기존 `make_14.py`, `fix14*.py`, `fix_14_16.py` 및 10번의 기존 지도 스크립트는 예전 스키마용이다. 새 결과는 위 명령으로 생성한다. 12·15번 파생 결과는 이번에 재생성하지 않았다. 특히 15번의 동명 단독 조인과 예전 `per_10k` 참조는 공통 코드 및 새 지표명으로 수정한 후 사용해야 한다.
