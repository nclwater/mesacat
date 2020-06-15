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


class TestEvacuationModel(TestCase):

    # def test_model_download(self):
    #     domain = gpd.read_file(os.path.join(sample_data, 'bwaise-small.gpkg')).geometry[0]
    #     EvacuationModel(domain=domain, output_path=os.path.join(outputs, 'download'),
    #                     seed=1, hazard=extents)

    def test_model_run(self):
        import networkx as nx
        test_model_path = os.path.join(sample_data, 'test-model')
        geopackage = test_model_path + '.gpkg'
        agents = gpd.read_file(geopackage, layer='agents')
        targets = gpd.read_file(geopackage, layer='targets')
        network = nx.read_gml(test_model_path + '.gml')

        EvacuationModel(
            agents=agents,
            targets=targets,
            network=network,
            output_path=os.path.join(outputs, 'test-model'),
            seed=1, hazard=extents).run(50)
