from dataclasses import dataclass

from app.schemas.config import ConfigPayload

# Termos que indicam acoplamento a provider específico (ADR-0006).
# Qualquer um desses em seção de instrução é aviso de linter.
PROVIDER_TERMS: list[str] = [
    "claude",
    "gpt",
    "chatgpt",
    "anthropic",
    "openai",
    "gemini",
    "llama",
    "mistral",
    "<thinking>",
    "</thinking>",
    "thinking block",
    "chain of thought",
]

# Nomes canônicos de ferramentas conhecidas, em snake_case.
# Aparecer em instrução sem estar em payload.tools → aviso.
KNOWN_TOOLS: list[str] = [
    "web_search",
    "file_read",
    "file_write",
    "code_interpreter",
    "calculator",
    "shell_exec",
    "crawl",
    "browse",
]


@dataclass(frozen=True)
class LintWarning:
    section: str
    code: str
    message: str


def lint_payload(payload: ConfigPayload) -> list[LintWarning]:
    warnings: list[LintWarning] = []
    _check_provider_coupling(payload, warnings)
    _check_tool_citations(payload, warnings)
    return warnings


def _instruction_sections(payload: ConfigPayload) -> dict[str, str]:
    ins = payload.instructions
    return {
        "persona": ins.persona,
        "situation": ins.situation,
        "tone": ins.tone,
        "objective": ins.objective,
        "guardrails": ins.guardrails,
    }


def _check_provider_coupling(payload: ConfigPayload, out: list[LintWarning]) -> None:
    for section_name, text in _instruction_sections(payload).items():
        if not text:
            continue
        lower = text.lower()
        for term in PROVIDER_TERMS:
            if term.lower() in lower:
                out.append(
                    LintWarning(
                        section=section_name,
                        code="provider-coupling",
                        message=(
                            f"instrução em '{section_name}' menciona "
                            f"termo acoplado a provider: '{term}'"
                        ),
                    )
                )


def _check_tool_citations(payload: ConfigPayload, out: list[LintWarning]) -> None:
    enabled = set(payload.tools)
    all_text = " ".join(_instruction_sections(payload).values()).lower()
    for tool in KNOWN_TOOLS:
        if tool in all_text and tool not in enabled:
            out.append(
                LintWarning(
                    section="instructions",
                    code="tool-not-enabled",
                    message=f"instrução menciona '{tool}' mas a ferramenta não está habilitada",
                )
            )
