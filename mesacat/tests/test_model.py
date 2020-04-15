from mesacat.model import EvacuationModel
from unittest import TestCase


class TestEvacuationModel(TestCase):

    def setUp(self):
        self.model = EvacuationModel(10, 'sample_data/bwaise.osm', seed=1)
        self.steps = 10

    def test_create_movie(self):

        self.model.run(self.steps)
        self.model.create_movie('model.mp4')

    def test_run(self):
        self.model.run(self.steps)
