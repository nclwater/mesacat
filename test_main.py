from main import EvacuationModel

model = EvacuationModel(10, 'tests/sample_data/bwaise.osm')
for _ in range(10):
    model.step()
