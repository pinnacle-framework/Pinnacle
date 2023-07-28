# Frequently asked questions

***Is SuperDuperDB a database?***

No, SuperDuperDB is an environment to run alongside your database, which makes it 🚀 **SUPER-DUPER** 🚀, by adding comprehensive AI functionality. This fact explains our decorator:

```python
from pinnacledb import pinnacle

db = pymongo.MongoClient().documents

db = pinnacle(db)
```

***Do you provide integrations with other data-bases, -lakes or -warehouses?***

Not currently. We are currently discussing how to proceed here, in open source.
We believe that there is sufficient developer pain and a large enough community 
around MongoDB to start there.
Please review our issue boards [on GitHub](https://github.com/SuperDuperDB/pinnacledb) for more information.

***Why MongoDB and not another data store as you first data integration?***

The genesis of SuperDuperDB took place in a context where we were serving unstructured documents
at inference time. Working backwards from there, we wanted our development process to reflect
that production environment. We started with large dumps of JSON documents, but quickly 
hit a brick-wall; we deferred to hosting our own MongoDB community edition deployments 
for model development, allowing us to transition smoothly to production.

This symmetry between production and development, provides the possibility for significantly 
reduced overhead in building AI models and applications. SuperDuperDB is ***the way***
to employ such a symmetry with unstructured documents in MongoDB.

***Is SuperDuperDB an MLOps framework?***

We understand MLOps to mean DevOps for machine learning (ML) and AI.
That means focus on delivering ML and AI in conjunction with continuous integration and deployment (CI / CD), deployments defined by infrastructure as code. 

While SuperDuperDB can be used to great effect to reduce the complexity of MLOps, our starting point
is a far simply problem setting:

> *Given I have AI models built as Python objects, how do I apply these to my data deployment with
zero overhead and no detours through traditional DevOps pipelines?*

From this point of view, SuperDuperDB is an effort to **avoid MLOps** per se. That results in 
MLOps becoming significantly simpler, the moment it

***How do I deploy SuperDuperDB alongside the FARM stack?***

The [FARM stack](https://www.mongodb.com/developer/languages/python/farm-stack-fastapi-react-mongodb/)
refers to application development using FastAPI, React and MongoDB. 
In this triumvirate, MongoDB constitutes the datalayer, and the backend is deployed in Python
via FastAPI, and as usual the frontend is built in React-Javascript. Due to this Python centricity and the developments in AI in Python in 2023, SuperDuperDB is an ideal candidate to integrate here: AI models are managed by SuperDuperDB, and predictions are stored in MongoDB.

We are working on a [RESTful client-server](clientserver) implementation, allowing queries involving vector-search
models to be dispatched directly from a React frontend. For applications which do not require
models at query-time, model outputs may be consumed directly via MongoDB, if [change-data-capture (CDC)](CDC) is activated. 