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
    targets_at_capacity_color = 'grey'
    targets_marker = 'o'
    targets_size = 10
    agents_color = 'C1'
    rerouted_agents_color = 'red'
    repeatedly_rerouted_agents_color = 'purple'
    agents_marker = 'o'
    agents_size = 10
    agents_alpha = 1
    edge_color = '#999999'

    graph = nx.read_gml(in_path + '.gml')
    nodes, _ = osmnx.save_load.graph_to_gdfs(graph)
    nodes.index = nodes.index.astype('int64')

    # Road network
    f, ax = osmnx.plot_graph(graph, show=False, dpi=200, node_size=0, edge_color=edge_color, edge_linewidth=0.5)

    geopackage = in_path + '.gpkg'

    hazard = gpd.read_file(geopackage, layer='hazard')
    target_nodes = gpd.read_file(geopackage, layer='targets')
    target_nodes = target_nodes.set_index(target_nodes.osmid.astype('int64'))

    # Flood hazard zone
    hazard.plot(ax=ax, alpha=hazard_alpha, color=hazard_color)

    # Targets

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
                     label='Rerouted Agents',
                     color=rerouted_agents_color,
                     marker=agents_marker,
                     markersize=agents_size,
                     alpha=agents_alpha,
                     linestyle='None'),
        lines.Line2D([], [],
                     label='Repeatedly Rerouted Agents',
                     color=repeatedly_rerouted_agents_color,
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
                     label='Targets at Capacity',
                     color=targets_at_capacity_color,
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
        agents = ax.scatter(start.geometry.x, start.geometry.y,
                            marker=agents_marker, s=agents_size, alpha=agents_alpha, color=agents_color)

        targets = ax.scatter(target_nodes.geometry.x, target_nodes.geometry.y,
                             color=targets_color, s=targets_size, marker=targets_marker, zorder=4)

        for step in model_df.index:
            agents_at_step = agent_df[agent_df.Step == step]
            evacuated_agents = agents_at_step[agents_at_step.status == 1]
            agent_locations = nodes.loc[agents_at_step.position]
            agents.set_offsets(agents_at_step[['lon', 'lat']].values)
            agents.set_color([
                agents_color if a == 0
                else rerouted_agents_color if a == 1
                else repeatedly_rerouted_agents_color
                for a in agents_at_step.reroute_count
            ])

            occupants = target_nodes.join(
                evacuated_agents.position.value_counts().rename('occupants')).occupants.replace(float('NaN'), 0)
            occupants = target_nodes.join(occupants).replace(float('NaN'), 0).occupants.values
            targets.set_sizes(occupants)
            targets.set_color([targets_color if o < 100 else targets_at_capacity_color for o in occupants])
            evacuated_total = model_df.evacuated.loc[step]
            stranded = model_df.stranded.loc[step]
            ax.set_title('T={}min\n{}/{} Agents Evacuated ({:.0f}%)\n{}/{} Agents Stranded ({:.0f}%)'.format(
                (step * 10) // 60,
                evacuated_total,
                len(agent_locations),
                evacuated_total / len(agent_locations) * 100,
                stranded,
                len(agent_locations),
                stranded / len(agent_locations) * 100
            ))
            writer.grab_frame()
