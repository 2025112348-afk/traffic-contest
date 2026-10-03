import tempfile
import unittest
from pathlib import Path

import pandas as pd

from refresh_10_14 import match_population


class PopulationMatchingTests(unittest.TestCase):
    def match(self, rows, regions):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'population.csv'
            pd.DataFrame(rows, columns=['지역', '연령', '2025']).to_csv(
                path, encoding='cp949', index=False)
            return match_population(path, pd.DataFrame(
                regions, columns=['dong_code', 'province', 'sigungu', 'dong']))

    def test_alias_matches_and_preserves_original_province(self):
        pop, status, _, _ = self.match([
            ['광주광역시', '합계', '100'], ['계림1동', '합계', '100'],
            ['계림1동', '65세이상', '20']],
            [['1', '전남광주통합특별시', '동구', '계림1동']])
        self.assertEqual(pop.population.tolist(), ['100'])
        self.assertEqual(status.population_source_province.tolist(), ['광주광역시'])
        self.assertEqual(status.population_status.tolist(), ['unique_normalized_province_dong_name_match'])

    def test_alias_collision_between_old_provinces_is_not_allocated(self):
        pop, status, source, _ = self.match([
            ['광주광역시', '합계', '100'], ['중앙동', '합계', '100'], ['중앙동', '65세이상', '20'],
            ['전라남도', '합계', '200'], ['중앙동', '합계', '200'], ['중앙동', '65세이상', '30']],
            [['1', '전남광주통합특별시', '동구', '중앙동']])
        self.assertTrue(pop.empty)
        self.assertEqual(status.population_status.tolist(), ['ambiguous_name'])
        self.assertFalse(source.matched.any())

    def test_districts_cannot_be_inferred_from_unique_source_name(self):
        pop, status, _, _ = self.match([
            ['경기도', '합계', '100'], ['중앙동', '합계', '100'], ['중앙동', '65세이상', '20']],
            [['1', '경기도', '가시', '중앙동'], ['2', '경기도', '나시', '중앙동']])
        self.assertTrue(pop.empty)
        self.assertEqual(status.population_status.tolist(), ['ambiguous_name'] * 2)


if __name__ == '__main__':
    unittest.main()
