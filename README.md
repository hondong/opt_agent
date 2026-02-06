# A simple CodeAgent for a Supply Chain Optimization Model Interpretations

## Context
This repository is to accompany a live demo section in the [online workshop](https://www.linkedin.com/posts/dhanashreelele_informs-agentic-or-activity-7415998989789085697-C5qM?utm_source=share&utm_medium=member_desktop&rcm=ACoAAAUML_wBTmSGC7gKrAQewVWlcBWN7Qj6rhI) AI agent masterclass on Jan 9, 2026. The entire presented deck of this workshop is available [here](https://docs.google.com/presentation/d/18JXI1UmiNE6NOqYasGkOSYvnRRuBnRv1EshTVcQOBfY/edit?usp=sharing). Code here covers the specific section (Slide 60-74) presented by [Hongbo Dong](https://www.linkedin.com/in/hongbo-dong-4a443b24/).

Goal of this code repository is to illustrate one usecase where LLM models can be used to create an interpretation agent for facilitate users to interpret input/output and logic around an optimization model. It contains two parts:
1. A supply chain optimization model described in this paper: [Optimisation model for multi-item multi-echelon supply chains with nested multi-level products](https://www.sciencedirect.com/science/article/pii/S0377221720306950). Quetschlich, Moetz & Otto, European Journal of Operations Research. 2020 with open [data set](https://data.mendeley.com/datasets/pr3sdy5vp3/1). The benefits of using this set-up is its non-trivial and close to realisitic problems to be solved in supply chain planning/management.
2. A very simple CodeAgent (using [HuggingFace smolagents](https://huggingface.co/docs/smolagents/en/index) library) that can write code to analyze model input/outputs. The code agent here is very simple, no sophisticated implementation of agent memory or what so ever. This is only to serve the purpose of a gentle introduction of writing AI agents to users with Operations Research background.

The idea of using LLM to resolve the bottleneck of human-model-interface is considered in recent research papers, such as:

1. [Democratizing Optimization with Generative AI](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5511218), Simchi-Levi, Dai, Menache and Wu, Manuscript on SSRN, Oct. 2025
2. [Solver-in-the-Loop: MDP-Based Benchmarks for Self-Correction and Behavioral Rationality in Operations Research.](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6145307), Ao, Simchi-Levi and Wang, Jan. 2025

## Running the model and agent in Docker environment

I created to automatically install all necessary packages in an isolated container. Following the steps to reproduce results presented in the live demo: (Current Dockerfile version works well for Mac OS X, for other systems, adjustments on Dockerfile will be needed to install `pyscipopt` properly)

1. Clone this repository. 
```bash
git clone https://github.com/hbdong/opt_agent_wip.git
cd opt_agent_wip
```
Then create a [HuggingFace account](https://huggingface.co/) if you have not yet already. Further create an user access token. Replace the only line in `my_secrets.py` from
```
MY_HF_HUB_TOKEN = ""
```
to
```
MY_HF_HUB_TOKEN = "[my_created_hugging_face_token]"
```

2. Make sure Docker daemon is running on your machine (e.g., if on Mac OS X terminal run `open -a Docker`). For Docker beginners, install [Docker Desktop](https://docs.docker.com/get-started/get-docker/) and open the app.

3. Build Docker image and initiate a terminal.
```bash
docker build -t opt-agent .
docker run -it opt-agent bash
``` 

4. Running the optimization model. The last code line in the previous step would open a terminal inside the Docker container. The optimization model can be then run by:
```bash
python3 src/run.py
```
Depending on performance of machine, this step will take approximately 10 minutes solving an SCIP optimization model (mixed-integer programming). 

5. Query the agent by. 
```bash
python3 src/opt_agent.py -m 'Compute the number of distinct cars needed in each period from the input demand data. Save the results in a csv file and report the csv filename.'
```
Sample queries/prompts used in presentation is in the file `example_prompts.py`.

