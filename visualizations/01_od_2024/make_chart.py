r"""2024년 주수단 OD 전체 집계. 실행: .venv\Scripts\python.exe visualizations/01_od_2024/make_chart.py"""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import openpyxl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
source = next(ROOT.glob('2025-OD-PSN-MOD-10*/**/4. OD/*.xlsx'))
document = next(ROOT.glob('2025-OD-PSN-MOD-10*/**/*.hwpx'))
sheet = '2024_주수단OD'
modes = ['승용차', '버스', '도시철도', '일반철도', '고속철도', '항공', '해운']
keys = ['출발시도', '도착시도', '출발시군구', '도착시군구']
df = pd.read_excel(source, sheet_name=sheet, usecols='A:L', engine='openpyxl')
assert list(df.columns) == keys + modes + ['합계']
assert len(df) == 252 * 252
assert not df.isna().any().any(), '결측값 발견: 임의로 0으로 대체하지 않음'
for col in df.columns:
    df[col] = pd.to_numeric(df[col], errors='raise')
assert np.isfinite(df.to_numpy()).all()
assert (df[modes + ['합계']] >= 0).all().all()
assert (df[keys] % 1 == 0).all().all()
assert not df.duplicated(['출발시군구', '도착시군구']).any()
assert df['출발시군구'].nunique() == df['도착시군구'].nunique() == 252
assert df.groupby('출발시군구')['출발시도'].nunique().max() == 1
assert df.groupby('도착시군구')['도착시도'].nunique().max() == 1
row_error = float((df[modes].sum(axis=1) - df['합계']).abs().max())
assert row_error < 1e-6
totals = df[modes].sum()
wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
ref_rows = list(wb['대존_2024'].values)
reference = pd.Series([ref_rows[r-1][19] for r in [22,45,68,91,114,137,160]], index=modes)
assert np.allclose(totals, reference, rtol=0, atol=1e-5)
wb.close()
same = df['출발시군구'].eq(df['도착시군구'])
summary = pd.DataFrame({'교통수단': modes, '통행량_통행_일': totals.values,
                        '비율_pct': totals.values / totals.sum() * 100,
                        '동일존_통행_일': df.loc[same, modes].sum().values,
                        '다른존_통행_일': df.loc[~same, modes].sum().values})
summary = summary.sort_values('통행량_통행_일', ascending=False)
summary.to_csv(OUT / 'mode_summary.csv', index=False, encoding='utf-8-sig')
df.to_csv(OUT / 'od_2024_clean.csv', index=False, encoding='utf-8-sig')
audit = {'source': source.relative_to(ROOT).as_posix(), 'sheet': sheet,
         'documentation': document.relative_to(ROOT).as_posix(),
         'rows': len(df), 'origin_zones': 252, 'destination_zones': 252,
         'missing_cells': 0, 'duplicate_od_pairs': 0, 'negative_values': 0,
         'same_zone_rows': int(same.sum()), 'same_zone_trips': float(df.loc[same, modes].sum().sum()),
         'different_zone_trips': float(df.loc[~same, modes].sum().sum()),
         'total_trips': float(totals.sum()), 'max_row_total_error': row_error,
         'max_reference_error': float((totals-reference).abs().max())}
