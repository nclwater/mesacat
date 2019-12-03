from mesa import Agent, Model


class EvacuationAgent(Agent):
    """A person with an age"""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.age = 25


class EvacuationModel(Model):
    """A model with some number of agents"""
    def __init__(self, N):
        self.num_agents = N

        # Create agents
        for i in range(self.num_agents):
            a = EvacuationAgent(i, self)
