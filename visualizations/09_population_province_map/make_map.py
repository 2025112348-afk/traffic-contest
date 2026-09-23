from pathlib import Path
import pandas as pd, geopandas as gpd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']='Malgun Gothic'
plt.rcParams['axes.unicode_minus']=False
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent; OUT.mkdir(exist_ok=True)
popfile=sorted(ROOT.glob('연령_및_성별_인구_*.xlsx'),key=lambda p:p.stat().st_mtime,reverse=True)[0]
d=pd.read_excel(popfile,sheet_name='데이터',header=1)
groups=d.iloc[:,0].dropna().tolist(); provinces=groups[4:21]; rows=[]
for i,name in enumerate(provinces):
    b=d.iloc[(i+4)*28:(i+5)*28]; rows.append({'시도':name,'총인구':float(b.iloc[0,2]),'65세이상':float(b.iloc[24,2])})
stats=pd.DataFrame(rows); stats['고령화율']=stats['65세이상']/stats['총인구']*100
g=gpd.read_file(ROOT/'N3A_G0110000.shp'); g['code']=g.BJCD.astype(str).str[:2].astype(int)
names={11:'서울특별시',26:'부산광역시',27:'대구광역시',28:'인천광역시',29:'광주광역시',30:'대전광역시',31:'울산광역시',36:'세종특별자치시',41:'경기도',51:'강원특별자치도',43:'충청북도',44:'충청남도',52:'전북특별자치도',46:'전라남도',47:'경상북도',48:'경상남도',50:'제주특별자치도'}
g['시도']=g.code.map(names); assert g.시도.notna().all()
m=g.dissolve('시도',as_index=False).merge(stats,on='시도',validate='one_to_one'); assert len(m)==17
m.drop(columns='geometry').to_csv(OUT/'province_age_population.csv',index=False,encoding='utf-8-sig')
fig,axes=plt.subplots(1,2,figsize=(16,9),facecolor='#f8fafc')
for ax,column,cmap,label,fmt in [(axes[0],'고령화율','YlOrRd','65세 이상 인구 비율 (%)','{:.1f}%'),(axes[1],'총인구','Blues','총인구 (명)','{:,.0f}명')]:
    m.plot(column=column,ax=ax,cmap=cmap,edgecolor='white',linewidth=.7,legend=True,legend_kwds={'label':label,'shrink':.65}); ax.set_axis_off(); ax.set_title('고령화율' if column=='고령화율' else '총인구',fontsize=16,weight='bold',color='#172b4d')
    for _,r in m.iterrows():
        p=r.geometry.representative_point(); ax.text(p.x,p.y,f"{r['시도']}\n{fmt.format(r[column])}",ha='center',va='center',fontsize=7)
fig.text(.06,.95,'2025년 시도별 인구 구조 비교',fontsize=22,weight='bold',color='#172b4d'); fig.text(.06,.91,'왼쪽: 고령화율 · 오른쪽: 총인구 규모',fontsize=11,color='#475569'); fig.text(.06,.035,'자료: 연령 및 성별 인구(2025년) · 경계: N3A_G0110000.shp\n현재 인구 파일은 시도 집계이므로 읍면동별 차이는 표시하지 않습니다.',fontsize=9,color='#475569'); fig.subplots_adjust(top=.85,bottom=.1,left=.03,right=.97,wspace=.08); fig.savefig(OUT/'province_age_map.png',dpi=180); plt.close(fig)
(OUT/'README.md').write_text(f'''# 2025년 시도별 인구·고령화율 지도\n\n![지도](province_age_map.png)\n\n`{popfile.name}`의 `데이터` 시트에서 17개 시도의 총인구와 65세 이상 인구를 사용했습니다. 고령화율은 65세 이상 인구를 총인구로 나눈 값입니다. 읍면동 경계 도형을 시도 코드로 묶어 시도별 경계를 만들었습니다.\n\n현재 파일은 실제 읍면동별 행이 아니라 시도 집계 자료이므로 지도도 시도 수준입니다.\n''',encoding='utf-8')
