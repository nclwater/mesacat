from mesa import Agent, Model
from mesa.time import RandomActivation
import osmnx
from networkx import MultiDiGraph
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector
from networkx import shortest_path, NetworkXException
from matplotlib import animation as manimation
# import time


def count_evacuated_agents(model):
    return len(model.grid.G.nodes[model.target_node]['agent'])


class EvacuationModel(Model):
    """A model with some number of agents"""
    def __init__(self, num_agents, osm_file, target_node=None, seed=None):
        self._seed = seed
        self.interactive = False
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

        self.f, self.ax = osmnx.plot_graph(self.grid.G, show=False)
        self.f.set_dpi(200)
        nodes = [a.pos for a in self.schedule.agents]
        self.nodes.loc[nodes].plot(ax=self.ax, color='C1')
        self.data_collector = DataCollector(model_reporters={'evacuated': count_evacuated_agents},
                                            agent_reporters={'Position': 'pos'})

    def show(self):
        self.interactive = True
        self.f.show()

    def place_agent(self, agent):
        node = self.random.choice(list(self.G.nodes))
        self.grid.place_agent(agent, node)

    def step(self):
        """Advance the model by one step."""
        self.data_collector.collect(self)
        self.schedule.step()
        nodes = self.nodes.loc[[a.pos for a in self.schedule.agents]]
        self.ax.collections[-1].remove()
        nodes.plot(ax=self.ax, color='C1', alpha=0.2)
        self.ax.set_title('Evacuated agents: {}'.format(count_evacuated_agents(self)))
        if self.interactive:
            self.f.canvas.draw()
            self.f.canvas.flush_events()

        # time.sleep(0.1)

    def create_movie(self, path, steps=120, fps=5):
        assert not self.interactive, 'Cannot create movie if interactive is True'
        writer = manimation.writers['ffmpeg']
        metadata = dict(title='Movie Test', artist='Matplotlib', comment='Movie support!')
        writer = writer(fps=fps, metadata=metadata)

        with writer.saving(self.f, path, self.f.dpi):
            for _ in range(steps):
                self.step()
                writer.grab_frame()


class EvacuationAgent(Agent):
    """A person with an age"""
    def __init__(self, unique_id, model: EvacuationModel):
        super().__init__(unique_id, model)
        self.model = model
        self.route = None
        self.route_index = 0

    def update_route(self):
        try:
            self.route = shortest_path(self.model.G, self.pos, self.model.target_node)
        except NetworkXException:
            self.model.place_agent(self)
            self.update_route()

    def step(self):
        self.move()

    def move(self):
        self.route_index += 1
        if self.route_index < len(self.route):
            self.model.grid.move_agent(self, self.route[self.route_index])
        pass
