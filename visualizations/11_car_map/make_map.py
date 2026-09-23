from pathlib import Path
import glob,pandas as pd, geopandas as gpd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager
root=Path(__file__).resolve().parents[2]; out=root/'visualizations/11_car_map'
font_manager.fontManager.addfont(r'C:\Windows\Fonts\malgun.ttf')
plt.rcParams['font.family']='Malgun Gothic'
plt.rcParams['axes.unicode_minus']=False
fp=font_manager.FontProperties(fname=r'C:\Windows\Fonts\malgun.ttf')
raw=glob.glob(str(root/'*1인당*자동차*csv'))[0]
d=pd.read_csv(raw,encoding='cp949',header=None,skiprows=2,names=['region','cars_per_person']); d['cars_per_person']=pd.to_numeric(d.cars_per_person,errors='coerce'); d=d.dropna(subset=['cars_per_person']); d['region']=d.region.astype(str).str.strip()
# province rows only, identified by official names after normalizing special自治 names
aliases={'강원도':'강원특별자치도','전라북도':'전북특별자치도'}
prov_names=['서울특별시','부산광역시','대구광역시','인천광역시','광주광역시','대전광역시','울산광역시','세종특별자치시','경기도','강원특별자치도','충청북도','충청남도','전북특별자치도','전라남도','경상북도','경상남도','제주특별자치도']
# robust match by exact name or legacy aliases
rows=[]
for n in prov_names:
 cand=d[d.region.eq(n)]
 if cand.empty:
  legacy={'강원특별자치도':'강원도','전북특별자치도':'전라북도'}.get(n)
  cand=d[d.region.eq(legacy)] if legacy else cand
 if not cand.empty: rows.append({'region':n,'cars_per_person':float(cand.iloc[0].cars_per_person)})
prov=pd.DataFrame(rows); prov.to_csv(out/'car_per_person_province.csv',index=False,encoding='utf-8-sig')
# boundary codes
code={'서울특별시':'11','부산광역시':'26','대구광역시':'27','인천광역시':'28','광주광역시':'29','대전광역시':'30','울산광역시':'31','세종특별자치시':'36','경기도':'41','강원특별자치도':'51','충청북도':'43','충청남도':'44','전북특별자치도':'52','전라남도':'46','경상북도':'47','경상남도':'48','제주특별자치도':'50'}
prov['pcode']=prov.region.map(code); g=gpd.read_file(root/'N3A_G0110000.shp',encoding='euc-kr').set_crs(5179,allow_override=True); g['pcode']=g.BJCD.astype(str).str[:2]; g=g.dissolve('pcode').reset_index(); m=g.merge(prov,on='pcode',how='left')
fig,ax=plt.subplots(figsize=(12,12)); m.plot(column='cars_per_person',cmap='YlOrRd',edgecolor='white',linewidth=.25,legend=True,ax=ax,missing_kwds={'color':'#d9d9d9'},legend_kwds={'label':'1인당 자동차 등록대수 (대)','shrink':.55}); ax.set_title('시도별 1인당 자동차 등록대수',fontproperties=fp,fontsize=20,weight='bold'); ax.axis('off')
for _,r in m.dropna(subset=['cars_per_person']).drop_duplicates('pcode').iterrows():
 p=r.geometry.representative_point(); ax.text(p.x,p.y,f"{r.region}\n{r.cars_per_person:.1f}대",fontproperties=fp,fontsize=8,ha='center',va='center')
fig.tight_layout(); fig.savefig(out/'car_per_person_map.png',dpi=220,bbox_inches='tight')
