from mesa import Agent, Model
from mesa.time import RandomActivation
import osmnx
from networkx import MultiDiGraph
from mesa.space import NetworkGrid


class EvacuationModel(Model):
    """A model with some number of agents"""
    def __init__(self, num_agents, osm_file, seed=None):
        self._seed = seed
        self.num_agents = num_agents
        self.schedule = RandomActivation(self)
        self.G: MultiDiGraph = osmnx.graph_from_file(osm_file, simplify=False)
        self.nodes, self.edges = osmnx.save_load.graph_to_gdfs(self.G)
        self.grid = NetworkGrid(self.G)
        # Create agents
        for i in range(self.num_agents):
            a = EvacuationAgent(i, self)
            self.schedule.add(a)
            node = self.random.choice(list(self.G.nodes))
            self.grid.place_agent(a, node)

    def step(self):
        """Advance the model by one step."""
        self.schedule.step()
        f, ax = osmnx.plot_graph(self.grid.G, show=False)
        nodes = [a.pos for a in self.schedule.agents]
        self.nodes.loc[nodes].plot(ax=ax)
        f.show()


class EvacuationAgent(Agent):
    """A person with an age"""
    def __init__(self, unique_id, model: EvacuationModel):
        super().__init__(unique_id, model)
        self.location = model.random.choice(list(model.G.nodes))
        self.model = model

    def step(self):
        print(self.location)
        self.move()

    def move(self):
        self.model.grid.move_agent(self, self.model.grid.get_neighbors(self.pos)[0])
        pass


