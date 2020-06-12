from mesacat.utils import create_movie, target_occupancy_plot
from unittest import TestCase
import os

sample_data = os.path.join(os.path.dirname(__file__), 'sample_data')
outputs = os.path.join(os.path.dirname(__file__), 'outputs')


class TestUtils(TestCase):

    def test_target_occupancy(self):
        target_occupancy_plot(os.path.join(sample_data, 'test-model'), os.path.join(outputs, 'test-model.png'))

    def test_create_movie(self):
        create_movie(os.path.join(sample_data, 'test-model'), os.path.join(outputs, 'test-model.mp4'))
