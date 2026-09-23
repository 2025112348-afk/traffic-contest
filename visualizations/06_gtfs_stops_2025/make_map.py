"""2025년 3월 GTFS 정차 지점 분포: PNG와 외부 접속 없는 HTML."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
source = ROOT/'대중교통GTFS(2025년 기준)'/'202503_GTFS_DataSet'/'stops.txt'
df = pd.read_csv(source,encoding='utf-8-sig',dtype={'stop_id':str,'stop_name':str})
assert list(df.columns) == ['stop_id','stop_name','stop_lat','stop_lon']
assert not df.isna().any().any()
assert not df.stop_id.duplicated().any()
assert df.stop_id.str.strip().ne('').all() and df.stop_name.str.strip().ne('').all()
for col in ['stop_lat','stop_lon']:
    df[col] = pd.to_numeric(df[col],errors='raise')
    assert np.isfinite(df[col]).all()
assert df.stop_lat.between(-90,90).all() and df.stop_lon.between(-180,180).all()
assert df.stop_lat.between(32,40).all() and df.stop_lon.between(123,133).all()
duplicates = int(df.duplicated(['stop_lat','stop_lon']).sum())
df.to_csv(OUT/'stops_clean.csv',index=False,encoding='utf-8-sig')
# 설치된 라이브러리의 저해상도 Natural Earth 지형을 배경으로만 사용.
base_path = Path(pyogrio.__file__).parent/'tests/fixtures/naturalearth_lowres/naturalearth_lowres.shp'
base = gpd.read_file(base_path)
base = base.cx[123.9:132.2,32.8:38.9]
assert base.crs.to_epsg() == 4326
geometries = []
for geom in base.geometry:
    polys = list(geom.geoms) if geom.geom_type == 'MultiPolygon' else [geom]
    for poly in polys:
        if poly.geom_type == 'Polygon':
            geometries.append([[float(x),float(y)] for x,y in poly.exterior.coords])
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':11})
fig,ax = plt.subplots(figsize=(11,10),facecolor='#f8fafc')
ax.set_facecolor('#eaf3f8')
base.plot(ax=ax,color='#f5f3ed',edgecolor='#bbc5ca',linewidth=.7)
ax.scatter(df.stop_lon,df.stop_lat,s=.8,alpha=.28,color='#155da8',edgecolors='none',rasterized=True)
ax.set_xlim(123.9,132.2)
ax.set_ylim(32.8,38.9)
ax.set_aspect(1/np.cos(np.deg2rad(36)))
ax.set_xlabel('경도 (°)')
ax.set_ylabel('위도 (°)')
ax.grid(alpha=.15)
fig.text(.08,.95,'대중교통 정차 지점은 어디에 있을까?',fontsize=22,fontweight='bold',color='#172b4d')
fig.text(.08,.905,f'2025년 3월 GTFS · stops.txt의 {len(df):,}개 ID · 같은 좌표의 다른 ID 유지',fontsize=11,color='#475569')
fig.text(.08,.035,'점은 GTFS에 수록된 정차 지점입니다. 운행 횟수·이용객 수·접근성을 뜻하지 않습니다.\n배경: Natural Earth 저해상도 지형(작은 섬 생략 가능). 지역별 집계나 행정경계 판정에는 사용하지 않았습니다.',fontsize=9,color='#475569')
fig.subplots_adjust(top=.86,bottom=.12,left=.09,right=.97)
fig.savefig(OUT/'stops_distribution.png',dpi=180)
plt.close(fig)
data = [[r.stop_id,r.stop_name,round(r.stop_lon,7),round(r.stop_lat,7)] for r in df.itertuples()]
template = (OUT/'map_template.html').read_text(encoding='utf-8')
html = template.replace('__STOPS__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'))
html = html.replace('__LAND__',json.dumps(geometries,separators=(',',':')))
(OUT/'stops_map.html').write_text(html,encoding='utf-8')
audit = {'source':source.relative_to(ROOT).as_posix(),'rows':len(df),'missing_cells':0,
         'duplicate_stop_ids':0,'duplicate_coordinate_rows_after_first':duplicates,
         'invalid_coordinates':0,'removed_rows':0,
         'latitude_range':[float(df.stop_lat.min()),float(df.stop_lat.max())],
         'longitude_range':[float(df.stop_lon.min()),float(df.stop_lon.max())],
         'background_source':str(base_path),'background_crs':str(base.crs)}
(OUT/'validation.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
report = f'''# 2025년 3월 GTFS 정차 지점 분포

![정차 지점 분포](stops_distribution.png)

`stops_map.html`을 브라우저에서 열면 확대·이동·정류장 이름/ID 검색이 가능합니다. 점 위에 마우스를 올리면 가까운 지점 하나의 이름·ID·좌표가 나타납니다. 같은 위치에 여러 ID가 있으면 하나만 표시될 수 있습니다. 파일 안에 데이터가 포함되어 있어 외부 지도 서버나 인터넷 연결이 필요하지 않습니다.

## 사용 데이터
- 원본: `{source.relative_to(ROOT).as_posix()}`.
- 열: `stop_id`(지점 식별자), `stop_name`(이름), `stop_lat`(위도), `stop_lon`(경도).
- 앞선 인구 분석의 2023년과 별개로, 보유 GTFS 중 가장 최근인 2025년 3월 자료를 사용했습니다. 현재 실시간 정류장 정보가 아닙니다.
- 이번 단계는 정차 지점 위치만 사용합니다. 노선·운행·승객과 연결하지 않았고 ID 접두사로 교통수단을 추정하지 않았습니다.

## 전처리 및 검증
1. `stops.txt`를 UTF-8 CSV로 읽었습니다. 줄 사이 빈 줄은 CSV 판독기의 기본 동작으로 건너뛰었습니다. ID는 문자열로 보존했습니다. `extracted` 사본은 중복 집계하지 않았습니다.
2. {len(df):,}행을 확인했습니다. 필수 열의 결측, 빈 ID/이름, 중복 ID는 없습니다.
3. 위도·경도를 숫자로 변환하고 유한값과 전 세계 좌표 범위를 검사했습니다. 넓은 확인 범위(위도 32~40도, 경도 123~133도) 안에도 모두 들어갑니다. 이는 모든 좌표의 현장 정확성을 보증하지 않습니다.
4. 같은 위도·경도가 앞선 행과 중복되는 행은 {duplicates:,}개입니다. 서로 다른 정차 지점 ID일 수 있어 삭제하지 않았습니다. 이름이 같아도 합치지 않았습니다. 제거하거나 채운 행은 없습니다.
5. PNG에는 원본 좌표를 사용했습니다. HTML은 파일 크기를 줄이도록 소수 7자리까지 좌표를 보존했습니다. 표본추출 없이 모든 지점을 넣었습니다.
6. 지도는 경도에 cos(36도)를 적용한 단순 좌표 표시입니다. 거리·면적을 측정하는 도구가 아닙니다. 확대와 이동으로 세부 분포를 확인할 수 있습니다.
7. 배경은 설치된 pyogrio에 포함된 Natural Earth 저해상도 지형입니다. 작은 섬이 생략될 수 있으며 정차 지점을 배경 경계로 자르지 않았습니다. 행정구역별 집계나 정밀한 위치 판정에는 사용하지 않았습니다.

## 읽는 방법
- 점이 빽빽한 곳은 수록 지점이 많이 겹치는 곳입니다. 전국 그림에서는 중첩과 투명도 때문에 정확한 개수를 눈으로 셀 수 없습니다.
- 지점 개수는 정류장 건물 수와 같지 않을 수 있습니다. 방향별 정류장이나 같은 좌표의 별도 ID를 그대로 유지했습니다.
- 운행 횟수, 운영 중 여부, 이용객, 배차 간격, 접근성은 이 지도만으로 판단할 수 없습니다. 이를 보려면 노선·운행시각 자료와 추가로 연결해야 합니다.
- 행정경계가 없어 이번 단계에서는 시도별 개수를 계산하지 않았습니다.

## 결과 파일
- `stops_map.html`: 오프라인 확대·이동·검색 지도.
- `stops_distribution.png`: 전체 분포 이미지.
- `stops_clean.csv`: 검증한 전체 정차 지점.
- `validation.json`: 원본 경로와 검증 수치.
- 재실행: `.venv/Scripts/python.exe visualizations/06_gtfs_stops_2025/make_map.py`.
'''
(OUT/'README.md').write_text(report,encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False,indent=2))
