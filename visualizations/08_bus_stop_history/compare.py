from pathlib import Path
import pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']='Malgun Gothic'; plt.rcParams['axes.unicode_minus']=False
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent; OUT.mkdir(exist_ok=True)
spec=[(2021,ROOT/'2022-TM-PT-GTFS 대중교통GTFS(2021년 기준)'/'GTFS_202103_DataSet'),(2022,ROOT/'2023-TM-PT-GTFS 대중교통GTFS(2022년 기준)'/'202203_GTFS_DataSet'),(2023,ROOT/'2024-TM-PT-GTFS 대중교통GTFS(2023년 기준)'/'202303_GTFS_DataSet'),(2024,ROOT/'2025-TM-PT-GTFS 대중교통GTFS(2024년 기준)'/'202403_GTFS_DataSet'),(2025,ROOT/'대중교통GTFS(2025년 기준)'/'202503_GTFS_DataSet')]
rows=[]
for year,d in spec:
 if not (d/'stops.txt').exists(): continue
 routes=pd.read_csv(d/'routes.txt',usecols=['route_id','route_type']); trips=pd.read_csv(d/'trips.txt',usecols=['route_id','trip_id']); stops=pd.read_csv(d/'stops.txt',usecols=['stop_id'],dtype=str)
 br=set(routes.loc[routes.route_type.isin([0,3,5]),'route_id']); bt=set(trips.loc[trips.route_id.isin(br),'trip_id']); ids=set()
 for c in pd.read_csv(d/'stop_times.txt',usecols=['trip_id','stop_id'],dtype=str,chunksize=500000): ids.update(c.loc[c.trip_id.isin(bt),'stop_id'])
 ids &= set(stops.stop_id); rows.append({'연도':year,'버스정류장':len(ids),'버스노선':len(br),'버스운행':len(bt)}); print(rows[-1],flush=True)
out=pd.DataFrame(rows); out.to_csv(OUT/'bus_stop_history.csv',index=False,encoding='utf-8-sig')
fig,ax=plt.subplots(figsize=(11,6),facecolor='#f8fafc'); ax.plot(out.연도,out.버스정류장,'o-',lw=2.5,color='#2563eb');
for x,y in zip(out.연도,out.버스정류장): ax.annotate(f'{y:,}',(x,y),xytext=(0,9),textcoords='offset points',ha='center')
ax.set_xticks(out.연도); ax.set_ylabel('버스 정류장 ID 수'); ax.set_xlabel('GTFS 기준연도'); ax.grid(axis='y',alpha=.25); ax.tick_params(length=0)
for s in ax.spines.values(): s.set_visible(False)
fig.text(.08,.93,'과거와 2025년, 버스 정류장은 어떻게 달라졌을까?',fontsize=19,weight='bold',color='#172b4d'); fig.text(.08,.06,'route_type 0·3·5 버스 노선에 연결된 stop_id 집계. ID 수는 시설 수·이용객·운행횟수가 아니며 자료 구축 차이가 포함될 수 있습니다.',fontsize=9,color='#475569'); fig.subplots_adjust(top=.82,bottom=.2,left=.1,right=.97); fig.savefig(OUT/'bus_stop_history.png',dpi=180); plt.close(fig)
delta=(out.iloc[-1].버스정류장/out.iloc[0].버스정류장-1)*100
(OUT/'README.md').write_text(f'''# 과거와 2025년 버스 정류장 비교\n\n![비교](bus_stop_history.png)\n\n2021·2022·2023·2024·2025년 기준 GTFS 자료에서 같은 방식으로 버스 정류장을 집계했습니다.\n\n| 기준연도 | 버스 정류장 ID | 버스 노선 | 버스 운행회차 |\n|---|---:|---:|---:|\n'''+'\n'.join(f"| {r.연도} | {r.버스정류장:,} | {r.버스노선:,} | {r.버스운행:,} |" for r in out.itertuples())+f'''\n\n각 연도의 routes.txt에서 KTDB 버스 유형 0(시내·농어촌·마을), 3(시외), 5(공항리무진)을 고른 뒤 trips→stop_times로 연결된 stop_id를 추출하고 stops.txt에 존재하는 ID만 셌습니다. 2021년 대비 2025년 변화는 {delta:+.2f}%입니다.\n\n이 차이는 실제 정류장 신설·폐지뿐 아니라 GTFS ID 개편, 노선·운행 범위, 자료 구축 방식 차이가 포함될 수 있습니다. 원본은 수정하지 않았습니다.\n''',encoding='utf-8')
