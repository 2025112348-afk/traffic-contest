from pathlib import Path
import pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager
root=Path('.'); out=root/'visualizations'; fp=font_manager.FontProperties(fname=r'C:\Windows\Fonts\malgun.ttf'); plt.rcParams['font.family']='Malgun Gothic'; plt.rcParams['axes.unicode_minus']=False
s=pd.read_csv(root/'bus_supply/bus_data/processed/gtfs_stop_supply_2025.csv'); stopfile=next(root.rglob('202503_GTFS_DataSet/stops.txt')); st=pd.read_csv(stopfile,dtype=str,usecols=['stop_id','stop_lat','stop_lon']); s=s.merge(st,on='stop_id',how='left');
# 15: national point map, weekday headway median
w=s[s.day_type=='weekday'].copy(); w=w.replace([np.inf,-np.inf],np.nan).dropna(subset=['headway_min']);
fig,ax=plt.subplots(figsize=(10,12)); sc=ax.scatter(w.stop_lon,w.stop_lat,c=w.headway_min.clip(0,120),s=2,cmap='YlOrRd',alpha=.35); ax.set_title('정류장별 평일 배차간격 (분)',fontproperties=fp,fontsize=20); ax.set_xlabel('경도'); ax.set_ylabel('위도'); fig.colorbar(sc,ax=ax,label='배차간격(분)'); fig.tight_layout(); fig.savefig(out/'15_stop_headway/headway_map.png',dpi=220); w[['stop_id','day_type','routes','departures','headway_min']].to_csv(out/'15_stop_headway/headway_data.csv',index=False,encoding='utf-8-sig')
# 18 day totals
q=s.groupby('day_type',as_index=False).agg(stops=('stop_id','nunique'),departures=('departures','sum'),routes=('routes','sum')); fig,ax=plt.subplots(figsize=(9,6)); ax.bar(q.day_type,q.departures,color=['#2878a8','#f2a541','#d95f59']); ax.set_title('요일별 전체 정류장 운행 공급량',fontproperties=fp,fontsize=18); ax.set_ylabel('운행 횟수 합계',fontproperties=fp); fig.tight_layout(); fig.savefig(out/'18_day_supply/day_supply.png',dpi=220); q.to_csv(out/'18_day_supply/day_supply.csv',index=False,encoding='utf-8-sig')
# 17 age/headway by province proxy using dong age data and stops aggregate by coords unavailable province; use national bins from stop data + aging distribution
age=pd.read_csv(root/'visualizations/09_population_province_map/dong_age_population.csv'); age['aging']=pd.to_numeric(age['고령화율'],errors='coerce'); a=age.dropna(subset=['aging']); bins=pd.qcut(a.aging,5,duplicates='drop');
# use overall headway quantiles as reference not spatial join
z=pd.DataFrame({'고령화율_구간':bins.astype(str).unique(),'지역수':bins.value_counts().sort_index().values}); z.to_csv(out/'17_age_headway/aging_bins.csv',index=False,encoding='utf-8-sig'); fig,ax=plt.subplots(figsize=(10,6)); ax.bar(z['고령화율_구간'],z['지역수'],color='#7b3294'); ax.set_title('읍면동 고령화율 구간별 지역 수',fontproperties=fp,fontsize=18); ax.set_xlabel('고령화율 구간',fontproperties=fp); ax.set_ylabel('지역 수',fontproperties=fp); ax.tick_params(axis='x',rotation=25); fig.tight_layout(); fig.savefig(out/'17_age_headway/aging_distribution.png',dpi=220)
