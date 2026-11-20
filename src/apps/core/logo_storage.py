def write_logo_chunk(destination, chunk):
    count = destination.write(chunk)
    # Some storage streams signal success by returning None.
    if count is not None and count != len(chunk):
        raise OSError("Short write while storing a service logo.")
