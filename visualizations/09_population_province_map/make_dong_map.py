from pathlib import Path
import pandas as pd, geopandas as gpd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']='Malgun Gothic'; plt.rcParams['axes.unicode_minus']=False
R=Path(__file__).resolve().parents[2]; O=Path(__file__).resolve().parent; p=sorted(R.glob('연령_및_성별_인구_*.csv'),key=lambda x:x.stat().st_mtime,reverse=True)[0]
d=pd.read_csv(p,encoding='euc-kr'); d.columns=['지역','연령','값']; d['값']=pd.to_numeric(d['값'],errors='coerce'); prov=set(['서울특별시','부산광역시','대구광역시','인천광역시','광주광역시','대전광역시','울산광역시','세종특별자치시','경기도','강원특별자치도','충청북도','충청남도','전북특별자치도','전라남도','경상북도','경상남도','제주특별자치도']); cur=''; z=[]
for _,r in d.iloc[2:].iterrows():
 if r.지역 in prov: cur=r.지역
 if cur and r.연령 in ['합계','65세이상'] and r.지역 not in prov: z.append([cur,r.지역,r.연령,r.값])
t=pd.DataFrame(z,columns=['시도','읍면동','연령','인구']).pivot_table(index=['시도','읍면동'],columns='연령',values='인구',aggfunc='sum').reset_index(); t['고령화율']=t['65세이상']/t['합계']*100
g=gpd.read_file(R/'N3A_G0110000.shp',encoding='euc-kr'); g['code']=g.BJCD.astype(str).str[:2].astype(int); n={11:'서울특별시',26:'부산광역시',27:'대구광역시',28:'인천광역시',29:'광주광역시',30:'대전광역시',31:'울산광역시',36:'세종특별자치시',41:'경기도',51:'강원특별자치도',43:'충청북도',44:'충청남도',52:'전북특별자치도',46:'전라남도',47:'경상북도',48:'경상남도',50:'제주특별자치도'}; g['시도']=g.code.map(n); g['읍면동']=g.NAME.str.strip(); m=g.merge(t,on=['시도','읍면동'],how='inner'); m[['시도','읍면동','합계','65세이상','고령화율']].to_csv(O/'dong_age_population.csv',index=False,encoding='utf-8-sig')
fig,ax=plt.subplots(1,2,figsize=(22,13),facecolor='#f8fafc',constrained_layout=True); q1=m['고령화율'].quantile([.02,.98]); q2=m['합계'].quantile([.02,.98]);
gpd.GeoDataFrame(m).plot(column='고령화율',ax=ax[0],cmap='YlOrRd',vmin=q1.iloc[0],vmax=q1.iloc[1],edgecolor='#ffffff',linewidth=.08,legend=True,legend_kwds={'label':'65세 이상 비율 (%)','shrink':.7}); gpd.GeoDataFrame(m).plot(column='합계',ax=ax[1],cmap='Blues',vmin=q2.iloc[0],vmax=q2.iloc[1],edgecolor='#ffffff',linewidth=.08,legend=True,legend_kwds={'label':'총인구 (명, 2~98 백분위 범위)','shrink':.7}); [a.set_axis_off() for a in ax]; ax[0].set_title('읍면동별 고령화율',fontsize=18); ax[1].set_title('읍면동별 총인구',fontsize=18); fig.suptitle('2025년 읍면동별 인구 지도',fontsize=25); fig.savefig(O/'dong_age_map.png',dpi=240); plt.close(fig)
(O/'README_dong.md').write_text(f'CSV의 합계·65세이상 행을 읍면동 경계 NAME과 시도명으로 연결했습니다. 연결된 읍면동은 {len(m):,}개입니다. 고령화율은 65세 이상 인구/총인구입니다. 인구가 적어도 고령화율이 높은 지역은 DRT·마을버스 우선 후보로 검토할 수 있으나 정류장 거리·배차·승하차 수요를 추가해야 합니다.',encoding='utf-8')
