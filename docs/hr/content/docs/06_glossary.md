---
sidebar_position: 6
tags:
  - quickstart
---

# Glossary of concepts and classes

| Concept | Description |
| - | - |
| [**`Datalayer`**](07_datalayer_overview.md) | the main class used to connect with SuperDuperDB |
| [**`db`**](04_connecting.md) | name, by convention, of the instance of the `Datalayer` built at the beginning of all `pinnacledb` programs |
| [**`Component`**](09_component_abstraction.md) | the base class which manages meta-data and serialization of all developer-added functionality |
| [**`Predictor`**](17_supported_ai_frameworks.md) | A mixin class for `Component` descendants, to implement predictions |
| [**`Model`**](17_supported_ai_frameworks.md) | the `Component` type responsible for wrapping AI models |
| [**`Document`**](10_document_encoder_abstraction.md) | the wrapper around dictionaries which `pinnacledb` uses to send data back-and-forth to `db` |
| [**`Encoder`**](10_document_encoder_abstraction.md) | the `Component` type responsible for encoding special data-types |
| [**`Schema`**](10_document_encoder_abstraction.md) | the `Component` type used to work with columnar data including special data-types |
| [**`Listener`**](21_apply_models.mdx) | `Component` to "listen" and `.predict` on incoming data |
| [**`VectorIndex`**](25_vector_search.mdx) | `Component` to perform vector-search - builds on `Model` and `Listener` |