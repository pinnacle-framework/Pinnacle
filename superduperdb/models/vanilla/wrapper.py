import multiprocessing
from pinnacledb.core.model import Model


class Function(Model):
    def predict_one(self, x, **kwargs):
        return self.object.a(x, **kwargs)

    def _predict(self, docs, num_workers=0):
        outputs = []
        if num_workers:
            pool = multiprocessing.Pool(processes=num_workers)
            for r in pool.map(self.object, docs):
                outputs.append(r)
            pool.close()
            pool.join()
        else:
            for r in docs:
                outputs.append(self.object(r))
        return outputs
