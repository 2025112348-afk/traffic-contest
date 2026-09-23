from pathlib import Path
import pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager
root=Path(__file__).resolve().parents[2]; out=root/'visualizations/12_car_stop_scatter'; fp=font_manager.FontProperties(fname=r'C:\Windows\Fonts\malgun.ttf')
car=pd.read_csv(root/'visualizations/11_car_map/car_per_person_province.csv'); car['cars_per_1000']=car.cars_per_person*1000
st=pd.read_csv(root/'visualizations/10_stop_supply_index/stop_supply_by_dong.csv'); agg=st.groupby('province',as_index=False).agg(population=('population','sum'),stops=('stops','sum')); agg['stops_per_10k']=agg.stops/agg.population*10000
for d,c in [(car,'region'),(agg,'province')]: d['key']=d[c].astype(str).str.replace('특별자치도','').str.replace('특별자치시','').str.replace('특별시','').str.replace('광역시','').str.replace('도','').str.strip()
m=car.merge(agg,on='key',how='inner'); m.to_csv(out/'car_stop_data.csv',index=False,encoding='utf-8-sig')
fig,ax=plt.subplots(figsize=(13,9)); ax.scatter(m.cars_per_1000,m.stops_per_10k,s=130,color='#2878a8',edgecolor='white',linewidth=1)
for _,r in m.iterrows():
    name=str(r.region)
    if '\ucda9\uccad\ubd81' in name: off=(-38,12)
    elif '\uacbd\uc0c1\ubd81' in name: off=(10,-16)
    else: off=(5,5)
    ax.annotate(r.region,(r.cars_per_1000,r.stops_per_10k),xytext=off,textcoords='offset points',fontproperties=fp,fontsize=10)
ax.set_xlabel('인구 1,000명당 자동차 등록대수 (대)',fontproperties=fp,fontsize=14); ax.set_ylabel('인구 1만 명당 버스 정류장 수',fontproperties=fp,fontsize=14); ax.set_title('자동차 등록대수와 버스 정류장 수 비교',fontproperties=fp,fontsize=20); ax.tick_params(labelsize=11); ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(out/'car_stop_scatter.png',dpi=220,bbox_inches='tight')
