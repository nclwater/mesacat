from mesacat.model import EvacuationModel
from unittest import TestCase
import geopandas as gpd
import os

sample_data = os.path.join(os.path.dirname(__file__), 'sample_data')
outputs = os.path.join(os.path.dirname(__file__), 'outputs')
if not os.path.exists(outputs):
    os.mkdir(outputs)

osm_data = os.path.join(sample_data, 'bwaise.osm')

extents = gpd.read_file(os.path.join(sample_data, 'extents.gpkg'))
extents = extents[(extents.threshold == 0.1) & (extents.rainfall == 20) & (extents.duration == 3600 * 6)]


class TestEvacuationModel(TestCase):

    @classmethod
    def setUpClass(cls):

        cls.model = EvacuationModel(osm_file=osm_data, seed=1, hazard=extents, target_node=6996374452)
        cls.steps = 10

    def test_create_movie(self):

        self.model.run(self.steps)
        self.model.create_movie(os.path.join(outputs, 'model.mp4'))

    def test_run(self):
        self.model.run(self.steps)
