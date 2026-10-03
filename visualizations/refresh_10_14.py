"""Rebuild the requested CSVs from ../traffic, keeping unresolved population null."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from rebuild_dong_supply import ROOT, DEFAULT_BOUNDARY, REGION, boundaries, rebuild

PROVINCES = {'서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시',
             '대전광역시', '울산광역시', '세종특별자치시', '경기도', '강원특별자치도',
             '충청북도', '충청남도', '전북특별자치도', '전라남도', '경상북도', '경상남도', '제주특별자치도'}

# Dataset-specific aliases to the supplied boundary vocabulary, not a claim
# that historical population has been redistributed onto current boundaries.
SIDO_ALIASES = {'강원도': '강원특별자치도', '전라북도': '전북특별자치도',
                '광주광역시': '전남광주통합특별시', '전라남도': '전남광주통합특별시'}
PROVINCES |= set(SIDO_ALIASES) | set(SIDO_ALIASES.values())


def resolve_sido(name):
    if pd.isna(name):
        return None
    name = str(name).strip()
    return SIDO_ALIASES.get(name, name)


def match_population(path, boundary):
    raw = pd.read_csv(path, encoding='cp949', dtype=str)
    year = raw.columns[2]
    rows, province, pending = [], None, None
    for i, (name, age, value) in enumerate(raw.itertuples(index=False, name=None), start=2):
        if name in PROVINCES:
            province, pending = name, None
            continue
        if age == '합계' and province:
            if pending is not None:
                raise ValueError('Population row is missing its elderly row.')
            pending = {'province': province, 'dong': name, 'population': value,
                       'source_line': i}
        elif age == '65세이상' and province:
            if pending is None or pending['dong'] != name:
                raise ValueError('Population/elderly row order is inconsistent.')
            rows.append(dict(pending, elderly=value))
            pending = None
    if pending is not None:
        raise ValueError('Trailing population row lacks elderly count.')
    source = pd.DataFrame(rows)
    source = source.rename(columns={'province': 'population_source_province'})
    source['join_province'] = source.population_source_province.map(resolve_sido)
    source['dong'] = source.dong.str.strip()
    keys = ['join_province', 'dong']
    source['source_key_count'] = source.groupby(keys).dong.transform('size')
    target = boundary[REGION].copy()
    target['join_province'] = target.province.map(resolve_sido)
    target['dong'] = target.dong.str.strip()
    target['boundary_key_count'] = target.groupby(keys).dong.transform('size')
    unique_source = source[source.source_key_count == 1]
    candidate = target.merge(unique_source, on=keys, how='left', validate='many_to_one')
    candidate['population_status'] = 'unmatched_name_or_boundary_vintage'
    duplicate_keys = set(map(tuple, source.loc[source.source_key_count > 1, keys].values))
    ambiguous = candidate[keys].apply(tuple, axis=1).isin(duplicate_keys) | (candidate.boundary_key_count > 1)
    candidate.loc[ambiguous, 'population_status'] = 'ambiguous_name'
    matched = candidate.source_line.notna() & ~ambiguous
    candidate.loc[matched, 'population_status'] = 'unique_province_dong_name_match'
    alias_matched = matched & (candidate.population_source_province != candidate.province)
    candidate.loc[alias_matched, 'population_status'] = 'unique_normalized_province_dong_name_match'
    population = candidate.loc[matched, ['dong_code', 'population', 'elderly']].copy()
    accepted_keys = set(map(tuple, candidate.loc[matched, keys].values))
    source['matched'] = source[keys].apply(tuple, axis=1).isin(accepted_keys)
    return population, candidate[REGION + ['population_status', 'source_line', 'population_source_province']], source, year


def draw(boundary, table, column, title, label, path):
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    frame = boundary.merge(table[['dong_code', column]], on='dong_code', validate='one_to_one')
    lo, hi = frame[column].dropna().quantile([.02, .98])
    fig, ax = plt.subplots(figsize=(11, 12))
    frame.plot(column=column, ax=ax, cmap='YlOrRd', vmin=lo, vmax=hi,
               linewidth=.08, edgecolor='white', legend=True,
               legend_kwds={'label': label, 'shrink': .6},
               missing_kwds={'color': '#dddddd'})
    ax.set_title(title, fontsize=17)
    ax.axis('off')
    fig.text(.5, .025, '경계: 2026-07-01 | 회색: 산출 불가 | 색상: 2~98 백분위 범위', ha='center')
    fig.savefig(path, dpi=180, bbox_inches='tight')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT.parent / 'traffic')
    args = parser.parse_args()
    source = args.source_root
    # Archive declares 5179, but coordinates are lon/lat (124..132, 33..39).
    # The terrain collection script identifies this source as EPSG:4326.
    boundary = boundaries(DEFAULT_BOUNDARY, source_crs='EPSG:4326')
    population_files = list(source.glob('연령_및_성별_인구_*.csv'))
    if len(population_files) != 1:
        raise ValueError('Expected exactly one source population CSV.')
    population, status, source_population, year = match_population(population_files[0], boundary)
    # 07 defines the bus-only stop universe (route_type 0, 3, 5); do not include rail/air.
    stops_path = ROOT / 'visualizations/07_bus_stops_2025/bus_stops.csv'
    stops = pd.read_csv(stops_path, dtype={'stop_id': str})
    supply_path = source / 'bus_supply/bus_data/processed/gtfs_stop_supply_2025.csv'
    supply = pd.read_csv(supply_path, dtype={'stop_id': str})
    supply = supply[supply.stop_id.isin(stops.stop_id)].copy()
    if set(stops.stop_id) != set(supply.loc[supply.day_type == 'weekday', 'stop_id']):
        raise ValueError('Bus stop universe and weekday supply universe differ.')
    ten, fourteen, audit = rebuild(boundary, stops, supply, population, allow_missing_population=True)
    ten = ten.merge(status[['dong_code', 'population_status', 'source_line', 'population_source_province']], on='dong_code', validate='one_to_one')
    ten = ten.rename(columns={'source_line': 'population_source_line'})
    for table in [ten, fourteen]:
        table['boundary_date'] = '2026-07-01'
        table['stop_reference_period'] = '2025-03'
    ten['population_year'] = year
    fourteen['population_year'] = year
    fourteen = fourteen.merge(ten[['dong_code', 'population_status']],
                              on='dong_code', how='left', validate='one_to_one')
    fourteen['supply_reference_period'] = '2025-03'
    assert ten.dong_code.is_unique and fourteen.dong_code.is_unique
    assert ten.dong_code.equals(fourteen.dong_code)
    matched_statuses = ['unique_province_dong_name_match', 'unique_normalized_province_dong_name_match']
    assert ten.loc[~ten.population_status.isin(matched_statuses), 'population'].isna().all()
    audit.update({'boundary': str(DEFAULT_BOUNDARY), 'population_source': str(population_files[0]),
                  'supply_source': str(supply_path), 'stops_source': str(stops_path),
                  'boundary_date': '2026-07-01', 'population_year': year, 'supply_period': '2025-03',
                  'boundary_crs_correction': 'Archive metadata EPSG:5179 overridden with EPSG:4326 before projection; coordinates are longitude/latitude, consistent with terrain source documentation.',
                  'population_matching': 'Province aliases normalized to supplied boundary vocabulary, then exact dong name; keys must be unique in both source and boundary AFTER normalization. No district inferred and no ambiguous names allocated.',
                  'province_aliases': SIDO_ALIASES,
                  'population_status_counts': ten.population_status.value_counts().to_dict(),
                  'unmatched_source_population_rows': int((~source_population.matched).sum()),
                  'weekday_missing_headways_kept': int(supply.loc[supply.day_type == 'weekday', 'headway_min'].isna().sum())})
    out10 = ROOT / 'visualizations/10_stop_supply_index'
    out14 = ROOT / 'visualizations/14_dong_supply'
    audit_dir = ROOT / 'visualizations/dong_supply_audit'
    audit_dir.mkdir(exist_ok=True)
    ten.to_csv(out10 / 'stop_supply_by_dong.csv', index=False, encoding='utf-8-sig')
    fourteen.to_csv(out14 / 'dong_supply.csv', index=False, encoding='utf-8-sig')
    status[~status.population_status.isin(matched_statuses)].to_csv(
        audit_dir / 'unresolved_population_regions.csv', index=False, encoding='utf-8-sig')
    source_population[~source_population.matched].to_csv(
        audit_dir / 'unmatched_source_population.csv', index=False, encoding='utf-8-sig')
    (audit_dir / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    draw(boundary, ten, 'per10k', '행정동별 인구 1만 명당 버스 정류장 수', '정류장 / 인구 1만 명', out10 / 'stop_supply_map.png')
    draw(boundary, fourteen, 'departures_per_stop', '행정동별 정류장당 평일 버스 운행 공급량', '운행횟수 / 정류장', out14 / 'dong_supply_map.png')
    print(json.dumps({k: v for k, v in audit.items() if k != 'spatially_unmatched_stops'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
