import time
import random
import string
import torch
import gc

from classType import (
    ChatCompletionMessageToolCall,
    ChatCompletionResponse,
    ChatCompletionResponseStreamChoice,
    DeltaMessage,
    FunctionCall,
)
from transformers import AutoTokenizer
from vllm import SamplingParams, AsyncLLMEngine


async def predict_glm4(
    model_id: str, params: dict, model: AsyncLLMEngine, tokenizer: AutoTokenizer
):
    output = ""
    is_function_call = False
    has_send_first_chunk = False
    function_name = None
    response_id = generate_id("chatcmpl-", 29)

    # -----------------------------------------------------------------------------------------
    # tools = (
    # {tool["function"]["name"] for tool in params["tools"]}
    # if params["tools"]
    # else None
    # )

    # 修改：确保 tools 变量总是一个可迭代对象，即使 params["tools"] 为 None（避免迭代 NoneType）
    tools = {tool["function"]["name"] for tool in params.get("tools", [])}
    # -----------------------------------------------------------------------------------------

    async for new_response in generate_stream_glm4(params, model, tokenizer):
        decoded_unicode = new_response["text"]
        delta_text = decoded_unicode[len(output):]
        output = decoded_unicode
        lines = output.strip().split("\n")

        # 检查是否为工具
        # 这是一个简单的工具比较函数，不能保证拦截所有非工具输出的结果，比如参数未对齐等特殊情况。
        # TODO 如果你希望做更多处理，可以在这里进行逻辑完善。

        if not is_function_call and len(lines) >= 2:
            first_line = lines[0].strip()
            if first_line in tools:
                is_function_call = True
                function_name = first_line

        # 工具调用返回
        if is_function_call:
            if not has_send_first_chunk:
                function_call = {"name": function_name, "arguments": ""}
                tool_call = ChatCompletionMessageToolCall(
                    index=0,
                    id=generate_id("call_", 24),
                    function=FunctionCall(**function_call),
                    type="function",
                )
                message = DeltaMessage(
                    content=None,
                    role="assistant",
                    function_call=None,
                    tool_calls=[tool_call],
                )
                choice_data = ChatCompletionResponseStreamChoice(
                    index=0, delta=message, finish_reason=None
                )
                chunk = ChatCompletionResponse(
                    model=model_id,
                    id=response_id,
                    choices=[choice_data],
                    object="chat.completion.chunk",
                )
                yield ""
                yield chunk.model_dump_json(exclude_unset=True)
                has_send_first_chunk = True

            function_call = {"name": None, "arguments": delta_text}
            tool_call = ChatCompletionMessageToolCall(
                index=0,
                id=None,
                function=FunctionCall(**function_call),
                type="function",
            )
            message = DeltaMessage(
                content=None, role=None, function_call=None, tool_calls=[tool_call]
            )
            choice_data = ChatCompletionResponseStreamChoice(
                index=0, delta=message, finish_reason=None
            )
            chunk = ChatCompletionResponse(
                model=model_id,
                id=response_id,
                choices=[choice_data],
                object="chat.completion.chunk",
            )
            yield chunk.model_dump_json(exclude_unset=True)

        # 用户请求了 Function Call 但是框架还没确定是否为Function Call
        elif (params["tools"] and params["tool_choice"] != "none") or is_function_call:
            continue

        # 常规返回
        else:
            finish_reason = new_response.get("finish_reason", None)
            if not has_send_first_chunk:
                message = DeltaMessage(
                    content="",
                    role="assistant",
                    function_call=None,
                )
                choice_data = ChatCompletionResponseStreamChoice(
                    index=0, delta=message, finish_reason=finish_reason
                )
                chunk = ChatCompletionResponse(
                    model=model_id,
                    id=response_id,
                    choices=[choice_data],
                    object="chat.completion.chunk",
                )
                yield chunk.model_dump_json(exclude_unset=True)
                has_send_first_chunk = True

            message = DeltaMessage(
                content=delta_text,
                role="assistant",
                function_call=None,
            )
            choice_data = ChatCompletionResponseStreamChoice(
                index=0, delta=message, finish_reason=finish_reason
            )
            chunk = ChatCompletionResponse(
                model=model_id,
                id=response_id,
                choices=[choice_data],
                object="chat.completion.chunk",
            )
            yield chunk.model_dump_json(exclude_unset=True)

    # 工具调用需要额外返回一个字段以对齐 OpenAI 接口
    if is_function_call:
        yield ChatCompletionResponse(
            model=model_id,
            id=response_id,
            choices=[
                ChatCompletionResponseStreamChoice(
                    index=0,
                    delta=DeltaMessage(
                        content=None,
                        role=None,
                        function_call=None,
                    ),
                    finish_reason="tool_calls",
                )
            ],
            object="chat.completion.chunk",
            usage=None,
        ).model_dump_json(exclude_unset=True)
    yield "[DONE]"


