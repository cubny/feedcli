import pytest
from click.testing import CliRunner
from feedcli.cli import main

def test_completion_bash():
    runner = CliRunner()
    result = runner.invoke(main, ["completion", "bash"])
    assert result.exit_code == 0
    assert "_feedcli_completion()" in result.output
    assert "complete -o nosort -F _feedcli_completion feedcli" in result.output

def test_completion_zsh():
    runner = CliRunner()
    result = runner.invoke(main, ["completion", "zsh"])
    assert result.exit_code == 0
    assert "_feedcli_completion()" in result.output
    assert "compdef _feedcli_completion feedcli" in result.output

def test_completion_fish():
    runner = CliRunner()
    result = runner.invoke(main, ["completion", "fish"])
    assert result.exit_code == 0
    assert "function _feedcli_completion" in result.output
    assert "complete --no-files --command feedcli" in result.output

def test_completion_invalid_shell():
    runner = CliRunner()
    result = runner.invoke(main, ["completion", "invalid"])
    assert result.exit_code != 0
    assert "is not one of 'bash', 'zsh', 'fish'" in result.output
