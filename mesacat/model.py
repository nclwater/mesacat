from __future__ import annotations
from mesa import Model
from mesa.time import RandomActivation
import osmnx
from osmnx.footprints import create_footprints_gdf
from networkx import Graph
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector
from matplotlib import animation, lines
from geopandas import GeoDataFrame, sjoin
from pandas import Series
from typing import Optional, Iterable
from . import agent
from scipy.spatial import cKDTree
import numpy as np
from shapely.geometry import Polygon
import igraph
from matplotlib.patches import Patch


class EvacuationModel(Model):
    """A Mesa ABM model to simulate evacuation during a flood

    Args:
        hazard: Spatial table of flood hazard zones in WGS84
        output_path: Path to output files without extension
        domain: Polygon used to select OSM data, required if the graph, agents or targets are not specified
        target_types: List of OSM amenity values to use as targets, defaults to school
        network: Undirected network generated from OSM road network
        targets: Spatial table of OSM amenities
        agents: Spatial table of agent starting locations
        seed: Seed value for random number generation

    Attributes:
        output_path (str): Path to output files without extension
        schedule (RandomActivation): Scheduler which activates each agent once per step,
            in random order, with the order reshuffled every step
        hazard (GeoDataFrame): Spatial table of flood hazard zones in WGS84
        G (Graph): Undirected network generated from OSM road network
        nodes (GeoDataFrame): Spatial table of nodes in G
        edges (GeoDataFrame): Spatial table edges in G
        grid (NetworkGrid): Network grid for agents to travel around based on G
        data_collector (DataCollector): Stores the model state at each time step
        target_nodes (Series): Series of nodes to evacuate to
        igraph: Duplicate of G as an igraph object to speed up routing

    """
    def __init__(
            self,
            hazard: GeoDataFrame,
            output_path: str,
            domain: Optional[Polygon] = None,
            target_types: Iterable[str] = tuple(['school']),
            network: Optional[Graph] = None,
            targets: Optional[GeoDataFrame] = None,
            agents: Optional[GeoDataFrame] = None,
            seed: Optional[int] = None):
        super().__init__()
        self._seed = seed
        self.output_path = output_path

        self.hazard = hazard
        self.schedule = RandomActivation(self)

        if network is None:
            self.G = osmnx.graph_from_polygon(domain, simplify=False)
            self.G = self.G.to_undirected()
        else:
            self.G = network

        self.nodes: GeoDataFrame
        self.edges: GeoDataFrame
        self.nodes, self.edges = osmnx.save_load.graph_to_gdfs(self.G)

        if agents is None:
            agents = GeoDataFrame(geometry=create_footprints_gdf(domain).centroid)

        if targets is None:
            targets = osmnx.pois_from_polygon(domain, amenities=list(target_types))
            # Query can return polygons as well as points, only using the points
            targets = targets[targets.geometry.geom_type == 'Point']

        output_gpkg = output_path + '.gpkg'

        driver = 'GPKG'
        agents.to_file(output_gpkg, layer='agents', driver=driver)
        targets[['osmid', 'geometry']].to_file(output_gpkg, layer='targets', driver=driver)

        targets.crs, agents.crs = [self.nodes.crs] * 2

        nodes_tree = cKDTree(np.transpose([self.nodes.geometry.x, self.nodes.geometry.y]))

        # Prevents warning about CRS not being the same
        self.hazard.crs = self.nodes.crs
        self.hazard.to_file(output_gpkg, layer='hazard', driver=driver)

        agents_in_hazard_zone: GeoDataFrame = sjoin(agents, self.hazard)
        agents_in_hazard_zone = agents_in_hazard_zone.loc[~agents_in_hazard_zone.index.duplicated(keep='first')]

        assert len(agents_in_hazard_zone) > 0, 'There are no agents within the hazard zone'

        targets_in_hazard_zone: GeoDataFrame = sjoin(targets, self.hazard)
        targets_in_hazard_zone = targets_in_hazard_zone.loc[~targets_in_hazard_zone.index.duplicated(keep='first')]

        targets_outside_hazard_zone = targets[~targets.index.isin(targets_in_hazard_zone.index.values)]

        assert len(targets_outside_hazard_zone) > 0, 'There are no targets outside the hazard zone'

        _, node_idx = nodes_tree.query(
            np.transpose([agents_in_hazard_zone.geometry.x, agents_in_hazard_zone.geometry.y]))

        _, target_node_idx = nodes_tree.query(
            np.transpose([targets_outside_hazard_zone.geometry.x, targets_outside_hazard_zone.geometry.y]))

        for (_, row), nearest_node in zip(targets_outside_hazard_zone.iterrows(), self.nodes.index[target_node_idx]):
            if not self.G.has_node(row.osmid):
                self.G.add_edge(nearest_node, row.osmid, length=0)
                self.G.nodes[row.osmid]['osmid'] = row.osmid
                self.G.nodes[row.osmid]['x'] = row.geometry.x
                self.G.nodes[row.osmid]['y'] = row.geometry.y

        self.nodes, self.edges = osmnx.save_load.graph_to_gdfs(self.G)

        self.nodes[['osmid', 'geometry']].to_file(output_gpkg, layer='nodes', driver=driver)
        self.edges[['osmid', 'geometry']].to_file(output_gpkg, layer='edges', driver=driver)

        output_gml = output_path + '.gml'
        osmnx.nx.write_gml(self.G, path=output_gml)
        self.igraph = igraph.read(output_gml)

        self.target_nodes = targets_outside_hazard_zone.osmid

        self.grid = NetworkGrid(self.G)

        # Create agents
        for i, idx in enumerate(node_idx):
            a = agent.EvacuationAgent(i, self)
            self.schedule.add(a)
            self.grid.place_agent(a, self.nodes.index[idx])
            a.update_route()

        self.data_collector = DataCollector(
            model_reporters={
                'evacuated':
                    lambda x: sum([len(x.grid.G.nodes[target_node]['agent']) for target_node in set(self.target_nodes)])
            },
            agent_reporters={'position': 'pos'})

    def step(self):
        """Advances the model by one step and then stores the current state in data_collector"""
        self.schedule.step()
        self.data_collector.collect(self)

    def run(self, steps: int):
        """Runs the model for the given number of steps

        Args:
            steps: number of steps to run the model for
        Returns:
            DataFrame: the agent vars dataframe
        """
        self.data_collector.collect(self)
        for step in range(steps):
            self.step()
            evacuated = self.data_collector.model_vars['evacuated'][-1]
            total = len(self.schedule.agents)
            if evacuated == total:
                break
        self.data_collector.get_agent_vars_dataframe().to_csv(self.output_path+'.csv')
        return self.data_collector.get_agent_vars_dataframe()

    def create_movie(self, fps: int = 5):
        """Generates an MP4 video of all model steps using FFmpeg (https://www.ffmpeg.org/)

        Args:
            fps: frames per second of the video
        """

        df = self.data_collector.get_agent_vars_dataframe()

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

        f, ax = osmnx.plot_graph(self.grid.G, show=False, dpi=200, node_size=0, edge_color=edge_color,
                                 edge_linewidth=0.5)

        self.hazard.plot(ax=ax, alpha=hazard_alpha, color=hazard_color)
        self.nodes.loc[self.target_nodes].plot(ax=ax,
                                               color=targets_color,
                                               markersize=targets_size,
                                               marker=targets_marker,
                                               zorder=4)

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
        with writer.saving(f, self.output_path+'.mp4', f.dpi):
            for step in range(self.schedule.steps + 1):
                nodes = self.nodes.loc[df.loc[(step,), 'position']]
                if step > 0:
                    ax.collections[-1].remove()
                nodes.plot(ax=ax, color=agents_color, alpha=agents_alpha, zorder=3, markersize=agents_size)
                ax.set_title('T={}min\n{}/{} Agents Evacuated ({:.0f}%)'.format(
                    (step * 10) // 60,
                    self.data_collector.model_vars['evacuated'][step],
                    len(self.schedule.agents),
                    self.data_collector.model_vars['evacuated'][step] / len(self.schedule.agents) * 100
                ))
                writer.grab_frame()
