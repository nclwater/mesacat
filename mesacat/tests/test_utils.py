from mesacat.utils import create_movie, create_plot
from unittest import TestCase
import os

sample_data = os.path.join(os.path.dirname(__file__), 'sample_data')
outputs = os.path.join(os.path.dirname(__file__), 'outputs')


class TestUtils(TestCase):

    def test_create_plot(self):
        create_plot(os.path.join(sample_data, 'test-model'), os.path.join(outputs, 'test-model.png'))

    def test_create_movie(self):
        create_movie(os.path.join(sample_data, 'test-model'), os.path.join(outputs, 'test-model.mp4'))
