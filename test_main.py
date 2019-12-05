from main import EvacuationModel
from matplotlib import animation as manimation

FFMpegWriter = manimation.writers['ffmpeg']
metadata = dict(title='Movie Test', artist='Matplotlib', comment='Movie support!')
writer = FFMpegWriter(fps=5, metadata=metadata)

model = EvacuationModel(5000, 'tests/sample_data/bwaise_large.osm', 6621896336, seed=1, interactive=False)

with writer.saving(model.f, "writer_test.mp4", model.f.dpi):
    for _ in range(120):
        model.step()
        writer.grab_frame()
