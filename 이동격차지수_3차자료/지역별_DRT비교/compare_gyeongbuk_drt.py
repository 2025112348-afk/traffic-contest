"""저장된 전국 지수를 유지하여 경북과 검증본 DRT를 비교한다."""
import hashlib
import html
import json
import math
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent
OUT = BASE / '지역별_DRT비교/gyeongbuk_drt_comparison'
INDEX = BASE / 'gyeonggi_drt_comparison/전국_최종지수_재계산.csv'
DRT = ROOT / 'DRT_버스형_읍면동_검증본.xlsx'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_sheet(path):
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(t.text or '' for t in item.findall('.//s:t', NS))
                       for item in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        sheet = next(s for s in wb.find('s:sheets', NS) if s.get('name') == '읍면동_DRT_상중')
        rel_id = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = next(r.get('Target') for r in rels if r.get('Id') == rel_id)
        member = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        rows = []
        for row in ET.fromstring(z.read(member)).findall('s:sheetData/s:row', NS):
            values = {}
            for c in row:
                col = ''.join(x for x in c.get('r') if x.isalpha())
                value = c.findtext('s:v', default='', namespaces=NS)
                if c.get('t') == 's':
                    value = strings[int(value)]
                elif c.get('t') == 'inlineStr':
                    value = ''.join(t.text or '' for t in c.findall('.//s:t', NS))
                values[col] = value
            rows.append(values)
        headers = rows.pop(0)
        return pd.DataFrame([{label: row.get(col, '') for col, label in headers.items()} for row in rows])


