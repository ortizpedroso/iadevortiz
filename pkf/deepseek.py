from __future__ import annotations

import os
from datetime import date

DEEPSEEK_CHAT_MODEL = "deepseek-chat"
DEEPSEEK_REASONER_MODEL = "deepseek-reasoner"

FILE_UPLOAD_TEMPLATE = """[file name]: {file_name}
[file content begin]
{file_content}
[file content end]
{question}"""

SEARCH_ANSWER_PT = """# 以下内容是基于用户发送的消息的搜索结果:
{search_results}
在我给你的搜索结果中，每个结果都是[webpage X begin]...[webpage X end]格式的，X代表每篇文章的数字索引。请在适当的情况下在句子末尾引用上下文。请按照引用编号[citation:X]的格式在答案中对应部分引用上下文。
在回答时，请注意以下几点：
- 今天是{cur_date}。
- 并非搜索结果的所有内容都与用户的问题密切相关，你需要结合问题，对搜索结果进行甄别、筛选。
- 对于客观类的问答，如果问题的答案非常简短，可以适当补充一到两句相关信息，以丰富内容。
- 除非用户要求，否则你回答的语言需要和用户提问的语言保持一致。

# 用户消息为：
{question}"""

SEARCH_ANSWER_EN = """# The following contents are the search results related to the user's message:
{search_results}
In the search results I provide to you, each result is formatted as [webpage X begin]...[webpage X end], where X represents the numerical index of each article. Please cite the context at the end of the relevant sentence when appropriate. Use the citation format [citation:X] in the corresponding part of your answer.
When responding, please keep the following points in mind:
- Today is {cur_date}.
- Not all content in the search results is closely related to the user's question. You need to evaluate and filter the search results based on the question.
- For objective Q&A, if the answer is very brief, you may add one or two related sentences to enrich the content.
- Unless the user requests otherwise, your response should be in the same language as the user's question.

# The user's message is:
{question}"""


def deepseek_api_key() -> str:
    return os.getenv("DEEPSEEK_API_KEY", "").strip()


def deepseek_enabled() -> bool:
    return bool(deepseek_api_key())


def is_deepseek_provider(name: str, base_url: str = "") -> bool:
    if (name or "").lower() == "deepseek":
        return True
    return "deepseek.com" in (base_url or "").lower()


def chat_model() -> str:
    return os.getenv("DEEPSEEK_MODEL", DEEPSEEK_CHAT_MODEL).strip() or DEEPSEEK_CHAT_MODEL


def reasoner_model() -> str:
    return (
        os.getenv("DEEPSEEK_REASONER_MODEL", "").strip()
        or os.getenv("PKF_REASONING_MODEL", "").strip()
        or DEEPSEEK_REASONER_MODEL
    )


def web_search_format() -> str:
    explicit = os.getenv("PKF_WEB_SEARCH_FORMAT", "").strip().lower()
    if explicit:
        return explicit
    if os.getenv("PKF_PROVIDER", "").strip().lower() == "deepseek":
        return "deepseek"
    return "plain"


def format_file_context(file_name: str, file_content: str, question: str) -> str:
    return FILE_UPLOAD_TEMPLATE.format(
        file_name=file_name,
        file_content=file_content,
        question=question,
    )


def format_search_results(query: str, results: list[dict], language: str = "pt") -> str:
    blocks: list[str] = []
    for index, item in enumerate(results, start=1):
        title = item.get("title") or "(sem título)"
        url = item.get("url") or ""
        snippet = (item.get("snippet") or item.get("content") or "").strip()
        blocks.append(
            f"[webpage {index} begin]\n"
            f"Title: {title}\n"
            f"URL: {url}\n"
            f"Content: {snippet[:1200]}\n"
            f"[webpage {index} end]"
        )
    search_results = "\n\n".join(blocks) if blocks else "(nenhum resultado)"
    cur_date = date.today().isoformat()
    template = SEARCH_ANSWER_PT if language.lower().startswith("pt") else SEARCH_ANSWER_EN
    return template.format(search_results=search_results, cur_date=cur_date, question=query)
