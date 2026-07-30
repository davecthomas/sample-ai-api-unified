"""Conversation capability screen: multi-turn chat, a tool-use loop, and async.

Exercises the engine-agnostic conversation API added in ai-api-unified 2.14/2.15.
``send_conversation`` sends one turn and returns an ``AITurnResult`` (text,
tool_calls, normalized finish_reason, token usage); the caller owns the tool
loop via ``extend_messages_with_turn`` and ``build_tool_result_message``.
``asend_conversation`` is the async variant, run here on Textual's own event
loop. Tool use and async are capability-gated (``supports_tool_use`` /
``supports_async``) and report clearly when the active engine lacks them.
"""

from __future__ import annotations

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ... import state
from .base import CapabilityScreen

# send_conversation is a method on the completions client, so this screen gates
# on the completions engine like the other completion-backed screens.
CAPABILITY = "completions"

SYSTEM_PROMPT = "You are a concise, friendly assistant. Keep replies to a few sentences."
TOOL_SYSTEM_PROMPT = (
    "You are a support agent. Use the lookup_ticket tool when asked about a ticket."
)
SAMPLE_MESSAGE = "In two sentences, what is a Merkle tree and why is it useful?"
TOOL_DEMO_MESSAGE = "Summarize the status of ticket VL-123 in one sentence."
MAX_TOOL_ITERATIONS = 4

# A tiny, safe, deterministic "backend" for the tool-use demo. The model decides
# when to call the tool; the app executes it locally and feeds the result back.
_TICKETS: dict[str, dict[str, str]] = {
    "VL-123": {"status": "in progress", "assignee": "Dana", "priority": "high"},
    "VL-200": {"status": "done", "assignee": "Rell", "priority": "low"},
    "VL-777": {"status": "blocked", "assignee": "Sam", "priority": "medium"},
}


def _lookup_ticket(ticket_id: str) -> dict:
    key = ticket_id.strip().upper()
    ticket = _TICKETS.get(key)
    if ticket is None:
        return {"error": f"no ticket {key!r}", "known": sorted(_TICKETS)}
    return {"ticket_id": key, **ticket}


def _finish(finish_reason) -> str:
    """Normalized finish reason as its plain string (``complete``/``tool_use``…)."""
    return str(getattr(finish_reason, "value", finish_reason))


def _usage(turn) -> str:
    u = turn.usage
    return f"{u.input_tokens or 0} in / {u.output_tokens or 0} out"


