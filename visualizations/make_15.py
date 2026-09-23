from pathlib import Path
import pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager
root=Path('.'); fp=font_manager.FontProperties(fname=r'C:\Windows\Fonts\malgun.ttf'); a=pd.read_csv(root/'visualizations/14_dong_supply/dong_supply.csv'); age=pd.read_csv(root/'visualizations/09_population_province_map/dong_age_population.csv'); age=age.rename(columns={'읍면동':'NAME','고령화율':'aging'}); m=a.merge(age[['NAME','aging']],on='NAME',how='inner'); m.to_csv(root/'visualizations/15_age_supply/age_supply.csv',index=False,encoding='utf-8-sig'); fig,ax=plt.subplots(figsize=(10,7)); ax.scatter(m.aging,m.per_10k,s=25,color='#7b3294',alpha=.6); ax.set_xlabel('고령화율 (%)',fontproperties=fp,fontsize=13); ax.set_ylabel('정류장당 평일 운행 공급량',fontproperties=fp,fontsize=13); ax.set_title('고령화율과 버스 공급량 비교',fontproperties=fp,fontsize=18); ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(root/'visualizations/15_age_supply/age_supply_scatter.png',dpi=200)
