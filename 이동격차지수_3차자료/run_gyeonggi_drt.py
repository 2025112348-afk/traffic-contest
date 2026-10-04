"""로컬 원자료로 최종 노트북을 재실행한 뒤 경기도 DRT를 대조한다."""
import contextlib
import hashlib
import io
import json
import sys
import types
from pathlib import Path

from compare_gyeonggi_drt import compare_gyeonggi_drt

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
OUTPUT = BASE / 'gyeonggi_drt_comparison'
OUTPUT.mkdir(exist_ok=True)
inputs = [
    ROOT.parent / 'traffic/1인당_자동차_등록대수_시도_시_군_구__20260923121149.csv',
    ROOT / 'data/processed/terrain/slope_score.csv',
    ROOT / 'data/101_DT_1IN1503_20261004030052.xls',
    ROOT / 'data/processed/medical/medical_access_score_hira.csv',
    ROOT / 'visualizations/10_stop_supply_index/stop_supply_by_dong.csv',
    ROOT / 'visualizations/14_dong_supply/dong_supply.csv',
]
for path in inputs:
    if not path.is_file():
        raise FileNotFoundError(path)

# Colab의 업로드만 로컬 경로로 치환하며 계산 코드는 그대로 실행한다.
queue = iter(inputs)
files = types.SimpleNamespace(upload=lambda: {str(next(queue)): b''})
colab = types.ModuleType('google.colab')
colab.files = files
google = types.ModuleType('google')
google.colab = colab
sys.modules['google'] = google
sys.modules['google.colab'] = colab
nb_path = BASE / 'Traffic_entropy_final.ipynb'
nb = json.loads(nb_path.read_text(encoding='utf-8'))
namespace = {}
log = io.StringIO()
with contextlib.redirect_stdout(log):
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            exec(compile(''.join(cell['source']), str(nb_path), 'exec'), namespace)
(OUTPUT / '최종코드_실행로그.txt').write_text(log.getvalue(), encoding='utf-8')
pd = namespace['pd']
master = namespace['eupmyeon_master']
assert len(master) == 3555, f'병합 후 행 수가 예상과 다름: {len(master)}'
assert not master['읍면_key'].duplicated().any(), '중복 지역 발견'
expected = {'지형장벽_취약점수': .160038, '자가용미보유_취약점수': .005189,
            '의료_취약점수': .336894, '버스정류장_취약점수': .010236,
            '배차간격_취약점수': .399321, '고령인구비율_취약점수': .088322}
