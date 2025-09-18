"""
NeuroCognitive Architecture (NCA) - LLM CLI Commands

This module provides CLI commands for interacting with LLMs through
the NeuroCognitive Architecture.

Commands:
    query: Query an LLM with memory-enhanced, health-aware, and goal-directed context
    providers: List available LLM providers
    models: List available models for a provider
    config: View or update LLM integration configuration
"""

import asyncio
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional, Any, Iterable, Sequence, NamedTuple

import typer
import yaml
from rich.console import Console

_UNSAFE_EDITOR_ARGUMENT_CHARS = frozenset({"&", ";", "|", ">", "<", "`", "$", "!"})


class EditorPolicy(NamedTuple):
    """Allow-list definition for permitted editor executables and flags."""

    allowed_exact: frozenset[str]
    allowed_prefixes: tuple[str, ...] = ()


_SAFE_EDITOR_POLICIES: dict[str, EditorPolicy] = {
    # Terminal editors
    "nano": EditorPolicy(frozenset(), ("+",)),
    "nano.exe": EditorPolicy(frozenset(), ("+",)),
    "vi": EditorPolicy(frozenset(), ("+",)),
    "vi.exe": EditorPolicy(frozenset(), ("+",)),
    "vim": EditorPolicy(frozenset(), ("+",)),
    "vim.exe": EditorPolicy(frozenset(), ("+",)),
    "nvim": EditorPolicy(frozenset(), ("+",)),
    "nvim.exe": EditorPolicy(frozenset(), ("+",)),
    # Graphical editors with limited safe flags
    "code": EditorPolicy(frozenset({"--wait", "--reuse-window", "--new-window"})),
    "code.exe": EditorPolicy(frozenset({"--wait", "--reuse-window", "--new-window"})),
    "code-insiders": EditorPolicy(
        frozenset({"--wait", "--reuse-window", "--new-window"})
    ),
    "code-insiders.exe": EditorPolicy(
        frozenset({"--wait", "--reuse-window", "--new-window"})
    ),
    "codium": EditorPolicy(frozenset({"--wait", "--reuse-window", "--new-window"})),
    "codium.exe": EditorPolicy(
        frozenset({"--wait", "--reuse-window", "--new-window"})
    ),
    "subl": EditorPolicy(frozenset({"--wait"})),
    "subl.exe": EditorPolicy(frozenset({"--wait"})),
    "sublime_text": EditorPolicy(frozenset({"--wait"})),
    "sublime_text.exe": EditorPolicy(frozenset({"--wait"})),
    "gedit": EditorPolicy(frozenset({"--wait"})),
    "gedit.exe": EditorPolicy(frozenset({"--wait"})),
    # Windows editors
    "notepad": EditorPolicy(frozenset()),
    "notepad.exe": EditorPolicy(frozenset()),
    "notepad++": EditorPolicy(frozenset({"-multiInst", "-notabbar", "-nosession"})),
    "notepad++.exe": EditorPolicy(
        frozenset({"-multiInst", "-notabbar", "-nosession"})
    ),
}

# Import dependencies with graceful fallback for missing components
try:
    from neuroca.core.cognitive_control.goal_manager import GoalManager
except ImportError:
    GoalManager = None

try:
    from neuroca.core.health.dynamics import HealthDynamicsManager
except ImportError:
    HealthDynamicsManager = None

try:
    from neuroca.integration.exceptions import LLMIntegrationError, ProviderNotFoundError
    from neuroca.integration.manager import LLMIntegrationManager
except ImportError:
    LLMIntegrationError = Exception
    ProviderNotFoundError = Exception
    LLMIntegrationManager = None

try:
    from neuroca.memory.factory import create_memory_system
except ImportError:
    create_memory_system = None

# Configure logging
logger = logging.getLogger(__name__)

# Create console for rich output
console = Console()

# Create the Typer app
llm_app = typer.Typer(name="llm", help="Commands for interacting with LLMs through the NCA.")

# Default config path
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "neuroca" / "llm_config.yaml"


