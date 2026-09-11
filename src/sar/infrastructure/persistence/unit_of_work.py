class UnitOfWork:
    def __init__(self, database):
        self.database = database

    def __enter__(self):
        self._context = self.database.connect()
        self.connection = self._context.__enter__()
        self.connection.execute("BEGIN IMMEDIATE")
        return self

    def __exit__(self, *args):
        return self._context.__exit__(*args)
