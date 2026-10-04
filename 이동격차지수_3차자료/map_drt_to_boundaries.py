"""제공된 똑버스 CSV를 최종 지수의 20260701 읍면동 경계 키에 연결한다.

실제 서비스 폴리곤을 생성하거나 면적 비율을 추정하지 않는다.
확인/후보/미해결을 분리하고 역 연계는 생활권 운행과 구분해 보류한다.
"""
import copy
import hashlib
import json
import re
import zipfile
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
OUT = BASE / 'drt_boundary_mapping'


def city_name(value):
    return re.match(r'^(.+?[시군])', value).group(1)


def convert():
    OUT.mkdir(exist_ok=True)
    boundary_path = ROOT / 'data/raw/terrain/emd_boundary_20260701.zip'
    master_path = ROOT / 'data/processed/terrain/slope_score.csv'
    drt_path = ROOT / 'data/raw/경기도_똑버스_운행현황.csv'
    rule_path = BASE / 'drt_boundary_rules.json'
    policy_path = BASE / 'drt_candidate_policy.json'
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    candidate_regions = {(r['city'], r['area']): r for r in policy['regions']}
    with zipfile.ZipFile(boundary_path) as z:
        boundary = json.loads(z.read('emd_20260701.geojson'))
    master = pd.read_csv(master_path)
    master = master.loc[master.sidonm.eq('경기도')].copy()
    features = {}
    for feature in boundary['features']:
        p = feature['properties']
        if p['sidonm'] == '경기도':
            key = f"{p['sidonm']} {p['sggnm']} {p['emdnm']}"
            assert key not in features, f'경계 지역 키 중복: {key}'
            features[key] = feature
    assert set(master['읍면_key']) == set(features), '경계와 지수의 경기도 지역 목록 불일치'
    assert len(master) == 602
    master['emd8'] = master['읍면_key'].map(lambda key: features[key]['properties']['emd8'])
    master['emdcd'] = master['읍면_key'].map(lambda key: features[key]['properties']['emdcd'])
    assert master['emd8'].notna().all() and master['emd8'].is_unique
    master['시군'] = master.sggnm.map(city_name)
    master[['읍면_key','sidonm','sggnm','emdnm','emd8','emdcd']].to_csv(
        OUT / '경기도_기준경계_코드표.csv', index=False, encoding='utf-8-sig')
    lookup = {(r['시군'], r.emdnm): r for _, r in master.iterrows()}
    assert len(lookup) == len(master), '시군+읍면동 키 충돌: 구 단위 구분 필요'
    rules = json.loads(rule_path.read_text(encoding='utf-8'))
    drt = pd.read_csv(drt_path)
    drt = drt.loc[drt['지자체'].ne('계')].copy()
    drt['운행구역ID'] = [f'DRT{i:03d}' for i in range(1, len(drt) + 1)]
    region_rows = []
    for _, row in drt.iterrows():
        city = city_name(row['지자체'])
        rule = candidate_regions.get((city, row['운행구역']))
        fleet = int(re.search(r'\d+', row['운행대수']).group())
        if rule:
            assert fleet == rule['fleet'], '사용자 권역 차량수와 원본 불일치'
        region_rows.append({'운행구역ID':row['운행구역ID'], '시군':city,
                            '원본운행구역':row['운행구역'],
                            '정리권역명':rule['label'] if rule else row['운행구역'],
                            '권역총차량수':fleet, '연계거점':' / '.join(rule['hubs']) if rule else '',
                            '후보관리대상':bool(rule)})
    regions = pd.DataFrame(region_rows)
    assert regions['후보관리대상'].sum() == 9
    regions.to_csv(OUT / '똑버스_운행권역표.csv', index=False, encoding='utf-8-sig')
    edges, unresolved = [], []
    for _, row in drt.iterrows():
        city, original = city_name(row['지자체']), row['운행구역']
        remaining = original
        common = {'운행구역ID': row['운행구역ID'], '시군': city, '원본운행구역': original,
                  '원본운행개시일': row['운행개시일'],
                  '근거확인일': '2026-10-05', '경계기준일': '2026-07-01'}

        def add(target, label, status, method, note, sources):
            assert (city, target) in lookup, f'기준 경계에 없는 대상: {city} {target}'
            m = lookup[(city, target)]
            edges.append({**common, '원본표현': label, '읍면_key': m['읍면_key'],
                          'sggnm': m.sggnm, 'emdnm': target, 'emd8': m.emd8,
                          'emdcd': m.emdcd,
                          '매핑상태': '후보' if (city, original) in candidate_regions else status,
                          '근거상태': status,
                          '후보관리사유': '사용자 지정 9개 권역 잠정 후보 관리' if (city, original) in candidate_regions else '',
                          '변환방식': method,
                          '운행범위': '전역여부 미확인' if method in ('명칭일치','축약명확장','명칭변경') else '하위구역 연결; 실제 서비스 경계 미확인',
                          '면적포함률': None, '근거설명': note,
                          '근거URL': ' | '.join(sources), '원본근거': 'data/raw/경기도_똑버스_운행현황.csv'})

        for rule in sorted(rules, key=lambda r: len(r['label']), reverse=True):
            if rule['city'] == city and rule['label'] in remaining:
                for target in rule['targets']:
                    add(target, rule['label'], rule['status'], rule['method'], rule['note'], rule['sources'])
                remaining = remaining.replace(rule['label'], ' ')
        expansions = {'광교1·2동':'광교1동·광교2동', '은현·남면':'은현면·남면', '남사·이동읍':'남사읍·이동읍'}
        expanded = remaining
        for before, after in expansions.items():
            expanded = expanded.replace(before, after)
        # 제거한 수동규칙 구역을 다시 단순 이름으로 확인 처리하지 않는다.
        for token in sorted(set(re.findall(r'[가-힣0-9]+(?:읍|면|동)(?=$|[\s,·()])', expanded))):
            if (city, token) in lookup:
                add(token, token, '확인', '명칭일치' if token in original else '축약명확장',
                    'CSV에 읍면동 명시. 행정동 전체를 운행한다는 판단은 하지 않음.', [])
                expanded = re.sub(re.escape(token) + r'(?=$|[\s,·()])', ' ', expanded)
        # 단순 권역 제목과 구분기호만 제거하여 누락된 리·역·생활권을 보존한다.
        residual = re.sub(r'서부권|동부권|북부권|남부권|시내권|[\s,·()]+', ' ', expanded).strip()
        if residual and (city, original) in candidate_regions:
            for hub in candidate_regions[(city, original)]['hubs']:
                residual = residual.replace(hub, '').strip()
        if residual:
            unresolved.append({**common, '미해결표현': residual,
                               '이유': '역 연계는 거점 승하차와 권역 운행 구분 필요' if '역' in residual else '대응표 또는 서비스 도형 필요'})
    mapping = pd.DataFrame(edges).drop_duplicates(['운행구역ID','읍면_key','원본표현','매핑상태'])
    mapping.to_csv(OUT / '똑버스_읍면동_대응표.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(unresolved, columns=list(common) + ['미해결표현','이유']).to_csv(
        OUT / '미해결_원본표현.csv', index=False, encoding='utf-8-sig')
    audits = []
    for _, row in drt.iterrows():
        sub = mapping.loc[mapping['운행구역ID'].eq(row['운행구역ID'])]
        pending = [r['미해결표현'] for r in unresolved if r['운행구역ID'] == row['운행구역ID']]
        confirmed = sub.loc[sub['매핑상태'].eq('확인')]
        candidates = sub.loc[sub['매핑상태'].eq('후보')]
        chosen = (city_name(row['지자체']), row['운행구역']) in candidate_regions
        audits.append({**{k:v for k,v in row.to_dict().items() if k != '운행대수'}, '확인_읍면동': ' / '.join(confirmed.emdnm.unique()),
                       '후보_읍면동': ' / '.join(candidates.emdnm.unique()),
                       '추가확인표현': ' / '.join(pending),
                       '행처리상태': '후보 관리' if chosen else '추가확인 필요' if len(candidates) or pending else '행정단위 연결 완료(서비스 경계 미확인)'})
    audit = pd.DataFrame(audits)
    assert len(audit) == len(drt) and audit['운행구역ID'].is_unique
    audit.to_csv(OUT / '원본운행구역별_검토표.csv', index=False, encoding='utf-8-sig')
    audit.loc[audit['행처리상태'].eq('후보 관리')].merge(regions[['운행구역ID','권역총차량수','연계거점','정리권역명']], on='운행구역ID', validate='one_to_one').to_csv(OUT / '후보9개_권역검토표.csv', index=False, encoding='utf-8-sig')
    ranked = pd.read_csv(BASE / 'gyeonggi_drt_comparison/경기도_이동격차순위_DRT대조.csv')
    linked = []
    for _, m in master.iterrows():
        sub = mapping.loc[mapping['읍면_key'].eq(m['읍면_key'])]
        yes = sub.loc[sub['매핑상태'].eq('확인')]
        candidate = sub.loc[sub['매핑상태'].eq('후보')]
        linked.append({'읍면_key':m['읍면_key'], 'emd8':m.emd8, 'emdcd':m.emdcd,
                       '경계기준_DRT연결':'확인' if len(yes) else '후보' if len(candidate) else '미확인',
                       '확인_운행구역ID':' / '.join(yes['운행구역ID'].unique()),
                       '후보_운행구역ID':' / '.join(candidate['운행구역ID'].unique()),
                       '후보연결존재':bool(len(candidate)),
                       '연결_원본운행구역':' / '.join(sub['원본운행구역'].unique()),
                       '경계변환_근거URL':' | '.join(sorted(set(s for s in sub['근거URL'] if s))),
                       '전역운행확인':False})
    link = pd.DataFrame(linked)
    result = ranked.merge(link, on='읍면_key', how='left', validate='one_to_one')
    assert len(result) == 602 and result['emd8'].notna().all()
    result.to_csv(OUT / '경기도_경계기준_DRT비교.csv', index=False, encoding='utf-8-sig')
    result.head(20).to_csv(OUT / '경기도_상위20_경계기준.csv', index=False, encoding='utf-8-sig')
    summaries = []
    for n in (10,20,50,602):
        top = result.head(n)
        old = int(top['DRT대조결과'].eq('운행구역에 읍면동 명시').sum())
        count = int(top['경계기준_DRT연결'].eq('확인').sum())
        summaries.append({'상위N':n, '기존명칭확인':old, '행정단위연결확인':count,
                          '확인비율':count/len(top), '후보만존재':int(top['경계기준_DRT연결'].eq('후보').sum()),
                          '후보연결존재':int(top['후보연결존재'].sum())})
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / '경계변환_전후요약.csv', index=False, encoding='utf-8-sig')
    new_geo = {'type':'FeatureCollection','name':'경기도_분석읍면동_DRT연결_서비스경계아님','features':[]}
    for _, r in result.iterrows():
        f = copy.deepcopy(features[r['읍면_key']])
        f['properties'].update({k: r[k] for k in ['읍면_key','경계기준_DRT연결','연결_원본운행구역','확인_운행구역ID','후보_운행구역ID','후보연결존재']})
        f['properties'].update({'이동격차지수':float(r['이동격차지수']), '경기도순위':int(r['경기도순위_잠정']),
                                'geometry_role':'분석용 행정동 경계; 실제 DRT 운행구역 아님'})
        new_geo['features'].append(f)
    (OUT / '경기도_분석경계_DRT연결.geojson').write_text(json.dumps(new_geo, ensure_ascii=False),encoding='utf-8')
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (boundary_path,master_path,drt_path,rule_path,policy_path)}
    (OUT / '입력검증.json').write_text(json.dumps({'sha256':hashes, '경계일':'2026-07-01',
        '조회일':'2026-10-05','경기도경계수':len(features),'원본운행구역수':len(drt)},ensure_ascii=False,indent=2),encoding='utf-8')
    write_report(result, audit, summary, mapping)
    print(summary.to_string(index=False))
    print('원본 행 처리:', audit['행처리상태'].value_counts().to_dict())
    print('새로 확인:', result.loc[result['경계기준_DRT연결'].eq('확인') & result['DRT대조결과'].ne('운행구역에 읍면동 명시'), ['sggnm','emdnm','경기도순위_잠정']].to_string(index=False))


