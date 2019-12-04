from main import EvacuationModel

model = EvacuationModel(100, 'tests/sample_data/bwaise.osm', 1795721333)
for _ in range(60):
    model.step()
