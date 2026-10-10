"""입력 스냅샷으로 두 DRT 시나리오를 같은 척도에서 재현한다.

실행: python run_comparison.py
필수: pandas, numpy, matplotlib. 원본 폴더/네트워크/Colab에 의존하지 않는다.
"""
from pathlib import Path
import hashlib
import json
import platform
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = Path(__file__).resolve().parent
INPUT = BASE / 'inputs'
OUT = BASE / 'outputs'
FIG = BASE / 'figures'
VARS = ['지형장벽_취약점수', '자가용미보유_취약점수', '의료_취약점수',
        '버스정류장_취약점수', '배차간격_취약점수', '고령인구비율_취약점수']
DRT = 'DRT공급부족_취약점수'
EPS = 1e-6


def save(df, name):
    df.to_csv(OUT / name, index=False, encoding='utf-8-sig', float_format='%.15g')


def entropy(df, columns):
    """원본 노트북과 같은 dropna, epsilon 보정, 엔트로피 산식."""
    x = df[columns].dropna().copy()
    assert len(x) > 1
    assert np.isfinite(x.to_numpy()).all()
    assert (x.ge(-1e-12) & x.le(1 + 1e-12)).all().all()
    x = x * (1 - 2 * EPS) + EPS
    p = x / x.sum(axis=0)
    e = -(p * np.log(p)).sum(axis=0) / np.log(len(x))
    d = 1 - e
    assert d.sum() > 0
    return pd.DataFrame({'지표': columns, '엔트로피': e.values,
                         '정보효용': d.values, '가중치': (d / d.sum()).values})


def load_inputs():
    for record in json.loads((INPUT / 'manifest.json').read_text(encoding='utf-8')):
        assert hashlib.sha256((BASE / record['file']).read_bytes()).hexdigest() == record['sha256'], record['file']
    national = pd.read_csv(INPUT / 'national_baseline.csv')
    raw = pd.read_csv(INPUT / 'current_operation.csv')
    sim = pd.read_csv(INPUT / 'reallocation.csv')
    rules = json.loads((INPUT / 'route_mapping.json').read_text(encoding='utf-8'))
    assert len(national) == 3555 and national['읍면_key'].is_unique
    gg = national.loc[national.sidonm.eq('경기도')].copy().reset_index(drop=True)
    assert len(gg) == 602 and gg['읍면_key'].is_unique
    assert len(sim) == 602 and sim['읍면_key'].is_unique
    assert set(gg['읍면_key']) == set(sim['읍면_key'])
    assert len(raw) == len(rules) == 61
    assert raw[['시군', '운행구역']].duplicated().sum() == 0
    for values in [raw['운행대수'], sim['재배치_대수'], sim['현재_귀속대수']]:
        assert values.notna().all() and np.isfinite(values).all() and values.ge(0).all()
    assert (sim['재배치_대수'] % 1 == 0).all()
    # 전국 6개 지표 가중치와 기존 지수의 재현 여부를 별도로 검증한다.
    original_weights = entropy(national, VARS).set_index('지표')['가중치']
    original_index = national[VARS].fillna(0).mul(original_weights).sum(axis=1)
    assert np.allclose(original_index, national['이동격차지수'], atol=1e-12, rtol=0)
    check = pd.read_csv(INPUT / 'original_weight_check.csv', index_col=0)
    assert np.allclose(original_weights.loc[check.index], check['재계산'], atol=1e-12, rtol=0)
    original_weights.rename('전국6지표_원본가중치').rename_axis('지표').reset_index().pipe(save, '원본6지표_가중치재현.csv')
    sim = sim.set_index('읍면_key').loc[gg['읍면_key']].reset_index()
    assert np.allclose(gg['이동격차지수'], sim['이동격차지수'], atol=1e-12, rtol=0)
    return national, gg, raw, sim, rules


