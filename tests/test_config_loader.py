import pytest
from capitec_pull.config_loader import load_branches, ConfigError

VALID = """
branches:
  - branch_code: "101"
    username: "test@hdmparts.co.za"
    password: "test@1234"
  - branch_code: "202"
    username: "test1@hdmparts.co.za"
    password: "1234"
  - branch_code: "303"
    username: "test2@hdmparts.co.za"
    password: "HDM"
"""


def _write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(text)
    return p


def test_loads_branches(tmp_path):
    branches = load_branches(_write(tmp_path, VALID))
    assert [b.branch_code for b in branches] == ["101", "202", "303"]
    assert branches[0].username == "test@hdmparts.co.za"
    assert branches[0].password == "test@1234"


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_branches(tmp_path / "nope.yaml")


def test_empty_branches_raises(tmp_path):
    with pytest.raises(ConfigError, match="at least one branch"):
        load_branches(_write(tmp_path, "branches: []\n"))


def test_missing_field_raises(tmp_path):
    bad = 'branches:\n  - branch_code: "101"\n    username: "u"\n'
    with pytest.raises(ConfigError, match="password"):
        load_branches(_write(tmp_path, bad))