@torch.inference_mode()
async def generate_stream_glm4(params: dict, engine: AsyncLLMEngine, tokenizer: AutoTokenizer):
    messages = params["messages"]
    tools = params["tools"]
    tool_choice = params["tool_choice"]
    temperature = float(params.get("temperature", 1.0))
    # ---------------------------------------------------------------
    repetition_penalty = float(params.get("repetition_penalty", 1.0))
    # repetition_penalty = float(params.get("repetition_penalty", 2.0))
    # ---------------------------------------------------------------
    top_p = float(params.get("top_p", 1.0))
    max_new_tokens = int(params.get("max_tokens", 8192))

    messages = process_response_glm4(
        messages, tools=tools, tool_choice=tool_choice)
    # 打印3和4的message
    print("# -------------------------------")
    print("Message:\n" + str(messages))
    print("# -------------------------------")

    # glm4 9b
    if 'glm-4' in params["model"]:
        eos_token_id = [151329, 151336, 151338]
    # glm3 6b
    else:
        eos_token_id = [
            tokenizer.eos_token_id,                    # [2]
            tokenizer.get_command("<|user|>"),         # [64795]
            tokenizer.get_command("<|observation|>")   # [64797]
        ]
        print("Stop Token ID: ", eos_token_id)

    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False
    )

    params_dict = {
        # 要返回的输出序列的数量
        "n": 1,
        # 从提示生成的输出序列数量
        "best_of": 1,
        # 根据新生成的文本中是否出现新标记来进行惩罚
        "presence_penalty": 1.0,
        # 根据新生成的文本中标记的频率进行惩罚
        "frequency_penalty": 0.0,
        # 控制采样的随机性（较低的值模型更加确定，较高的值使模型更具随机性）
        "temperature": temperature,
        # 控制要考虑的顶级标记的累积概率（较低的值模型更加确定，较高的值使模型更具随机性）
        "top_p": top_p,
        # 控制要考虑的顶级标记的数量（-1代表考虑所有标记）
        "top_k": -1,
        # 根据提示和新生成的文本中是否出现新标记来进行惩罚
        "repetition_penalty": repetition_penalty,
        # 是否采用束搜索而不是采样（模型将采用随机采样）
        "use_beam_search": False,
        # 根据序列长度进行惩罚
        "length_penalty": 1,
        # 控制束搜索的停止条件
        "early_stopping": False,

        # ----
        # "stop": ["<|", "[END]", "[actionnaire]"],
        # "stop": ["<|end|>"]
        # "stop_token_ids": [50256],
        # ------

        # 生成时停止生成的标记列表，返回的输出将包含停止token，除非停止标记是特殊token
        "stop_token_ids": eos_token_id,
        # 是否忽略EOS标记，并在生成EOS标记后继续生成token
        "ignore_eos": False,
        # 每个输出序列要生成的最大token数
        "max_tokens": max_new_tokens,
        # 每个输出token要返回的对数概率数量
        "logprobs": None,
        # 每个提示token要返回的对数概率数量
        "prompt_logprobs": None,
        # 是否跳过输出中的特殊token
        "skip_special_tokens": True,
    }
    sampling_params = SamplingParams(**params_dict)
    async for output in engine.generate(inputs=inputs, sampling_params=sampling_params, request_id=f"{time.time()}"):
        response = output.outputs[0].text
        print("######### ----------------------------------------------------------")
        print(f"Generated Response:\n", response)
        print("######### ----------------------------------------------------------\n\n\n")
        input_len = len(output.prompt_token_ids)
        output_len = len(output.outputs[0].token_ids)
        finish_reason = output.outputs[0].finish_reason
        yield {
            "text": response,
            "usage": {
                "prompt_tokens": input_len,
                "completion_tokens": output_len,
                "total_tokens": output_len + input_len,
            },
            "finish_reason": finish_reason
        }

    # 释放内存
    gc.collect()
    torch.cuda.empty_cache()


