from mesacat.model import EvacuationModel
from unittest import TestCase
import geopandas as gpd
import os

sample_data = os.path.join(os.path.dirname(__file__), 'sample_data')
outputs = os.path.join(os.path.dirname(__file__), 'outputs')
if not os.path.exists(outputs):
    os.mkdir(outputs)

extents = gpd.read_file(os.path.join(sample_data, 'extents.gpkg'))
extents = extents[(extents.threshold == 0.1) & (extents.rainfall == 20) &
                  (extents.duration == 3600 * 6) & (extents.green == 1)]

domain = gpd.read_file(os.path.join(sample_data, 'bwaise.gpkg')).geometry[0]


class TestEvacuationModel(TestCase):

    def test_model_run(self):
        EvacuationModel(domain=domain, output_path=os.path.join(outputs, 'test-model'),
                        seed=1, hazard=extents).run(10000)
