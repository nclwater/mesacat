from mesa import Agent, Model
from mesa.time import RandomActivation
import osmnx


class EvacuationAgent(Agent):
    """A person with an age"""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.age = 25

    def step(self):
        pass


class EvacuationModel(Model):
    """A model with some number of agents"""
    def __init__(self, num_agents, osm_file):
        self.num_agents = num_agents
        self.schedule = RandomActivation(self)
        self.G = osmnx.graph_from_file(osm_file)
        # Create agents
        for i in range(self.num_agents):
            a = EvacuationAgent(i, self)
            self.schedule.add(a)

    def step(self):
        """Advance the model by one step."""
        self.schedule.step()
