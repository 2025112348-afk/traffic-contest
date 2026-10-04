"""최종 노트북의 eupmyeon_master를 받아 경기도와 똑버스 CSV를 비교한다."""
import re
from pathlib import Path
import pandas as pd


def compare_gyeonggi_drt(master, drt, output_dir='gyeonggi_drt_comparison'):
    required = ['sidonm', 'sggnm', 'emdnm', '이동격차지수']
    missing = set(required) - set(master.columns)
    if missing:
        raise ValueError(f'최종 지수 계산을 먼저 실행하세요. 누락 열: {missing}')
    gg = master.loc[master['sidonm'].eq('경기도')].copy()
    if gg.empty:
        raise ValueError('경기도 행이 없습니다.')
    # 전국에서 계산된 점수와 가중치를 유지한 채 경기도만 추출한다.
    gg['비교_시군'] = gg['sggnm'].str.extract(r'^(.+?[시군])', expand=False)
    gg['경기도순위_잠정'] = gg['이동격차지수'].rank(method='min', ascending=False).astype('Int64')
    score_cols = [c for c in master.columns if c.endswith('_취약점수')]
    gg['결측항목'] = gg[score_cols].apply(lambda row: ', '.join(row.index[row.isna()]), axis=1)
    gg['순위주의'] = gg['결측항목'].ne('')
    gg['결측없는지역내순위'] = gg.loc[~gg['순위주의'], '이동격차지수'].rank(method='min', ascending=False).astype('Int64')
    drt = drt.loc[drt['지자체'].ne('계')].copy()
    drt['비교_시군'] = drt['지자체'].str.extract(r'^(.+?[시군])', expand=False)
    # 원문에 읍/면 접미사가 생략된 두 표현만 명시적으로 확장한다.
    expansions = {'은현·남면·덕정역': '은현면·남면·덕정역', '남사·이동읍': '남사읍·이동읍',
                  '광교1·2동': '광교1동·광교2동'}
    def tokens(area):
        area = expansions.get(str(area), str(area))
        return set(re.findall(r'[가-힣0-9]+(?:읍|면|동)(?=$|[\s,·()])', area))
    drt['명시지역'] = drt['운행구역'].map(tokens)
    def match(row):
        city_rows = drt.loc[drt['비교_시군'].eq(row['비교_시군'])]
        hits = city_rows.loc[city_rows['명시지역'].map(lambda x: row['emdnm'] in x)]
        if len(hits):
            status = '운행구역에 읍면동 명시'
        elif len(city_rows):
            status = '읍면동 미확인(해당 시군 운행 기록 있음)'
        else:
            status = '제공 CSV에 해당 시군 기록 없음'
        return pd.Series({
            'DRT대조결과': status,
            '일치_운행구역': ' / '.join(hits['운행구역'].astype(str)),
            '일치_운행개시일': ' / '.join(hits['운행개시일'].astype(str)),
            '시군전체_운행구역': ' / '.join(city_rows['운행구역'].astype(str)),
        })
    gg = pd.concat([gg, gg.apply(match, axis=1)], axis=1)
    gg = gg.sort_values('이동격차지수', ascending=False)
    front = ['경기도순위_잠정', 'sggnm', 'emdnm', '이동격차지수', 'DRT대조결과',
             '일치_운행구역', '일치_운행개시일', '순위주의', '결측항목', '결측없는지역내순위']
    gg = gg[front + [c for c in gg.columns if c not in front]]
    summaries = []
    for label, subset in [('전체', gg), ('결측없는지역', gg.loc[~gg['순위주의']])]:
        for k in (10, 20, 50):
            top = subset.head(k)
            confirmed = top['DRT대조결과'].eq('운행구역에 읍면동 명시').sum()
            summaries.append({'대상': label, '상위N': k, '실제지역수': len(top),
                              '읍면동명시운행지역수': int(confirmed),
                              '명시확인비율': confirmed / len(top) if len(top) else float('nan'),
                              '결측포함지역수': int(top['순위주의'].sum())})
    summary = pd.DataFrame(summaries)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    gg.to_csv(output / '경기도_이동격차순위_DRT대조.csv', index=False, encoding='utf-8-sig')
    gg.head(20).to_csv(output / '경기도_상위20_DRT대조.csv', index=False, encoding='utf-8-sig')
    summary.to_csv(output / '경기도_상위권_DRT요약.csv', index=False, encoding='utf-8-sig')
    return gg, summary