def _validate_editor_arguments(editor_key: str, arguments: Iterable[str]) -> list[str]:
    """Validate editor arguments against a strict allow-list for the executable."""

    policy = _SAFE_EDITOR_POLICIES.get(editor_key)
    if policy is None:
        raise ValueError(
            f"Editor executable '{editor_key}' is not in the supported allow-list"
        )

    safe_arguments: list[str] = []
    for argument in arguments:
        if not isinstance(argument, str):
            raise ValueError("Editor command arguments must be strings")
        if "\x00" in argument:
            raise ValueError("Editor command contains null bytes")
        if any(control in argument for control in ("\r", "\n")):
            raise ValueError("Editor command contains control characters")
        if any(char in _UNSAFE_EDITOR_ARGUMENT_CHARS for char in argument):
            raise ValueError(
                "Editor command contains potentially unsafe shell metacharacters"
            )
        if any(ch.isspace() for ch in argument):
            raise ValueError("Editor command arguments must not include whitespace")

        if argument in policy.allowed_exact or any(
            argument.startswith(prefix) for prefix in policy.allowed_prefixes
        ):
            safe_arguments.append(argument)
            continue

        raise ValueError(
            f"Argument '{argument}' is not permitted for editor '{editor_key}'"
        )

    return safe_arguments


def _build_editor_command(editor_cmd: Sequence[str], config_path: Path) -> list[str]:
    """Return a sanitized command sequence for launching the editor."""

    if not editor_cmd:
        raise ValueError("Editor command must not be empty")

    executable_path, editor_key = _validate_editor_executable(editor_cmd[0])
    safe_arguments = _validate_editor_arguments(editor_key, editor_cmd[1:])
    safe_config_path = _sanitize_editor_config_path(config_path)
    command = [executable_path, *safe_arguments, safe_config_path]
    return command


def _validate_editor_executable(executable: str) -> tuple[str, str]:
    """Ensure the resolved editor path is absolute and backed by an allow-listed executable."""

    if not isinstance(executable, str):
        raise ValueError("Editor executable must be a string")
    if "\x00" in executable or any(control in executable for control in ("\r", "\n")):
        raise ValueError("Editor executable contains control characters")

    executable_path = Path(executable)
    if not executable_path.is_absolute():
        raise ValueError("Editor executable path must be absolute")
    if not executable_path.exists():
        raise ValueError("Editor executable path does not exist")
    if not executable_path.is_file():
        raise ValueError("Editor executable path must reference a file")

    canonical_name = executable_path.name.lower()
    if canonical_name not in _SAFE_EDITOR_POLICIES:
        raise ValueError(
            f"Editor '{canonical_name}' is not permitted. Choose a supported editor."
        )

    return os.fspath(executable_path), canonical_name


def _sanitize_editor_config_path(config_path: Path) -> str:
    """Return a normalised absolute filesystem path for the config file."""

    expanded = config_path.expanduser()
    absolute = os.path.abspath(os.fspath(expanded))
    if "\x00" in absolute or any(control in absolute for control in ("\r", "\n")):
        raise ValueError("Configuration path contains invalid control characters")
    return absolute


def _launch_editor(command: Sequence[str]) -> None:
    """Execute the configured editor with hardening applied."""

    if not command:
        raise ValueError("Editor command must not be empty")

    executable, *arguments = command
    executable_path, editor_key = _validate_editor_executable(executable)
    if not arguments:
        raise ValueError("Editor launch command missing configuration path argument")

    option_arguments = arguments[:-1]
    config_argument = arguments[-1]
    if not isinstance(config_argument, (str, os.PathLike)):
        raise ValueError("Configuration path argument must be a string or path-like")

    safe_arguments = _validate_editor_arguments(editor_key, option_arguments)
    safe_config_path = _sanitize_editor_config_path(Path(config_argument))
    sanitized_command = [executable_path, *safe_arguments, safe_config_path]
    safe_command = _finalize_editor_command(sanitized_command)

    subprocess.run(safe_command, check=True, shell=False)


def _finalize_editor_command(command: Sequence[str]) -> tuple[str, ...]:
    """Re-validate and freeze an editor command before execution."""

    sanitized_parts: list[str] = []
    for part in command:
        if not isinstance(part, str):
            raise ValueError("Editor command components must be strings")
        if not part:
            raise ValueError("Editor command components must not be empty")
        if "\x00" in part or any(control in part for control in ("\r", "\n")):
            raise ValueError("Editor command contains invalid control characters")
        sanitized_parts.append(part)
    return tuple(sanitized_parts)