def write_report(result, audit, summary, mapping):
    lines = ['# 똑버스 운행구역의 분석 읍면동 기준 변환', '',
             '코드가 사용한 `data/raw/terrain/emd_boundary_20260701.zip`의 경기도 602개 경계와 `slope_score.csv`의 지역 키가 일치함을 검증했다. 경계의 `emd8`(행정동 코드)와 `emdcd`(원본 제공 코드)를 보존했다. 서로 다른 코드 체계를 길이만 보고 바꾸지 않았다.', '',
             '**완료한 것은 운행구역 명칭을 분석용 행정단위에 연결하는 작업이다. 실제 운행구역 폴리곤을 복원하거나 포함 면적을 계산한 것은 아니다.** 모든 지역의 전역 운행 여부는 미확인이다.', '',
             '## 결과', '', '| 범위 | 기존 이름 확인 | 변환 후 연결 확인 | 확인 비율 | 후보만 존재 |', '|---|---:|---:|---:|---:|']
    for _, r in summary.iterrows():
        lines.append(f"| 상위 {int(r['상위N'])} | {int(r['기존명칭확인'])} | {int(r['행정단위연결확인'])} | {r['확인비율']:.1%} | {int(r['후보만존재'])} |")
    lines += ['', '## 상위 20개', '', '| 순위 | 지역 | 연결 상태 | 연결 운행구역 |', '|---:|---|---|---|']
    for _, r in result.head(20).iterrows():
        lines.append(f"| {r['경기도순위_잠정']} | {r['sggnm']} {r['emdnm']} | {r['경계기준_DRT연결']} | {r['연결_원본운행구역']} |")
    lines += ['', '## 판정 기준', '',
              '- 확인: 시군+읍면동 명칭 일치, 명시적 축약 확장, 또는 공식 자료로 확인한 소속/명칭변경. 하위구역을 연결해도 읍면동 전역의 운행은 의미하지 않는다.',
              '- 후보: 사용자 지정 9개 권역은 모든 읍면동 연결을 후보로 관리한다. 기존에 일부 확인된 양주2동·백석읍·광적면·은현면·남면도 해당 권역에서는 후보로 집계하되 근거상태에 기존 확인을 보존한다. 후보 목록은 완전한 포함 목록을 보장하지 않는다.',
              '- 미확인: 이 자료로 연결되지 않은 지역. 미운행을 의미하지 않는다.',
              '- 양주역·덕정역은 운행권역표의 연계거점으로 보존하고 읍면동 후보를 추가하지 않았다.',
              '- 차량수는 운행권역표에서 권역당 한 번만 저장한다. 후보9개 검토표는 같은 권역 합계를 보여주는 요약본이다. 읍면동 대응표에는 차량수를 배분하거나 복제하지 않는다.',
              '- 하나의 읍면동에 다른 권역의 확인 연결이 있으면 최종 상태는 확인으로 표시한다. 이 경우에도 후보연결존재와 후보 권역ID를 남겨 후보가 숨겨지지 않도록 한다.',
              '- 원본 CSV의 시점을 유지하면서 행정단위만 2026-07-01 경계에 연결한다. 검색에서 발견한 최신 확장 서비스는 임의 추가하지 않았다. 현재 서비스의 유지 여부와 경계 변동 전체를 검증한 것은 아니다.',
              '', '## 추가 확인이 필요한 운행구역', '', '| 시군 | 원본 구역 | 후보 | 미해결 표현 |', '|---|---|---|---|']
    for _, r in audit.loc[audit['행처리상태'].isin(['추가확인 필요','후보 관리'])].iterrows():
        lines.append(f"| {r['지자체']} | {r['운행구역']} | {r['후보_읍면동']} | {r['추가확인표현']} |")
    lines += ['', '## 근거와 재현', '', '변환 규칙은 `../drt_boundary_rules.json`, 행별 출처는 `똑버스_읍면동_대응표.csv`에 기록했다. 확인일은 2026-10-05이다.', '']
    urls = sorted({u.strip() for s in mapping['근거URL'] for u in s.split(' | ') if u.strip()})
    for i, u in enumerate(urls,1):
        lines.append(f'- [공식 근거 {i}]({u})')
    lines += ['', '`python 이동격차지수_3차자료/map_drt_to_boundaries.py`', '',
              'GeoJSON은 QGIS 등에서 열 수 있는 분석 읍면동 경계이다. 색칠된 행정동 전체를 DRT 서비스 면적으로 해석하면 안 된다. 실제 전부·일부·미포함 판정과 면적 포함률을 만들려면 서비스 경계 도형 또는 좌표가 있는 운행 정류장 목록이 추가로 필요하다. 정류장 좌표만 있어도 면적 커버리지는 별도 정의가 필요하다.', '',
              '지수·가중치는 바꾸지 않았다. 기존 결과 문서의 결측·이상치·가중치 신뢰성 한계는 그대로 적용한다. 연결 확인 비율은 지수 정확도·이용률·면적 커버리지와 다르다.']
    (OUT / '경계변환_결과.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__ == '__main__':
    convert()
