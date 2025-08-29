"""Basic tests to verify project setup."""


def test_project_setup():
    """Test that basic project setup is working."""
    assert True


def test_imports():
    """Test that main modules can be imported."""
    import todo
    import todo.cli.main

    assert todo is not None
    assert todo.cli.main is not None
    assert todo.cli.main.app is not None
