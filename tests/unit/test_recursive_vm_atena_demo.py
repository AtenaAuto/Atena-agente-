from examples.recursive_vm_atena_demo import run_recursive_demo


def test_recursive_vm_demo_runs_and_returns_http_response_and_atena_output():
    report = run_recursive_demo()
    logs = "\n".join(report["logs"])

    assert report["page_faults"] >= 1
    assert "/vm/atena/production_contracts.py" in report["vm_files"]
    assert "ATENA_VM validate_contract" in logs
    assert "host<vm_http HTTP/1.1 200 OK" in logs
