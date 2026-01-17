"""Shell integration code generation."""


BASH_ZSH_WRAPPER = """
# wt shell integration for {shell}
wt() {{
    if [[ "$1" == "switch" ]]; then
        # Use --shell-helper flag to get directory path
        local output
        output=$(command wt "$@" --shell-helper 2>&1)
        local exit_code=$?

        if [[ $exit_code -eq 0 && -d "$output" ]]; then
            # Success: output is a directory path, cd to it
            cd "$output" || return 1
        else
            # Error or non-switch command: print output
            echo "$output"
            return $exit_code
        fi
    else
        # All other commands: pass through
        command wt "$@"
    fi
}}
"""


FISH_WRAPPER = """
# wt shell integration for fish
function wt
    if test "$argv[1]" = "switch"
        # Use --shell-helper flag to get directory path
        set output (command wt $argv --shell-helper 2>&1)
        set exit_code $status

        if test $exit_code -eq 0 -a -d "$output"
            # Success: output is a directory path, cd to it
            cd "$output"; or return 1
        else
            # Error or non-switch command: print output
            echo "$output"
            return $exit_code
        end
    else
        # All other commands: pass through
        command wt $argv
    end
end
"""


def generate_shell_init(shell: str) -> str:
    """
    Generate shell integration code for the specified shell.

    Args:
        shell: Shell type (bash, zsh, or fish)

    Returns:
        Shell code to be evaluated

    Raises:
        ValueError: If shell is not supported
    """
    shell = shell.lower()

    if shell in ("bash", "zsh"):
        return BASH_ZSH_WRAPPER.format(shell=shell).strip()
    elif shell == "fish":
        return FISH_WRAPPER.strip()
    else:
        raise ValueError(
            f"Unsupported shell: {shell}\n"
            f"Supported shells: bash, zsh, fish"
        )


def get_supported_shells() -> list:
    """Get list of supported shell names."""
    return ["bash", "zsh", "fish"]
