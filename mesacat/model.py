from __future__ import annotations
from mesa import Model
from mesa.time import RandomActivation
import osmnx
from networkx import MultiDiGraph
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector
from matplotlib import animation
from geopandas import GeoDataFrame, sjoin
from typing import Optional
from . import agent


class EvacuationModel(Model):
    """A Mesa ABM model to simulate evacuation during a flood

    Args:
        num_agents: Number of agents to generate
        osm_file: Path to an OpenStreetMap XML file (.osm)
        hazard: A GeoDataFrame containing geometries representing flood hazard zones in WGS84
        target_node: Ths ID of the node to evacuate to, if not specified will be chosen randomly
        seed: Seed value for random number generation

    Attributes:
        num_agents (int): Number of agents to generate
        schedule (RandomActivation): A RandomActivation scheduler which activates each agent once per step,
            in random order, with the order reshuffled every step
        G (MultiDiGraph): A MultiDiGraph generated from OSM data
        nodes (GeoDataFrame): A GeoDataFrame containing nodes in G
        edges (GeoDataFrame): A GeoDataFrame containing edges in G
        grid (NetworkGrid): A NetworkGrid for agents to travel around
        target_node (int): Ths ID of the node to evacuate to
        data_collector (DataCollector): A DataCollector to store the model state at each time step
    """
    def __init__(self, num_agents: int, osm_file: str, hazard: GeoDataFrame, target_node: Optional[int] = None,
                 seed: Optional[int] = None):
        super().__init__()
        self._seed = seed

        self.hazard = hazard
        self.num_agents = num_agents
        self.schedule = RandomActivation(self)
        self.G: MultiDiGraph = osmnx.graph_from_file(osm_file, simplify=False)
        self.nodes, self.edges = osmnx.save_load.graph_to_gdfs(self.G)

        # Prevents warning about CRS not being the same
        self.hazard.crs = self.edges.crs

        nodes_to_drop: GeoDataFrame = sjoin(self.edges, hazard)

        self.G.remove_edges_from(nodes_to_drop[['u', 'v']].to_numpy())

        self.grid = NetworkGrid(self.G)
        self.target_node = target_node if target_node is not None else self.random.choice(self.nodes.index)
        # Create agents
        for i in range(self.num_agents):
            a = agent.EvacuationAgent(i, self)
            self.schedule.add(a)
            self.place_agent(a)
            a.update_route()

        self.data_collector = DataCollector(
            model_reporters={'evacuated': lambda x: len(x.grid.G.nodes[x.target_node]['agent'])},
            agent_reporters={'position': 'pos'})

    def place_agent(self, evacuation_agent: agent.EvacuationAgent):
        """Positions an agent at a random node

        Args:
            evacuation_agent: The agent to move
        """
        node = self.random.choice(list(self.G.nodes))
        self.grid.place_agent(evacuation_agent, node)

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

        with writer.saving(f, path, f.dpi):
            for step in range(self.schedule.steps):
                nodes = self.nodes.loc[df.loc[(step,), 'position']]
                if step > 0:
                    ax.collections[-1].remove()
                nodes.plot(ax=ax, color='C1', alpha=0.2)
                writer.grab_frame()



