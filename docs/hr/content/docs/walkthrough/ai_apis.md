---
sidebar_position: 19
---

# Using AI APIs as `Predictor` descendants

In SuperDuperDB, developers are able to interact with popular AI API providers, in a way very similar to 
[integrating with AI open-source or home-grown models](18_ai_models.mdx). Instantiating a model from 
these providers is similar to instantiating a `Model`:

## OpenAI

**Supported**

| Description | Class-name |
| --- | --- |
| Embeddings | `OpenAIEmbedding` |
| Chat models | `OpenAIChatCompletion` |
| Image generation models | `OpenAIImageCreation` |
| Image edit models | `OpenAIImageEdit` |
| Audio transcription models | `OpenAIAudioTranscription` |

**Usage**

```python
from pinnacledb.ext.openai import OpenAI<ModelType> as ModelCls

db.add(Modelcls(identifier='my-model', **kwargs))
```

## Cohere

**Supported**

| Description | Class-name |
| --- | --- |
| Embeddings | `CohereEmbedding` |
| Chat models | `CohereChatCompletion` |

**Usage**

```python
from pinnacledb.ext.cohere import Cohere<ModelType> as ModelCls

db.add(Modelcls(identifier='my-model', **kwargs))
```

## Anthropic

**Supported**

| Description | Class-name |
| --- | --- |
| Chat models | `AnthropicCompletions` |

**Usage**

```python
from pinnacledb.ext.anthropic import Anthropic<ModelType> as ModelCls

db.add(Modelcls(identifier='my-model', **kwargs))
```