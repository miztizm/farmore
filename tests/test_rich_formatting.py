"""
Tests for Rich formatting utilities.

"Tests are just documentation that complains when you break things." — schema.cx
"""

import pytest
from rich.console import Console
from rich.table import Table

from farmore.rich_utils import (
    Colors,
    console,
    create_data_table,
    create_summary_table,
    format_action,
    format_count,
    format_repo_name,
    print_error,
    print_info,
    print_success,
    print_warning,
)


def test_console_instance():
    """Test that console is a Rich Console instance."""
    assert isinstance(console, Console)


def test_colors_constants():
    """Test that color constants are defined."""
    assert Colors.SUCCESS == "green"
    assert Colors.ERROR == "red"
    assert Colors.WARNING == "yellow"
    assert Colors.INFO == "cyan"
    assert Colors.MUTED == "dim"


def test_format_repo_name():
    """Test repository name formatting."""
    result = format_repo_name("owner/repo")
    assert "owner/repo" in result
    assert Colors.REPO_NAME in result


def test_format_count():
    """Test count formatting."""
    result = format_count(42, "repositories")
    assert "42" in result
    assert "repositories" in result


def test_format_action():
    """Test action formatting with auto-color selection."""
    # Test auto-color selection
    assert Colors.SUCCESS in format_action("CLONE")
    assert Colors.SUCCESS in format_action("cloned")
    assert Colors.INFO in format_action("UPDATE")
    assert Colors.WARNING in format_action("SKIP")
    assert Colors.ERROR in format_action("FAIL")
    
    # Test explicit color
    result = format_action("TEST", Colors.INFO)
    assert Colors.INFO in result


def test_create_summary_table():
    """Test summary table creation."""
    table = create_summary_table("Test Summary")
    assert isinstance(table, Table)
    assert table.title == "Test Summary"


def test_create_data_table():
    """Test data table creation."""
    table = create_data_table("Test Data")
    assert isinstance(table, Table)
    assert table.title == "Test Data"
    
    # Test without title
    table_no_title = create_data_table()
    assert isinstance(table_no_title, Table)


def test_print_functions_no_error(capsys):
    """Test that print functions execute without errors."""
    # These should not raise exceptions
    print_success("Success message")
    print_error("Error message")
    print_warning("Warning message")
    print_info("Info message")
    
    # Verify something was printed (Rich uses stderr by default)
    captured = capsys.readouterr()
    # Note: Rich may use stderr, so we just check no exceptions were raised

