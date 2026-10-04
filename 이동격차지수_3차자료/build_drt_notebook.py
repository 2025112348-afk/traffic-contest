"""비교 코드를 포함한 Colab 노트북을 생성한다. 원본은 수정하지 않는다."""
import json
from pathlib import Path

base = Path(__file__).resolve().parent
root = base.parent
nb = json.loads((base / 'Traffic_entropy_final.ipynb').read_text(encoding='utf-8'))
code = (base / 'compare_gyeonggi_drt.py').read_text(encoding='utf-8')
drt_text = (root / 'data/raw/경기도_똑버스_운행현황.csv').read_text(encoding='utf-8-sig')
intro = '''## 8. 최초 이름 일치 비교 (참고용 기준선)

최신 판정은 아래 9번의 경계 기준·후보 관리 결과를 사용합니다. 8번은 이전 이름 비교를 보존한 기준선입니다.

앞의 최종 지수 계산을 실행한 다음 실행합니다. 기존 Colab에 계산 결과가 남아 있으면 아래 코드 셀만 복사해도 됩니다.
전국 기준 가중치와 점수를 그대로 유지하고 경기도만 추출합니다. 경기도만으로 가중치를 다시 계산하지 않습니다.

제공된 운행현황 CSV 사본을 코드에 포함했습니다. 현재 시점의 운행을 별도로 확인한 자료가 아닙니다.
시군과 읍면동 명칭이 운행구역에 명시된 경우만 확인으로 표시합니다. 신도시·지구명, 법정동/행정동 차이와 개편 명칭은 자동 추정하지 않습니다.
‘미확인’ 또는 ‘기록 없음’은 미운행 판정이 아닙니다. 명칭이 일치해도 읍면동 전역을 운행한다는 뜻은 아닙니다.
이 자료에는 승객·탑승 기록이 없어 주민의 실제 이용 여부나 이용률을 판단할 수 없습니다.

결측 포함 지역은 잠정 순위에 주의 표시를 붙입니다. 결측 없는 지역만의 순위도 함께 제공하지만 기존 가중치는 그대로이므로 데이터 문제를 모두 해결한 결과는 아닙니다.
상위 10/20/50은 점수 순 정렬 후 해당 행 수를 선택합니다(경계 동점의 전원 포함 방식이 아님).
'''
run = code + '\n\nfrom io import StringIO\n' + f'drt_source = pd.read_csv(StringIO({drt_text!r}))\n' + '''
gyeonggi_drt, gyeonggi_drt_summary = compare_gyeonggi_drt(eupmyeon_master, drt_source)
display(gyeonggi_drt.head(20)[['경기도순위_잠정', 'sggnm', 'emdnm', '이동격차지수', 'DRT대조결과', '일치_운행구역', '순위주의']])
display(gyeonggi_drt_summary)
'''
nb['cells'].extend([
    {'cell_type': 'markdown', 'metadata': {}, 'source': intro.splitlines(keepends=True)},
    {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': run.splitlines(keepends=True)},
    {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': [
        "# 비교 결과 CSV 3개를 ZIP으로 내려받기 (Colab)\n",
        "import shutil\n",
        "shutil.make_archive('gyeonggi_drt_comparison', 'zip', 'gyeonggi_drt_comparison')\n",
        "from google.colab import files\n",
        "files.download('gyeonggi_drt_comparison.zip')\n",
    ]},
])
import pandas as pd
mapping_dir = base / 'drt_boundary_mapping'
link_cols = ['읍면_key','emd8','emdcd','경계기준_DRT연결','확인_운행구역ID','후보_운행구역ID','후보연결존재','연결_원본운행구역','경계변환_근거URL']
links = pd.read_csv(mapping_dir / '경기도_경계기준_DRT비교.csv', dtype={'emd8':str,'emdcd':str})[link_cols]
link_csv = links.to_csv(index=False)
regions_csv = (mapping_dir / '똑버스_운행권역표.csv').read_text(encoding='utf-8-sig')
candidates_csv = (mapping_dir / '후보9개_권역검토표.csv').read_text(encoding='utf-8-sig')
mapping_csv = (mapping_dir / '똑버스_읍면동_대응표.csv').read_text(encoding='utf-8-sig')
candidate_code = f'''from io import StringIO
boundary_links = pd.read_csv(StringIO({link_csv!r}), dtype={{'emd8':str, 'emdcd':str}})
drt_regions = pd.read_csv(StringIO({regions_csv!r}))
candidate_regions = pd.read_csv(StringIO({candidates_csv!r}))
boundary_mapping = pd.read_csv(StringIO({mapping_csv!r}), dtype={{'emd8':str, 'emdcd':str}})
assert set(gyeonggi_drt['읍면_key']) == set(boundary_links['읍면_key']), '경계 목록이 변경됨: 대응표 재생성 필요'
boundary_result = gyeonggi_drt.merge(boundary_links, on='읍면_key', validate='one_to_one')
display(candidate_regions)
display(boundary_result.head(20)[['경기도순위_잠정','sggnm','emdnm','이동격차지수','경계기준_DRT연결','후보연결존재']])
boundary_summary = pd.DataFrame([{{
    '상위N':n,
    '확인':int(boundary_result.head(n)['경계기준_DRT연결'].eq('확인').sum()),
    '후보만존재':int(boundary_result.head(n)['경계기준_DRT연결'].eq('후보').sum()),
    '후보연결존재':int(boundary_result.head(n)['후보연결존재'].sum())
}} for n in (10,20,50,len(boundary_result))])
display(boundary_summary)
from pathlib import Path
candidate_out = Path('drt_boundary_mapping')
candidate_out.mkdir(exist_ok=True)
for name, frame in [('경기도_경계기준_DRT비교',boundary_result),('후보9개_권역검토표',candidate_regions),('똑버스_운행권역표',drt_regions),('똑버스_읍면동_대응표',boundary_mapping),('경계변환_요약',boundary_summary)]:
    frame.to_csv(candidate_out / (name+'.csv'), index=False, encoding='utf-8-sig')
'''
nb['cells'].extend([
    {'cell_type':'markdown','metadata':{},'source':[
        '## 9. 경계 기준 비교 — 9개 권역 후보 관리\n',
        '2026-07-01 경계 코드에 연결한 대응표를 포함했습니다. 9개 권역은 모두 후보로 집계하며 원래 확인 근거는 별도 보존합니다. 후보를 운행 확인 수에 포함하지 않습니다. 다른 권역에서 확인된 동일 읍면동은 확인으로 남고 후보연결존재도 표시합니다.\n',
        '차량수는 운행권역표에 권역 합계로 보존합니다. 읍면동별 배분값은 없습니다. 양주역·덕정역은 연계거점으로만 남깁니다. 대응표는 작성 시점의 고정 자료이며 지수만 현재 실행 결과로 연결합니다. 원본·경계·정책 변경 시 로컬 변환 및 노트북 생성 스크립트를 다시 실행하세요.\n'
    ]},
    {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':candidate_code.splitlines(keepends=True)},
    {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':[
        "shutil.make_archive('drt_boundary_mapping', 'zip', 'drt_boundary_mapping')\n",
        "files.download('drt_boundary_mapping.zip')\n"
    ]}
])
dest = base / 'Traffic_entropy_final_경기도_DRT비교.ipynb'
dest.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
print(dest)
