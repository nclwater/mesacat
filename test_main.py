from main import EvacuationModel
from unittest import TestCase


class TestEvacuationModel(TestCase):

    def test_create_movie(self):

        model = EvacuationModel(100, 'tests/sample_data/bwaise_large.osm', 6621896336, seed=1)

        model.create_movie('model.mp4', steps=10)