(OUT / 'validation.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
plt.rcParams.update({'font.family': 'Malgun Gothic', 'axes.unicode_minus': False, 'font.size': 11})
fig, ax = plt.subplots(figsize=(12, 6.8), facecolor='#f8fafc')
ax.set_facecolor('#f8fafc')
values = summary['통행량_통행_일'] / 10000
bars = ax.barh(summary['교통수단'], values, color=['#2563eb'] + ['#7799ba']*6, height=.62)
ax.invert_yaxis()
ax.set_xlim(0, values.max()*1.43)
ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
ax.set_xlabel('평일 평균 통행량 (만 통행/일)', labelpad=12)
ax.set_axisbelow(True)
ax.grid(axis='x', color='#dce3eb', linewidth=.7)
for spine in ax.spines.values():
    spine.set_visible(False)
ax.tick_params(axis='both', length=0)
for bar, (_, row) in zip(bars, summary.iterrows()):
    ax.text(bar.get_width()+values.max()*.016, bar.get_y()+bar.get_height()/2,
            f"{row['통행량_통행_일']:,.0f}  ({row['비율_pct']:.2f}%)", va='center', fontsize=10)
fig.text(.09,.94,'2024년, 어떤 교통수단으로 이동했을까?',fontsize=21,weight='bold',color='#172b4d')
fig.text(.09,.885,f'전국 252존 · 동일 존 내부 통행 포함 · 총 {totals.sum():,.0f} 통행/일',fontsize=12,color='#475569')
fig.text(.09,.045,'자료: 전국_2024년~2055년 주수단별OD(252).xlsx / 2024_주수단OD\n7개 주수단 합계 기준 비율. 이용자 수·차량 대수가 아닌 통행 횟수이며, 표시값만 반올림했습니다.',fontsize=9,color='#475569')
fig.subplots_adjust(left=.10,right=.97,top=.82,bottom=.17)
fig.savefig(OUT/'mode_totals.png',dpi=180)
fig.savefig(OUT/'mode_totals.svg')
plt.close(fig)
table = '\n'.join(f"| {r['교통수단']} | {r['통행량_통행_일']:,.0f} | {r['비율_pct']:.2f}% |" for _, r in summary.iterrows())
report = f'''# 첫 번째 시각화: 2024년 교통수단별 통행량

![교통수단별 통행량](mode_totals.png)

## 1. 사용한 데이터
- 원본: `{source.relative_to(ROOT).as_posix()}`
- 시트: `{sheet}`. 2030~2055년 장래연도 시트는 사용하지 않았습니다.
- 설명자료: `{document.relative_to(ROOT).as_posix()}`
- 설명자료 제1절의 용어 정의와 제2절의 전국 지역간 주수단통행량 표를 확인했습니다. 단위는 엑셀 `대존_2024`에도 통행/일로 표기되어 있습니다.
- 전국 252존(시·군·구 기준의 분석 지역), 252 × 252 = {len(df):,}개 출발지·도착지 조합입니다. 지역 코드는 이름으로 변환하지 않았으며 지역별 지도나 비교는 이번 단계에 포함하지 않습니다.
- 평일(주말·공휴일 제외) 평균 일 통행량입니다. 사람 수나 차량 대수가 아니므로 같은 사람이 여러 번 이동하면 여러 통행입니다.
- 주수단은 전체 이동에서 대표하는 교통수단입니다. 예를 들어 승용차로 역에 접근한 뒤 철도를 이용하는 이동에서 접근 승용차 통행을 별도로 더하지 않습니다.

## 2. 전처리와 집계
1. `extracted` 사본은 읽지 않고 위 원본 파일 하나만 사용했습니다. 원본은 수정하지 않았습니다.
2. 첫 행을 열 이름으로 읽고 A:L의 12개 열만 선택했습니다. 이후 열은 이번 분석에 사용하지 않았습니다.
3. 출발·도착 시도/시군구 코드 4개, 수단별 통행량 7개, 검산용 합계 1개로 구분했습니다.
4. 숫자 형식, 결측값, 음수, 무한대, 중복 OD, 252 × 252 조합을 검사했습니다. 결측값·중복·음수는 모두 0건이며 삭제하거나 임의로 채운 값은 없습니다. 0 통행도 유지했습니다.
5. 동일 존 내부 통행 {int(same.sum()):,}개 행도 포함했습니다. 내부 통행 합계는 {audit['same_zone_trips']:,.0f}, 다른 존 간 통행 합계는 {audit['different_zone_trips']:,.0f} 통행/일입니다. 따라서 그래프는 '서로 다른 지역 사이의 이동만'을 뜻하지 않습니다.
6. A→B와 B→A는 서로 다른 방향의 통행이므로 모두 합산했습니다. 왕복이라는 이유로 2로 나누지 않았습니다.
7. 수단별 열을 각각 합산했습니다. `합계` 열을 여덟 번째 수단으로 더하지 않았습니다. 비율은 해당 수단 합계 ÷ 7개 수단 전체 합계 × 100입니다.
8. 집계 전에는 소수점을 보존하고, 그래프와 표의 표시값만 정수로 반올림했습니다. 작은 수단도 정확한 값과 비율을 읽도록 막대 끝에 수치를 표시했습니다. 가로축은 0부터 시작하는 선형축입니다.

## 3. 결과와 해석
| 교통수단 | 통행/일 (반올림) | 7개 수단 중 비율 |
|---|---:|---:|
{table}

전체 합계는 **{totals.sum():,.0f} 통행/일**입니다. 승용차 비율이 가장 높고 버스, 도시철도가 뒤를 잇습니다. 이 결과는 내부 통행을 포함한 해당 데이터의 7개 수단 구성비이며, 장거리 이동만의 구성비나 도보·자전거 등을 모두 포함하는 전체 이동의 분담률로 해석하면 안 됩니다. 수단별 규모 차이를 보여주며 그 원인을 설명하는 분석은 아닙니다.

## 4. 검증 및 재실행
- 각 행의 7개 수단 합계와 원본 합계 열의 최대 차이: {row_error:.10g} 통행/일.
- 원본 `대존_2024`의 수단별 총합계와 재집계값의 최대 차이: {audit['max_reference_error']:.10g} 통행/일. 부동소수점 오차 범위에서 일치합니다.
- 상세 검사: `validation.json`; 가공 데이터: `od_2024_clean.csv`; 수단별 집계: `mode_summary.csv`.
- 사용 라이브러리: pandas {pd.__version__}, openpyxl {openpyxl.__version__}, matplotlib {matplotlib.__version__}, numpy {np.__version__}.
- 작업 폴더에서 실행: `.venv\\Scripts\\python.exe visualizations/01_od_2024/make_chart.py`

다음 단계에서는 동일 존 내부 통행을 제외한 뒤 이 그래프와 비교할 수 있습니다.
'''
(OUT/'README.md').write_text(report,encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(summary.to_string(index=False))
print(json.dumps(audit, ensure_ascii=False, indent=2))