def main():
    OUT.mkdir(exist_ok=True)
    index = pd.read_csv(INDEX)
    gb = index.loc[index.sidonm.eq('경상북도')].copy()
    drt = read_sheet(DRT)
    drt = drt.loc[drt['시도'].eq('경상북도')].copy()
    keys = ['sggnm', 'emdnm']
    assert not gb.duplicated(keys).any()
    score_cols = [c for c in gb if c.endswith('_취약점수')]
    gb['입력결측주의'] = gb[score_cols].isna().any(axis=1)
    gb['경북순위_잠정'] = gb['이동격차지수'].rank(method='min', ascending=False).astype(int)
    drt['sggnm'] = drt['시군구'].str.strip()
    drt['emdnm'] = drt['읍면동'].str.strip()
    fields = ['서비스명', '유형', '운행범위', '운영상태', '신뢰도', '행정동코드', '코드매칭', '출처URL', '출처게시일', '비고']
    grouped = drt.groupby(keys, as_index=False)[fields].agg(lambda s: ' | '.join(dict.fromkeys(str(v) for v in s if str(v))))
    result = gb.merge(grouped, on=keys, how='left', validate='one_to_one', indicator=True)
    result['DRT기록있음'] = result['_merge'].eq('both')
    result['대조결과'] = result['DRT기록있음'].map({True: '검증본 운행기록 있음', False: '검증본에서 미확인'})
    result = result.drop(columns='_merge').sort_values(['경북순위_잠정', 'sggnm', 'emdnm'])
    unmatched = grouped.merge(gb[keys], on=keys, how='left', indicator=True).query('_merge == "left_only"')
    assert len(result) == len(gb)
    result.to_csv(OUT / '경북_전체_읍면동_DRT비교.csv', index=False, encoding='utf-8-sig')
    drt.to_csv(OUT / '경북_DRT원자료.csv', index=False, encoding='utf-8-sig')
    unmatched.to_csv(OUT / '경북_DRT미연결.csv', index=False, encoding='utf-8-sig')
    summaries = []
    for label, fraction in [('상위10%', .1), ('상위20%', .2), ('전체', 1)]:
        target = math.ceil(len(result) * fraction)
        threshold = result.iloc[target - 1]['이동격차지수']
        subset = result[result['이동격차지수'] >= threshold]
        n = int(subset['DRT기록있음'].sum())
        summaries.append({'범위': label, '읍면동수': len(subset), 'DRT기록있음': n,
                          '자료미확인': len(subset) - n, '기록확인비율_pct': round(n / len(subset) * 100, 2)})
        if label == '상위20%':
            subset.to_csv(OUT / '경북_상위20퍼센트_DRT비교.csv', index=False, encoding='utf-8-sig')
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / '경북_상위권요약.csv', index=False, encoding='utf-8-sig')
    counties = result.groupby('sggnm').agg(읍면동수=('emdnm', 'size'), 평균지수=('이동격차지수', 'mean'), DRT기록있음=('DRT기록있음', 'sum'))
    counties['기록확인비율_pct'] = 100 * counties['DRT기록있음'] / counties['읍면동수']
    counties.sort_values('평균지수', ascending=False).to_csv(OUT / '경북_시군요약.csv', encoding='utf-8-sig')
    display_cols = ['경북순위_잠정', 'sggnm', 'emdnm', '이동격차지수', '대조결과', '서비스명', '운행범위']
    def md_table(frame):
        clean = frame.fillna('').map(lambda v: str(round(v, 4)) if isinstance(v, float) else str(v))
        return '\n'.join(['| ' + ' | '.join(clean.columns) + ' |', '| ' + ' | '.join(['---'] * len(clean.columns)) + ' |'] + ['| ' + ' | '.join(v.replace('|', '/') for v in row) + ' |' for row in clean.values.tolist()])
    notes = [
        '기존 전국 정규화·엔트로피 가중치·지수를 유지하고 경북 내에서 순위를 매겼다. 경북만으로 지수를 재계산하지 않았다.',
        '시도·시군구·읍면동 명칭의 정확 일치로 연결했다. 코드와 실제 서비스 경계를 검증한 결과는 아니다. 원자료 코드·출처·비고는 비교표에 보존했다.',
        '운행기록 있음은 제공된 검증본에 기록이 있다는 뜻이다. 현재 운행 여부를 웹으로 재검증하지 않았으며, 기록이 없는 곳을 미운행으로 판단하지 않는다.',
        '상위 비율은 읍면동 수에 비율을 곱해 올림한 뒤 경계 점수의 동점을 모두 포함한다. 지역별 기록확인비율은 인구·면적 커버리지나 이용률이 아니다.',
        '읍면동 일부 운행·운행범위 불명도 기록 있음으로 분류했다. 상세 범위는 원자료 열을 확인해야 한다.',
        '지수는 잠정 결과다. 원본의 결측 처리·대체값·이상치·가중치 한계가 유지된다. 시군 평균은 읍면동 단순평균으로 인구가중 평균이 아니다.',
        'DRT 조사는 원본 안내 기준 2026-09-28~2026-10-01이며 지수 입력은 자료별 시점이 다르다. 도입 전후 효과나 인과관계를 평가하지 않는다.',
    ]
    report = ['# 경상북도 이동격차지수와 DRT 기록 비교', '',
              f'분석일: 2026-10-06. 지수 {len(gb)}개 읍면동, DRT {len(drt)}행·{len(grouped)}개 지역, 명칭 연결 {int(result.DRT기록있음.sum())}개, 미연결 {len(unmatched)}개.',
              f'지수 구성 취약점수에 결측이 남은 지역: {int(gb.입력결측주의.sum())}개. 이 수는 이미 대체된 결측까지 포함하지 않는다.', '',
              '## 상위권과 전체 비교', '', md_table(summary), '', '## 경북 상위 20개', '',
              md_table(result.head(20)[display_cols]), '', '## DRT 기록이 있는 지역 중 지수 상위 10개', '',
              md_table(result[result.DRT기록있음].head(10)[display_cols]), '', '## 해석 기준', '',
              *['- ' + note for note in notes], '', '## 재현', '', '`python 이동격차지수_3차자료/지역별_DRT비교/compare_gyeongbuk_drt.py`']
    (OUT / '경북_DRT비교_결과.md').write_text('\n'.join(report), encoding='utf-8')
    cards = ''.join(f'<div><b>{r["범위"]}</b><br>{r["DRT기록있음"]}/{r["읍면동수"]}개 기록 확인<br>{r["기록확인비율_pct"]}%<progress max="100" value="{r["기록확인비율_pct"]}"></progress></div>' for r in summaries)
    page = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>경북 이동격차·DRT 비교</title><style>body{font-family:system-ui;margin:32px;color:#18283b}section{display:flex;gap:20px}section div{background:#eef4fa;padding:20px;flex:1}progress{display:block;width:100%;margin-top:12px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}th{background:#edf2f7;position:sticky;top:0}input{padding:12px;margin:16px 0;width:320px}</style><h1>경북 이동격차지수 × DRT 기록</h1><p>기존 전국 지수 기준 · 읍면동 단위 · 잠정 순위</p><section>' + cards + '</section><p>자료 미확인은 미운행을 뜻하지 않습니다. 기록 확인 비율은 서비스 면적·인구 커버리지가 아닙니다.</p><input id="q" placeholder="시군·읍면동·서비스명 검색" aria-label="비교표 검색">' + result[display_cols].fillna('').to_html(index=False, float_format=lambda v: f'{v:.4f}', table_id='regions') + '<h2>해석 기준</h2><ul>' + ''.join('<li>' + html.escape(n) + '</li>' for n in notes) + '</ul><script>document.getElementById("q").addEventListener("input",e=>{document.querySelectorAll("#regions tbody tr").forEach(r=>r.hidden=!r.textContent.includes(e.target.value))});</script></html>'
    (OUT / '경북_DRT비교.html').write_text(page, encoding='utf-8')
    (OUT / '입력파일_기록.json').write_text(json.dumps([{'path': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [INDEX, DRT]], ensure_ascii=False, indent=2), encoding='utf-8')
    print(summary.to_string(index=False))
    print(result.head(10)[display_cols].to_string(index=False))
    print('Missing scores:', int(gb.입력결측주의.sum()), 'Unmatched:', len(unmatched))


if __name__ == '__main__':
    main()
