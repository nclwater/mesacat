from __future__ import annotations
from mesa import Model
from mesa.time import RandomActivation
import osmnx
from osmnx.footprints import create_footprints_gdf
from networkx import Graph
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector
from geopandas import GeoDataFrame, sjoin
from pandas import Series
from typing import Optional, Iterable
from . import agent
from scipy.spatial import cKDTree
import numpy as np
from shapely.geometry import Polygon
import igraph
import pandas as pd


class EvacuationModel(Model):
    """A Mesa ABM model to simulate evacuation during a flood

    Args:
        hazard: Spatial table of flood hazard zones in WGS84
        output_path: Path to output files without extension
        domain: Polygon used to select OSM data, required if the graph, agents or targets are not specified
        target_types: List of OSM amenity values to use as targets, defaults to school
        network: Undirected network generated from OSM road network
        targets: Spatial table of OSM amenities
        target_capacity: The number of agents that can be evacuated to each target
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
        target_capacity (int): The number of agents that can be evacuated to each target
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
            target_capacity: int = 100,
            agents: Optional[GeoDataFrame] = None,
            seed: Optional[int] = None):
        super().__init__()
        self._seed = seed
        self.output_path = output_path

        self.hazard = hazard
        self.schedule = RandomActivation(self)
        self.target_capacity = target_capacity

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

        targets.crs, agents.crs = [self.nodes.crs] * 2

        nodes_tree = cKDTree(np.transpose([self.nodes.geometry.x, self.nodes.geometry.y]))

        # Prevents warning about CRS not being the same
        self.hazard.crs = self.nodes.crs
        self.hazard.to_file(output_gpkg, layer='hazard', driver=driver)

        agents_in_hazard_zone: GeoDataFrame = sjoin(agents, self.hazard)
        agents_in_hazard_zone = agents_in_hazard_zone.loc[~agents_in_hazard_zone.index.duplicated(keep='first')]
        agents_in_hazard_zone.geometry.to_file(output_gpkg, layer='agents', driver=driver)

        assert len(agents_in_hazard_zone) > 0, 'There are no agents within the hazard zone'

        targets_in_hazard_zone: GeoDataFrame = sjoin(targets, self.hazard)
        targets_in_hazard_zone = targets_in_hazard_zone.loc[~targets_in_hazard_zone.index.duplicated(keep='first')]

        targets_outside_hazard_zone = targets[~targets.index.isin(targets_in_hazard_zone.index.values)]
        targets_outside_hazard_zone.to_file(output_gpkg, layer='targets', driver=driver)

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
            a.update_location()

        self.data_collector = DataCollector(
            model_reporters={
                'evacuated': evacuated,
                'stranded': stranded
            },
            agent_reporters={'position': 'pos',
                             'reroute_count': 'reroute_count',
                             'lat': 'lat',
                             'lon': 'lon',
                             'highway': 'highway',
                             'status': status})

    def step(self):
        """Advances the model by one step and then stores the current state in data_collector"""
        self.schedule.step()
        self.data_collector.collect(self)

    def run(self, steps: int):
        """Runs the model for the given number of steps`

        Args:
            steps: number of steps to run the model for
        Returns:
            DataFrame: the agent vars dataframe
        """
        self.data_collector.collect(self)
        for _ in range(steps):
            self.step()
            if self.data_collector.model_vars['evacuated'][-1] + self.data_collector.model_vars['stranded'][-1] == len(
                    self.schedule.agents):
                # Continue for 5 steps after all agents evacuated or stranded
                for _ in range(5):
                    self.step()
                break
        self.data_collector.get_agent_vars_dataframe().astype({'highway': pd.Int64Dtype()}).to_csv(
            self.output_path + '.agent.csv')
        self.data_collector.get_model_vars_dataframe().to_csv(self.output_path + '.model.csv')
        return self.data_collector.get_agent_vars_dataframe()


def evacuated(m):
    return len([a for a in m.schedule.agents if a.evacuated])


def stranded(m):
    return len([a for a in m.schedule.agents if a.stranded])


def status(a):
    return 1 if a.evacuated else 2 if a.stranded else 0
