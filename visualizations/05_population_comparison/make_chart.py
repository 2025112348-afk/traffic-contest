"""배포본별 기준연도 인구를 시도 수준으로 맞춰 비교한다."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
YEARS = [2019, 2022, 2023, 2024]
aliases = {'강원도':'강원특별자치도','전라북도':'전북특별자치도'}
frames, audits = [], []
for year, release in zip(YEARS,[2020,2023,2024,2025]):
    source = next(ROOT.glob(f'{release}-OD-PSN-MOD-10*/**/3. 사회경제지표/*.xlsx'))
    raw = pd.read_excel(source,sheet_name='총인구')
    if year == 2019:
        names = raw['시군구'].str.split('_',n=1,expand=True)
        df = pd.DataFrame({'원본시도':names[0],'시군구':names[1],'존코드':raw['중존번호'],'인구_명':raw[f'{year}년']})
    else:
        code = {2022:'지역간존체계(250)',2023:'시군구 존체계',2024:'시군구 코드'}[year]
        df = raw[['시도코드','시군구',code,f'{year}년']].copy()
        df.columns = ['원본시도','시군구','존코드','인구_명']
    assert not df.isna().any().any()
    for col in ['원본시도','시군구']:
        df[col] = df[col].str.strip()
        assert df[col].ne('').all()
    for col in ['존코드','인구_명']:
        df[col] = pd.to_numeric(df[col],errors='raise')
        assert np.isfinite(df[col]).all()
    assert (df['인구_명'] >= 0).all()
    assert not df['존코드'].duplicated().any()
    assert not df.duplicated(['원본시도','시군구']).any()
    zone_source = next(p for p in ROOT.glob(f'{release}-OD-PSN-MOD-10*/**/1. 존체계/*.xlsx') if not p.name.startswith('~'))
    if year == 2024:
        zones = pd.read_excel(zone_source,sheet_name='전국지역간',header=1)[['대존','소존','252존체계']]
    else:
        zones = pd.read_excel(zone_source).iloc[:,:3]
    zone_codes = pd.to_numeric(zones.iloc[:,2],errors='raise')
    assert zone_codes.nunique() == len(zones)
    assert set(df['존코드']).issubset(set(zone_codes))
    missing = zones.loc[~zone_codes.isin(df['존코드'])].iloc[:,:3]
    assert missing.empty or missing.iloc[:,1].astype(str).str.contains('울릉').all()
    excluded = df.loc[df['시군구'].eq('울릉군')].copy()
    df = df.loc[~df['시군구'].eq('울릉군')].copy()
    df['시도'] = df['원본시도'].replace(aliases)
    gunwi = df['시군구'].eq('군위군')
    assert gunwi.sum() == 1
    transferred = float(df.loc[gunwi & df['시도'].ne('대구광역시'),'인구_명'].sum())
    df.loc[gunwi,'시도'] = '대구광역시'
    df['연도'] = year
    # 부천의 시→구 분할은 시도 합산으로 흡수. 시군구 목록의 연도 간 범위도 검증.
    df['범위검증용지역'] = df['시군구'].str.replace(' ','',regex=False)
    df.loc[df['시군구'].str.startswith('부천시'),'범위검증용지역'] = '부천시'
    df.loc[df['시도'].eq('인천광역시') & df['시군구'].eq('남구'),'범위검증용지역'] = '미추홀구'
    df.loc[df['시도'].eq('세종특별자치시'),'범위검증용지역'] = '세종시'
    frames.append(df)
    audits.append({'year':year,'source':source.relative_to(ROOT).as_posix(),
                   'zone_source':zone_source.relative_to(ROOT).as_posix(),
                   'raw_rows':len(raw),'included_rows':len(df),'expected_zones':len(zones),
                   'missing_zone_rows':missing.to_dict(orient='records'),
                   'excluded_ulleung_rows':excluded.to_dict(orient='records'),
                   'gunwi_transferred_to_daegu':transferred,
                   'missing_cells':0,'duplicates':0,'negative_values':0})
base_regions = set(zip(frames[0]['시도'],frames[0]['범위검증용지역']))
for df in frames[1:]:
    assert set(zip(df['시도'],df['범위검증용지역'])) == base_regions, '지역 범위 차이 발견'
clean = pd.concat(frames,ignore_index=True)
summary = clean.groupby(['연도','시도'],as_index=False)['인구_명'].sum()
wide = summary.pivot(index='시도',columns='연도',values='인구_명')
assert wide.shape == (17,4) and not wide.isna().any().any()
for year in YEARS:
    assert np.isclose(wide[year].sum(),clean.loc[clean['연도'].eq(year),'인구_명'].sum(),rtol=0,atol=1e-6)
wide['증감_명'] = wide[2024]-wide[2019]
wide['증감률_pct'] = (wide[2024]/wide[2019]-1)*100
wide = wide.sort_values(2024,ascending=False)
clean.to_csv(OUT/'population_comparable_regions.csv',index=False,encoding='utf-8-sig')
wide.to_csv(OUT/'population_comparison.csv',encoding='utf-8-sig')
(OUT/'validation.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2),encoding='utf-8')
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
fig,axes = plt.subplots(2,1,figsize=(13,12),gridspec_kw={'height_ratios':[1,1.3]},facecolor='#f8fafc')
ax = axes[0]
colors = ['#94a3b8','#86b5d7','#467fc2','#163f88']
y = np.arange(17)
for j,year in enumerate(YEARS):
    ax.barh(y+(j-1.5)*.19,wide[year]/10000,height=.18,label=str(year),color=colors[j])
ax.set_yticks(y,wide.index)
ax.invert_yaxis()
ax.set_xlabel('인구 (만 명)')
ax.set_title('시·도별 인구 규모 — 2024년 인구순',loc='left',fontweight='bold')
ax.legend(ncol=4,loc='lower right',frameon=False)
ax = axes[1]
change = wide.sort_values('증감률_pct',ascending=False)
bars = ax.barh(change.index,change['증감률_pct'],color=['#2563eb' if v>=0 else '#bd6556' for v in change['증감률_pct']],height=.64)
ax.invert_yaxis()
ax.axvline(0,color='#64748b',linewidth=1)
ax.set_xlim(min(-12,change['증감률_pct'].min()-4),change['증감률_pct'].max()+5)
ax.set_xlabel('2019년 대비 2024년 변화 (%)')
ax.set_title('2019년 대비 변화 — 같은 비교 범위로 집계',loc='left',fontweight='bold')
for bar,v in zip(bars,change['증감률_pct']):
    ax.text(v+(.35 if v>=0 else -.35),bar.get_y()+bar.get_height()/2,f'{v:+.2f}%',ha='left' if v>=0 else 'right',va='center')
for ax in axes:
    ax.set_facecolor('#f8fafc')
    ax.set_axisbelow(True)
    ax.grid(axis='x',alpha=.2)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
fig.text(.08,.962,'지역별 인구, 2019년에서 2024년까지',fontsize=23,weight='bold',color='#172b4d')
fig.text(.08,.932,'2019·2022·2023·2024년 각 배포본의 기준연도 인구 비교',fontsize=12,color='#475569')
fig.text(.08,.035,'전 연도 울릉군 제외 · 군위군은 전 연도 대구로 통일 · 강원·전북 명칭 통일\n서로 다른 교통수요 분석용 배포본 비교입니다. 차이에는 인구 변화 외에 자료 구축·보정 차이가 포함될 수 있습니다.',fontsize=10,color='#475569')
fig.subplots_adjust(left=.18,right=.96,top=.88,bottom=.105,hspace=.30)
fig.savefig(OUT/'population_comparison.png',dpi=180)
fig.savefig(OUT/'population_comparison.svg')
plt.close(fig)
table = '\n'.join('| '+str(region)+' | '+' | '.join(f'{r[y]:,.0f}' for y in YEARS)+f" | {r['증감률_pct']:+.2f}% |" for region,r in wide.iterrows())
sources = '\n'.join(f"- {a['year']}년: `{a['source']}` / `총인구` / `{a['year']}년` 열" for a in audits)
checks = '\n'.join(f"- {a['year']}년: 원본 {a['raw_rows']}행 → 비교 {a['included_rows']}행. 군위군 대구 재분류 {a['gunwi_transferred_to_daegu']:,.2f}명." for a in audits)
report = f'''# 2019·2022·2023·2024년 시도별 인구 비교

![비교 그래프](population_comparison.png)

## 사용한 데이터
{sources}

각 배포본의 기준연도 자료만 사용했습니다. 장래 예측 열은 사용하지 않았습니다. 2020·2021년은 이 비교에 자료가 없어 보간하거나 채우지 않았습니다. 인구 값에 소수점이 있는 교통수요 분석용 사회경제지표입니다. 주민등록인구 원자료와 같은 시계열이라고 가정하지 않았습니다.

## 지역 범위와 전처리
1. 2019년 `시군구`의 `시도_시군구` 문자열을 분리했습니다. 다른 연도는 시도·시군구 열을 사용했습니다. 존코드는 연도별로 달라지므로 연도 간 동일 지역의 고정 식별자로 사용하지 않았습니다.
2. 숫자 형식, 결측 셀, 중복 지역·존코드, 음수 인구를 확인했습니다. 모두 이상이 없었습니다. 별도 존체계 파일과 대조해 누락 행도 확인했습니다.
3. 울릉군은 2019·2023·2024년에 행이 없고 2022년에는 0명입니다. 이를 실제 인구 0명으로 해석하지 않고 **모든 연도에서 제외**했습니다. 따라서 경북 및 전체 합계는 울릉군 제외 값입니다.
4. 군위군은 2019·2022년 경북에서 2023·2024년 대구로 소속이 달라졌습니다. 경계 변화의 영향을 줄이기 위해 **과거 두 연도도 군위군을 대구에 포함**했습니다. 원본 시도와 변경된 시도를 CSV에 함께 보존했습니다.
5. 강원도→강원특별자치도, 전라북도→전북특별자치도로 명칭을 통일했습니다.
6. 부천시는 2024년에 3개 구로 나뉩니다. 시도별 합산에서 모두 경기도로 묶었습니다. 시군구 범위 대조 때만 이 3개 구를 부천시로 묶고 공백을 제거했습니다. 인천 남구/미추홀구, 세종시/세종특별자치시 명칭도 대조용으로 통일해 네 연도의 지역명 집합이 같은지 검사했습니다. 미세한 행정경계 변화까지 일치한다는 의미는 아닙니다.
7. 시도별로 합산하고 전체 합계 보존을 검증했습니다. 소수점은 유지하고 표시값만 반올림했습니다. 증감률은 `(2024년/2019년−1)×100`입니다.

{checks}

## 비교 결과
| 시도 | 2019년(명) | 2022년(명) | 2023년(명) | 2024년(명) | 2019→2024 |
|---|---:|---:|---:|---:|---:|
{table}

## 해석 시 고려할 점
- 위 그래프는 인구 규모, 아래 그래프는 변화율을 보여줍니다. 두 그래프의 지역 정렬 기준이 다릅니다.
- 서로 다른 시기에 구축된 배포본 간 차이로, 실제 인구 변화뿐 아니라 추계·보정·구축 방식의 차이가 섞일 수 있습니다. 원인을 이 집계만으로 단정하지 않습니다.
- 부천의 수록 인구는 2023년 795,281명에서 2024년 3개 구 합계 660,329명으로 달라집니다. 구 분할을 합산해도 차이가 크므로 이를 실제 인구 감소라고 단정할 수 없습니다. 경기도 변화 해석에도 이 점이 적용됩니다.
- 이전 2023년 단독 그래프의 강원·전북 명칭은 이번 비교에서 통일했습니다. 과거 군위군 소속을 조정했으므로 과거 원본의 시도 합계와는 차이가 있습니다.

## 결과와 재실행
- `population_comparison.csv`: 17개 시도 × 4개 연도 및 변화율.
- `population_comparable_regions.csv`: 원본 시도, 비교 시도, 지역별 수치와 연도.
- `validation.json`: 출처·누락·범위 조정 기록.
- 실행: `.venv/Scripts/python.exe visualizations/05_population_comparison/make_chart.py`
'''
(OUT/'README.md').write_text(report,encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(wide.round(2).to_string())
