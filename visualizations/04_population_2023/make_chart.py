"""2023년 사회경제지표의 총인구를 시도별로 비교한다."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
source = next(ROOT.glob('2024-OD-PSN-MOD-10*/3. 사회경제지표/*.xlsx'))
zone_source = next(ROOT.glob('2024-OD-PSN-MOD-10*/1. 존체계/*.xlsx'))
df = pd.read_excel(source, sheet_name='총인구', usecols='A:D').rename(
    columns={'시도코드': '시도', '시군구 존체계': '존코드', '2023년': '인구_명'})
assert list(df.columns) == ['시도', '시군구', '존코드', '인구_명']
assert not df.isna().any().any()
for col in ['시도', '시군구']:
    df[col] = df[col].str.strip()
    assert df[col].ne('').all()
for col in ['존코드', '인구_명']:
    df[col] = pd.to_numeric(df[col], errors='raise')
    assert np.isfinite(df[col]).all()
assert (df['인구_명'] >= 0).all()
assert (df['존코드'] % 1 == 0).all()
assert not df['존코드'].duplicated().any()
assert not df.duplicated(['시도', '시군구']).any()
zones = pd.read_excel(zone_source).rename(columns={'대존':'시도','소존':'시군구','250존체계':'존코드'})
zones['시도'] = zones['시도'].str.strip().replace({'강원특별자치도': '강원도'})
assert len(zones) == 250 and zones['존코드'].nunique() == 250
assert set(df['존코드']).issubset(set(zones['존코드']))
matched = df.merge(zones[['존코드','시도','시군구']],on='존코드',validate='one_to_one',suffixes=('','_존체계'))
assert matched['시도'].eq(matched['시도_존체계']).all()
missing = zones.loc[~zones['존코드'].isin(df['존코드']), ['시도','시군구','존코드']]
summary = df.groupby('시도',as_index=False).agg(인구_명=('인구_명','sum'),수록지역수=('존코드','size'))
expected = zones.groupby('시도').size()
summary['예상지역수'] = summary['시도'].map(expected)
summary['누락지역수'] = summary['예상지역수'] - summary['수록지역수']
summary['수록인구중비율_pct'] = summary['인구_명']/df['인구_명'].sum()*100
summary = summary.sort_values('인구_명',ascending=False)
assert len(summary) == 17
assert np.isclose(summary['인구_명'].sum(),df['인구_명'].sum(),rtol=0,atol=1e-6)
df.to_csv(OUT/'population_2023_clean.csv',index=False,encoding='utf-8-sig')
summary.to_csv(OUT/'population_by_province.csv',index=False,encoding='utf-8-sig')
missing.to_csv(OUT/'missing_regions.csv',index=False,encoding='utf-8-sig')
audit = {'source':source.relative_to(ROOT).as_posix(),'sheet':'총인구','year_column':'2023년',
         'zone_source':zone_source.relative_to(ROOT).as_posix(),'rows':len(df),'expected_zones':len(zones),
         'missing_cells_in_existing_rows':0,'duplicate_zone_codes':0,'negative_population':0,
         'fractional_population_rows':int((df['인구_명']%1 != 0).sum()),
         'missing_regions':missing.to_dict(orient='records'),'included_total':float(df['인구_명'].sum())}
(OUT/'validation.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':11})
fig,ax = plt.subplots(figsize=(12,9.5),facecolor='#f8fafc')
ax.set_facecolor('#f8fafc')
labels = [r['시도'] + (' *' if r['누락지역수'] else '') for _,r in summary.iterrows()]
values = summary['인구_명']/10000
bars = ax.barh(labels, values, color=['#2563eb' if i<3 else '#809bb6' for i in range(17)],height=.65)
ax.invert_yaxis()
ax.set_xlim(0,values.max()*1.28)
ax.set_xlabel('인구 (만 명)')
ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
ax.set_axisbelow(True)
ax.grid(axis='x',color='#dce3eb',linewidth=.7)
ax.tick_params(length=0)
for spine in ax.spines.values():
    spine.set_visible(False)
for bar,(_,r) in zip(bars,summary.iterrows()):
    ax.text(bar.get_width()+values.max()*.012,bar.get_y()+bar.get_height()/2,f"{r['인구_명']:,.0f}명",va='center',fontsize=10)
fig.text(.07,.95,'2023년, 지역별 인구는 얼마나 다를까?',fontsize=22,weight='bold',color='#172b4d')
fig.text(.07,.905,'사회경제지표의 총인구 · 249개 수록 지역을 17개 시·도로 집계',fontsize=12,color='#475569')
fig.text(.07,.055,'* 경상북도는 원본에 울릉군(존 225)이 없어 울릉군을 제외한 합계입니다.\n자료: 전국지역간_사회경제지표.xlsx / 총인구 / 2023년. 원본 지역명 유지, 표시값만 반올림.\n교통수요 분석용 배포 자료의 인구이며, 주민등록인구 통계와 동일하다고 확인된 값은 아닙니다.',fontsize=9,color='#475569')
fig.subplots_adjust(left=.18,right=.97,top=.85,bottom=.16)
fig.savefig(OUT/'population_by_province.png',dpi=180)
fig.savefig(OUT/'population_by_province.svg')
plt.close(fig)
table = '\n'.join(f"| {r['시도']} | {r['인구_명']:,.0f} | {r['수록지역수']} / {r['예상지역수']} |" for _,r in summary.iterrows())
report = f'''# 2023년 지역별 인구 비교

![시도별 인구](population_by_province.png)

## 사용 자료
- 원본: `{source.relative_to(ROOT).as_posix()}`
- 사용 시트: `총인구`; 사용 연도: `2023년`. 장래 인구와 다른 연령층 시트는 합산하지 않았습니다.
- 지역 누락 확인용: `{zone_source.relative_to(ROOT).as_posix()}`.
- 앞서 분석한 2023년 교통자료와 같은 배포 묶음의 사회경제지표입니다. 이번 그래프에는 OD 통행량을 사용하지 않았습니다.
- 원본 인구에 소수점이 포함되어 있습니다. 교통수요 분석용 배포 자료의 수치로 읽어야 하며, 주민등록인구 원자료와 동일하다고 확인된 값은 아닙니다. 소수점의 발생 원인이나 외국인 포함 여부는 이번 확인 범위에서 확정하지 않았습니다.

## 전처리
1. A:D의 시도, 시군구, 존코드, 2023년 인구만 읽었습니다. 원본 `시도코드` 열에는 숫자가 아닌 시도명이 들어 있어 `시도`로 이름을 바꿨습니다.
2. 지역명 앞뒤 공백을 정리하고 숫자 열을 확인했습니다. 강원도·전라북도 등 인구 원본의 지역명을 유지했습니다. 존체계의 `강원특별자치도`는 대조할 때 인구 시트의 `강원도`와 같은 이름으로 맞췄습니다.
3. 기존 {len(df)}행의 결측 셀, 음수 인구, 중복 존코드는 모두 0건입니다. 소수 인구가 있는 행은 {audit['fractional_population_rows']}개입니다.
4. 별도 250존 목록과 대조하니 **존 225, 경상북도 울릉군 행이 빠져 있습니다**. 이는 셀 결측과 다른 문제입니다. 임의로 0명 또는 추정 인구를 넣지 않았습니다. 기존 행의 존코드와 시도 대응도 확인했습니다.
5. 시군구를 나눈 단위가 지역마다 달라 첫 비교는 17개 시도로 통일했습니다. 같은 시도에 속한 수록 지역의 인구를 합산했습니다. 별도 총계 행을 중복 합산하지 않았습니다.
6. 인구가 많은 순서로 정렬했습니다. 소수점을 유지해 계산하고 그래프와 본문 표에서만 정수로 반올림했습니다. CSV에는 계산값을 보존했습니다.
7. 249개 지역 합계와 17개 시도 집계의 합계가 일치하는지 검증했습니다. 총합은 {df['인구_명'].sum():,.2f}명으로, **울릉군이 제외된 수록 인구 합계**입니다.

## 결과
| 시도 | 수록 인구 합계(명, 반올림) | 수록 / 예상 지역 수 |
|---|---:|---:|
{table}

경기도, 서울특별시, 부산광역시 순으로 수록 인구 규모가 큽니다. 인구의 절대 규모를 비교한 것으로 면적당 인구밀도나 증가율을 뜻하지 않습니다. 경상북도 값은 울릉군 미포함이며 정확한 전국 총인구로 인용하면 안 됩니다.

## 파일과 재실행
- `population_2023_clean.csv`: 수록된 249개 지역의 2023년 인구.
- `population_by_province.csv`: 17개 시도별 합계, 지역 수, 누락 수, 수록 인구 중 비율.
- `missing_regions.csv`: 원본 인구 시트에 없는 지역.
- `validation.json`: 검증 결과와 출처.
- 실행: `.venv/Scripts/python.exe visualizations/04_population_2023/make_chart.py`
'''
(OUT/'README.md').write_text(report,encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(summary.to_string(index=False))
print(json.dumps(audit,ensure_ascii=False,indent=2))