weights = namespace['weights']
weight_check = pd.DataFrame({'재계산': weights, '저장출력': pd.Series(expected)})
weight_check['절대차이'] = (weight_check['재계산'] - weight_check['저장출력']).abs()
weight_check.to_csv(OUTPUT / '전국가중치_재현검증.csv', encoding='utf-8-sig')
reproduced = bool(weight_check['절대차이'].max() < 1e-6)
drt_path = ROOT / 'data/raw/경기도_똑버스_운행현황.csv'
result, summary = compare_gyeonggi_drt(master, pd.read_csv(drt_path), OUTPUT)
master.to_csv(OUTPUT / '전국_최종지수_재계산.csv', index=False, encoding='utf-8-sig')
manifest = [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs + [nb_path, drt_path]]
(OUTPUT / '입력파일_기록.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('전국 행수:', len(master), '경기도 행수:', len(result), '저장 가중치 재현:', reproduced)
print(weight_check.to_string())
print(result.head(20)[['경기도순위_잠정','sggnm','emdnm','이동격차지수','DRT대조결과','일치_운행구역','순위주의']].to_string(index=False))
print(summary.to_string(index=False))
print('경기도 결측 포함:', int(result['순위주의'].sum()))
report = [
    '# 경기도 이동격차 순위와 똑버스 운행현황 비교',
    '',
    '> 이 문서는 최초의 이름 일치 기준 결과다. 이후 행정동 경계 코드와 공식 소속·명칭변경 자료를 적용한 [경계변환 결과](../drt_boundary_mapping/경계변환_결과.md)를 추가했다. 상위 20개는 이름 기준 5개(25%), 변환 후 행정단위 연결 기준 6개(30%)다. 두 비율 모두 실제 서비스 면적 또는 이용률이 아니다.',
    '> 최신 결과에서는 사용자 지정 9개 권역을 후보로 관리한다. 후보는 확인 수에서 제외하고 차량수는 권역 합계로만 보존한다. 원래 확인된 관계도 근거상태에 따로 남긴다. 후보 목록은 [9개 권역 검토표](../drt_boundary_mapping/후보9개_권역검토표.csv)를 참고한다.',
    '',
    f'전국 {len(master):,}개 지역을 최종 노트북 코드 그대로 재계산한 뒤 경기도 {len(result)}개 읍면동을 추출했다. 전국 가중치의 저장 출력 재현 여부: {reproduced} (소수점 6자리 반올림 오차 범위). 경기도만으로 가중치를 다시 계산하지 않았다.',
    '',
    '제공된 `data/raw/경기도_똑버스_운행현황.csv`의 시군과 명시된 읍면동을 대조했다. 최신 운행 지속 여부와 실제 탑승 여부는 검증하지 않았다.',
    '',
    '## 결과',
    '',
    '| 범위 | 명시 운행 확인 | 확인 비율 |',
    '|---|---:|---:|',
]
for _, r in summary.loc[summary['대상'].eq('전체')].iterrows():
    report.append(f"| 상위 {r['상위N']}개 | {r['읍면동명시운행지역수']}개 | {r['명시확인비율']:.0%} |")
report += ['', '| 경기도 순위 | 시군 | 읍면동 | 지수 | 대조 결과 | 근거 운행구역 |', '|---:|---|---|---:|---|---|']
for _, r in result.head(20).iterrows():
    report.append(f"| {r['경기도순위_잠정']} | {r['sggnm']} | {r['emdnm']} | {r['이동격차지수']:.6f} | {r['DRT대조결과']} | {r['일치_운행구역']} |")
report += [
    '', '## 해석과 한계', '',
    '- 상위 20개 중 5개는 운행구역에 읍면동 이름이 명시된다. 6개는 해당 시군에 운행 기록은 있으나 해당 읍면동을 명칭으로 확인하지 못했고, 9개는 해당 시군 자체가 제공 CSV에 없다.',
    '- 미확인은 미운행을 뜻하지 않는다. 리·신도시·지구명, 법정동/행정동 차이, 다른 DRT 서비스, 자료 기준일 차이를 추가 확인해야 한다. 명시된 지역도 전역 운행을 보장하지 않는다.',
    '- CSV에는 승객 수나 탑승 기록이 없으므로 실제 이용률 또는 DRT 효과를 계산할 수 없다. 25%는 상위 20개 지역 중 명칭으로 운행을 확인한 비율이다.',
    f"- 경기도 {int(result['순위주의'].sum())}개 지역에는 최종 코드의 결측 0 대체 문제가 남는다. 상위 50개에는 이 결측 지역이 없지만, 그 지역들이 과소평가되어 상위권에서 빠졌을 가능성은 남는다.",
    '- 버스 자료의 지역 평균 대체, 이상치, 기존 엔트로피 가중치 한계는 원본과 동일하다. 따라서 잠정 순위로 해석해야 한다.',
    '- DRT 운행과 취약성의 공간적 중첩을 확인하는 분석이다. DRT 도입 타당성이나 도입 전후 효과를 입증하는 분석은 아니다.',
    '', '## 가중치와 순위의 신뢰성 평가', '',
    '현재 결과는 계산 재현성을 확인한 탐색적·잠정 지수다. 가중치가 현실의 이동 취약성을 얼마나 정확하게 반영하는지는 아직 충분히 검증하지 않았다. 신뢰도를 하나의 퍼센트로 제시할 근거는 없다.',
    '',
    '| 평가 기준 | 현재 판단 | 확인 근거 또는 미검증 사항 |',
    '|---|---|---|',
    '| 계산 재현성 | 확인됨 | 원자료 재계산 가중치가 최종 노트북 저장 출력과 소수점 6자리 반올림 오차 범위에서 일치한다. 같은 처리를 재현한 것으로, 방법론의 타당성까지 입증하지는 않는다. |',
    '| 입력자료의 타당성 | 보완 필요 | 결측, 지역 평균 대체, 이상치와 자동차등록대수의 대리지표 한계가 남는다. |',
    '| 가중치의 안정성 | 미검증 | 결측·이상치 처리 및 분석 대상 변경에 따른 가중치와 순위 변화를 체계적으로 검증하지 않았다. |',
    '| 현실 설명력 | 미검증 | 실제 이동시간, 교통 불편 조사, 미충족 이동수요 등 독립 자료와 비교하지 않았다. |',
    '', '### 똑버스 명시 확인 비율 25%의 의미', '',
    '상위 20개 중 5개가 CSV의 운행구역에 명시된다는 결과는 가중치의 정확도가 25%라는 뜻이 아니다. 똑버스 운행지역은 이동 취약성의 정답표가 아니며, 예산·도입 시기·정책 목적 등이 선정에 영향을 줄 수 있다. 이번 분석에서는 이러한 요인의 실제 영향을 검증하지 않았다. 운행지역과 불일치하더라도 아직 서비스가 도입되지 않은 취약지역일 수 있고, 일치하더라도 지수의 타당성이 입증되는 것은 아니다. 현재 비교는 공간적 중첩을 보여주는 보조 분석으로 해석한다.',
    '', '### 가중치 해석 시 주의점', '',
    '엔트로피 가중치는 입력된 취약점수 분포의 차이를 반영한다. 배차간격 39.9%, 의료 33.7%는 사회적 중요도나 실제 이동 어려움에 대한 인과적 기여율이 아니다. 정류장 1.0%, 자가용미보유 0.5%도 해당 요인이 중요하지 않다는 증거가 아니다.',
    '',
    '자동차등록대수와 인구 대비 정류장 수의 극단값은 min-max 정규화와 점수 분포에 영향을 줄 수 있다. 가중치 계산에서는 결측 포함 행이 제외되고, 최종 지수 계산에서는 결측이 0으로 처리되므로 입력 처리에 따른 편향 가능성이 있다. 자동차등록대수는 주민의 실제 차량 이용 가능성을 직접 측정하지 않으며, 시군구 값을 복제한 자료는 같은 시군구 내 읍면동의 차이를 반영하지 못한다.',
    '',
    '기존 동일가중치 비교는 민감도분석의 출발점이지만 결측과 이상치의 영향이 함께 섞여 있다. 큰 순위 차이만으로 엔트로피 방식 또는 동일가중치 방식 중 하나가 더 타당하다고 판단할 수 없다.',
    '', '### 추가 검증 계획 — 아직 수행하지 않은 항목', '',
    '1. 행정구역 매칭과 결측을 정리하고, 결측을 가장 양호한 점수 0으로 처리하는 방식을 수정한다. 버스 지역 평균 대체 시 동일 이름의 타 시도 시군구가 섞이는 문제도 점검한다.',
    '2. 기존 정규화와 이상치 완화 방식(예: 윈저라이징·로그 변환·순위 기반 정규화)을 비교해 가중치 및 상위 지역 변화를 확인한다. 어떤 방식이 적절한지는 지표 의미와 자료 분포를 근거로 결정한다.',
    '3. 전처리 기준을 정리한 뒤 엔트로피·동일가중치 등에서 상위 20·50개 지역 중복률과 전체 순위 상관을 계산한다. 표본 구성 변경에 대한 안정성도 확인한다.',
    '4. 실제 이동시간, 교통 불편 조사, 미충족 이동수요 등 독립적인 자료로 외부 타당성을 검증한다. 이용실적을 확보하더라도 서비스 공급량과 도입 시점의 영향을 고려하며, 운행 또는 이용실적만으로 인과효과를 주장하지 않는다.',
    '', '### 보고서에서 사용할 결론', '',
    '> 본 지수는 읍면동별 이동 취약지역을 탐색하기 위한 잠정 지수이며, 계산 재현성은 확인하였다. 다만 결측·대체값·이상치 처리와 가중치 안정성 및 외부 타당성 검증이 남아 있다. 똑버스 운행현황과의 중첩은 보조적 비교 결과로 해석하며, 현재 순위만으로 예산 배분이나 DRT 도입 우선순위를 확정하기는 어렵다.',
    '', '## 재현', '',
    '`python 이동격차지수_3차자료/run_gyeonggi_drt.py`', '',
    '입력 경로와 SHA-256은 `입력파일_기록.json`, 가중치 비교는 `전국가중치_재현검증.csv`, 전체 계산값은 `전국_최종지수_재계산.csv`에 저장했다.',
]
(OUTPUT / '경기도_DRT비교_결과.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