def load_config(config_path: Optional[Path] = None) -> dict:
    """
    Load LLM integration configuration.
    
    Args:
        config_path: Path to configuration file (defaults to ~/.config/neuroca/llm_config.yaml)
        
    Returns:
        Configuration dictionary
    """
    config_path = config_path or DEFAULT_CONFIG_PATH
    
    # Create default config if it doesn't exist
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        default_config = {
            "default_provider": "ollama",
            "default_model": "gemma3:4b",
            "providers": {
                "openai": {
                    "api_key": os.environ.get("OPENAI_API_KEY", ""),
                    "default_model": "gpt-4"
                },
                "anthropic": {
                    "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
                    "default_model": "claude-3-opus-20240229"
                },
                "ollama": {
                    "base_url": "http://127.0.0.1:11434",
                    "default_model": "gemma3:4b"
                }
            },
            "store_interactions": True,
            "memory_integration": True,
            "health_awareness": True,
            "goal_directed": True
        }
        
        with open(config_path, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False)
        
        console.print(f"Created default configuration at {config_path}")
    
    # Load configuration
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
            
        return config or {}
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        return {}


async def get_managers(config: dict) -> tuple:
    """
    Create and initialize managers needed for LLM integration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Tuple of (llm_manager, additional_context)
    """
    # Check if core dependencies are available
    if not LLMIntegrationManager:
        console.print("[red]LLM integration components not available. Please check installation.[/red]")
        return None, {}
    
    llm_manager = None
    additional_context = {}
    
    try:
        # Initialize memory manager if enabled and available
        memory_manager = None
        if config.get("memory_integration", True) and create_memory_system:
            memory_manager = create_memory_system("manager")
            
        # Initialize health manager if enabled and available
        health_manager = None
        if config.get("health_awareness", True) and HealthDynamicsManager:
            health_manager = HealthDynamicsManager()
            
        # Initialize goal manager if enabled and available
        goal_manager = None
        if config.get("goal_directed", True) and GoalManager:
            goal_manager = GoalManager(
                health_manager=health_manager,
                memory_manager=memory_manager
            )
        
        # Initialize LLM integration manager
        llm_manager = LLMIntegrationManager(
            config=config,
            memory_manager=memory_manager,
            health_manager=health_manager,
            goal_manager=goal_manager
        )
        
        # Add system-wide context
        if health_manager:
            system_health = health_manager.get_system_health()
            additional_context["system_health"] = {
                "state": system_health.state.name,
                "parameters": system_health.parameters
            }
            
    except Exception as e:
        logger.error(f"Error initializing managers: {str(e)}")
        
    return llm_manager, additional_context


# Define response format enum for Typer
class ResponseFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    LIST = "list"
    MARKDOWN = "markdown"


