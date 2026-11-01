from yai_scout.kernel.yai_adapter import KERNEL_REQUIRED_VERSION, kernel_status


def test_yai_kernel_available_and_pinned():
    status = kernel_status()
    assert status["version"] == KERNEL_REQUIRED_VERSION
    assert status["match"] is True
    assert all(status["symbols"].values()), status["symbols"]
