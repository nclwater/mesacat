from mesa import Agent, Model
from mesa.time import RandomActivation
import osmnx
from networkx import MultiDiGraph
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector
from networkx import shortest_path, NetworkXException
from matplotlib import animation as manimation

def count_evacuated_agents(model):
    return len(model.grid.G.nodes[model.target_node]['agent'])


class EvacuationModel(Model):
    """A model with some number of agents"""
    def __init__(self, num_agents, osm_file, target_node=None, seed=None):
        self._seed = seed
        self.num_agents = num_agents
        self.schedule = RandomActivation(self)
        self.G: MultiDiGraph = osmnx.graph_from_file(osm_file, simplify=False)
        self.nodes, self.edges = osmnx.save_load.graph_to_gdfs(self.G)
        self.grid = NetworkGrid(self.G)
        self.target_node = target_node if target_node is not None else self.random.choice(self.nodes.index)
        # Create agents
        for i in range(self.num_agents):
            a = EvacuationAgent(i, self)
            self.schedule.add(a)
            self.place_agent(a)
            a.update_route()

        self.data_collector = DataCollector(model_reporters={'evacuated': count_evacuated_agents},
                                            agent_reporters={'Position': 'pos'})

    def place_agent(self, agent):
        node = self.random.choice(list(self.G.nodes))
        self.grid.place_agent(agent, node)

    def step(self):
        """Advance the model by one step."""
        self.data_collector.collect(self)
        self.schedule.step()

    def run(self, steps: int):
        for _ in range(steps):
            self.step()

        return self.data_collector.get_agent_vars_dataframe()

    def create_movie(self, path, fps=5):

        df = self.data_collector.get_agent_vars_dataframe()

        writer = manimation.writers['ffmpeg']
        metadata = dict(title='Movie Test', artist='Matplotlib', comment='Movie support!')
        writer = writer(fps=fps, metadata=metadata)

        f, ax = osmnx.plot_graph(self.grid.G, show=False, dpi=200, node_size=0)

        with writer.saving(f, path, f.dpi):
            for step in range(self.schedule.steps):
                nodes = self.nodes.loc[df.loc[(step,), 'Position']]
                if step > 0:
                    ax.collections[-1].remove()
                nodes.plot(ax=ax, color='C1', alpha=0.2)
                writer.grab_frame()


class EvacuationAgent(Agent):
    """A person with an age"""
    def __init__(self, unique_id, model: EvacuationModel):
        super().__init__(unique_id, model)
        self.model = model
        self.route = None
        self.route_index = 0
        self.speed = 3  # km/h
        self.distance_along_edge = 0

    def update_route(self):
        try:
            self.route = shortest_path(self.model.G, self.pos, self.model.target_node, 'length')
        except NetworkXException:
            self.model.place_agent(self)
            self.update_route()

    def step(self):
        self.move()

    def distance_to_next_node(self):
        return self.model.G.get_edge_data(
            self.route[self.route_index], self.route[self.route_index+1])[0]['length'] - self.distance_along_edge

    def move(self):
        if self.route_index < len(self.route) - 1:

            distance_to_travel = self.speed

            distance_to_next_node = self.distance_to_next_node()

            while distance_to_travel >= distance_to_next_node:
                self.distance_along_edge = 0
                distance_to_travel -= distance_to_next_node
                self.route_index += 1
                self.model.grid.move_agent(self, self.route[self.route_index])

                if self.route_index >= len(self.route) - 1:
                    break

                distance_to_next_node = self.distance_to_next_node()

            self.distance_along_edge += distance_to_travel