@llm_app.command("query")
def query_llm(
    prompt: Annotated[str, typer.Argument(help="The prompt to send to the LLM")],
    provider: Annotated[Optional[str], typer.Option("--provider", "-p", help="LLM provider to use")] = None,
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="Model to use")] = None,
    config_path: Annotated[Optional[str], typer.Option("--config", "-c", help="Path to configuration file")] = None,
    memory: Annotated[bool, typer.Option("--memory/--no-memory", help="Enable/disable memory integration")] = True,
    health: Annotated[bool, typer.Option("--health/--no-health", help="Enable/disable health awareness")] = True,
    goals: Annotated[bool, typer.Option("--goals/--no-goals", help="Enable/disable goal-directed context")] = True,
    temperature: Annotated[Optional[float], typer.Option("--temperature", "-t", help="Temperature for generation")] = None,
    max_tokens: Annotated[Optional[int], typer.Option("--max-tokens", help="Maximum tokens for generation")] = None,
    format: Annotated[ResponseFormat, typer.Option("--format", "-f", help="Output format")] = ResponseFormat.TEXT,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show detailed response information")] = False,
):
    """
    Query an LLM with NCA-enhanced context.
    
    Examples:
        neuroca llm query "What is neuroplasticity?"
        neuroca llm query --provider ollama --model gemma3:4b "Explain cognitive architecture"
        neuroca llm query --no-memory "How does working memory function?"
        neuroca llm query --format json "Generate a list of 5 cognitive biases"
    """
    # Check if LLM integration is available
    if not LLMIntegrationManager:
        console.print("[red]LLM integration not available. Please install missing dependencies.[/red]")
        console.print("Missing components may include: neuroca.integration, neuroca.core modules")
        raise typer.Exit(code=1)
    
    # Load configuration
    config = load_config(Path(config_path) if config_path else None)
    
    # Override config settings
    config["memory_integration"] = memory
    config["health_awareness"] = health
    config["goal_directed"] = goals
    
    # Execute the query
    async def execute():
        llm_manager, additional_context = await get_managers(config)
        
        if not llm_manager:
            console.print("[red]Failed to initialize LLM integration manager[/red]")
            raise typer.Exit(code=1)
        
        try:
            # Query the LLM
            response = await llm_manager.query(
                prompt=prompt,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                additional_context=additional_context
            )
            
            # Process response based on requested format
            if format == ResponseFormat.JSON:
                try:
                    from neuroca.integration.utils import parse_response
                    content = parse_response(response.content, "json")
                    formatted_content = json.dumps(content, indent=2)
                except ImportError:
                    formatted_content = response.content
            elif format == ResponseFormat.LIST:
                try:
                    from neuroca.integration.utils import parse_response
                    content = parse_response(response.content, "list")
                    formatted_content = "\n".join([f"- {item}" for item in content])
                except ImportError:
                    formatted_content = response.content
            elif format == ResponseFormat.MARKDOWN:
                formatted_content = response.content
            else:  # text
                formatted_content = response.content
            
            # Output the response
            if output:
                with open(output, "w") as f:
                    f.write(formatted_content)
                console.print(f"Response written to [bold]{output}[/bold]")
            else:
                console.print("\n[bold]===== LLM Response =====[/bold]\n")
                console.print(formatted_content)
                console.print("")
            
            # Show verbose information if requested
            if verbose:
                console.print("\n[bold]===== Response Details =====[/bold]\n")
                console.print(f"Provider: [cyan]{getattr(response, 'provider', 'unknown')}[/cyan]")
                console.print(f"Model: [cyan]{getattr(response, 'model', 'unknown')}[/cyan]")
                if hasattr(response, 'usage') and response.usage:
                    console.print(f"Tokens: [cyan]{response.usage.total_tokens}[/cyan] " + 
                               f"(Prompt: {response.usage.prompt_tokens}, " + 
                               f"Completion: {response.usage.completion_tokens})")
                console.print(f"Time: [cyan]{getattr(response, 'elapsed_time', 0):.2f}s[/cyan]")
                if hasattr(response, 'metadata') and "health_state" in response.metadata:
                    console.print(f"Health State: [yellow]{response.metadata['health_state']}[/yellow]")
                
                if hasattr(response, 'metadata') and "caution_note" in response.metadata:
                    console.print(f"[yellow]Caution: {response.metadata['caution_note']}[/yellow]")
                
        except Exception as e:
            if "ProviderNotFound" in str(type(e)):
                console.print(f"[red]Provider '{provider or config.get('default_provider')}' not configured[/red]")
            elif "LLMIntegration" in str(type(e)):
                console.print(f"[red]LLM integration error: {str(e)}[/red]")
            else:
                console.print(f"[red]Error: {str(e)}[/red]")
            raise typer.Exit(code=1)
        finally:
            # Close the manager
            if hasattr(llm_manager, 'close'):
                await llm_manager.close()
    
    # Run the async function
    asyncio.run(execute())


@llm_app.command("providers")
def list_providers(
    config_path: Annotated[Optional[str], typer.Option("--config", "-c", help="Path to configuration file")] = None
):
    """
    List available LLM providers.
    
    Example:
        neuroca llm providers
    """
    # Load configuration
    config = load_config(Path(config_path) if config_path else None)
    
    console.print("\n[bold]===== Available LLM Providers =====[/bold]\n")
    
    if not config.get("providers"):
        console.print("No providers configured")
    else:
        for provider in config["providers"]:
            if provider == config.get("default_provider"):
                console.print(f"[bold green]* {provider}[/bold green] (default)")
            else:
                console.print(f"  {provider}")
                
    console.print(f"\nDefault provider: [cyan]{config.get('default_provider', 'None')}[/cyan]")
    console.print(f"Default model: [cyan]{config.get('default_model', 'None')}[/cyan]")


