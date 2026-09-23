"""2023년 기준 배포 OD의 장래 전망을 집계한다. 별도 예측모형은 학습하지 않는다."""
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
source = next(ROOT.glob('2024-OD-PSN-MOD-10*/5. OD/*.xlsx'))
years = [2023, 2025, 2030, 2035, 2040, 2045, 2050]
modes = ['승용차', '버스', '지하철', '일반철도', '고속철도', '항공', '해운']
keys = ['출발시도', '도착시도', '출발시군구', '도착시군구']
records, audit = [], []
wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
baseline_keys = None
for year in years:
    sheet = f'{year}_주수단OD'
    rows = wb[sheet].iter_rows(max_col=12, values_only=True)
    header = list(next(rows))
    assert header == keys + modes + ['합계']
    df = pd.DataFrame(rows, columns=header)
    assert len(df) == 250 * 250
    assert not df.isna().any().any()
    df = df.apply(pd.to_numeric, errors='raise')
    assert np.isfinite(df.to_numpy()).all()
    assert (df[modes + ['합계']] >= 0).all().all()
    assert (df[keys] % 1 == 0).all().all()
    assert not df.duplicated(['출발시군구', '도착시군구']).any()
    assert df['출발시군구'].nunique() == df['도착시군구'].nunique() == 250
    ordered_keys = df[keys].sort_values(keys).reset_index(drop=True)
    if baseline_keys is None:
        baseline_keys = ordered_keys
    else:
        assert ordered_keys.equals(baseline_keys), '기준연도와 OD 코드 조합이 다름'
    row_error = float((df[modes].sum(axis=1) - df['합계']).abs().max())
    assert row_error < 1e-6
    totals = df[modes].sum()
    reference_rows = list(wb[f'대존_{year}'].values)
    reference = np.array([reference_rows[r-1][19] for r in [22,45,68,91,114,137,160]])
    ref_error = float(np.max(np.abs(totals.values - reference)))
    assert ref_error < 1e-5
    assert abs(totals.sum() - reference_rows[182][19]) < 1e-5
    same = df['출발시군구'].eq(df['도착시군구'])
    for mode in modes:
        records.append({'연도': year, '구분': '기준연도' if year == 2023 else '장래예측',
                        '교통수단': mode, '통행량_통행_일': totals[mode],
                        '구성비_pct': totals[mode]/totals.sum()*100,
                        '동일존_통행_일': df.loc[same, mode].sum(),
                        '다른존_통행_일': df.loc[~same, mode].sum()})
    audit.append({'year': year, 'sheet': sheet, 'rows': len(df), 'missing': 0,
                  'duplicate_pairs': 0, 'negative': 0, 'same_zone_rows': int(same.sum()),
                  'max_row_error': row_error, 'max_summary_error': ref_error})
    print(f'{year}: verified {len(df)} rows', flush=True)
wb.close()
long = pd.DataFrame(records)
wide = long.pivot(index='연도', columns='교통수단', values='통행량_통행_일')[modes]
wide['전체'] = wide.sum(axis=1)
change = (wide.loc[2050] / wide.loc[2023] - 1) * 100
long.to_csv(OUT/'forecast_by_mode.csv', index=False, encoding='utf-8-sig')
wide.to_csv(OUT/'forecast_totals.csv', encoding='utf-8-sig')
(OUT/'validation.json').write_text(json.dumps({'source': source.relative_to(ROOT).as_posix(), 'checks': audit}, ensure_ascii=False, indent=2), encoding='utf-8')
plt.rcParams.update({'font.family': 'Malgun Gothic', 'axes.unicode_minus': False, 'font.size': 10})
fig, axes = plt.subplots(2, 4, figsize=(16, 8.5), facecolor='#f8fafc')
for ax, mode in zip(axes.flat, ['전체'] + modes):
    values = wide[mode] / 10000
    ax.set_facecolor('#f8fafc')
    ax.axvspan(2025, 2050, color='#eaf0fa')
    ax.plot(years, values, '--o', color='#2563eb', linewidth=2, markersize=4)
    ax.scatter([2023], [values.loc[2023]], color='#172b4d', s=48, zorder=5)
    ax.set_title(f'{mode}  |  2050년 {change[mode]:+.1f}%', loc='left', fontsize=12, fontweight='bold')
    ax.set_ylim(0, values.max()*1.27)
    ax.set_xlim(2022, 2052)
    ax.set_xticks([2023, 2030, 2040, 2050])
    ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,.1f}'))
    ax.set_ylabel('만 통행/일')
    ax.grid(axis='y', alpha=.25)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for year in [2023, 2050]:
        ax.annotate(f'{values.loc[year]:,.1f}', (year,values.loc[year]), xytext=(0,9),textcoords='offset points',ha='center',fontsize=9)
