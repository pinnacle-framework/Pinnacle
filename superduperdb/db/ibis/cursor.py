import dataclasses as dc
import typing as t

from pinnacledb.db.base.cursor import SuperDuperCursor


@dc.dataclass
class SuperDuperIbisCursor(SuperDuperCursor):
    db: t.Any = None

    def execute(self):
        try:
            raw_cursor = self.raw_cursor.execute()
        except:
            return None
        self.dict_cursor = raw_cursor.to_dict(orient="records")
        self._n = len(self.dict_cursor)
        self._index = 0
        return self

    def cursor_next(self):
        if self._index < self._n:
            row = self.dict_cursor[self._index]
            self._index += 1
            return row
        else:
            raise StopIteration
