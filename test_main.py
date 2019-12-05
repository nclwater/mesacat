from main import EvacuationModel

model = EvacuationModel(5000, 'tests/sample_data/bwaise_large.osm', 6621896336, seed=1)
for _ in range(120):
    model.step()
