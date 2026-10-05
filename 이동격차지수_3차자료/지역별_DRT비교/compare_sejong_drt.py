"""세종시 표기를 통일하고 서비스 중복을 지역 단위로 묶어 비교한다."""
import hashlib
import json
import math

import pandas as pd

from compare_gyeongbuk_drt import BASE, INDEX, DRT, read_sheet

OUT = BASE / '지역별_DRT비교/sejong_drt_comparison'


def main():
    OUT.mkdir(exist_ok=True)
    index = pd.read_csv(INDEX)
    index = index[index.sidonm.eq('세종특별자치시')].copy()
    drt = read_sheet(DRT)
    drt = drt[drt['시도'].eq('세종특별자치시')].copy()
    assert set(index.sggnm) == {'세종시'}
    assert set(drt['시군구']) == {'세종특별자치시'}
    assert not index.emdnm.duplicated().any()
    drt['연결시군구'] = '세종시'
    drt.to_csv(OUT / '세종_DRT원자료.csv', index=False, encoding='utf-8-sig')
    fields = ['서비스명', '유형', '운행범위', '운영상태', '신뢰도', '행정동코드', '코드매칭', '출처URL', '출처게시일', '비고']
    grouped = drt.groupby('읍면동', as_index=False)[fields].agg(lambda s: ' | '.join(dict.fromkeys(v for v in s if v)))
    unmatched = grouped[~grouped['읍면동'].isin(index.emdnm)]
    unmatched.to_csv(OUT / '세종_DRT미연결.csv', index=False, encoding='utf-8-sig')
    df = index.merge(grouped, left_on='emdnm', right_on='읍면동', how='left', validate='one_to_one', indicator=True)
    df['DRT기록있음'] = df['_merge'].eq('both')
    df['대조결과'] = df.DRT기록있음.map({True: '검증본 운행기록 있음', False: '검증본에서 미확인'})
    df['세종시순위_잠정'] = df['이동격차지수'].rank(method='min', ascending=False).astype(int)
    df['지역유형'] = df.emdnm.map(lambda s: '읍·면' if s.endswith(('읍', '면')) else '동')
    df = df.drop(columns=['_merge', '읍면동']).sort_values('세종시순위_잠정')
    df.to_csv(OUT / '세종시_전체_DRT비교.csv', index=False, encoding='utf-8-sig')
    subsets = [('전체', df), ('읍·면', df[df.지역유형.eq('읍·면')]), ('동', df[df.지역유형.eq('동')])]
    for label, fraction in [('상위20%', .2), ('상위50%', .5)]:
        cutoff = df.iloc[math.ceil(len(df)*fraction)-1]['이동격차지수']
        subsets.append((label, df[df['이동격차지수'] >= cutoff]))
    summary = pd.DataFrame([{'범위': label, '지역수': len(s), 'DRT기록있음': int(s.DRT기록있음.sum()),
                             '자료미확인': int((~s.DRT기록있음).sum()), '기록확인비율_pct': round(s.DRT기록있음.mean()*100, 2)} for label, s in subsets])
    summary.to_csv(OUT / '세종시_요약.csv', index=False, encoding='utf-8-sig')
    columns = ['세종시순위_잠정', 'emdnm', '이동격차지수', '대조결과', '서비스명', '운행범위']
    table = df[columns].rename(columns={'emdnm': '읍면동'})
    def md(frame):
        values = frame.fillna('').map(lambda v: f'{v:.4f}' if isinstance(v, float) else str(v))
        return '\n'.join(['| ' + ' | '.join(values.columns) + ' |', '| ' + ' | '.join(['---']*len(values.columns)) + ' |'] + ['| ' + ' | '.join(v.replace('|', '/') for v in row) + ' |' for row in values.values.tolist()])
    notes = [
        '기존 전국 정규화·가중치·지수를 유지하고 세종시 내 순위를 추가했다. 분석 대상은 저장된 지수의 24개 지역이며 최신 행정구역 전체를 별도 검증한 결과는 아니다.',
        '세종시로 범위를 제한한 뒤 DRT 시군구 표기 세종특별자치시를 지수의 세종시와 연결하고 읍면동 명칭을 정확 대조했다. 실제 서비스 경계·행정동 코드의 별도 검증은 하지 않았다.',
        'DRT 10행 중 조치원읍의 두 서비스는 지역 집계에서 한 번만 센다. 원자료 행별 출처·상태·범위는 세종_DRT원자료.csv에 보존했다.',
        '두루타 기록에는 고정노선형·노선예약형·실시간 호출형이 함께 포함된다. 이번 집계는 제공된 검증본의 서비스 범위를 그대로 사용하며 순수 실시간 호출형만을 뜻하지 않는다.',
        '운행기록 있음은 자료상 기록이며 최신 운행 여부를 웹으로 재확인하지 않았다. 일부 리·마을 또는 범위 불명 기록이므로 읍면동 전역 운행을 뜻하지 않는다.',
        '자료 미확인은 실제 미운행을 뜻하지 않는다. 연기면과 동 지역에 대한 운행 여부는 추가 조사해야 한다.',
        '상위 비율은 지역 수에 비율을 곱해 올림하고 경계점수 동점을 포함한다. 기록확인비율은 인구·면적 커버리지나 이용률이 아니다.',
        '지수는 잠정 결과이며 기존 전처리·이상치·가중치 한계가 유지된다. 자료별 기준시점이 달라 DRT의 도입 전후 효과나 인과관계를 평가할 수 없다.',
    ]
    report = ['# 세종시 이동격차지수와 DRT 기록 비교', '', '분석일: 2026-10-06', '',
              f'지수 {len(index)}개 지역, DRT {len(drt)}행·{len(grouped)}개 지역, 미연결 {len(unmatched)}개.', '',
              md(summary), '', '## 주요 결과', '',
              '상위 5개 지역에는 모두 DRT 기록이 있다. 읍·면 10개 중 9개에 기록이 있고, 연기면(시내 7위)은 미확인이다. 동 지역 14개는 모두 미확인이다. 도시·농촌 구성 차이를 고려해 전체 비율과 읍·면 비율을 함께 해석한다.', '',
              '## 전체 비교', '', md(table), '', '## 해석 기준', '', *['- ' + n for n in notes], '',
              '## 재현', '', '`python 이동격차지수_3차자료/지역별_DRT비교/compare_sejong_drt.py`']
    (OUT / '세종시_DRT비교_결과.md').write_text('\n'.join(report), encoding='utf-8')
    page = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>세종시 이동격차·DRT 비교</title><style>body{font-family:system-ui;margin:32px;color:#18283b}table{border-collapse:collapse;width:100%;margin:24px 0}td,th{padding:9px;text-align:left;border-bottom:1px solid #ddd}th{background:#edf2f7}input{padding:12px;width:280px}</style><h1>세종시 이동격차지수 × DRT 기록</h1><p>기존 전국 지수 기준 · 세종시 내 잠정 순위 · 자료 미확인은 미운행을 뜻하지 않습니다.</p>' + summary.to_html(index=False) + '<input id="q" placeholder="읍면동·서비스 검색" aria-label="비교표 검색">' + table.fillna('').to_html(index=False, float_format=lambda x:f'{x:.4f}', table_id='regions') + '<h2>해석 기준</h2><ul>' + ''.join('<li>'+n+'</li>' for n in notes) + '</ul><script>document.getElementById("q").addEventListener("input",e=>document.querySelectorAll("#regions tbody tr").forEach(r=>r.hidden=!r.textContent.includes(e.target.value)));</script></html>'
    (OUT / '세종시_DRT비교.html').write_text(page, encoding='utf-8')
    (OUT / '입력파일_기록.json').write_text(json.dumps([{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [INDEX, DRT]], ensure_ascii=False, indent=2), encoding='utf-8')
    assert len(df) == len(index) and int(df.DRT기록있음.sum()) == len(grouped)-len(unmatched)
    saved = pd.read_csv(OUT / '세종시_전체_DRT비교.csv')
    assert len(saved) == len(df) and not saved.emdnm.duplicated().any()
    print(summary.to_string(index=False))
    print(table.head(12).to_string(index=False))
    print('Unmatched:', len(unmatched), 'Missing scores:', int(df[[c for c in df if c.endswith('_취약점수')]].isna().any(axis=1).sum()))


if __name__ == '__main__':
    main()
