import pandas as pd
import geopandas as gpd
import osmnx
from matplotlib import animation, lines
from matplotlib.patches import Patch
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec


def create_movie(in_path: str, out_path: str, fps: int = 5):
    """Generates an MP4 video of all model steps using FFmpeg (https://www.ffmpeg.org/)

    Args:
        in_path: path to model output files without extension
        out_path: path to movie file
        fps: frames per second of the video
    """
    agent_df, model_df, graph, nodes, edges, hazard, target_nodes = read_model(in_path)

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

    # Road network
    f, ax = osmnx.plot_graph(graph, show=False, dpi=200, node_size=0, edge_color=edge_color, edge_linewidth=0.5)

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
        start = nodes.loc[agent_df.loc[[0]].position]
        agents = ax.scatter(start.geometry.x, start.geometry.y,
                            marker=agents_marker, s=agents_size, alpha=agents_alpha, color=agents_color)

        targets = ax.scatter(target_nodes.geometry.x, target_nodes.geometry.y,
                             color=targets_color, s=targets_size, marker=targets_marker, zorder=4)

        for step in model_df.index:
            agents_at_step = agent_df.loc[[step]]
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
                evacuated_agents.position.value_counts().rename('occupants')).occupants.replace(float('NaN'), 0).values
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


def create_plot(in_path, out_path):
    agent_df, model_df, graph, nodes, edges, hazard, target_nodes = read_model(in_path)
    gs = GridSpec(2, 2, width_ratios=[30, 1])

    f = plt.figure(figsize=(8, 8))
    top_ax = f.add_subplot(gs[0, :])

    evacuated = agent_df[agent_df.status == 1]

    stranded = agent_df[agent_df.status == 2].groupby('Step').count().AgentID.rename('Stranded')
    occupancy = evacuated.groupby([evacuated.index, 'position']).count().AgentID.rename(
        'occupancy').reset_index().pivot(
        values='occupancy', columns='position', index='Step').rename(columns=target_nodes.name.to_dict())
    occupancy.join(stranded).set_index(occupancy.index.values * 10 / 60).plot(
        ax=top_ax, legend=True, secondary_y=[stranded.name])
    top_ax.set_xlabel('Time (minutes)')
    top_ax.set_ylabel('Number of Agents Evacuated')
    top_ax.right_ax.set_ylabel('Number of Agents Stranded')
    h1, l1 = top_ax.get_legend_handles_labels()
    h2, l2 = top_ax.right_ax.get_legend_handles_labels()
    top_ax.legend(h1 + h2, l1 + l2, ncol=2, bbox_to_anchor=(0.5, 1.2), loc='center')
    top_ax.right_ax.set_xticklabels(top_ax.get_xticks() * 10)

    bottom_ax = f.add_subplot(gs[1, 0])
    cax = f.add_subplot(gs[1, 1])
    traffic = agent_df[['AgentID', 'highway']].drop_duplicates().groupby('highway').count().AgentID.rename('traffic')
    edges.set_index(edges.osmid.astype(pd.Int64Dtype())).join(traffic).loc[traffic.index.values].plot(
        column='traffic', ax=bottom_ax, cmap='copper_r', legend=True,
        legend_kwds={'label': 'Traffic', 'cax': cax})

    target_nodes.plot(ax=bottom_ax, color=plt.rcParams['axes.prop_cycle'].by_key()['color'][:len(target_nodes)])

    bottom_ax.set_xlabel('Latitude')
    bottom_ax.set_ylabel('Longitude')

    f.savefig(out_path, bbox_inches='tight')


def read_model(path):
    agent_df = pd.read_csv(path + '.agent.csv', index_col='Step', dtype={'highway': pd.Int64Dtype()})
    model_df = pd.read_csv(path + '.model.csv')

    graph = nx.read_gml(path + '.gml')
    nodes, edges = osmnx.save_load.graph_to_gdfs(graph)
    nodes.index = nodes.index.astype('int64')

    geopackage = path + '.gpkg'

    hazard = gpd.read_file(geopackage, layer='hazard')
    target_nodes = gpd.read_file(geopackage, layer='targets')
    target_nodes = target_nodes.set_index(target_nodes.osmid.astype('int64'))

    return agent_df, model_df, graph, nodes, edges, hazard, target_nodes
