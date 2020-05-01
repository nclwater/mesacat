from __future__ import annotations
from mesa import Model
from mesa.time import RandomActivation
import osmnx
from networkx import MultiDiGraph
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector
from matplotlib import animation
from geopandas import read_file, GeoDataFrame, sjoin
from typing import Optional
import pandas as pd
from . import agent
from scipy.spatial import cKDTree
import numpy as np
from xml.etree import ElementTree as ET
from shapely.geometry import Point
import os
import igraph


class EvacuationModel(Model):
    """A Mesa ABM model to simulate evacuation during a flood

    Args:
        osm_file: Path to an OpenStreetMap XML file (.osm)
        hazard: A GeoDataFrame containing geometries representing flood hazard zones in WGS84
        target_xpath: The XPath expression used to select target nodes from OSM data, defaults to schools
        seed: Seed value for random number generation

    Attributes:
        schedule (RandomActivation): A RandomActivation scheduler which activates each agent once per step,
            in random order, with the order reshuffled every step
        osm_file (str): Path to an OpenStreetMap XML file (.osm)
        hazard (GeoDataFrame): A GeoDataFrame containing geometries representing flood hazard zones in WGS84
        building_centroids (GeoDataFrame): A GeoDataFrame of buildings found in osm_file
            An agents will be placed at the nearest node to each building within the hazard zone
        G (MultiDiGraph): A MultiDiGraph generated from OSM road network
        nodes (GeoDataFrame): A GeoDataFrame containing nodes in G
        edges (GeoDataFrame): A GeoDataFrame containing edges in G
        grid (NetworkGrid): A NetworkGrid for agents to travel around based on G
        data_collector (DataCollector): A DataCollector to store the model state at each time step
    """
    def __init__(self, osm_file: str, hazard: GeoDataFrame, target_xpath: str = "node//*[@k='amenity'][@v='school']..",
                 seed: Optional[int] = None):
        super().__init__()
        self._seed = seed

        self.hazard = hazard
        self.schedule = RandomActivation(self)
        self.G: MultiDiGraph = osmnx.graph_from_file(osm_file, simplify=False)
        self.nodes: GeoDataFrame
        self.edges: GeoDataFrame
        self.nodes, self.edges = osmnx.save_load.graph_to_gdfs(self.G)
        osmnx.nx.write_gml(self.G, path=osm_file + '.gml')
        self.igraph = igraph.read(osm_file + '.gml')

        with open(osm_file) as f:
            tree = ET.fromstring(f.read())

        building_centroids = osm_file + '_buildings.gpkg'
        if os.path.exists(building_centroids):
            self.building_centroids = read_file(building_centroids)
        else:

            buildings = []
            for building in tree.findall("way//*[@k='building'].."):
                lats, lons = [], []
                for node in building.findall('nd'):
                    element = tree.find("node[@id='{}']".format(node.attrib['ref']))
                    lats.append(float(element.attrib['lat']))
                    lons.append(float(element.attrib['lon']))
                buildings.append(Point((min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2))

            self.building_centroids = GeoDataFrame(geometry=buildings, crs=self.nodes.crs)
            self.building_centroids.to_file(building_centroids, driver='GPKG')

        targets_path = osm_file + '_targets.csv'
        if not os.path.exists(targets_path):
            targets = [(target.attrib['lon'], target.attrib['lat']) for target in tree.findall(target_xpath)]
            pd.DataFrame.from_records(targets, columns=['lon', 'lat']).to_csv(targets_path, index=False)
        else:
            targets = pd.read_csv(targets_path).values.tolist()

        nodes_tree = cKDTree(np.transpose([self.nodes.geometry.x, self.nodes.geometry.y]))

        # Prevents warning about CRS not being the same
        self.hazard.crs = self.nodes.crs

        agents_in_hazard_zone: GeoDataFrame = sjoin(self.building_centroids, self.hazard)
        agents_in_hazard_zone = agents_in_hazard_zone.loc[~agents_in_hazard_zone.index.duplicated(keep='first')]

        targets = GeoDataFrame(geometry=[Point(*target) for target in targets], crs=self.hazard.crs)

        targets_in_hazard_zone: GeoDataFrame = sjoin(targets, self.hazard)
        targets_in_hazard_zone = targets_in_hazard_zone.loc[~targets_in_hazard_zone.index.duplicated(keep='first')]

        targets_outside_hazard_zone = targets[~targets.index.isin(targets_in_hazard_zone.index.values)]

        _, node_idx = nodes_tree.query(
            np.transpose([agents_in_hazard_zone.geometry.x, agents_in_hazard_zone.geometry.y]))

        _, target_node_idx = nodes_tree.query(
            np.transpose([targets_outside_hazard_zone.geometry.x, targets_outside_hazard_zone.geometry.y]))

        self.target_nodes = self.nodes.index[target_node_idx]

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
                    lambda x: sum([len(x.grid.G.nodes[target_node]['agent']) for target_node in self.target_nodes])
            },
            agent_reporters={'position': 'pos'})

    def step(self):
        """Stores the current state in data_collector and advances the model by one step"""
        self.data_collector.collect(self)
        self.schedule.step()

    def run(self, steps: int):
        """Runs the model for the given number of steps

        Args:
            steps: number of steps to run the model for
        Returns:
            DataFrame: the agent vars dataframe
        """
        for _ in range(steps):
            self.step()

        return self.data_collector.get_agent_vars_dataframe()

    def create_movie(self, path: str, fps: int = 5):
        """Generates an MP4 video of all model steps using FFmpeg (https://www.ffmpeg.org/)

        Args:
            path: path to create the MP4 file
            fps: frames per second of the video
        """

        df = self.data_collector.get_agent_vars_dataframe()

        writer = animation.writers['ffmpeg']
        metadata = dict(title='Movie Test', artist='Matplotlib', comment='Movie support!')
        writer = writer(fps=fps, metadata=metadata)

        f, ax = osmnx.plot_graph(self.grid.G, show=False, dpi=200, node_size=0)
        self.hazard.plot(ax=ax, alpha=0.2, color='blue')
        self.nodes.loc[self.target_nodes].plot(
            ax=ax, color='green', markersize=20)

        with writer.saving(f, path, f.dpi):
            for step in range(self.schedule.steps):
                nodes = self.nodes.loc[df.loc[(step,), 'position']]
                if step > 0:
                    ax.collections[-1].remove()
                nodes.plot(ax=ax, color='C1', alpha=0.2)
                writer.grab_frame()
