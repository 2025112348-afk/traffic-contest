"""Rebuild 10/14 on one explicitly dated administrative boundary.

See DONG_SUPPLY_REBUILD.md for input contracts. Existing outputs are untouched
unless all inputs pass validation; default output is a separate review folder.
"""
import argparse
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOUNDARY = ROOT / 'data/raw/terrain/emd_boundary_20260701.zip'
REGION = ['dong_code', 'province', 'sigungu', 'dong']


def boundaries(path, source_crs=None):
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.endswith('.geojson')]
            if len(names) != 1:
                raise ValueError('Boundary archive must contain exactly one GeoJSON.')
            data = json.loads(archive.read(names[0]))
        crs = data.get('crs')
        if isinstance(crs, dict):
            crs = crs.get('properties', {}).get('name')
        if not crs:
            raise ValueError('Boundary CRS must be explicit.')
        frame = gpd.GeoDataFrame.from_features(data['features'], crs=crs)
    else:
        frame = gpd.read_file(path)
    if source_crs:
        frame = frame.set_crs(source_crs, allow_override=True)
    xmin, ymin, xmax, ymax = frame.total_bounds
    if frame.crs and frame.crs.is_projected and -180 <= xmin <= xmax <= 180 and -90 <= ymin <= ymax <= 90:
        raise ValueError('Boundary coordinates look geographic but metadata says projected; verify and specify source CRS.')
    frame = frame.rename(columns={'emdcd': 'dong_code', 'sidonm': 'province',
                                  'sggnm': 'sigungu', 'emdnm': 'dong'})
    frame = frame[REGION + ['geometry']].copy()
    frame['dong_code'] = frame.dong_code.astype(str)
    if frame[REGION].isna().any().any() or frame.dong_code.duplicated().any():
        raise ValueError('Boundary region identifiers must be complete and unique.')
    if not frame.dong_code.str.fullmatch(r'\d{10}').all():
        raise ValueError('dong_code must be the 10-digit administrative code (emdcd).')
    if frame.crs is None or (~frame.geometry.is_valid).any() or frame.geometry.is_empty.any():
        raise ValueError('Boundary CRS/geometries are missing or invalid.')
    return frame.to_crs(5179)


def numeric(frame, columns):
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors='raise')
        if not np.isfinite(frame[column]).all() or (frame[column] < 0).any():
            raise ValueError(f'{column} must contain finite nonnegative values.')


