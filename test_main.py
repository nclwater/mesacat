from main import EvacuationModel

model = EvacuationModel(10, 'tests/sample_data/bwaise.osm', 1795721333)
for _ in range(50):
    model.step()
