"""경북 비교 결과에서 상주시를 추출한다. 지수와 전국 가중치는 유지한다."""
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'gyeongbuk_drt_comparison/경북_전체_읍면동_DRT비교.csv'
OUT = BASE / 'sangju_drt_comparison'


def main():
    OUT.mkdir(exist_ok=True)
    df = pd.read_csv(SOURCE)
    df = df.loc[df.sggnm.eq('상주시')].copy()
    assert len(df) > 0 and not df.emdnm.duplicated().any()
    df = df.sort_values(['이동격차지수', 'emdnm'], ascending=[False, True])
    df.insert(0, '상주시순위_잠정', df['이동격차지수'].rank(method='min', ascending=False).astype(int))
    df['지역유형'] = df.emdnm.map(lambda name: '읍·면' if name.endswith(('읍', '면')) else '동')
    df.to_csv(OUT / '상주시_전체_DRT비교.csv', index=False, encoding='utf-8-sig')
    summaries = []
    for label, subset in [('전체', df), ('읍·면', df[df.지역유형.eq('읍·면')]), ('동', df[df.지역유형.eq('동')])]:
        n = int(subset.DRT기록있음.sum())
        summaries.append([label, len(subset), n, len(subset)-n, round(100*n/len(subset), 2) if len(subset) else 0])
    for label, fraction in [('상위20%', .2), ('상위50%', .5)]:
        threshold = df.iloc[math.ceil(len(df)*fraction)-1]['이동격차지수']
        subset = df[df['이동격차지수'] >= threshold]
        n = int(subset.DRT기록있음.sum())
        summaries.append([label, len(subset), n, len(subset)-n, round(100*n/len(subset), 2)])
    summary = pd.DataFrame(summaries, columns=['범위', '지역수', 'DRT기록있음', '자료미확인', '기록확인비율_pct'])
    summary.to_csv(OUT / '상주시_요약.csv', index=False, encoding='utf-8-sig')
    columns = ['상주시순위_잠정', '경북순위_잠정', 'emdnm', '이동격차지수', '대조결과', '서비스명', '운행범위']
    table = df[columns].rename(columns={'emdnm': '읍면동'})
    def md(frame):
        clean = frame.fillna('').map(lambda v: f'{v:.4f}' if isinstance(v, float) else str(v))
        return '\n'.join(['| ' + ' | '.join(clean.columns) + ' |', '| ' + ' | '.join(['---']*len(clean.columns)) + ' |'] + ['| ' + ' | '.join(v.replace('|', '/') for v in row) + ' |' for row in clean.values.tolist()])
    missing = df[~df.DRT기록있음].head(5)
    notes = ('기존 전국 지수와 가중치는 유지하고 상주시 내 순위를 추가했다. 상위 비율은 지역 수를 올림하고 경계 점수의 동점을 포함한다. '
             'DRT 기록은 검증본의 시군구·읍면동 명칭을 연결한 결과다. 자료 미확인은 실제 미운행이 아니며, 기록 있음도 읍면동 전역 운행을 보장하지 않는다. '
             '운행범위·출처·신뢰도·비고는 전체 CSV에 보존했다. 최신 운행 여부는 별도 검증하지 않았다. '
             '지수의 기존 결측 대체·이상치·가중치 한계는 유지되며, 인과효과나 도입 전후 개선을 평가한 결과가 아니다.')
    report = ['# 상주시 이동격차지수와 DRT 기록 비교', '', '분석일: 2026-10-06', '', md(summary), '',
              '## 전체 읍면동 비교', '', md(table), '', '## 기록 미확인 지역 중 지수 상위 후보', '',
              md(missing[columns].rename(columns={'emdnm': '읍면동'})), '',
              '위 지역은 실제 운행 여부를 추가 조사할 대상이며 신규 도입 대상으로 확정한 것이 아니다.', '',
              '## 해석 기준', '', notes, '', '## 재현', '', '`python 이동격차지수_3차자료/지역별_DRT비교/compare_sangju_drt.py`']
    (OUT / '상주시_DRT비교_결과.md').write_text('\n'.join(report), encoding='utf-8')
    page = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>상주시 이동격차·DRT 비교</title><style>body{font-family:system-ui;margin:32px;color:#18283b}table{border-collapse:collapse;width:100%;margin:24px 0}td,th{padding:9px;text-align:left;border-bottom:1px solid #ddd}th{background:#edf2f7}input{padding:12px;width:280px}</style><h1>상주시 이동격차지수 × DRT 기록</h1><p>2026-10-06 · 기존 전국 지수 기준 · 상주시 내 잠정 순위</p>' + summary.to_html(index=False) + '<input id="q" placeholder="읍면동·서비스 검색" aria-label="비교표 검색">' + table.fillna('').to_html(index=False, float_format=lambda x:f'{x:.4f}', table_id='regions') + '<p>' + notes + '</p><script>document.getElementById("q").addEventListener("input",e=>document.querySelectorAll("#regions tbody tr").forEach(r=>r.hidden=!r.textContent.includes(e.target.value)));</script></html>'
    (OUT / '상주시_DRT비교.html').write_text(page, encoding='utf-8')
    (OUT / '입력파일_기록.json').write_text(json.dumps({'path': str(SOURCE.relative_to(BASE)), 'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest()}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(summary.to_string(index=False))
    print(table.to_string(index=False))
    print('Status:', df['운영상태'].value_counts().to_dict(), 'Scope:', df['운행범위'].value_counts().to_dict())
    saved = pd.read_csv(OUT / '상주시_전체_DRT비교.csv')
    assert len(saved) == len(df) and int(saved.DRT기록있음.sum()) == int(df.DRT기록있음.sum())


if __name__ == '__main__':
    main()