def map_current(gg, raw, rules):
    lookup = gg.assign(시군=gg.sggnm.str.extract(r'^(.+?[시군])', expand=False))
    assert not lookup[['시군', 'emdnm']].duplicated().any()
    keys = lookup.set_index(['시군', 'emdnm'])['읍면_key'].to_dict()
    edges, audit = [], []
    for r, (_, source) in zip(rules, raw.iterrows()):
        assert (r['city'], r['area'], r['fleet']) == (source['시군'], source['운행구역'], source['운행대수'])
        assert len(r['targets']) > 0 and len(set(r['targets'])) == len(r['targets'])
        fleet = r['fleet'] / len(r['targets'])
        for target in r['targets']:
            assert (r['city'], target) in keys, (r['city'], target)
            edges.append({'운행구역ID': r['route_id'], '시군': r['city'], '운행구역': r['area'],
                          '권역차량수': r['fleet'], '읍면_key': keys[r['city'], target],
                          '대상수': len(r['targets']), '가상귀속대수': fleet,
                          '연결상태': r['status'], '배분가정': r['allocation'], '근거와한계': r['note'],
                          '참고URL': ' | '.join(r['sources'])})
        audit.append({'운행구역ID': r['route_id'], '시군': r['city'], '운행구역': r['area'],
                      '원본대수': r['fleet'], '배분합계': fleet * len(r['targets']),
                      '대상수': len(r['targets']), '대상읍면동': ' / '.join(r['targets']),
                      '연결상태': r['status'], '배분가정': r['allocation'], '근거와한계': r['note']})
    edges, audit = pd.DataFrame(edges), pd.DataFrame(audit)
    assert np.allclose(audit['원본대수'], audit['배분합계'], atol=1e-12, rtol=0)
    current = edges.groupby('읍면_key')['가상귀속대수'].sum().reindex(gg['읍면_key'], fill_value=0).to_numpy()
    assert np.isclose(current.sum(), raw['운행대수'].sum())
    save(edges, '현재운행_권역별_읍면동배분.csv')
    save(audit, '현재운행_61개권역_검증.csv')
    return current, edges, audit


def calculate(gg, sim, current, edges):
    b = sim['재배치_대수'].to_numpy(dtype=float)
    assert np.isclose(current.sum(), b.sum())
    low, high = min(current.min(), b.min()), max(current.max(), b.max())
    assert high > low
    a_df, b_df = gg[VARS].copy(), gg[VARS].copy()
    a_df[DRT] = 1 - (current - low) / (high - low)
    b_df[DRT] = 1 - (b - low) / (high - low)
    # 원본 6개 점수의 전국 정규화를 보존. DRT는 A/B 합동 Min-Max.
    # 두 시나리오를 동등하게 포함해 공통 엔트로피 가중치를 한 번만 적합한다.
    pooled = pd.concat([a_df, b_df], ignore_index=True)
    wtable = entropy(pooled, VARS + [DRT])
    w = wtable.set_index('지표')['가중치']
    result = gg[['읍면_key', 'sidonm', 'sggnm', 'emdnm'] + VARS].copy()
    result['시군'] = result.sggnm.str.extract(r'^(.+?[시군])', expand=False)
    result['기존6지표_이동격차지수'] = gg['이동격차지수']
    result['기존6지표_순위'] = gg['이동격차지수'].rank(ascending=False, method='min').astype(int)
    result['기존지표_결측항목'] = gg[VARS].apply(lambda r: ', '.join(r.index[r.isna()]), axis=1)
    result['기존지표_결측있음'] = gg[VARS].isna().any(axis=1)
    for c in ['버스정류장_취약점수_대체여부', '배차간격_취약점수_대체여부']:
        result[c] = gg[c]
    result['현재_가상귀속대수'] = current
    result['재배치_대수'] = b
    result['대수변화_재배치빼기현재'] = b - current
    result['현재_DRT공급부족점수'] = a_df[DRT]
    result['재배치_DRT공급부족점수'] = b_df[DRT]
    result['현재반영_이동격차지수'] = a_df.fillna(0).mul(w).sum(axis=1)
    result['재배치반영_이동격차지수'] = b_df.fillna(0).mul(w).sum(axis=1)
    result['지수변화_재배치빼기현재'] = result['재배치반영_이동격차지수'] - result['현재반영_이동격차지수']
    delta = result['지수변화_재배치빼기현재']
    result['변화판정'] = np.where(delta < -1e-12, '개선', np.where(delta > 1e-12, '악화', '동일'))
    for scenario in ['현재', '재배치']:
        result[f'{scenario}반영_순위'] = result[f'{scenario}반영_이동격차지수'].rank(ascending=False, method='min').astype(int)
        result[f'{scenario}반영_동일가중지수'] = (a_df if scenario == '현재' else b_df).fillna(0).mean(axis=1)
    result['순위변화_양수면취약순위하락'] = result['재배치반영_순위'] - result['현재반영_순위']
    candidate = edges.loc[edges['연결상태'].eq('후보')].groupby('읍면_key')['가상귀속대수'].sum()
    result['현재_후보권역귀속대수'] = result['읍면_key'].map(candidate).fillna(0)
    result['현재_후보연결포함'] = result['현재_후보권역귀속대수'].gt(0)
    result['현재_연결운행구역'] = result['읍면_key'].map(edges.groupby('읍면_key')['운행구역'].agg(' / '.join)).fillna('제공 자료에서 연결 없음(분석상 0대)')
    result['입력시뮬레이션_현재귀속대수'] = sim['현재_귀속대수']
    result['현재귀속_재구성차이'] = current - sim['현재_귀속대수']
    # 비교의 핵심 불변식: 동일한 기존 6개 점수와 가중치에서는 DRT 항만 변한다.
    expected_delta = -w[DRT] * (b - current) / (high - low)
    assert np.allclose(delta, expected_delta, atol=1e-12, rtol=0)
    assert np.isclose(delta.mean(), 0, atol=1e-12)
    assert np.isclose(w.sum(), 1)
    assert result.filter(regex='반영_이동격차지수$').notna().all().all()
    assert (result['현재반영_이동격차지수'].between(0, 1) & result['재배치반영_이동격차지수'].between(0, 1)).all()
    sensitivity = pd.concat([entropy(a_df, VARS + [DRT]).assign(적합자료='현재만'),
                             entropy(b_df, VARS + [DRT]).assign(적합자료='재배치만'),
                             wtable.assign(적합자료='합동_주분석')], ignore_index=True)
    save(sensitivity, '가중치_별도적합_참고.csv')
    return result, wtable, {'drt_min': float(low), 'drt_max': float(high),
                          'pooled_rows': len(pooled), 'entropy_complete_rows': len(pooled.dropna()),
                          'epsilon': EPS, 'normalization': '기존6개 전국점수 보존; DRT 두 시나리오 합동 Min-Max',
                          'weights_population': '경기도 602개 × 2시나리오 중 7지표 완전행',
                          'missing_policy': '원본과 동일: 가중치 적합시 결측행 제외, 합산시 결측점수 0'}


