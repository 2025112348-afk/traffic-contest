from pathlib import Path
import pandas as pd, geopandas as gpd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']='Malgun Gothic'; plt.rcParams['axes.unicode_minus']=False
R=Path(__file__).resolve().parents[2]; O=Path(__file__).resolve().parent
d=pd.read_csv(O/'stop_supply_by_dong.csv'); g=gpd.read_file(R/'N3A_G0110000.shp',encoding='euc-kr').set_crs(5179,allow_override=True)
codes={'11':'서울특별시','26':'부산광역시','27':'대구광역시','28':'인천광역시','29':'광주광역시','30':'대전광역시','31':'울산광역시','36':'세종특별자치시','41':'경기도','51':'강원특별자치도','43':'충청북도','44':'충청남도','52':'전북특별자치도','46':'전라남도','47':'경상북도','48':'경상남도','50':'제주특별자치도'}
g['province']=g.BJCD.astype(str).str[:2].map(codes); g['dong']=g.NAME.str.strip(); m=g.merge(d,on=['province','dong'],how='inner'); lo,hi=m.per10k.quantile([.02,.98]); top=d.sort_values(['per10k','aging'],ascending=[True,False]).head(5)
fig,ax=plt.subplots(figsize=(16,14),facecolor='#f8fafc'); m.plot(column='per10k',ax=ax,cmap='YlGnBu',vmin=lo,vmax=hi,edgecolor='white',linewidth=.04,legend=True,legend_kwds={'label':'인구 1만 명당 버스 정류장 수','shrink':.65}); ax.set_axis_off(); fig.suptitle('인구 대비 버스 정류장 공급 격차',fontsize=26,weight='bold',color='#172b4d'); fig.text(.07,.92,'색이 연할수록 인구 대비 정류장 공급이 적음 · 2025년 3월 GTFS',fontsize=13,color='#475569'); lines=['공급이 가장 낮은 상위 5개 읍면동']+[f"{i}. {r.province} {r.dong}  |  {r.per10k:.2f}개/1만명  |  인구 {r.population:,.0f}명  |  고령화율 {r.aging:.1f}%" for i,(_,r) in enumerate(top.iterrows(),1)]; fig.text(.07,.045,'\n'.join(lines),fontsize=11,color='#172b4d'); fig.text(.07,.012,'읍면동 2,354개 · 정류장 미매칭 4,862개 · 색상 범위는 2~98 백분위',fontsize=10,color='#475569'); fig.subplots_adjust(top=.87,bottom=.16,left=.03,right=.97); fig.savefig(O/'stop_supply_map.png',dpi=260); plt.close(fig)
