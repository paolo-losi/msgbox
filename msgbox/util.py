def status(status, desc):
    assert status in ('OK', 'ERROR')
    return dict(status=status, desc=desc)