def summarize(result):
    rows = []
    for label, subset in [('경기도 전체', result), ('기존6지표 상위20', result.nsmallest(20, '기존6지표_순위')),
                          ('기존6지표 상위50', result.nsmallest(50, '기존6지표_순위')),
                          ('기존지표 결측없음', result.loc[~result['기존지표_결측있음']])]:
        for scenario, fleet in [('현재', '현재_가상귀속대수'), ('재배치', '재배치_대수')]:
            s = subset[f'{scenario}반영_이동격차지수']
            rows.append({'대상': label, '시나리오': scenario, '읍면동수': len(subset), '대수합계': subset[fleet].sum(),
                         '공급양수_읍면동수': int(subset[fleet].gt(0).sum()), '지수평균': s.mean(),
                         '지수표준편차_ddof0': s.std(ddof=0), '지수최대': s.max(), '지수최소': s.min(),
                         '기존지표결측_읍면동수': int(subset['기존지표_결측있음'].sum())})
    summary = pd.DataFrame(rows)
    city = result.groupby('시군', as_index=False).agg(
        읍면동수=('읍면_key', 'size'), 현재대수=('현재_가상귀속대수', 'sum'), 재배치대수=('재배치_대수', 'sum'),
        현재지수평균=('현재반영_이동격차지수', 'mean'), 재배치지수평균=('재배치반영_이동격차지수', 'mean'),
        지수변화평균=('지수변화_재배치빼기현재', 'mean'),
        개선지역수=('변화판정', lambda s: int(s.eq('개선').sum())),
        악화지역수=('변화판정', lambda s: int(s.eq('악화').sum())),
        기존결측지역수=('기존지표_결측있음', 'sum'))
    return summary, city


