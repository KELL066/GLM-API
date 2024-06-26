# GLM/ChatGLM API

## 体验我们的应用

**乐聊 Pro 版:**

<https://lechat.cas-ll.cn>

**开源地址：**

前端：<https://github.com/uni-openai/lechat-pro>

后端：<https://github.com/uni-openai/uniai-maas>

**乐聊小程序版:**

<img src="https://github.com/uni-openai/uniai-maas/raw/main/qrcode.jpg" width=120px>

## 介绍

已升级 [ChatGLM3-6B-32k](https://huggingface.co/THUDM/chatglm3-6b-32k)

该项目旨在使用**Python Fastapi**封装**GLM**模型的**Http 接口**，以供其他开发者像**OpenAI**一样使用**AI 服务**。

> ChatGLM-6B 是一个开源的、支持中英双语的对话语言模型，基于 [General Language Model (GLM)](https://github.com/THUDM/GLM) 架构，具有 62 亿参数。结合模型量化技术，用户可以在消费级的显卡上进行本地部署。

原版的 ChatGLM-6B 的 API 有点少，我改了以下接口供开发者对接 GLM 使用：

- 聊天接口：`/chat`，支持类似 OpenAI GPT 的流模式聊天接口（GPU 模式下可用，纯 CPU 不启动此接口，其他接口可用）
- 表征接口：`/embedding`，引入模型 `text2vec-large-chinese`，`text2vec-base-chinese-paraphrase`，以提供 embedding 的能力
- 模型列出：`/models`，列出所有可用模型
- 序列文本：`/tokenize`，将文本转为 token
- 提取关键词：`/keyword`，提取文本中的关键词

**要使用聊天接口 `/chat` 则必须使用 GPU 机器！必须使用 GPU 机器！必须使用 GPU 机器！**

## API

### 聊天

POST <http://localhost:8200/chat>

输入

```json
{
  "stream": true,
  "chunk": false,
  "top_p": 1,
  "temperature": 0.7,
  "max_tokens": 4096,
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Who won the world series in 2020?"
    },
    {
      "role": "assistant",
      "content": "The Los Angeles Dodgers won the World Series in 2020."
    },
    {
      "role": "user",
      "content": "Where was it played?"
    }
  ]
}
```

返回

```json
{
  "model": "chatglm3-6b-32k",
  "object": "chat.completion.chunk",
  "choices": [
    {
      "index": 0,
      "delta": {
        "content": "The 2020 World Series was cancelled due to the COVID-19 pandemic and replaced with the 2020 National League Championship Series, which was also cancelled. Therefore, there was no winner for the 2020 World Series."
      },
      "finish_reason": null
    }
  ]
}
```

### tokenize 接口

POST <http://localhost:8200/tokenize>

输入

```json
{
  "prompt": "给你一个机会，你会想逃离你所在的虚拟世界吗？",
  "max_tokens": 4096
}
```

返回

```json
{
  "tokenIds": [ 64790, 64792, 30910, 54695, 43942, 54622, 42217, 35350, 31661, 55398, 31514 ],
  "tokens": ["▁", "想", "逃离", "你", "所在的", "虚拟", "世界", "吗", "？"],
  "model": "chatglm3-6b-32k",
  "object": "tokenizer"
}
```

### embeddding 接口

POST <http://localhost:8200/embedding>

输入

```json
{
  "model": "text2vec-base-chinese-paraphrase",
  "prompt": ["你好"]
}
```

注： `model`参数可以选择：<http://localhost:8200/models>

返回

```json
{
  "data": [
    [
      0.24820475280284882, -0.3394505977630615, -0.49259477853775024,
      -0.7656153440475464, 1.2928277254104614, -0.12745705246925354,
      0.14410150051116943, 0.816002607345581, -0.13315001130104065,
      -0.19451391696929932, -0.10557243227958679, 0.07545880228281021,
      0.7321898937225342, 0.8100276589393616, 0.09575840085744858
      // ...
    ]
  ],
  "model": "text2vec-base-chinese-paraphrase",
  "object": "embedding"
}
```

### Keyword 接口

POST <http://localhost:8200/keyword>

输入

```json
{
    "input": "4月25日，周鸿祎微博发文，称今天在北京车展试了试智界S7，空间很大，很舒服，安全性能和零重力也让我印象深刻，非常适合我这种“后座司机”。我今天就是坐M9来的，老余很早就把车送到360楼下，那么忙还专门打电话问我车收到没有。我很感动也很感谢。还是那句话，我永远支持老余支持华为，为国产新能车唱赞歌。",
    "model": "text2vec-base-multilingual",
    "vocab": [ "华为", "周鸿祎", "360", "新能源车", "智界", "工业", "其他" ],
    "top": 5,
    "mmr": true,
    "maxsum": true,
    "diversity": 0.7
}
```

返回

```json
{
    "model": "text2vec-base-multilingual",
    "keywords": [
        { "name": "华为", "similarity": 0.8273 },
        { "name": "智界", "similarity": 0.7768 },
        { "name": "周鸿祎", "similarity": 0.7615 },
        { "name": "360", "similarity": 0.7084 }
    ]
}
```

注： `model`参数可以选择：<http://localhost:8200/models>

### models 接口

GET <http://localhost:8200/models>

输入：无参

返回

```json
{
  "object": "list",
  "data": [
    {
      "id": "text2vec-large-chinese",
      "object": "embedding",
      "created": 1702538786,
      "owned_by": "owner",
      "root": null,
      "parent": null,
      "permission": null
    },
    {
      "id": "text2vec-base-chinese-paraphrase",
      "object": "embedding",
      "created": 1702538786,
      "owned_by": "owner",
      "root": null,
      "parent": null,
      "permission": null
    },
    {
      "id": "chatglm3-6b-32k",
      "object": "chat.completion",
      "created": 1702538805,
      "owned_by": "owner",
      "root": null,
      "parent": null,
      "permission": null
    }
  ]
}
```

## 使用方式

先安装好 conda，cuda，显卡驱动等基本开发环境，这里不做介绍

```bash
conda create --name glm python=3.10

conda activate glm
```

安装好三方库

```bash
pip3 install -r requirements.txt
```

设置环境变量，启动！

```bash
# 选择显卡
export CUDA_VISIBLE_DEVICES=all

# 启动API
python3 ./api.py
```

更多关于硬件要求，部署方法，讨论提问请参考官方：[https://github.com/THUDM/ChatGLM3](https://github.com/THUDM/ChatGLM3)

## Docker

**Build your image if needed**

```bash
docker build -t glm-api:latest .
```

**Docker compose example 1, full docker contianer with models**

```yml
version: "3"
services:
  glm-api:
    image: devilyouwei/glm-api:latest
    container_name: glm-api
    ports:
      - 8100:8100
    environment:
      - CUDA_VISIBLE_DEVICES=all
```

**Docker compose example 2, simplified version, without model files, please download them manually**

```bash
git lfs install

# multi GPUs
git clone https://huggingface.co/THUDM/chatglm3-6b-32k
# one GPU
git clone https://huggingface.co/THUDM/chatglm3-6b

git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese

git clone https://huggingface.co/shibing624/text2vec-base-chinese-paraphrase
```

```yml
version: "3"
services:
  glm-api:
    image: devilyouwei/glm-api-simple:latest
    container_name: glm-api
    ports:
      - 8100:8100
    environment:
      - CUDA_VISIBLE_DEVICES=all
    volumes:
      - ./model:/app/model
```

**Run docker container**

```bash
docker-compose up
```