@llm_app.command("config")
def manage_config(
    view: Annotated[bool, typer.Option("--view", help="View current configuration")] = False,
    edit: Annotated[bool, typer.Option("--edit", help="Edit configuration file")] = False,
    path: Annotated[bool, typer.Option("--path", help="Show configuration file path")] = False,
    provider: Annotated[Optional[str], typer.Option("--provider", help="Set default provider")] = None,
    model: Annotated[Optional[str], typer.Option("--model", help="Set default model")] = None,
    api_key: Annotated[Optional[str], typer.Option("--api-key", help="Set API key for provider (specify provider with --provider)")] = None,
    config_path: Annotated[Optional[str], typer.Option("--config", "-c", help="Path to configuration file")] = None
):
    """
    View or update LLM integration configuration.
    
    Examples:
        neuroca llm config --view
        neuroca llm config --path
        neuroca llm config --provider openai --model gpt-4
        neuroca llm config --provider openai --api-key sk-...
        neuroca llm config --edit
    """
    # Determine configuration path
    conf_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    
    # Create default config if it doesn't exist
    config = load_config(conf_path)
    
    # Handle path option
    if path:
        console.print(f"Configuration file: [cyan]{conf_path}[/cyan]")
        return
    
    # Handle edit option
    if edit:
        editor_setting = os.environ.get("EDITOR")
        if editor_setting:
            try:
                editor_cmd = shlex.split(editor_setting)
            except ValueError as err:
                console.print(
                    "[red]Unable to parse EDITOR command from environment:"
                    f" {err}. Falling back to default editor.[/red]"
                )
                editor_cmd = []
        else:
            editor_cmd = []

        if not editor_cmd:
            editor_cmd = ["notepad"] if os.name == "nt" else ["nano"]

        editor_executable = editor_cmd[0]
        resolved_editor = shutil.which(editor_executable)
        if resolved_editor is None:
            console.print(
                "[red]Editor executable not found. Set the EDITOR environment variable",
                " to a valid command.[/red]"
            )
            raise typer.Exit(code=1)

        try:
            safe_editor_cmd = _build_editor_command([resolved_editor, *editor_cmd[1:]], conf_path)
        except ValueError as err:
            console.print(
                "[red]Unsafe editor command resolved from EDITOR environment variable:",
                f" {err}. Aborting launch.[/red]",
            )
            raise typer.Exit(code=1)

        try:
            _launch_editor(safe_editor_cmd)
        except FileNotFoundError:
            console.print(
                "[red]Editor executable not found. Set the EDITOR environment variable"
                " to a valid command.[/red]"
            )
            raise typer.Exit(code=1)
        except subprocess.CalledProcessError as err:
            console.print(
                "[red]Editor exited with a non-zero status code."
                f" (code: {err.returncode})[/red]"
            )
            raise typer.Exit(code=err.returncode or 1)
        except ValueError as err:
            console.print(
                "[red]Unsafe editor command prevented execution:",
                f" {err}. Please update your EDITOR setting.[/red]",
            )
            raise typer.Exit(code=1)
        return
    
    # Handle view option
    if view:
        console.print("\n[bold]===== LLM Integration Configuration =====[/bold]\n")
        
        # Generate masked config for display
        display_config = config.copy()
        for _p_name, p_config in display_config.get("providers", {}).items():
            if "api_key" in p_config and p_config["api_key"]:
                p_config["api_key"] = "****" + p_config["api_key"][-4:] if len(p_config["api_key"]) > 4 else "********"
        
        console.print(yaml.dump(display_config, default_flow_style=False))
        return
    
    # Handle configuration updates
    if provider or model or api_key:
        modified = False
        
        # Set default provider
        if provider:
            config["default_provider"] = provider
            modified = True
            console.print(f"Default provider set to [cyan]{provider}[/cyan]")
        
        # Set default model
        if model:
            if provider:
                if "providers" not in config:
                    config["providers"] = {}
                if provider not in config["providers"]:
                    config["providers"][provider] = {}
                config["providers"][provider]["default_model"] = model
                console.print(f"Default model for {provider} set to [cyan]{model}[/cyan]")
            else:
                config["default_model"] = model
                console.print(f"Default model set to [cyan]{model}[/cyan]")
            modified = True
        
        # Set API key
        if api_key:
            if not provider:
                console.print("[red]Please specify a provider with --provider when setting an API key[/red]")
                raise typer.Exit(code=1)
                
            if "providers" not in config:
                config["providers"] = {}
            if provider not in config["providers"]:
                config["providers"][provider] = {}
            config["providers"][provider]["api_key"] = api_key
            console.print(f"API key for [cyan]{provider}[/cyan] updated")
            modified = True
        
        # Save updated configuration
        if modified:
            try:
                with open(conf_path, "w") as f:
                    yaml.dump(config, f, default_flow_style=False)
                console.print(f"Configuration saved to [cyan]{conf_path}[/cyan]")
            except Exception as e:
                console.print(f"[red]Error saving configuration: {str(e)}[/red]")
                raise typer.Exit(code=1)
        
        return
    
    # If no options specified, show usage
    console.print("Please specify an option. Use --help for more information.")
    raise typer.Exit(code=1)


