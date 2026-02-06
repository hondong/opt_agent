from huggingface_hub import login
from smolagents import InferenceClientModel, CodeAgent, InferenceClientModel
from agent_tools import GetSolutionFlow, GetSolutionInventory, get_product_list_by_group
from model_context import MODEL_CONTEXT_STRING
from my_secrets import MY_HF_HUB_TOKEN
import click

if MY_HF_HUB_TOKEN:
    login(token=MY_HF_HUB_TOKEN)
else:
    login()

my_inference_model = InferenceClientModel(
    # model_id="deepseek-ai/DeepSeek-V3.2",
    # model_id="deepseek-ai/deepseek-coder-33b-instruct",
    model_id="Qwen/Qwen2.5-Coder-32B-Instruct",
    token=MY_HF_HUB_TOKEN,
    temperature=0.0,
)

agent = CodeAgent(
    tools=[
        get_product_list_by_group,
        GetSolutionFlow(),
        GetSolutionInventory(),
    ], model=my_inference_model,
    additional_authorized_imports=['pandas', 'numpy', 'matplotlib.pyplot'],
)

# A simple cli using Python package click to allow user to input user_query and run the agent
if __name__ == "__main__":

    @click.command()
    @click.option('-m', '--message', help='The user query to be processed by the agent.')
    def run_agent(message: str):
        response = agent.run(
            MODEL_CONTEXT_STRING + message,
            max_steps=10,
        )
        print("Agent Response:")
        print(response)

    run_agent() # pylint: disable=no-value-for-parameter
