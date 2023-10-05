# SuperDuperDB now supports Cohere and Anthropic APIs

*We're happy to announce the integration of two more AI APIs, Cohere and Anthropic, into SuperDuperDB.*

---

[Cohere](https://cohere.com/) and [Anthropic](https://www.anthropic.com/) provides AI developers with sorely needed alternatives to OpenAI for key AI tasks, 
including:

- text-embeddings as a service
- chat-completions as as service.

<!--truncate-->

## How to use the new integrations with your data

We've posted some extensive content on how to use [OpenAI or Sentence-Transformers for encoding text as vectors](https://docs.pinnacledb.com/docs/use_cases/items/compare_vector_search_solutions)
in your MongoDB datastore, and also [how to question-your your docs hosted in MongoDB](https://docs.pinnacledb.com/blog/building-a-documentation-chatbot-using-fastapi-react-mongodb-and-pinnacledb).

Now developers can easily use Cohere and Anthropic and drop in-replacements for the OpenAI models:

For **embedding text as vectors** with OpenAI developers can continue to import the functionality like this:

```python
from pinnacledb.ext.openai.model import OpenAIEmbedding

model = OpenAIEmbedding(model='text-embedding-ada-002')
```

Now developers can **also** import Cohere's embedding functionality:

```python
from pinnacledb.ext.cohere.model import CohereEmbedding

model = CohereEmbedding()
```

Similarly, for **chat-completion**, can continue to use OpenAI like this:

```python
from pinnacledb.ext.openai.model import OpenAIChatCompletion

chat = OpenAIChatCompletion(
    prompt='Answer the following question clearly, concisely and accurately',
    model='gpt-3.5-turbo',
)
```

Now developers can **also** import Anthropic's embedding functionality:

```python
from pinnacledb.ext.anthropic.model import AnthropicCompletions

chat = AnthropicCompletions(
    prompt='Answer the following question clearly, concisely and accurately',
)
```

### Useful Links

- **[Website](https://pinnacledb.com/)**
- **[GitHub](https://github.com/SuperDuperDB/pinnacledb)**
- **[Documentation](https://docs.pinnacledb.com/docs/docs/intro.html)**
- **[Blog](https://docs.pinnacledb.com/blog)**
- **[Example Use-Cases & Apps](https://docs.pinnacledb.com/docs/category/use-cases)**
- **[Slack Community](https://join.slack.com/t/pinnacledb/shared_invite/zt-1zuojj0k0-RjAYBs1TDsvEa7yaFGa6QA)**
- **[LinkedIn](https://www.linkedin.com/company/pinnacledb/)**
- **[Twitter](https://twitter.com/pinnacledb)**
- **[Youtube](https://www.youtube.com/@pinnacledb)**

### Contributors are welcome!

SuperDuperDB is open-source and permissively licensed under the [Apache 2.0 license](https://github.com/SuperDuperDB/pinnacledb/blob/main/LICENSE). We would like to encourage developers interested in open-source development to contribute in our discussion forums, issue boards and by making their own pull requests. We'll see you on [GitHub](https://github.com/SuperDuperDB/pinnacledb)!

### Become a Design Partner!

We are looking for visionary organizations which we can help to identify and implement transformative AI applications for their business and products. We're offering this absolutely for free. If you would like to learn more about this opportunity please reach out to us via email: partnerships@pinnacledb.com