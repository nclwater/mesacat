import pandas as pd
import geopandas as gpd
import osmnx
from matplotlib import animation, lines
from matplotlib.patches import Patch
import networkx as nx


def create_movie(in_path: str, out_path: str, fps: int = 5):
    """Generates an MP4 video of all model steps using FFmpeg (https://www.ffmpeg.org/)

    Args:
        in_path: path to model output files without extension
        out_path: path to movie file
        fps: frames per second of the video
    """

    agent_df = pd.read_csv(in_path + '.agent.csv')
    model_df = pd.read_csv(in_path + '.model.csv')

    writer = animation.writers['ffmpeg']
    metadata = dict(title='Movie Test', artist='Matplotlib', comment='Movie support!')
    writer = writer(fps=fps, metadata=metadata)

    hazard_color = 'blue'
    hazard_alpha = 0.2
    targets_color = 'green'
    targets_marker = 'x'
    targets_size = 10
    agents_color = 'C1'
    agents_marker = 'o'
    agents_size = 10
    agents_alpha = 0.2
    edge_color = '#999999'

    graph = nx.read_gml(in_path + '.gml')
    nodes, _ = osmnx.save_load.graph_to_gdfs(graph)
    nodes.index = nodes.index.astype('int64')

    f, ax = osmnx.plot_graph(graph, show=False, dpi=200, node_size=0, edge_color=edge_color, edge_linewidth=0.5)

    geopackage = in_path + '.gpkg'

    hazard = gpd.read_file(geopackage, layer='hazard')
    target_nodes = gpd.read_file(geopackage, layer='targets')

    hazard.plot(ax=ax, alpha=hazard_alpha, color=hazard_color)
    target_nodes.plot(ax=ax, color=targets_color, markersize=targets_size, marker=targets_marker, zorder=4)

    ax.legend(handles=[
        Patch(label='Hazard', facecolor=hazard_color, alpha=hazard_alpha),
        lines.Line2D([], [],
                     label='Agents',
                     color=agents_color,
                     marker=agents_marker,
                     markersize=agents_size,
                     alpha=agents_alpha,
                     linestyle='None'),
        lines.Line2D([], [],
                     label='Targets',
                     color=targets_color,
                     marker=targets_marker,
                     markersize=targets_size,
                     linestyle='None'),
        lines.Line2D([], [],
                     label='Road Network',
                     color=edge_color,
                     linestyle='-')
    ])
    with writer.saving(f, out_path, f.dpi):
        start = nodes.loc[agent_df[agent_df.Step == 0].position]
        line = ax.scatter(start.geometry.x, start.geometry.y,
                          marker=agents_marker, s=agents_size, alpha=agents_alpha, color=agents_color)
        for step in model_df.index:
            agents = nodes.loc[agent_df[agent_df.Step == step].position]
            line.set_offsets(list(zip(agents.geometry.x, agents.geometry.y)))
            evacuated = model_df.evacuated.loc[step]
            ax.set_title('T={}min\n{}/{} Agents Evacuated ({:.0f}%)'.format(
                (step * 10) // 60,
                evacuated,
                len(agents),
                evacuated / len(agents) * 100
            ))
            writer.grab_frame()
