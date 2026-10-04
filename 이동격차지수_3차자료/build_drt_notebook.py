"""비교 코드를 포함한 Colab 노트북을 생성한다. 원본은 수정하지 않는다."""
import json
from pathlib import Path

base = Path(__file__).resolve().parent
root = base.parent
nb = json.loads((base / 'Traffic_entropy_final.ipynb').read_text(encoding='utf-8'))
code = (base / 'compare_gyeonggi_drt.py').read_text(encoding='utf-8')
drt_text = (root / 'data/raw/경기도_똑버스_운행현황.csv').read_text(encoding='utf-8-sig')
intro = '''## 8. 경기도 이동격차 순위와 똑버스 운행현황 대조

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
dest = base / 'Traffic_entropy_final_경기도_DRT비교.ipynb'
dest.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
print(dest)