@llm_app.command("bench")
def bench_llm(
    provider: Annotated[str, typer.Option("--provider", "-p", help="Provider name (default: ollama)")] = "ollama",
    model: Annotated[str, typer.Option("--model", "-m", help="Model name (default: gemma3:4b)")] = "gemma3:4b",
    suite: Annotated[str, typer.Option("--suite", help="Comma-separated: latency; 'all' currently maps to 'latency'")] = "all",
    runs: Annotated[int, typer.Option("--runs", help="Runs for applicable suites (default: 20)")] = 20,
    concurrency: Annotated[int, typer.Option("--concurrency", help="Concurrency for applicable suites (default: 2)")] = 2,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON results")] = False,
    explain: Annotated[bool, typer.Option("--explain", help="Print a concise summary after JSON")] = False,
) -> None:
    """
    Run the local LLM benchmark suite using the in-repo benchmarks module.
    Examples:
        neuroca llm bench --provider ollama --model gemma3:4b --suite all --runs 20 --concurrency 2 --pretty --explain
        neuroca llm bench --suite latency,resilience --runs 50 --concurrency 4
    """
    # Import modular latency bench from repo; add repo root to sys.path if needed
    try:
        import benchmarks.llm_bench.latency as bench_latency  # type: ignore
        import benchmarks.llm_bench.util as bench_util  # type: ignore
    except Exception:
        try:
            here = Path(__file__).resolve()
            # .../_Neuroca/src/neuroca/cli/commands/llm.py -> repo root is parents[4]
            repo_root = here.parents[4]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
            import benchmarks.llm_bench.latency as bench_latency  # type: ignore
            import benchmarks.llm_bench.util as bench_util  # type: ignore
        except Exception as e:
            console.print("[red]Benchmarks package not available.[/red]")
            console.print("Expected package: benchmarks/llm_bench with latency.py and util.py")
            raise typer.Exit(code=1)

    suites = [s.strip().lower() for s in suite.split(",") if s.strip()]
    if "all" in suites:
        suites = ["latency"]

    async def _execute_bench():
        # Minimal manager config for stable benchmarking (no templates, no memory/health/goals)
        cfg = bench_util.build_manager_config(provider=provider, model=model, template_dirs=[])
        mgr = LLMIntegrationManager(config=cfg)
        try:
            results: dict[str, Any] = {}
            if "latency" in suites:
                results["latency"] = await bench_latency.run(
                    mgr,
                    provider=provider,
                    model=model,
                    runs=runs,
                    concurrency=concurrency,
                )

            # Print JSON results
            payload = results["latency"] if len(suites) == 1 else results
            text = json.dumps(payload, indent=2) if pretty else json.dumps(payload)
            console.print(text)

            if explain:
                try:
                    err = payload.get("errors", 0) if isinstance(payload, dict) else 0
                    console.print(f"[bold]Summary:[/bold] suite={','.join(suites)} errors={err}")
                except Exception:
                    pass
        finally:
            if hasattr(mgr, "close"):
                await mgr.close()

    try:
        asyncio.run(_execute_bench())
    except Exception as e:
        console.print(f"[red]Benchmark error: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    llm_app()
