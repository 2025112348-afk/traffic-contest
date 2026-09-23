"""노선 유형→운행→정차 지점 연결로 버스 정류장만 선택한다."""
from pathlib import Path
import json
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = ROOT/'대중교통GTFS(2025년 기준)'/'202503_GTFS_DataSet'
types = {0:'시내·농어촌·마을버스',3:'시외버스',5:'공항리무진버스'}
routes = pd.read_csv(DATA/'routes.txt',usecols=['route_id','route_type'])
trips = pd.read_csv(DATA/'trips.txt',usecols=['route_id','trip_id'])
stops = pd.read_csv(DATA/'stops.txt',dtype={'stop_id':str,'stop_name':str})
assert not routes.isna().any().any() and not trips.isna().any().any()
assert not routes.route_id.duplicated().any() and not trips.trip_id.duplicated().any()
assert set(trips.route_id).issubset(set(routes.route_id))
bus_routes = routes.loc[routes.route_type.isin(types)]
bus_trips = trips.merge(bus_routes,on='route_id',how='inner',validate='many_to_one')
lookup = bus_trips.set_index('trip_id').route_type
known_trips = set(trips.trip_id)
ids = {k:set() for k in types}
counts = {k:0 for k in types}
total_rows = 0
for chunk in pd.read_csv(DATA/'stop_times.txt',usecols=['trip_id','stop_id'],dtype=str,chunksize=500000):
    assert not chunk.isna().any().any()
    assert set(chunk.trip_id).issubset(known_trips)
    categories = chunk.trip_id.map(lookup)
    for k in types:
        selected = chunk.loc[categories.eq(k),'stop_id']
        ids[k].update(selected.unique())
        counts[k] += len(selected)
    total_rows += len(chunk)
    if total_rows % 2500000 == 0:
        print(f'Checked {total_rows:,} stop-time rows',flush=True)
bus_ids = set().union(*ids.values())
assert bus_ids.issubset(set(stops.stop_id))
bus = stops.loc[stops.stop_id.isin(bus_ids)].copy()
assert len(bus) == len(bus_ids)
# 설명서 10쪽과 대조한다. 버스 유형 간 공용 정류장은 합집합으로 한 번만 센다.
assert len(bus) == 213625
assert [len(ids[k]) for k in types] == [211585,1745,1562]
assert total_rows == 18889140
bus.to_csv(OUT/'bus_stops.csv',index=False,encoding='utf-8-sig')
classification = bus[['stop_id','stop_name']].copy()
for k,name in types.items():
    classification[name] = classification.stop_id.isin(ids[k])
classification.to_csv(OUT/'bus_stop_types.csv',index=False,encoding='utf-8-sig')
selection = {'method':'routes.route_type in [0,3,5] -> trips -> stop_times -> stops',
             'documentation':'202503_GTFS_설명서.pdf, pages 4 and 10',
             'all_stops':len(stops),'bus_stops':len(bus),'excluded_stops':len(stops)-len(bus),
             'bus_routes':len(bus_routes),'bus_trips':len(bus_trips),'stop_time_rows_scanned':total_rows,
             'per_type':{str(k):{'name':name,'stops':len(ids[k]),'stop_time_rows':counts[k]} for k,name in types.items()}}
