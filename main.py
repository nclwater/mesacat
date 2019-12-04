from mesa import Agent, Model
from mesa.time import RandomActivation
import osmnx
from networkx import MultiDiGraph
from mesa.space import ContinuousSpace


class EvacuationModel(Model):
    """A model with some number of agents"""
    def __init__(self, num_agents, osm_file, seed=None):
        self._seed = seed
        self.num_agents = num_agents
        self.schedule = RandomActivation(self)
        self.G: MultiDiGraph = osmnx.graph_from_file(osm_file)
        self.gdf = osmnx.save_load.graph_to_gdfs(self.G, nodes=False, node_geometry=False)
        minx, miny, maxx, maxy = self.gdf.geometry.total_bounds
        self.space = ContinuousSpace(x_max=maxx, x_min=minx, y_max=maxy, y_min=miny, torus=False)
        # Create agents
        for i in range(self.num_agents):
            a = EvacuationAgent(i, self)
            self.schedule.add(a)

            x = self.random.uniform(self.space.x_min, self.space.x_max)
            y = self.random.uniform(self.space.y_min, self.space.y_max)
            self.space.place_agent(a, (x, y))

    def step(self):
        """Advance the model by one step."""
        self.schedule.step()


class EvacuationAgent(Agent):
    """A person with an age"""
    def __init__(self, unique_id, model: EvacuationModel):
        super().__init__(unique_id, model)
        self.location = model.random.choice(list(model.G.nodes))
        self.model = model

    def step(self):
        print(self.location)

    def move(self):
        pass


