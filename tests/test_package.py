from openfrontbench.server import main


def test_server_main_callable() -> None:
    assert callable(main)


def test_package_imports() -> None:
    import openfrontbench

    assert openfrontbench.__name__ == "openfrontbench"