class ConversationScreen(CapabilityScreen):
    title_text = "Conversation (chat / tools / async)"
    subtitle_text = (
        "Multi-turn chat via send_conversation, a caller-owned tool loop, and an async turn."
    )

    def __init__(self) -> None:
        super().__init__()
        # The API message list keeps engine-shaped turns for replay; the
        # transcript keeps plain text for display. Committed only on a
        # successful turn, so a failed turn never leaves an orphan user message.
        self._messages: list = []
        self._transcript: list = []
        # One turn at a time: turns mutate shared history, so overlapping turns
        # would interleave and corrupt it.
        self._busy = False

    def compose_body(self) -> ComposeResult:
        yield Static("", classes="field-label", id="engine-line")
        yield Input(placeholder="Your message…", id="message")
        with Horizontal(classes="actions"):
            yield Button("Send turn", variant="primary", id="send")
            yield Button("Async turn", id="async")
        with Horizontal(classes="actions"):
            yield Button("Tool-use demo", id="tool")
            yield Button("Sample", id="sample")
            yield Button("Reset", id="reset")

    def on_mount(self) -> None:
        engine = state.current_engine(CAPABILITY) or "unset"
        self.query_one("#engine-line", Static).update(f"engine: {engine}  (send_conversation)")

    # ── gating helpers ───────────────────────────────────────────────

    def _ready(self) -> bool:
        if self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            return True
        self.set_result("result", "[yellow]Completions engine not configured.[/yellow]")
        return False

    def _pii_blocked(self) -> bool:
        """send_conversation raises while PII redaction is on (replayed turn
        content is opaque and can't be redacted), so pre-check like streaming."""
        from ... import middleware_profile as mp

        if mp.read_profile().pii.enabled:
            self.set_result(
                "result",
                "[yellow]Conversation turns are unavailable while PII redaction is "
                "enabled — replayed turn content is opaque and can't be redacted. "
                "Disable it on the Middleware screen.[/yellow]",
            )
            return True
        return False

    def _can_start(self) -> bool:
        """Shared entry gate for every action: completions ready, not mid-turn,
        PII off. Engine capability (tool use / async) is checked in the worker,
        where the client is built."""
        if not self._ready():
            return False
        if self._busy:
            self.set_result("result", "[yellow]A turn is already running.[/yellow]")
            return False
        return not self._pii_blocked()

    def _engine_gate(self, client, *, need_async: bool = False) -> str | None:
        """A yellow message if the engine can't run a conversation turn, else None.
        send_conversation requires tool-use support even without tools."""
        caps = client.capabilities
        if not caps.supports_tool_use:
            return (
                f"{escape(client.model_name)} does not support conversation turns "
                "(send_conversation requires supports_tool_use, which is False). Switch "
                "completions to claude, openai, openai-responses, google-gemini, or a "
                "Nova/Claude model on Bedrock."
            )
        if need_async and not caps.supports_async:
            return (
                f"{escape(client.model_name)} has no async client (supports_async is "
                "False). Bedrock has no async SDK; try claude, openai, openai-responses, "
                "or google-gemini."
            )
        return None

    def _render_transcript(self, turn=None, note: str = "") -> str:
        lines = []
        for role, text in self._transcript:
            label = "You" if role == "you" else "Assistant"
            lines.append(f"[b]{label}:[/b] {escape(text)}")
        body = "\n\n".join(lines) if lines else "[dim]No messages yet.[/dim]"
        if turn is not None:
            body += f"\n\n[dim]finish={escape(_finish(turn.finish_reason))} · tokens {_usage(turn)}[/dim]"
        if note:
            body += f"\n[dim]{escape(note)}[/dim]"
        return body

    def _render_tool_steps(self, steps: list) -> str:
        blocks = ["[b]Tool-use loop[/b] — send_conversation with a lookup_ticket tool:\n"]
        for step in steps:
            if step[0] == "turn":
                turn = step[1]
                if turn.text:
                    blocks.append(f"[b]Assistant:[/b] {escape(turn.text)}")
                for call in turn.tool_calls:
                    blocks.append(
                        f"[cyan]→ tool call[/cyan] {escape(call.name)}({escape(str(call.input))}) "
                        f"[dim]id={escape(str(call.id))}[/dim]"
                    )
                blocks.append(
                    f"[dim]finish={escape(_finish(turn.finish_reason))} · {_usage(turn)}[/dim]"
                )
            else:  # ("tool", call, output)
                _tag, call, output = step
                blocks.append(
                    f"[green]← tool result[/green] {escape(call.name)} → {escape(str(output))}"
                )
        return "\n\n".join(blocks)

    # ── chat turn (sync or async, one shared worker) ─────────────────

    @on(Button.Pressed, "#send")
    def _on_send(self) -> None:
        self._start_turn(use_async=False)

    @on(Input.Submitted, "#message")
    def _on_submit(self) -> None:
        self._start_turn(use_async=False)

    @on(Button.Pressed, "#async")
    def _on_async(self) -> None:
        self._start_turn(use_async=True)

    def _start_turn(self, *, use_async: bool) -> None:
        message = self.query_one("#message", Input).value
        if not message.strip():
            self.set_result("result", "[yellow]Type a message first.[/yellow]")
            return
        if not self._can_start():
            return
        self._busy = True
        self.set_result("result", "[dim]Sending turn…[/dim]")
        self.run_worker(self._turn_worker(message, use_async), exclusive=False, exit_on_error=False)

    async def _turn_worker(self, message: str, use_async: bool) -> None:
        import asyncio

        from ai_api_unified import AIFactory

        try:
            client = AIFactory.get_ai_completions_client()
            gate = self._engine_gate(client, need_async=use_async)
            if gate:
                self.set_result("result", f"[yellow]{gate}[/yellow]")
                return
            # Work on a copy so the shared history is committed only on success —
            # a failed turn leaves no orphan user message to wedge later turns.
            messages = [*self._messages, {"role": "user", "content": message}]
            if use_async:
                # await yields the event loop during network I/O, so the UI stays live.
                turn = await client.asend_conversation(
                    SYSTEM_PROMPT, messages, max_response_tokens=1024
                )
            else:
                # to_thread keeps the blocking call off the event loop.
                turn = await asyncio.to_thread(
                    client.send_conversation, SYSTEM_PROMPT, messages, max_response_tokens=1024
                )
            client.extend_messages_with_turn(messages, turn)
            self._messages = messages
            self._transcript.append(("you", message))
            self._transcript.append(("assistant", turn.text or ""))
            self.query_one("#message", Input).value = ""
            note = "(ran on the event loop via asend_conversation)" if use_async else ""
            self.set_result("result", self._render_transcript(turn, note=note))
        except Exception as error:  # noqa: BLE001 - surface any provider/config error
            self.set_result("result", f"[red]{escape(f'{type(error).__name__}: {error}')}[/red]")
        finally:
            self._busy = False

    # ── tool-use demo (self-contained loop, own message list) ────────

    @on(Button.Pressed, "#tool")
    def _on_tool(self) -> None:
        if not self._can_start():
            return
        self._busy = True
        self.set_result("result", "[dim]Running the tool-use loop…[/dim]")
        self.run_worker(self._tool_worker(), exclusive=False, exit_on_error=False)

    async def _tool_worker(self) -> None:
        import asyncio

        from ai_api_unified import AIFactory, AITool

        try:
            client = AIFactory.get_ai_completions_client()
            gate = self._engine_gate(client)
            if gate:
                self.set_result("result", f"[yellow]{gate}[/yellow]")
                return

            def run_loop() -> list:
                tools = [
                    AITool(
                        name="lookup_ticket",
                        description="Look up a support ticket by its id.",
                        input_schema={
                            "type": "object",
                            "properties": {"ticket_id": {"type": "string"}},
                            "required": ["ticket_id"],
                        },
                        strict=True,
                    )
                ]
                messages = [{"role": "user", "content": TOOL_DEMO_MESSAGE}]
                steps: list = []
                for _ in range(MAX_TOOL_ITERATIONS):
                    turn = client.send_conversation(
                        TOOL_SYSTEM_PROMPT, messages, tools=tools, max_response_tokens=1024
                    )
                    steps.append(("turn", turn))
                    if turn.finish_reason != "tool_use":
                        break
                    client.extend_messages_with_turn(messages, turn)
                    for tool_call in turn.tool_calls:
                        output = _lookup_ticket(str(tool_call.input.get("ticket_id", "")))
                        steps.append(("tool", tool_call, output))
                        messages.append(
                            client.build_tool_result_message(
                                tool_call_id=tool_call.id,
                                result=output,
                                is_error="error" in output,
                            )
                        )
                return steps

            steps = await asyncio.to_thread(run_loop)
            self.set_result("result", self._render_tool_steps(steps))
        except Exception as error:  # noqa: BLE001 - surface any provider/config error
            self.set_result("result", f"[red]{escape(f'{type(error).__name__}: {error}')}[/red]")
        finally:
            self._busy = False

    # ── sample / reset ───────────────────────────────────────────────

    @on(Button.Pressed, "#sample")
    def _on_sample(self) -> None:
        self.query_one("#message", Input).value = SAMPLE_MESSAGE

    @on(Button.Pressed, "#reset")
    def _on_reset(self) -> None:
        self._messages = []
        self._transcript = []
        self.query_one("#message", Input).value = ""
        self.set_result("result", "[dim]Conversation cleared.[/dim]")