def rebuild(boundary, stops, supply, population, allow_missing_population=False):
    """Return both tables and audit; reject ambiguous spatial assignments."""
    regions = boundary[REGION]
    if stops.stop_id.isna().any() or stops.stop_id.duplicated().any():
        raise ValueError('Stop IDs must be unique and non-null.')
    numeric(stops, ['stop_lat', 'stop_lon'])
    if (~stops.stop_lat.between(-90, 90)).any() or (~stops.stop_lon.between(-180, 180)).any():
        raise ValueError('Invalid WGS84 stop coordinates.')
    points = gpd.GeoDataFrame(stops, geometry=gpd.points_from_xy(
        stops.stop_lon, stops.stop_lat), crs=4326).to_crs(boundary.crs)
    joined = gpd.sjoin(points, boundary[['dong_code', 'geometry']],
                       how='left', predicate='intersects')
    if joined.stop_id.duplicated().any():
        raise ValueError('Some stops intersect multiple regions; resolve boundary ties first.')
    matched = joined.dropna(subset=['dong_code'])
    if matched.empty:
        raise ValueError('No stops matched the boundary; check CRS and coverage before writing.')
    counts = matched.groupby('dong_code').stop_id.nunique().rename('stops')

    if population.dong_code.isna().any() or population.dong_code.duplicated().any():
        raise ValueError('Population requires exactly one row per administrative dong_code.')
    numeric(population, ['population', 'elderly'])
    if (population.elderly > population.population).any():
        raise ValueError('Elderly population exceeds total population.')
    if not set(population.dong_code).issubset(set(regions.dong_code)):
        raise ValueError('Population contains codes outside the selected boundary.')
    if not allow_missing_population and set(population.dong_code) != set(regions.dong_code):
        raise ValueError('Population codes must exactly match the selected boundary. '
                         'Supply a documented date/code crosswalk upstream if needed.')
    ten = regions.merge(population[['dong_code', 'population', 'elderly']],
                        on='dong_code', how='left', validate='one_to_one')
    ten = ten.join(counts, on='dong_code')
    ten['stops'] = ten.stops.fillna(0).astype(int)
    denominator = ten.population.where(ten.population > 0)
    ten['aging'] = ten.elderly / denominator * 100
    ten['per10k'] = ten.stops / denominator * 10000

    weekday = supply.loc[supply.day_type == 'weekday'].copy()
    if weekday.empty or weekday.stop_id.isna().any() or weekday.stop_id.duplicated().any():
        raise ValueError('Supply needs one weekday row per stop, including missing headways.')
    numeric(weekday, ['departures'])
    weekday['headway_min'] = pd.to_numeric(weekday.headway_min, errors='raise')
    present = weekday.headway_min.dropna()
    if (~np.isfinite(present)).any() or (present < 0).any():
        raise ValueError('Headways must be nonnegative finite values or null.')
    missing_coords = weekday.loc[~weekday.stop_id.isin(stops.stop_id), 'stop_id']
    if len(missing_coords):
        raise ValueError(f'{len(missing_coords)} supply stops lack coordinates; use complete stops.txt.')
    weekday = weekday.merge(joined[['stop_id', 'dong_code']], on='stop_id',
                            validate='one_to_one')
    agg = weekday.dropna(subset=['dong_code']).groupby('dong_code').agg(
        departures=('departures', 'sum'), stops=('stop_id', 'nunique'),
        headway_min=('headway_min', 'mean'))
    fourteen = regions.join(agg, on='dong_code')
    fourteen[['departures', 'stops']] = fourteen[['departures', 'stops']].fillna(0)
    fourteen['stops'] = fourteen.stops.astype(int)
    fourteen['departures_per_stop'] = fourteen.departures / fourteen.stops.where(fourteen.stops > 0)
    audit = {'regions': len(regions), 'coordinate_stops': len(stops),
             'spatially_unmatched_stops': joined.loc[joined.dong_code.isna(), 'stop_id'].tolist(),
             'weekday_stops': len(weekday),
             'unmatched_weekday_departures': float(weekday.loc[weekday.dong_code.isna(), 'departures'].sum()),
             'matched_weekday_departures': float(fourteen.departures.sum())}
    assert ten.stops.sum() == len(matched)
    assert np.isclose(fourteen.departures.sum() + audit['unmatched_weekday_departures'], weekday.departures.sum())
    return ten, fourteen, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boundary', type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument('--boundary-crs', help='Explicit correction for verified incorrect source CRS metadata')
    parser.add_argument('--boundary-date', required=True)
    parser.add_argument('--population', type=Path, required=True)
    parser.add_argument('--population-date', required=True)
    parser.add_argument('--stops', type=Path, required=True)
    parser.add_argument('--supply', type=Path, required=True)
    parser.add_argument('--supply-date', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'visualizations/rebuilt_dong_supply')
    args = parser.parse_args()
    boundary = boundaries(args.boundary, args.boundary_crs)
    ten, fourteen, audit = rebuild(
        boundary, pd.read_csv(args.stops, dtype={'stop_id': str}),
        pd.read_csv(args.supply, dtype={'stop_id': str}),
        pd.read_csv(args.population, dtype={'dong_code': str}))
    audit['inputs'] = {k: str(v) for k, v in vars(args).items()}
    args.output.mkdir(parents=True, exist_ok=True)
    ten.to_csv(args.output / 'stop_supply_by_dong.csv', index=False, encoding='utf-8-sig')
    fourteen.to_csv(args.output / 'dong_supply.csv', index=False, encoding='utf-8-sig')
    (args.output / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(ten)} regions to {args.output}')


if __name__ == '__main__':
    main()