def make_figures(result, weights):
    names = {f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams['font.family'] = next((f for f in ['Malgun Gothic', 'NanumGothic', 'AppleGothic'] if f in names), 'DejaVu Sans')
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    x, y = result['현재반영_이동격차지수'], result['재배치반영_이동격차지수']
    colors = result['변화판정'].map({'개선': '#147d92', '악화': '#d06c45', '동일': '#a6adb5'})
    axes[0].scatter(x, y, c=colors, s=15, alpha=.7)
    lim = [min(x.min(), y.min()) - .005, max(x.max(), y.max()) + .005]
    axes[0].plot(lim, lim, '--', color='#555', lw=1)
    axes[0].set(xlabel='현재 운행 반영 지수', ylabel='재배치 반영 지수', title='경기도 602개 읍면동 · 대각선 아래는 개선', xlim=lim, ylim=lim)
    top = result.nsmallest(20, '기존6지표_순위').iloc[::-1]
    axes[1].barh(top['sggnm'] + ' ' + top['emdnm'], top['지수변화_재배치빼기현재'], color='#147d92')
    axes[1].axvline(0, color='#555', lw=1)
    axes[1].set(title='기존 6지표 상위 20개 지역의 지수 변화', xlabel='재배치 - 현재 (음수: 개선)')
    fig.savefig(FIG / '01_두시나리오_비교.png', dpi=180)
    fig.savefig(FIG / '01_두시나리오_비교.pdf')
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4), layout='constrained')
    labels = weights['지표'].str.replace('_취약점수', '', regex=False)
    ax.barh(labels.iloc[::-1], weights['가중치'].iloc[::-1] * 100, color='#147d92')
    ax.set(xlabel='공통 엔트로피 가중치 (%)', title='경기도 두 시나리오 합동 적합 · 7개 지표')
    for i, v in enumerate(weights['가중치'].iloc[::-1] * 100):
        ax.text(v + .2, i, f'{v:.3f}%', va='center', fontsize=9)
    ax.set_xlim(0, weights['가중치'].max() * 115)
    fig.savefig(FIG / '02_공통가중치.png', dpi=180)
    plt.close(fig)


def md_table(df):
    """tabulate 없이 Markdown 출력."""
    def fmt(x):
        return f'{x:.6f}' if isinstance(x, (float, np.floating)) else str(x)
    return '\n'.join(['| ' + ' | '.join(map(str, df.columns)) + ' |',
                      '| ' + ' | '.join(['---'] * len(df.columns)) + ' |'] +
                     ['| ' + ' | '.join(fmt(x) for x in row) + ' |' for row in df.itertuples(index=False, name=None)])


