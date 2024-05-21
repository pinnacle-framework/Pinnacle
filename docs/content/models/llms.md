# LLMs

`pinnacledb` allows users to work with LLM services and models

Here is a table of LLMs supported in `pinnacledb`:

| Class | Description |
| --- | --- |
| `pinnacledb.ext.transformers.LLM` | Useful for trying and fine-tuning a range of open-source LLMs |
| `pinnacledb.ext.vllm.vLLM` | Useful for fast self-hosting of LLM models with CUDA |
| `pinnacledb.ext.llamacpp.LlamaCpp` | Useful for fast self-hosting of LLM models without requiring CUDA |
| `pinnacledb.ext.openai.OpenAIChatCompletion` | Useful for getting started quickly |
| `pinnacledb.ext.anthropic.AnthropicCompletion` | Useful alternative for getting started quickly |

You can find the snippets [here](../reusable_snippets/build_llm)

:::tip
Connect your LLM to data and vector-search using `SequentialModel` or `GraphModel`.
:::
