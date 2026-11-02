# Copyright 2025 OmniSecure Inc.
# Modified by the Lamia project from Strix.

"""Shell completion scripts and candidates for the Lamia CLI."""

from __future__ import annotations

import sys

from lamia.interface.terminal_text import has_terminal_control, sanitize_terminal_text


_ROOT_COMMANDS = ("auth", "view", "export", "completions", "completion")
_AUTH_COMMANDS = ("login", "status", "logout", "help")
_AUTH_LOGIN_PROVIDERS = ("chatgpt",)
_AUTH_LOGIN_FLAGS = ("--manual", "-h", "--help")


def run_completions(argv: list[str]) -> int:
    """Print a shell integration script or hidden completion candidates."""
    if argv and argv[0] == "--candidates":
        for candidate in completion_candidates(argv[1:]):
            sys.stdout.write(candidate + "\n")
        return 0
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(
            "Usage: lamia completions <zsh|bash|fish>\n\n"
            "Enable tab completion for the current shell:\n"
            "  zsh:  source <(lamia completions zsh)\n"
            "  bash: source <(lamia completions bash)\n"
            "  fish: lamia completions fish | source\n"
        )
        return 0
    shell = argv[0].lower()
    scripts = {"zsh": _zsh_script, "bash": _bash_script, "fish": _fish_script}
    generator = scripts.get(shell)
    if generator is None:
        sys.stderr.write(
            f"Unknown shell: {sanitize_terminal_text(shell)}. Choose zsh, bash, or fish.\n"
        )
        return 2
    sys.stdout.write(generator())
    return 0


def completion_candidates(words: list[str]) -> list[str]:
    """Return candidates for words after the ``lamia`` executable."""
    prior, current = _split_cursor(words)
    if not prior:
        candidates = _matching(_ROOT_COMMANDS, current)
    elif prior[0] == "auth":
        candidates = _auth_candidates(prior[1:], current)
    else:
        candidates = []
    return [candidate for candidate in candidates if not has_terminal_control(candidate)]


def _split_cursor(words: list[str]) -> tuple[list[str], str]:
    if not words:
        return [], ""
    return words[:-1], words[-1]


def _auth_candidates(prior: list[str], current: str) -> list[str]:
    if not prior:
        return _matching(_AUTH_COMMANDS, current)
    if prior[0] != "login":
        return []
    if len(prior) == 1:
        return _matching((*_AUTH_LOGIN_PROVIDERS, *_AUTH_LOGIN_FLAGS), current)
    if prior[1] == "chatgpt":
        return _matching(_AUTH_LOGIN_FLAGS, current)
    return []


def _matching(candidates: tuple[str, ...] | list[str], prefix: str) -> list[str]:
    return sorted({candidate for candidate in candidates if candidate.startswith(prefix)})


def _zsh_script() -> str:
    return r"""#compdef lamia
_lamia() {
  local -a candidates
  candidates=("${(@f)$($words[1] completions --candidates "${words[@]:2}")}")
  _describe 'lamia' candidates
}
compdef _lamia lamia
"""


def _bash_script() -> str:
    return r"""_lamia_completion() {
  local -a candidates
  local candidate
  while IFS= read -r candidate; do
    candidates+=("$candidate")
  done < <(lamia completions --candidates "${COMP_WORDS[@]:1:$COMP_CWORD}")
  COMPREPLY=("${candidates[@]}")
  for candidate in "${COMPREPLY[@]}"; do
    if [[ $candidate == */ ]]; then
      if type compopt >/dev/null 2>&1; then
        compopt -o nospace
      fi
      break
    fi
  done
}
complete -F _lamia_completion lamia
"""


def _fish_script() -> str:
    return r"""function __lamia_candidates
  set -l words (commandline -opc)
  set -e words[1]
  command lamia completions --candidates $words (commandline -ct)
end
complete -c lamia -f -a '(__lamia_candidates)'
"""
