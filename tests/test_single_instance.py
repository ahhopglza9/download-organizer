from single_instance import acquire, release


def test_second_acquire_fails_until_released():
    name = "DownloadOrganizerTest-single-instance"
    first = acquire(name)
    assert first is not None
    assert acquire(name) is None
    release(first)
    again = acquire(name)
    assert again is not None
    release(again)


def test_acquire_gives_up_after_wait():
    name = "DownloadOrganizerTest-wait-timeout"
    first = acquire(name)
    try:
        assert acquire(name, wait=0.3) is None
    finally:
        release(first)


def test_acquire_waits_for_release():
    import threading

    name = "DownloadOrganizerTest-wait-release"
    first = acquire(name)
    threading.Timer(0.4, release, args=(first,)).start()
    second = acquire(name, wait=3)
    assert second is not None
    release(second)
