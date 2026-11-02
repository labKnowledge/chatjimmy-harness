"""Typer CLI entrypoint for the ChatJimmy harness."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from chatjimmy_harness import __version__
from chatjimmy_harness.agent import run_agent
from chatjimmy_harness.client import Attachment, ChatJimmy, DEFAULT_MODEL
from chatjimmy_harness.harness import load_suite, run_bench, run_suite
from chatjimmy_harness.tools import DEFAULT_TOOL_NAMES

COMMANDS = frozenset(
    {
        "version",
        "health",
        "models",
        "ask",
        "chat",
        "run",
        "bench",
        "doctor",
        "agent",
        "tools",
        "help",
    }
)

app = typer.Typer(
    name="chatjimmy",
    help='Interactive agent by default. Print one-shot with -p. Try: cj   or   cj -p "What is 2+2?"',
    no_args_is_help=False,
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()
err_console = Console(stderr=True)


def _client(base_url: str, timeout: int) -> ChatJimmy:
    return ChatJimmy(base_url=base_url, timeout=timeout)


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _print_stats(stats) -> None:
    if stats is None:
        err_console.print("[dim](no stats returned)[/dim]")
        return
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("k", style="dim")
    table.add_column("v")
    for k, v in [
        ("prefill", f"{stats.prefill_tokens} tok @ {stats.prefill_rate:.0f} tok/s"),
        ("decode", f"{stats.decode_tokens} tok @ {stats.decode_rate:.0f} tok/s"),
        ("ttft", f"{stats.ttft:.4f}s"),
        ("total", f"{stats.total_time:.4f}s"),
        ("roundtrip", f"{stats.roundtrip_time:.1f} ms"),
        ("done", stats.done_reason or "-"),
    ]:
        table.add_row(k, v)
    err_console.print(table)


def _load_attachment(path: Path) -> Attachment:
    data = path.read_bytes()
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        content = data.decode("latin-1")
    return Attachment(name=path.name, size=len(data), content=content)


def _resolve_prompt(prompt: str) -> str:
    """Accept `-` or empty+piped stdin as the prompt body."""
    if prompt == "-":
        data = sys.stdin.read()
        if not data.strip():
            err_console.print("[red]empty stdin[/red]")
            raise typer.Exit(2)
        return data
    if not prompt and not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data
    return prompt


def _run_ask(
    *,
    base_url: str,
    timeout: int,
    prompt: str,
    model: str,
    system: str,
    top_k: int,
    stream: bool,
    stats: bool,
    attach: Path | None,
    json_out: bool,
) -> None:
    prompt = _resolve_prompt(prompt)
    if not prompt.strip():
        err_console.print('[red]need a prompt[/red] — try: cj "What is 2+2?"')
        raise typer.Exit(2)

    client = _client(base_url, timeout)
    attachment = _load_attachment(attach) if attach else None
    messages = [{"role": "user", "content": prompt}]
    show_stats = stats or _env_flag("CHATJIMMY_STATS")

    if stream and not json_out:
        gen = client.chat_stream(
            messages=messages,
            model=model,
            system_prompt=system,
            top_k=top_k,
            attachment=attachment,
        )
        resp = None
        try:
            while True:
                chunk = next(gen)
                console.print(chunk, end="", markup=False, soft_wrap=True)
        except StopIteration as stop:
            resp = stop.value
        console.print()
        if show_stats:
            _print_stats(resp.stats if resp else None)
        return

    resp = client.chat(
        messages=messages,
        model=model,
        system_prompt=system,
        top_k=top_k,
        attachment=attachment,
    )
    if json_out:
        console.print_json(
            data={
                "text": resp.text,
                "stats": None if resp.stats is None else resp.stats.__dict__,
            }
        )
        return

    console.print(resp.text, markup=False, soft_wrap=True)
    if show_stats:
        _print_stats(resp.stats)


def _rewrite_bare_prompt_argv() -> None:
    """`cj "hello"` → `cj ask "hello"` (print). Empty args stay empty → interactive agent."""
    args = sys.argv[1:]
    if not args:
        return

    i = 0
    while i < len(args):
        a = args[i]
        if a in {"-h", "--help"}:
            return
        if a in {"-p", "--print"}:
            # value belongs to print mode; do not rewrite into ask
            if i + 1 < len(args):
                return
            return
        if a.startswith("--print="):
            return
        if a.startswith("--"):
            if a in {"--base-url", "--timeout", "--workspace", "-w"} and i + 1 < len(args):
                i += 2
                continue
            if a.split("=", 1)[0] in {"--base-url", "--timeout", "--workspace"}:
                i += 1
                continue
            if "=" in a:
                i += 1
                continue
            i += 1
            continue
        if a in {"-w"}:
            i += 2 if i + 1 < len(args) else 1
            continue
        if a.startswith("-") and a != "-":
            i += 1
            continue
        # first positional
        if a not in COMMANDS:
            sys.argv.insert(i + 1, "ask")
        return


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    base_url: str = typer.Option(
        "https://chatjimmy.ai",
        "--base-url",
        envvar="CHATJIMMY_BASE_URL",
        help="API base URL",
    ),
    timeout: int = typer.Option(
        60,
        "--timeout",
        envvar="CHATJIMMY_TIMEOUT",
        help="HTTP timeout in seconds",
    ),
    print_prompt: Optional[str] = typer.Option(
        None,
        "--print",
        "-p",
        help="One-shot print mode (non-interactive ask). Example: cj -p \"What is 2+2?\"",
    ),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        help="Workspace for the default interactive agent",
    ),
    stats: bool = typer.Option(
        False,
        "--stats",
        help="Show HC1 stats with -p print mode",
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url
    ctx.obj["timeout"] = timeout
    ctx.obj["workspace"] = workspace.resolve()

    if ctx.invoked_subcommand is not None:
        return

    # cj -p "…" → print one-shot answer
    if print_prompt is not None:
        _run_ask(
            base_url=base_url,
            timeout=timeout,
            prompt=print_prompt,
            model=DEFAULT_MODEL,
            system="",
            top_k=8,
            stream=True,
            stats=stats,
            attach=None,
            json_out=False,
        )
        raise typer.Exit(0)

    # cj → interactive agent REPL
    from chatjimmy_harness.config import HarnessConfig, config_from_env

    cfg = config_from_env(HarnessConfig())
    client = _client(base_url, timeout)
    _run_agent_repl(
        client=client,
        workspace=workspace.resolve(),
        tools=list(DEFAULT_TOOL_NAMES),
        system="",
        model=DEFAULT_MODEL,
        top_k=8,
        max_turns=cfg.max_turns,
        allow_shell=True,
        command_timeout_s=30.0,
        first_prompt="",
        mode=cfg.interaction_mode,
    )
    raise typer.Exit(0)


@app.command("version")
def version_cmd() -> None:
    """Print harness version."""
    console.print(__version__)


@app.command()
def doctor(ctx: typer.Context) -> None:
    """One-shot readiness check: version, PATH, API health, models."""
    from shutil import which

    ok = True
    console.print(f"[bold]chatjimmy-harness[/bold] {__version__}")

    for name in ("chatjimmy", "cj"):
        path = which(name)
        if path:
            console.print(f"[green]✓[/green] {name} → {path}")
        else:
            ok = False
            console.print(
                f"[red]✗[/red] {name} not on PATH — "
                "run: uv tool install -e .  (and put ~/.local/bin on PATH)"
            )

    client = _client(ctx.obj["base_url"], ctx.obj["timeout"])
    try:
        h = client.health()
    except Exception as exc:  # noqa: BLE001
        ok = False
        console.print(f"[red]✗[/red] API unreachable: {exc}")
    else:
        if h.healthy:
            detail = h.backend_details.get("hardware_name", "")
            q = h.backend_details.get("queue_size", "?")
            console.print(
                f"[green]✓[/green] API healthy"
                + (f"  ({detail}, queue={q})" if detail else "")
            )
        else:
            ok = False
            console.print(f"[red]✗[/red] API unhealthy: status={h.status} backend={h.backend}")

    try:
        ms = client.models()
        ids = ", ".join(m.id for m in ms) or "(none)"
        console.print(f"[green]✓[/green] models: {ids}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        console.print(f"[red]✗[/red] models: {exc}")

    console.print("[dim]try:[/dim] cj")
    console.print('[dim]     [/dim] cj -p "What is 2+2?"')
    console.print("[dim]     [/dim] chatjimmy run examples/smoke.json")
    raise typer.Exit(0 if ok else 1)


@app.command("tools")
def tools_cmd() -> None:
    """List built-in agent tools."""
    from chatjimmy_harness.tools import build_registry, tool_specs_prompt

    console.print(tool_specs_prompt(build_registry()))


@app.command()
def health(ctx: typer.Context) -> None:
    """Check chatjimmy.ai health."""
    client = _client(ctx.obj["base_url"], ctx.obj["timeout"])
    try:
        h = client.health()
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]unreachable:[/red] {exc}")
        raise typer.Exit(1) from exc
    color = "green" if h.healthy else "red"
    console.print(f"[{color}]status={h.status} backend={h.backend}[/{color}]")
    if h.backend_details:
        console.print(json.dumps(h.backend_details, indent=2))
    console.print(f"[dim]{h.timestamp}[/dim]")
    raise typer.Exit(0 if h.healthy else 1)


@app.command()
def models(ctx: typer.Context) -> None:
    """List available models."""
    client = _client(ctx.obj["base_url"], ctx.obj["timeout"])
    table = Table("id", "owned_by", "created")
    for m in client.models():
        table.add_row(m.id, m.owned_by, str(m.created))
    console.print(table)


@app.command()
def ask(
    ctx: typer.Context,
    prompt: str = typer.Argument(
        "",
        help='User prompt (use "-" to read stdin). Or: cj "your question"',
    ),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m"),
    system: str = typer.Option("", "--system", "-s", help="System prompt"),
    top_k: int = typer.Option(8, "--top-k", "-k"),
    stream: bool = typer.Option(True, "--stream/--no-stream"),
    stats: bool = typer.Option(
        False,
        "--stats",
        help="Print HC1 inference stats (or set CHATJIMMY_STATS=1)",
    ),
    attach: Optional[Path] = typer.Option(
        None, "--attach", "-a", exists=True, dir_okay=False, help="Attach a file"
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON result"),
) -> None:
    """Single-turn chat completion."""
    _run_ask(
        base_url=ctx.obj["base_url"],
        timeout=ctx.obj["timeout"],
        prompt=prompt,
        model=model,
        system=system,
        top_k=top_k,
        stream=stream,
        stats=stats,
        attach=attach,
        json_out=json_out,
    )


@app.command()
def chat(
    ctx: typer.Context,
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m"),
    system: str = typer.Option("", "--system", "-s"),
    top_k: int = typer.Option(8, "--top-k", "-k"),
    stats: bool = typer.Option(False, "--stats"),
) -> None:
    """Interactive multi-turn REPL. Commands: /reset /stats /system /exit."""
    client = _client(ctx.obj["base_url"], ctx.obj["timeout"])
    messages: list[dict[str, str]] = []
    show_stats = stats or _env_flag("CHATJIMMY_STATS")
    system_prompt = system

    console.print(
        Panel.fit(
            f"[bold]chatjimmy[/bold]  model={model}  top_k={top_k}\n"
            "message  ·  /reset  /stats  /system …  /exit",
            border_style="cyan",
        )
    )

    while True:
        try:
            user = console.input("[bold cyan]you>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        if not user:
            continue
        if user in {"/exit", "/quit", ":q"}:
            break
        if user == "/reset":
            messages.clear()
            console.print("[dim]history cleared[/dim]")
            continue
        if user == "/stats":
            show_stats = not show_stats
            console.print(f"[dim]stats={'on' if show_stats else 'off'}[/dim]")
            continue
        if user.startswith("/system"):
            system_prompt = user[len("/system") :].strip()
            console.print(f"[dim]system prompt set ({len(system_prompt)} chars)[/dim]")
            continue

        messages.append({"role": "user", "content": user})
        console.print("[bold magenta]jimmy>[/bold magenta] ", end="")
        gen = client.chat_stream(
            messages=messages,
            model=model,
            system_prompt=system_prompt,
            top_k=top_k,
        )
        parts: list[str] = []
        resp = None
        try:
            while True:
                chunk = next(gen)
                parts.append(chunk)
                console.print(chunk, end="", markup=False, soft_wrap=True)
        except StopIteration as stop:
            resp = stop.value
        except Exception as exc:  # noqa: BLE001
            messages.pop()
            console.print()
            err_console.print(f"[red]error:[/red] {exc}")
            continue
        console.print()

        text = resp.text if resp else "".join(parts)
        messages.append({"role": "assistant", "content": text})
        if show_stats and resp is not None:
            _print_stats(resp.stats)


def _agent_on_step(*, quiet: bool, json_out: bool):
    from chatjimmy_harness.agent import parse_tool_call

    printed_final = False

    def on_step(step) -> None:
        nonlocal printed_final
        if quiet or json_out:
            return
        if step.kind == "assistant":
            call = parse_tool_call(step.text)
            if call:
                args_s = ", ".join(f"{k}={v!r}" for k, v in call.args.items())
                if len(args_s) > 80:
                    args_s = args_s[:77] + "..."
                err_console.print(f"[magenta]tool_call[/magenta] {call.name}({args_s})")
            else:
                console.print("[bold magenta]jimmy>[/bold magenta] ", end="")
                console.print(step.text, markup=False, soft_wrap=True)
                printed_final = True
        elif step.kind == "tool":
            status = "[green]ok[/green]" if step.ok else "[red]err[/red]"
            preview = (step.result or "").replace("\n", " ")[:120]
            err_console.print(f"  {status} [cyan]{step.tool}[/cyan] {preview}")
        elif step.kind == "repair":
            err_console.print("[yellow]repair[/yellow] format nudge")
        elif step.kind == "compact":
            err_console.print(f"[dim]compact[/dim] {step.text}")

    return on_step, lambda: printed_final


def _run_agent_repl(
    *,
    client: ChatJimmy,
    workspace: Path,
    tools: list[str],
    system: str,
    model: str,
    top_k: int,
    max_turns: int,
    allow_shell: bool,
    command_timeout_s: float,
    first_prompt: str = "",
    mode: str = "act",
) -> None:
    from chatjimmy_harness.config import HarnessConfig, config_from_env

    history: list[dict[str, str]] = []
    system_prompt = system
    ws = workspace.resolve()
    turns_cap = max_turns
    interaction_mode = mode if mode in {"act", "plan"} else "act"

    console.print(
        Panel.fit(
            f"[bold]chatjimmy agent[/bold]  model={model}  mode={interaction_mode}  "
            f"workspace={ws}\n"
            "message  ·  /reset  /tools  /mode act|plan  /workspace <path>  "
            "/system …  /max-turns N  /exit",
            border_style="magenta",
        )
    )

    pending = first_prompt.strip()

    while True:
        if pending:
            user = pending
            pending = ""
        else:
            try:
                user = console.input("[bold cyan]you>[/bold cyan] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break

        if not user:
            continue
        if user in {"/exit", "/quit", ":q"}:
            break
        if user == "/reset":
            history.clear()
            console.print("[dim]history cleared[/dim]")
            continue
        if user == "/tools":
            from chatjimmy_harness.tools import build_registry, tool_specs_prompt

            console.print(
                tool_specs_prompt(
                    build_registry(tools, interaction_mode=interaction_mode)  # type: ignore[arg-type]
                )
            )
            continue
        if user == "/help":
            console.print(
                "/reset  /tools  /mode act|plan  /workspace <path>  /system <text>  "
                "/max-turns <n>  /exit"
            )
            continue
        if user.startswith("/mode"):
            raw = user[len("/mode") :].strip().lower()
            if raw not in {"act", "plan"}:
                err_console.print("[red]usage:[/red] /mode act|plan")
                continue
            interaction_mode = raw
            console.print(f"[dim]mode={interaction_mode}[/dim]")
            continue
        if user.startswith("/workspace"):
            raw = user[len("/workspace") :].strip() or "."
            path = Path(raw).expanduser()
            if not path.exists() or not path.is_dir():
                err_console.print(f"[red]not a directory:[/red] {path}")
                continue
            ws = path.resolve()
            console.print(f"[dim]workspace={ws}[/dim]")
            continue
        if user.startswith("/system"):
            system_prompt = user[len("/system") :].strip()
            console.print(f"[dim]system prompt set ({len(system_prompt)} chars)[/dim]")
            continue
        if user.startswith("/max-turns"):
            raw = user[len("/max-turns") :].strip()
            try:
                turns_cap = max(1, int(raw))
            except ValueError:
                err_console.print("[red]usage:[/red] /max-turns 8")
                continue
            console.print(f"[dim]max_turns={turns_cap}[/dim]")
            continue
        if user.startswith("/"):
            err_console.print(f"[dim]unknown command:[/dim] {user}  (try /help)")
            continue

        on_step, _printed = _agent_on_step(quiet=False, json_out=False)
        cfg = config_from_env(
            HarnessConfig(interaction_mode=interaction_mode, max_turns=turns_cap)  # type: ignore[arg-type]
        )
        result = run_agent(
            client,
            user,
            workspace=ws,
            tools=tools,
            system_prompt=system_prompt,
            model=model,
            top_k=top_k,
            max_turns=turns_cap,
            allow_shell=allow_shell,
            command_timeout_s=command_timeout_s,
            on_step=on_step,
            messages=history,
            config=cfg,
        )
        history = list(result.messages)
        if result.error:
            err_console.print(f"[yellow]{result.error}[/yellow]")
        extra = ""
        if result.compacted or result.repair_nudges:
            extra = f" compact={result.compacted} repair={result.repair_nudges}"
        err_console.print(
            f"[dim]turns={result.turns} tools={result.tool_calls} "
            f"msgs={len(history)}{extra}[/dim]"
        )


@app.command()
def agent(
    ctx: typer.Context,
    prompt: str = typer.Argument(
        "",
        help='Task (optional). Empty starts interactive REPL. Use "-" for stdin.',
    ),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        help="Sandbox root for file/shell tools",
    ),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m"),
    system: str = typer.Option("", "--system", "-s"),
    top_k: int = typer.Option(8, "--top-k", "-k"),
    max_turns: int = typer.Option(12, "--max-turns", min=1),
    mode: str = typer.Option(
        "act",
        "--mode",
        help="Interaction mode: act (default) or plan (read-only)",
    ),
    tool: Optional[list[str]] = typer.Option(
        None,
        "--tool",
        "-t",
        help="Enable a tool by name (repeatable). Default: all.",
    ),
    no_shell: bool = typer.Option(
        False, "--no-shell", help="Disable run_shell / run_python"
    ),
    timeout_cmd: float = typer.Option(
        30.0, "--cmd-timeout", help="Timeout for shell/python tools (seconds)"
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Multi-turn REPL (default when no prompt). Keeps history across tasks.",
    ),
    json_out: bool = typer.Option(False, "--json"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Only print final answer"),
) -> None:
    """Tool-using agent. No prompt → interactive REPL; with prompt → one shot (or -i)."""
    from chatjimmy_harness.agent import parse_tool_call
    from chatjimmy_harness.config import HarnessConfig, config_from_env

    # Only pull stdin as the task when explicitly "-" (keep stdin free for the REPL).
    if prompt == "-":
        prompt = _resolve_prompt("-")

    if mode not in {"act", "plan"}:
        err_console.print("[red]--mode must be act or plan[/red]")
        raise typer.Exit(2)

    client = _client(ctx.obj["base_url"], ctx.obj["timeout"])
    tools = tool if tool else list(DEFAULT_TOOL_NAMES)
    if no_shell:
        tools = [t for t in tools if t not in {"run_shell", "run_python"}]

    cfg = config_from_env(
        HarnessConfig(interaction_mode=mode, max_turns=max_turns)  # type: ignore[arg-type]
    )

    use_repl = interactive or (not prompt.strip() and not json_out)
    if use_repl:
        if json_out:
            err_console.print("[red]--json is for one-shot agent runs[/red]")
            raise typer.Exit(2)
        _run_agent_repl(
            client=client,
            workspace=workspace,
            tools=tools,
            system=system,
            model=model,
            top_k=top_k,
            max_turns=max_turns,
            allow_shell=not no_shell,
            command_timeout_s=timeout_cmd,
            first_prompt=prompt,
            mode=mode,
        )
        return

    if not prompt.strip():
        err_console.print(
            '[red]need a task[/red] — try: cj agent "list files"  or  cj agent -i'
        )
        raise typer.Exit(2)

    on_step, printed_final = _agent_on_step(quiet=quiet, json_out=json_out)
    result = run_agent(
        client,
        prompt,
        workspace=workspace.resolve(),
        tools=tools,
        system_prompt=system,
        model=model,
        top_k=top_k,
        max_turns=max_turns,
        allow_shell=not no_shell,
        command_timeout_s=timeout_cmd,
        on_step=on_step,
        config=cfg,
    )

    if json_out:
        console.print_json(data=result.to_dict())
        raise typer.Exit(0 if result.finished and not result.error else 1)

    if (quiet or not printed_final()) and result.text:
        if quiet or parse_tool_call(result.text) is None:
            console.print(result.text, markup=False, soft_wrap=True)

    if result.error:
        err_console.print(f"[yellow]{result.error}[/yellow]")
    err_console.print(
        f"[dim]turns={result.turns} tools={result.tool_calls} "
        f"workspace={workspace.resolve()}[/dim]"
    )
    raise typer.Exit(0 if result.finished and not result.error else 1)


@app.command("run")
def run_cmd(
    ctx: typer.Context,
    suite_path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, help="Suite JSON or JSONL file"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    system: Optional[str] = typer.Option(None, "--system", "-s"),
    top_k: Optional[int] = typer.Option(None, "--top-k", "-k"),
    workspace: Optional[Path] = typer.Option(
        None,
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        help="Default workspace for agent cases",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write full JSON results"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
) -> None:
    """Run an evaluation suite against ChatJimmy."""
    client = _client(ctx.obj["base_url"], ctx.obj["timeout"])
    suite = load_suite(suite_path)
    result = run_suite(
        client,
        suite,
        model=model,
        top_k=top_k,
        system_prompt=system,
        workspace=workspace,
        suite_dir=suite_path.parent,
    )

    if not quiet:
        table = Table("id", "ok", "latency", "tools", "checks", "preview")
        for case in result.cases:
            preview = (case.error or case.text).replace("\n", " ")[:64]
            checks = ",".join(case.failed_checks or case.passed_checks) or "-"
            table.add_row(
                case.id,
                "[green]PASS[/green]" if case.ok else "[red]FAIL[/red]",
                f"{case.latency_s:.2f}s",
                str(case.tool_calls) if case.agent else "-",
                checks,
                preview,
            )
        console.print(table)
        console.print(
            f"{result.name}: {result.passed}/{result.total} passed "
            f"in {result.finished_at - result.started_at:.2f}s"
        )

    if output:
        output.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        if not quiet:
            console.print(f"[dim]wrote {output}[/dim]")

    raise typer.Exit(0 if result.failed == 0 else 1)


@app.command()
def bench(
    ctx: typer.Context,
    prompt: str = typer.Argument(
        "Write one short sentence about silicon.",
        help="Prompt used for each timed run",
    ),
    runs: int = typer.Option(5, "--runs", "-n", min=1),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m"),
    system: str = typer.Option("", "--system", "-s"),
    top_k: int = typer.Option(8, "--top-k", "-k"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Measure latency and HC1 decode rate over repeated runs."""
    client = _client(ctx.obj["base_url"], ctx.obj["timeout"])
    result = run_bench(
        client,
        prompt,
        runs=runs,
        model=model,
        system_prompt=system,
        top_k=top_k,
    )
    summary = result.summary()

    if json_out:
        console.print_json(data=summary)
        raise typer.Exit(0 if summary["errors"] == 0 else 1)

    table = Table("metric", "min", "p50", "mean", "p95", "max")
    for key, label in [
        ("latency_s", "latency (s)"),
        ("ttft_s", "ttft (s)"),
        ("decode_rate_tok_s", "decode tok/s"),
        ("decode_tokens", "decode tokens"),
    ]:
        block = summary.get(key)
        if not block:
            continue
        table.add_row(
            label,
            f"{block['min']:.3f}",
            f"{block['p50']:.3f}",
            f"{block['mean']:.3f}",
            f"{block['p95']:.3f}",
            f"{block['max']:.3f}",
        )
    console.print(table)
    console.print(
        f"ok={summary['ok']}/{summary['runs']}  wall={summary['wall_s']:.2f}s"
    )
    raise typer.Exit(0 if summary["errors"] == 0 else 1)


def run() -> None:
    _rewrite_bare_prompt_argv()
    app()


if __name__ == "__main__":
    run()
