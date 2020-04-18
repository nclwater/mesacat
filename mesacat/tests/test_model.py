from mesacat.model import EvacuationModel
from unittest import TestCase
import geopandas as gpd
from xml.etree import ElementTree as ET
import os
import numpy as np
from shapely.geometry import Point

sample_data = os.path.join(os.path.dirname(__file__), 'sample_data')
outputs = os.path.join(os.path.dirname(__file__), 'outputs')
if not os.path.exists(outputs):
    os.mkdir(outputs)

osm_data = os.path.join(sample_data, 'bwaise.osm')

extents = gpd.read_file(os.path.join(sample_data, 'extents.gpkg'))
extents = extents[(extents.threshold == 0.1) & (extents.rainfall == 20) & (extents.duration == 3600 * 6)]

with open(osm_data) as f:
    tree = ET.fromstring(f.read())

building_ways = tree.findall("way//*[@k='building']..")
buildings = []
for building in building_ways:
    nodes = building.findall('nd')
    lats, lons = [], []
    for node in nodes:
        node_id = node.attrib['ref']
        element = tree.find("node[@id='{}']".format(node_id))
        attrib = element.attrib
        lats.append(float(attrib['lat']))
        lons.append(float(attrib['lon']))

    lat, lon = np.mean(np.transpose([lats, lons]), axis=0)
    buildings.append(Point(lon, lat))

agent_locations = gpd.GeoDataFrame(geometry=buildings, crs=4326)


class TestEvacuationModel(TestCase):

    def setUp(self):

        self.model = EvacuationModel(osm_file=osm_data, seed=1,
                                     hazard=extents, target_node=6996374452, agent_locations=agent_locations)
        self.steps = 10

    def test_create_movie(self):

        self.model.run(self.steps)
        self.model.create_movie(os.path.join(outputs, 'model.mp4'))

    def test_run(self):
        self.model.run(self.steps)
