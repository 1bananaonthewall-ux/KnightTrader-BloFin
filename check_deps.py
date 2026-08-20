try:
    import PIL
    print("PIL_OK", PIL.__version__)
except Exception as e:
    print("PIL_MISSING", repr(e))