fig.suptitle('2023년 기준 자료로 본 2050년까지의 통행량 전망', x=.06,y=.97,ha='left',fontsize=23,fontweight='bold',color='#172b4d')
fig.text(.06,.905,'● 2023 기준연도   ·   점선과 파란 배경: 원본의 장래 예측   ·   패널 제목의 증감률: 2023년 대비 2050년',color='#475569',fontsize=11)
fig.text(.06,.055,'전국 250존 · 동일 존 내부 통행 포함 · 평일 평균 · 패널마다 세로축 범위가 다릅니다.\n2025년도 이 자료에서는 예측치입니다. 점 사이의 선은 추세를 연결한 것이며, 중간 연도의 예측값을 생성하지 않았습니다.',color='#475569',fontsize=10)
fig.subplots_adjust(left=.06,right=.97,top=.83,bottom=.16,hspace=.38,wspace=.33)
fig.savefig(OUT/'forecast_trends.png',dpi=180)
fig.savefig(OUT/'forecast_trends.svg')
plt.close(fig)
total_table = '\n'.join(f'| {year} | {"기준연도" if year == 2023 else "장래 예측"} | {wide.loc[year,"전체"]:,.0f} |' for year in years)
mode_table = '\n'.join(f'| {mode} | {wide.loc[2023,mode]:,.0f} | {wide.loc[2050,mode]:,.0f} | {change[mode]:+.2f}% |' for mode in modes)
peak = int(wide['전체'].idxmax())
report = f'''# 2023년 기준 OD의 장래 통행량 전망

![예측 추이](forecast_trends.png)

## 사용한 데이터와 예측의 의미
- 원본: `{source.relative_to(ROOT).as_posix()}`
- 시트: {', '.join(f'`{y}_주수단OD`' for y in years)}.
- 2023년 분석과 동일한 배포본의 250존 자료입니다. 2024년 기준 252존 배포본은 섞지 않았습니다.
- 새로 예측모형을 만든 것이 아니라 **배포 파일에 포함된 장래 예측값을 시각화**했습니다. 2023년은 기준연도 OD이며, 단순 원시 관측치로 부르지 않습니다.
- 2025년은 현재 시점에 과거가 되었더라도 이 배포본에서는 예측치입니다. 이후 실측값으로 대체하지 않았습니다.
- 단위: 평일 평균 통행/일. 같은 존 내부 이동도 포함합니다. 이용자 수나 차량 대수가 아닙니다.

## 전처리와 검증
1. 각 시트 첫 행을 열 이름으로 사용하고 A:L의 지역 코드 4개, 수단 7개, 합계 1개를 선택했습니다.
2. 연도마다 250 × 250 = 62,500행을 확인했습니다. 7개 연도 총 437,500행입니다.
3. 숫자 형식, 유한값, 정수 지역 코드, 결측값, 음수, 중복 출발·도착 조합을 검사했습니다. 결측값·음수·중복은 모든 연도에서 0건으로 삭제나 대체는 하지 않았습니다.
4. 연도별 OD 코드 조합이 2023년과 동일한지 검사했습니다. 동일 존 250개 행도 유지하고, 양방향 통행은 각각 합산했습니다.
5. 7개 수단을 각각 합산했습니다. 합계 열을 다시 더하지 않았습니다. 비율은 각 연도의 7개 수단 총합을 분모로 계산했습니다.
6. 행별 수단 합계와 합계 열의 차이는 최대 {max(a['max_row_error'] for a in audit):.10g} 통행/일입니다. 수단별 집계와 `대존_연도` 요약표의 차이는 최대 {max(a['max_summary_error'] for a in audit):.10g} 통행/일로 부동소수점 오차 범위에서 일치합니다.
7. 계산은 소수점을 유지하고 표시할 때 반올림했습니다. 보간·외삽·신규 모델 학습은 하지 않았습니다. 점선은 제공된 연도 값만 연결합니다.

## 전체 통행량
| 연도 | 구분 | 통행/일 |
|---|---|---:|
{total_table}

제공된 연도 중 전체 통행량은 {peak}년에 가장 높고, 2050년은 2023년 대비 {change['전체']:+.2f}%입니다. 제공되지 않은 연도를 포함한 정확한 정점 연도라고 단정할 수 없습니다.

## 수단별 변화
| 수단 | 2023년 통행/일 | 2050년 통행/일 | 증감률 |
|---|---:|---:|---:|
{mode_table}

각 패널은 수단별 변화를 읽기 위해 서로 다른 세로축 범위를 사용하며, 모두 0에서 시작합니다. 패널 간 선의 높이로 절대량을 비교하지 마세요. 증감률은 (2050년 값 / 2023년 값 − 1) × 100입니다.

이 결과는 해당 배포본의 전망이며 미래에 확정적으로 발생할 수치는 아닙니다. 감소나 증가의 원인을 이 집계만으로 추론하지 않았습니다. 원본에 예측구간이 제공되지 않아 신뢰구간도 표시하지 않았습니다.

## 결과 파일과 재실행
- `forecast_by_mode.csv`: 연도·수단별 통행량, 구성비, 내부/외부 통행량.
- `forecast_totals.csv`: 연도별 수단 합계와 전체 합계.
- `validation.json`: 사용한 원본 경로와 연도별 검증 결과.
- 실행: `.venv/Scripts/python.exe visualizations/03_od_forecast_2023/make_chart.py`
'''
(OUT/'README.md').write_text(report,encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(wide.round(2).to_string())
print('2050 vs 2023 (%)',change.round(2).to_dict())
