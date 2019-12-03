from mesa import Agent, Model
from mesa.time import RandomActivation


class EvacuationAgent(Agent):
    """A person with an age"""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.age = 25


class EvacuationModel(Model):
    """A model with some number of agents"""
    def __init__(self, num_agents):
        self.num_agents = num_agents
        self.schedule = RandomActivation(self)
        # Create agents
        for i in range(self.num_agents):
            a = EvacuationAgent(i, self)
            self.schedule.add(a)

    def step(self):
        """Advance the model by one step."""
        self.schedule.step()


if __name__ == '__main__':
    model = EvacuationModel(10)
    model.step()