def write_report(result, weights, summary, audit, params, validation):
    counts = result['변화판정'].value_counts()
    w = weights.set_index('지표')['가중치'][DRT]
    top = result.nsmallest(20, '기존6지표_순위')
    changes = result.loc[result['현재귀속_재구성차이'].abs().gt(1e-10)]
    avg_a = result['현재반영_이동격차지수'].mean()
    avg_b = result['재배치반영_이동격차지수'].mean()
    rank_corr = np.corrcoef(result['현재반영_이동격차지수'].rank(), result['재배치반영_이동격차지수'].rank())[0, 1]
    top_overlap = len(set(result.nsmallest(20, '현재반영_순위')['읍면_key']) & set(result.nsmallest(20, '재배치반영_순위')['읍면_key']))
    report = f'''# DRT를 반영한 경기도 이동격차지수 비교

현재 운행 326대와 제공된 재배치 326대를 경기도 602개 읍면동에 반영한 **가정 기반 비교**다. 기존 6개 취약점수에 DRT 공급부족 점수를 추가했으며, 두 시나리오에 같은 정규화 기준과 같은 엔트로피 가중치를 사용했다. 지수가 클수록 취약하다.

## 결과

- 개선 {counts.get('개선', 0)}개, 악화 {counts.get('악화', 0)}개, 동일 {counts.get('동일', 0)}개.
- 전체 평균: 현재 {avg_a:.9f}, 재배치 {avg_b:.9f}.
- 기존 6지표 상위 20개 지역 평균 변화: {top['지수변화_재배치빼기현재'].mean():+.9f} (재배치 − 현재).
- DRT 공통 가중치: {w:.9%}. 가중치는 정책적 중요도나 실제 개선효과의 비율이 아니다.
- 두 시나리오 순위상관(Spearman): {rank_corr:.9f}, 각각 상위 20개 중 공통 지역 {top_overlap}개. 순위가 바뀐 지역은 {int(result['순위변화_양수면취약순위하락'].ne(0).sum())}개다. 지수가 개선되어도 다른 지역과의 상대순위는 악화될 수 있다.

{md_table(summary)}

**총량 326대를 보존하고 DRT 대수를 선형 변환하므로 전체 평균이 같은 것은 산식상 필연이다.** 전체 평균 감소를 재배치의 성공 기준으로 사용할 수 없다. 기존 취약지역의 점수 변화, 분산, 공급 지역 수와 악화지역을 함께 읽어야 한다. 차량 대수가 늘면 지수가 내려가도록 정의한 모형이므로 실제 이동시간·대기시간·이용자 편익의 개선을 실증한 결과가 아니다.

![비교](figures/01_두시나리오_비교.png)

## 동일한 기준으로 계산한 방법

1. `inputs/national_baseline.csv`는 최종 노트북을 기존에 재실행하여 저장한 전국 3,555행의 **전처리 결과 스냅샷**이다. 원본 노트북의 엔트로피 함수로 전국 6개 가중치와 기존 지수를 재현 검증했다. 제공 시뮬레이션의 기존 지수도 602행 모두 이 스냅샷과 일치한다.
2. 기존 6개 취약점수는 전국 기준 정규화 상태를 그대로 유지했다. 이번에는 자동차·고령인구 원자료부터 전처리를 다시 실행하지 않았다. 저장소에서 원본 고령인구 XLS가 빠져 있어, 독립 실행 가능한 입력으로 이 스냅샷을 보관했다. 원본 노트북과 과거 입력 해시 기록도 포함했다.
3. 현재 운행 CSV 61개 권역의 326대를 행정동에 연결했다. 권역별 대상 동이 n개면 각 동에 `권역대수/n`을 가상 귀속한다. 여러 권역이 같은 동에 연결되면 합산하며, 같은 권역 내 중복 동은 허용하지 않는다. 소수 대수는 실제 주차·배차 대수가 아닌 공유 차량의 분석상 지분이다.
4. 재배치 CSV의 `재배치_대수`를 그대로 사용했다. CSV의 `이동격차지수`나 `현재_귀속대수`를 7번째 지표로 사용하지 않았다. 제공된 재배치안의 최적성이나 차량 운영 가능성을 새로 검증한 것은 아니다.
5. 공통 DRT 점수: `1 − (대수 − {params['drt_min']:g}) / ({params['drt_max']:g} − {params['drt_min']:g})`. 최소·최대는 현재/재배치 두 분포를 합쳐 정했다. 제공 자료에서 연결되지 않은 동은 이 분석에서만 0대로 처리하며, 실제 DRT 미운행을 확정하지 않는다.
6. 두 시나리오 1,204행을 합쳐 원본과 동일한 엔트로피 알고리즘을 적용했다. 결측 없는 {params['entropy_complete_rows']}행에 `X'=X×(1−2ε)+ε`, `ε=10⁻⁶`, `P=X'/열합`, `E=−Σ(P ln P)/ln(n)`, `w=(1−E)/Σ(1−E)`를 적용했다. 최종 지수는 `Σ(w×취약점수)`다.
7. 경기도 밖의 DRT 자료가 없으므로 다른 지역을 임의로 0대로 두지 않고 **가중치는 경기도 비교용으로 새로 적합**했다. 따라서 원본 전국 6지표 가중치와 다르다. 서울 제외 여부는 이번 경기도 표본에는 해당하지 않는다.

{md_table(weights)}

두 시나리오에서 가중치를 따로 적합한 값도 `outputs/가중치_별도적합_참고.csv`에 제공하지만 주 비교에는 사용하지 않았다. 별도 적합 시 점수 변화에 가중치 변화가 섞이기 때문이다. 원본과 같은 동일가중치 1/7 결과도 전체 비교표에 실었다.

## 원본 현재 귀속대수 300대와의 차이

제공 시뮬레이션의 `현재_귀속대수` 합은 300대다. 새 운행 CSV의 326대를 전부 반영하기 위해 권역 연결을 다시 구성했다. {len(changes)}개 동의 귀속이 달라지며, 차이 합계는 {changes['현재귀속_재구성차이'].sum():g}대다. 이는 단순히 26대를 추가한 것만이 아니라 기존 귀속 위치와 공동권역 배분도 수정한 결과다. `outputs/현재귀속_300대와326대_차이.csv`에 전부 기록했다.

주요 사례: 연천읍·내산리는 기존 내산리→신서면 규칙을 반영해 1대씩, 의왕 초평동은 기존 규칙에 따라 부곡동에 연결한다. 향동동은 화전동, 스마트허브는 초지동에 연결한다. 운정·고덕·동탄·양주·민락 등은 기존 후보 정책을 유지하며 후보 대상에 균등 배분하는 분석 가정을 쓴다. 권역의 연결상태와 차량 배분 가정은 서로 다른 정보다.

## 연결 불확실성과 결측

- 후보 권역은 {int(audit['연결상태'].eq('후보').sum())}개, 해당 권역 차량은 {audit.loc[audit['연결상태'].eq('후보'), '원본대수'].sum():g}대다. 후보를 포함하여 전체 326대를 비교하므로 이 결과는 확정적인 행정동별 운행현황이 아니다. 정확한 서비스 경계·운영시간·좌석수·승객 수를 적용하지 않았다.
- `inputs/route_mapping.json`에 61개 권역의 대상 동, 연결 상태, 배분 가정과 근거를 모두 공개했다. 이천 시내권을 4개 행정동에 나누는 것, 감일·위례 지구 연결 등은 잠정 가정이다. 행정동 연결이 그 동 전역 운행을 뜻하지 않는다.
- 기존 6지표에 결측이 있는 동은 {int(result['기존지표_결측있음'].sum())}개다. 원본을 재현하기 위해 가중치 적합에서는 해당 행을 제외하고, 지수 합산에서는 결측점수를 0으로 처리했다. 이로 인한 취약성 과소평가 가능성이 있으며 해당 동을 결과표에 표시했다. 결측 없는 지역만의 요약도 별도 제공한다.
- 기존 버스 지역 평균 대체 및 자동차등록대수 대리지표의 한계는 유지된다. 7번째 지표는 인구·면적당 공급이 아니라 **읍면동에 귀속한 차량 대수**이므로 수요 대비 공급 적정성이나 서비스 수준을 직접 나타내지 않는다.
- 재배치안이 기존 지수에 따라 만들어졌다면 기존 취약지역의 점수가 내려가는 것은 설계상 기대되는 결과다. 독립적인 정책효과 검증과 구분해야 한다.

## 새로 확인한 행정동 연결 참고

광주시 공식 자료의 광남1동 관할 목록 및 광남2동 설명에 따라 태전동은 광남1·2동 후보로, 장지동은 광남1동에 연결했다. 고산동은 광주시 공식 안내 및 도시관리공사 목록을 근거로 오포1동에 연결했다. 서비스 경계는 별도 검증하지 않았다.

- [광주시 광남2동 일반현황](https://tour.gjcity.go.kr/csc/contents.do?mId=1601020000)
- [광주시 예방접종기관의 행정동·법정동 표기](https://www.gjcity.go.kr/depart/img/sub08/2025_child.pdf)
- [광주도시관리공사 공원 목록](https://gumc.or.kr/business/park8)

나머지 기존 관할 변환 근거는 `inputs/original_boundary_rules.json`과 권역별 CSV의 참고URL에 보존했다. 기존 자료의 링크 전체를 이번에 재조회한 것은 아니다.

## 검증 결과

{md_table(pd.DataFrame([validation]))}

## 파일과 재실행

- `outputs/01_현재운행반영_이동격차지수.csv`: 현재 운행을 반영한 602개 지역 지수와 순위.
- `outputs/02_재배치반영_이동격차지수.csv`: 재배치를 반영한 602개 지역 지수와 순위.
- `outputs/03_두시나리오_전체비교.csv`: 두 지수, 차량수, 변화, 순위, 동일가중 결과, 결측·후보 표시.
- `outputs/04_요약.csv`, `outputs/05_시군별비교.csv`: 범위별·시군별 요약.
- `outputs/06_공통엔트로피가중치.csv`: 주 비교의 가중치.
- `outputs/현재운행_권역별_읍면동배분.csv`, `outputs/현재운행_61개권역_검증.csv`: 배분 과정과 차량 보존 검증.
- `outputs/현재귀속_300대와326대_차이.csv`: 시뮬레이션의 현재값과 재구성한 현재값 차이.
- `figures/`: PNG 그림 및 비교 PDF.
- `과정_확인.ipynb`: 입력·매핑·산식·결과를 확인하고 다시 실행할 수 있는 노트북.

이 폴더에서 `python run_comparison.py`를 실행하면 결과와 그림을 다시 생성한다. `requirements.txt`에 실제 실행 환경 버전을 기록했다. 입력 SHA-256은 `inputs/manifest.json`, 실행에 사용한 모든 입력과 코드 해시는 `outputs/실행기록.json`에 있다. 입력 스냅샷을 변경하려면 manifest도 새 입력 기준으로 명시적으로 갱신해야 하며, 매핑 변경은 `route_mapping.json`을 수정하면 된다.
'''
    (BASE / 'README.md').write_text(report, encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)
    national, gg, raw, sim, rules = load_inputs()
    current, edges, audit = map_current(gg, raw, rules)
    result, weights, params = calculate(gg, sim, current, edges)
    summary, city = summarize(result)
    for scenario, num, fleet in [('현재', '01', '현재_가상귀속대수'), ('재배치', '02', '재배치_대수')]:
        cols = ['읍면_key', 'sidonm', 'sggnm', 'emdnm', fleet, f'{scenario}_DRT공급부족점수',
                f'{scenario}반영_이동격차지수', f'{scenario}반영_순위', '기존지표_결측있음', '기존지표_결측항목',
                '현재_후보연결포함']
        save(result[cols].sort_values(f'{scenario}반영_순위'), f'{num}_{"현재운행" if scenario == "현재" else "재배치"}반영_이동격차지수.csv')
    save(result.sort_values('기존6지표_순위'), '03_두시나리오_전체비교.csv')
    save(summary, '04_요약.csv')
    save(city.sort_values('지수변화평균'), '05_시군별비교.csv')
    save(weights, '06_공통엔트로피가중치.csv')
    save(result.nsmallest(20, '기존6지표_순위'), '07_기존상위20_비교.csv')
    save(result.loc[result['변화판정'].eq('개선')].sort_values('지수변화_재배치빼기현재'), '08_개선지역.csv')
    save(result.loc[result['변화판정'].eq('악화')].sort_values('지수변화_재배치빼기현재', ascending=False), '09_악화지역.csv')
    save(result.loc[result['현재귀속_재구성차이'].abs().gt(1e-10),
                    ['읍면_key', '입력시뮬레이션_현재귀속대수', '현재_가상귀속대수', '현재귀속_재구성차이', '현재_연결운행구역', '현재_후보연결포함']],
         '현재귀속_300대와326대_차이.csv')
    params['shared_weight_fit'] = True
    (OUT / '분석설정.json').write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding='utf-8')
    validation = {'전국행수': len(national), '경기도행수': len(result), '현재대수': float(current.sum()),
                  '재배치대수': float(sim['재배치_대수'].sum()), '입력현재귀속대수': float(sim['현재_귀속대수'].sum()),
                  '권역수': len(audit), '권역별차량보존': True, '키중복수': int(result['읍면_key'].duplicated().sum()),
                  '원본6지표재현': True, '공통가중치합계': float(weights['가중치'].sum()),
                  '지수변화산식검증': True, '평균동일검증': True}
    (OUT / '검증결과.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding='utf-8')
    make_figures(result, weights)
    write_report(result, weights, summary, audit, params, validation)
    records = [{'file': str(p.relative_to(BASE)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
               for p in sorted(INPUT.iterdir()) if p.is_file()]
    records.append({'file': Path(__file__).name, 'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    (OUT / '실행기록.json').write_text(json.dumps({'python': platform.python_version(), 'pandas': pd.__version__,
        'numpy': np.__version__, 'matplotlib': matplotlib.__version__, 'inputs_and_code': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(summary.to_string(index=False))
    print('\n공통 가중치\n' + weights.to_string(index=False))
    print('\n변화판정:', result['변화판정'].value_counts().to_dict())
    print('검증 통과. 결과 폴더:', BASE)
    return result, weights, summary


if __name__ == '__main__':
    main()
