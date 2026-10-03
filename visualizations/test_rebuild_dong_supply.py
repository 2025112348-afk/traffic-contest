import unittest

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from rebuild_dong_supply import rebuild


class RebuildTests(unittest.TestCase):
    def setUp(self):
        self.boundary = gpd.GeoDataFrame({
            'dong_code': ['1111053000', '1114053000'],
            'province': ['same', 'same'], 'sigungu': ['a', 'b'],
            'dong': ['duplicate name', 'duplicate name']},
            geometry=[box(126, 37, 127, 38), box(127, 37, 128, 38)], crs=4326)
        self.stops = pd.DataFrame({'stop_id': ['a', 'b', 'outside'],
                                   'stop_lat': [37.5, 37.5, 39],
                                   'stop_lon': [126.5, 127.5, 129]})
        self.supply = pd.DataFrame({'stop_id': ['a', 'b', 'outside'],
                                    'day_type': ['weekday'] * 3,
                                    'departures': [10, 20, 3],
                                    'headway_min': [None, 5, 10]})
        self.population = pd.DataFrame({'dong_code': ['1111053000', '1114053000'],
                                        'population': [100, 200], 'elderly': [10, 20]})

    def test_same_name_regions_remain_separate_and_totals_conserved(self):
        ten, fourteen, audit = rebuild(self.boundary, self.stops, self.supply, self.population)
        self.assertEqual(ten.population.tolist(), [100, 200])
        self.assertEqual(fourteen.departures.tolist(), [10, 20])
        self.assertEqual(audit['unmatched_weekday_departures'], 3)
        self.assertTrue(pd.isna(fourteen.headway_min.iloc[0]))

    def test_missing_population_stays_null_and_zero_stops_remain(self):
        ten, fourteen, _ = rebuild(self.boundary, self.stops.iloc[[0]],
                                   self.supply.iloc[[0]], self.population.iloc[[0]], True)
        self.assertTrue(pd.isna(ten.population.iloc[1]))
        self.assertEqual(ten.stops.iloc[1], 0)
        self.assertEqual(fourteen.departures.iloc[1], 0)
        self.assertTrue(pd.isna(fourteen.departures_per_stop.iloc[1]))

    def test_shared_boundary_point_rejected(self):
        stops = self.stops.copy()
        stops.loc[0, 'stop_lon'] = 127
        with self.assertRaisesRegex(ValueError, 'multiple regions'):
            rebuild(self.boundary, stops, self.supply, self.population)

    def test_missing_supply_coordinates_rejected(self):
        with self.assertRaisesRegex(ValueError, 'lack coordinates'):
            rebuild(self.boundary, self.stops.iloc[[0]], self.supply, self.population)


if __name__ == '__main__':
    unittest.main()