# ------------------------------------------------------------------------
"""
if "<|user|>" in response or "<|assistant|>" in response:
    yield {
        "text": response[:-7],
        "usage": {
            "prompt_tokens": input_len,
            "completion_tokens": output_len,
            "total_tokens": output_len + input_len,
        },
        "finish_reason": finish_reason
    }
    break
else:
    yield {
        "text": response,
        "usage": {
            "prompt_tokens": input_len,
            "completion_tokens": output_len,
            "total_tokens": output_len + input_len,
        },
        "finish_reason": finish_reason
    }
"""
# ------------------------------------------------------------------------


async def parse_output_text_glm4(
    model_id: str, value: str, function_call: FunctionCall = None
):
    delta = DeltaMessage(role="assistant", content=value)
    if function_call is not None:
        delta.function_call = function_call

    choice_data = ChatCompletionResponseStreamChoice(
        index=0, delta=delta, finish_reason=None
    )
    chunk = ChatCompletionResponse(
        model=model_id, choices=[choice_data], object="chat.completion.chunk"
    )
    yield "{}".format(chunk.model_dump_json(exclude_unset=True))
    yield "[DONE]"


def generate_id(prefix: str, k=29) -> str:
    suffix = "".join(random.choices(string.ascii_letters + string.digits, k=k))
    return f"{prefix}{suffix}"


def process_response_glm4(messages, tools=None, tool_choice="none"):
    _messages = messages
    processed_messages = []
    msg_has_sys = False

    def filter_tools(tool_choice, tools):
        function_name = tool_choice.get("function", {}).get("name", None)
        if not function_name:
            return []
        filtered_tools = [
            tool
            for tool in tools
            if tool.get("function", {}).get("name") == function_name
        ]
        return filtered_tools

    if tool_choice != "none":
        if isinstance(tool_choice, dict):
            tools = filter_tools(tool_choice, tools)
        if tools:
            processed_messages.append(
                {"role": "system", "content": None, "tools": tools}
            )
            msg_has_sys = True

    if isinstance(tool_choice, dict) and tools:
        processed_messages.append(
            {
                "role": "assistant",
                "metadata": tool_choice["function"]["name"],
                "content": "",
            }
        )

    for m in _messages:
        role, content, func_call = m.role, m.content, m.function_call
        tool_calls = getattr(m, "tool_calls", None)

        if role == "function":
            processed_messages.append(
                {"role": "observation", "content": content})
        elif role == "tool":
            processed_messages.append(
                {"role": "observation", "content": content, "function_call": True}
            )
        elif role == "assistant":
            if tool_calls:
                for tool_call in tool_calls:
                    processed_messages.append(
                        {
                            "role": "assistant",
                            "metadata": tool_call.function.name,
                            "content": tool_call.function.arguments,
                        }
                    )
            else:
                for response in content.split("\n"):
                    if "\n" in response:
                        metadata, sub_content = response.split(
                            "\n", maxsplit=1)
                    else:
                        metadata, sub_content = "", response
                    processed_messages.append(
                        {
                            "role": role,
                            "metadata": metadata,
                            "content": sub_content.strip(),
                        }
                    )
        else:
            if role == "system" and msg_has_sys:
                msg_has_sys = False
                continue
            processed_messages.append({"role": role, "content": content})

    if not tools or tool_choice == "none":
        for m in _messages:
            if m.role == "system":
                processed_messages.insert(
                    0, {"role": m.role, "content": m.content})
                break
    return processed_messages