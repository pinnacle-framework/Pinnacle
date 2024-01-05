import dataclasses as dc
from typing import Any, List

import requests

from pinnacledb.ext.llm.base import BaseLLMAPI, BaseLLMModel

VLLM_INFERENCE_PARAMETERS_LIST = [
    "n",
    "best_of",
    "presence_penalty",
    "frequency_penalty",
    "repetition_penalty",
    "temperature",
    "top_p",
    "top_k",
    "min_p",
    "use_beam_search",
    "length_penalty",
    "early_stopping",
    "stop",
    "stop_token_ids",
    "include_stop_str_in_output",
    "ignore_eos",
    "max_tokens",
    "logprobs",
    "prompt_logprobs",
    "skip_special_tokens",
    "spaces_between_special_tokens",
    "logits_processors",
]


@dc.dataclass
class VllmAPI(BaseLLMAPI):
    """
    Wrapper for requesting the vLLM API service
    (API Server format, started by vllm.entrypoints.api_server)
    {parent_doc}
    """

    __doc__ = __doc__.format(parent_doc=BaseLLMAPI.__doc__)

    def _generate(self, prompt: str, **kwargs) -> str:
        """
        Batch generate text from a prompt.
        """
        post_data = self.build_post_data(prompt, **kwargs)
        response = requests.post(self.api_url, json=post_data)
        return response.json()["text"][0]

    def build_post_data(self, prompt: str, **kwargs: dict[str, Any]) -> dict[str, Any]:
        total_kwargs = {}
        for key, value in {**self.inference_kwargs, **kwargs}.items():
            if key in VLLM_INFERENCE_PARAMETERS_LIST:
                total_kwargs[key] = value
        return {"prompt": prompt, **total_kwargs}


@dc.dataclass
class VllmModel(BaseLLMModel):
    """
    Load a large language model from VLLM.

    :param model_name: The name of the model to use.
    :param trust_remote_code: Whether to trust remote code.
    :param dtype: The data type to use.
    {parent_doc}
    """

    __doc__ = __doc__.format(parent_doc=BaseLLMModel.__doc__)

    tensor_parallel_size: int = 1
    trust_remote_code: bool = True
    vllm_kwargs: dict = dc.field(default_factory=dict)

    def __post_init__(self):
        self.on_ray = self.on_ray or bool(self.ray_address)
        super().__post_init__()

    def init(self):
        try:
            from vllm import LLM
        except ImportError:
            raise Exception("You must install vllm with command 'pip install vllm'")

        if self.on_ray:
            try:
                import ray
            except ImportError:
                raise Exception("You must install vllm with command 'pip install ray'")

            runtime_env = {"pip": ["vllm"]}
            if not ray.is_initialized():
                ray.init(address=self.ray_address, runtime_env=runtime_env)

            LLM = ray.remote(LLM).remote

        self.llm = LLM(
            model=self.model_name,
            tensor_parallel_size=self.tensor_parallel_size,
            trust_remote_code=self.trust_remote_code,
            **self.vllm_kwargs,
        )

    def _batch_generate(self, prompts: List[str], **kwargs: Any) -> List[str]:
        from vllm import SamplingParams

        # support more parameters
        sampling_params = SamplingParams(
            **self.get_kwargs(SamplingParams, kwargs, self.inference_kwargs)
        )

        if self.on_ray:
            import ray

            results = ray.get(
                self.llm.generate.remote(prompts, sampling_params, use_tqdm=False)
            )
        else:
            results = self.llm.generate(prompts, sampling_params, use_tqdm=False)

        return [result.outputs[0].text for result in results]

    def _generate(self, prompt: str, **kwargs: Any) -> str:
        return self._batch_generate([prompt], **kwargs)[0]