(OUT/'bus_selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
# 기존 지도 그리기 처리를 재사용하고 입력을 버스 CSV로 한정한다.
renderer = (ROOT/'visualizations/06_gtfs_stops_2025/make_map.py').read_text(encoding='utf-8')
renderer = renderer.replace("source = ROOT/'대중교통GTFS(2025년 기준)'/'202503_GTFS_DataSet'/'stops.txt'", "source = OUT/'bus_stops.csv'")
renderer = renderer.replace('대중교통 정차 지점','버스 정류장').replace('정차 지점','버스 정류장')
renderer = renderer.replace('stops.txt의','버스 노선에 연결된')
exec(compile(renderer,str(OUT/'renderer'), 'exec'),{'__file__':str(OUT/'make_bus_map.py'),'__name__':'__main__'})
table = '\n'.join(f'| {name} | {len(ids[k]):,} |' for k,name in types.items())
report = f'''# 2025년 3월 버스 정류장만 표시한 지도

![버스 정류장 지도](stops_distribution.png)

`stops_map.html`을 브라우저에서 열어 확대·이동·이름 또는 ID 검색을 할 수 있습니다. 데이터가 포함된 오프라인 지도입니다.

## 사용한 원본과 버스 정의
- 폴더: `대중교통GTFS(2025년 기준)/202503_GTFS_DataSet`.
- 사용 파일: `routes.txt`, `trips.txt`, `stop_times.txt`, `stops.txt`.
- 분류 근거: `대중교통GTFS(2025년 기준)/202503_GTFS_설명서.pdf` 4쪽의 KTDB 코드 정의와 10쪽의 규모표.
- 이 자료는 일반 GTFS와 route_type 코드가 다릅니다. **0=시내/농어촌/마을버스, 3=시외버스, 5=공항리무진버스**를 버스로 선택했습니다. 정류장 ID 접두사로 추정하지 않았습니다.
- 자료는 2025년 3월 평일 1일 기준입니다. 현재 실시간 운행 정보가 아닙니다.

## 전처리
1. 버스 노선 {len(bus_routes):,}개를 선택하고 trips와 연결해 운행 {len(bus_trips):,}개를 확인했습니다.
2. stop_times {total_rows:,}행을 50만 행씩 읽어 버스 운행의 stop_id를 수집했습니다. 노선·운행 ID 중복, 누락과 운행 참조 관계를 검사했습니다.
3. 수집한 정류장 ID의 합집합을 만들고 stops의 좌표·이름과 연결했습니다. 같은 정류장에 여러 버스 유형이 정차해도 1개 ID로 계산했습니다.
4. 전체 {len(stops):,}개 중 버스 정류장 **{len(bus):,}개**를 남기고 나머지 **{len(stops)-len(bus):,}개**를 제외했습니다. 버스 총계 및 유형별 개수는 설명서 10쪽과 일치합니다.
5. 좌표 결측, 중복 ID, 잘못된 위도·경도 범위를 검사했습니다. 같은 좌표의 서로 다른 ID는 합치지 않았습니다. 상세 좌표 검증은 `validation.json`에 있습니다.

| 버스 유형 | 정류장 ID 수 |
|---|---:|
{table}

유형 간 공용 정류장이 있어 표의 개수를 단순 합산하면 버스 전체 개수보다 커집니다.

## 지도 해석
- 점은 버스 노선과 연결된 정류장 ID입니다. 시설·건물 개수, 운행 횟수, 승객 수를 뜻하지 않습니다.
- 배경은 Natural Earth 저해상도 지형입니다. 제주 등 작은 섬이 생략될 수 있으며, 점이 바다 위에 보이는 것만으로 좌표 오류라고 판단하면 안 됩니다. 배경으로 정류장을 제거하지 않았습니다.
- PNG는 원본 좌표, HTML은 소수 7자리 좌표를 사용합니다. 단순 경위도 기반 표시로 거리 측정용이 아닙니다.
- HTML 지도는 확대·이동·검색을 지원하며 겹친 점 위에서는 가까운 ID 하나가 표시됩니다. 브라우저 실제 조작 검증은 수행하지 않았습니다.

## 결과 파일
- `bus_stops.csv`: 버스 정류장 ID·이름·좌표.
- `bus_stop_types.csv`: 정류장별 버스 유형 포함 여부.
- `bus_selection.json`: 연결·추출 검증 결과.
- `stops_map.html`: 버스만 표시한 검색 지도.
- 재실행: `.venv/Scripts/python.exe visualizations/07_bus_stops_2025/make_bus_map.py`.
- 지도 생성은 앞서 만든 `visualizations/06_gtfs_stops_2025/make_map.py`의 그리기 처리를 재사용합니다.
'''
(OUT/'README.md').write_text(report,encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps(selection,ensure_ascii=False,indent=2))
