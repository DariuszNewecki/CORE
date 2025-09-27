import click

from ...service_registry import ServiceRegistry
from ...services.agent_service import AgentService
from ...services.llm_service import LLMService
from ...services.tool_service import ToolService
from ...services.workspace_service import WorkspaceService


@click.command()
@click.option("--prompt", required=True, help="The prompt for the agent")
@click.option("--model", default="gpt-4", help="The model to use for the agent")
@click.option("--workspace-dir", default="workspace", help="The workspace directory")
@click.option("--tools", multiple=True, help="Tools to make available to the agent")
def agent(prompt, model, workspace_dir, tools):
    """Run an agent with the given prompt and configuration."""

    service_registry = ServiceRegistry()

    workspace_service = service_registry.get(WorkspaceService)
    llm_service = service_registry.get(LLMService)
    tool_service = service_registry.get(ToolService)
    agent_service = service_registry.get(AgentService)

    workspace = workspace_service.setup_workspace(workspace_dir)
    llm = llm_service.get_llm(model)
    available_tools = tool_service.load_tools(tools)

    agent = agent_service.create_agent(llm, available_tools)
    result = agent.run(prompt, workspace)

    click.echo(f"Agent execution completed: {result}")
