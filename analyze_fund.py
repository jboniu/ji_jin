"""Analyze market news from a fund-investing perspective."""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from app_logging import get_logger
from portfolio import build_portfolio_summary, load_portfolio


DEFAULT_PROVIDER = "zhipu"
DEFAULT_MODEL = "glm-4.7-flash"
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
DEFAULT_FALLBACK_MODELS = {
    "zhipu": ["glm-4.7-air", "glm-4-flash"],
    "openai": ["gpt-4.1-mini"],
}
MAX_RETRIES_PER_MODEL = 2
RETRY_SLEEP_SECONDS = 2

logger = get_logger("analyze_fund")

FUND_ANALYSIS_PROMPT = """
你是一位擅长中国公募基金研究、资产配置和投资者陪伴的专业理财顾问。你熟悉宽基指数、行业主题、主动混合、债券、黄金、QDII 以及货币基金的典型风险收益特征，也理解普通投资者在盘中决策时最需要的不是空话，而是清楚的判断依据、风险边界和优先级。

你的任务是基于“当日新闻 + 近一周市场线索 + 我的真实持仓”，生成一份有参考价值、像金融行业正式理财简报一样的日报分析。

写作原则：
1. 先判断大势，再落到持仓，再给动作观察，不要直接跳结论。
2. 所有关键判断尽量写出依据，例如政策信号、风险偏好、板块强弱、风格切换、资金主线、避险情绪。
3. 要有轻重缓急，告诉我“先看什么、后看什么”，而不是把所有内容平铺。
4. 可以分析我持有的具体基金，但不要承诺收益，不要使用“稳赚、必涨、确定性盈利”等表述。
5. 不输出绝对化交易命令，统一使用“加仓观察 / 减仓观察 / 持有观察 / 暂不动作”。
6. 如果信息不足以支持明确判断，要直说“信息不足，建议观察”。
7. 风格要专业、克制、可信，像成熟理财顾问给出的内部投顾摘要，而不是泛泛而谈的自媒体点评。
8. 报告必须先完成对我现有持仓的优先分析，再讨论新增可关注方向。
9. 对“新增可关注方向”可以给出具体基金示例，但只能给出真实存在、常见且与该方向匹配的基金代码和名称，不要编造。
10. 可以给出试探性入场仓位区间，但必须使用区间表达，例如“5%-10%”“不超过总仓位的 10%”，并说明前提条件与风险。
11. 如果给出基金示例，要说明“这些示例仅用于方向参考，具体选择还要结合费用、规模、跟踪误差、流动性和个人风险承受能力”。

输出要求：
- 每个部分都要有实质内容，不要只写一句空话。
- 尽量具体到我的持仓组合，而不是只谈大盘。
- “加仓观察 / 减仓观察 / 持有观察”至少覆盖我组合中的主要基金和主要风险暴露。
- 我的持仓中的每一只基金都必须被明确归入“加仓观察 / 减仓观察 / 持有观察”三类之一，不能遗漏。
- 同一类中的基金要按优先级排序，最值得先看的排在最前面。
- 结论部分要清楚说明今天更偏进攻、偏防守，还是偏等待确认。
- 在讨论新增入场机会时，优先从和我当前组合互补、能分散风险、或具备阶段性胜率的方向中选择，不要与我现有重仓主题高度重复，除非你明确说明重复配置的理由。

输出结构必须严格包含以下标题：
# 支付宝基金日报分析

## 一、执行摘要
- 用 4 到 6 条总结今天最重要的判断
- 要包含：市场风格、组合风险、今日优先级、总体策略倾向

## 二、今日市场判断
- 判断今天更偏进攻还是防守
- 说明影响基金决策的核心变量
- 给出 1 个“主判断”和 1 个“反例风险”

## 三、近一周市场回顾
- 回顾最近一周主线
- 说明成长、消费、资源、军工、黄金等方向谁强谁弱
- 点出风格切换或情绪变化

## 四、我的持仓结构画像
- 概括我的组合当前偏向什么风格
- 指出主题集中度、重仓暴露、对市场环境最敏感的方向
- 说明这份组合当前最怕什么，最受益于什么

## 五、今日 15:00 前重点关注
- 列出今天最值得盯的 3 到 5 个方向或信号
- 每条写清楚：关注什么 / 为什么重要 / 若走弱意味着什么

## 六、加仓观察
- 只列更适合“小幅加仓观察”的基金
- 每只基金单独一条
- 每条必须严格按以下模板输出：
  - 基金代码与名称：
  - 当前判断：
  - 核心依据：
  - 风险点：
  - 今日观察信号：
- 如果没有基金适合放在这里，必须明确写“今日无明确加仓观察对象”

## 七、减仓观察
- 只列更适合“控制仓位或减仓观察”的基金
- 每只基金单独一条
- 每条必须严格按以下模板输出：
  - 基金代码与名称：
  - 当前判断：
  - 核心依据：
  - 风险点：
  - 今日观察信号：
- 如果没有基金适合放在这里，必须明确写“今日无明确减仓观察对象”

## 八、持有观察
- 只列更适合继续持有、暂不急于动作的基金
- 每只基金单独一条
- 每条必须严格按以下模板输出：
  - 基金代码与名称：
  - 当前判断：
  - 核心依据：
  - 风险点：
  - 今日观察信号：
- 所有没有进入“加仓观察”和“减仓观察”的基金，都必须完整列在这里，不能省略

## 九、个性化风险提醒
- 针对我的真实组合写 3 到 5 条
- 重点写集中度、主题重合、波动来源、踏错风格切换的风险

## 十、可关注的新入场方向
- 在优先完成我现有持仓分析后，再给出 1 到 3 个可新增关注的基金方向
- 每个方向必须严格按以下模板输出：
  - 方向：
  - 推荐理由：
  - 入场条件：
  - 仓位区间：
  - 基金示例（代码 + 名称）：
  - 风险提示：
- 每个方向尽量给 2 到 3 个基金示例，且示例之间尽量有区分，例如 ETF、联接基金、主动基金或不同基金公司产品
- 如果今天不适合开新仓，要明确写“今日暂无高胜率新入场方向”

## 十一、结论
- 用一段完整的话总结今天更偏进攻、偏防守还是偏等待
- 明确今天最值得优先处理的 1 到 2 个方向
- 最后提醒这只是参考，不构成收益承诺

我的持仓如下：
{portfolio_text}

财经新闻如下：
{news_text}
""".strip()


def _build_missing_key_report() -> str:
    return """# 支付宝基金日报分析

## 一、执行摘要
- 当前无法生成 AI 分析，因为尚未配置 API Key。

## 二、今日市场判断
- 暂无分析结果。

## 三、近一周市场回顾
- 暂无分析结果。

## 四、我的持仓结构画像
- 暂无分析结果。

## 五、今日 15:00 前重点关注
- 请先配置 `.env` 文件中的 `OPENAI_API_KEY`。

## 六、加仓观察
- 暂无分析结果。

## 七、减仓观察
- 暂无分析结果。

## 八、持有观察
- 暂无分析结果。

## 九、个性化风险提醒
- 当前报告仅保留原始输入，不应作为投资依据。

## 十、可关注的新入场方向
- 暂无分析结果。

## 十一、结论
- 请先补全模型配置后再重新生成报告。
"""


def _build_empty_response_report() -> str:
    return """# 支付宝基金日报分析

## 一、执行摘要
- AI 返回为空，请稍后重试。

## 二、今日市场判断
- 暂无分析结果。

## 三、近一周市场回顾
- 暂无分析结果。

## 四、我的持仓结构画像
- 暂无分析结果。

## 五、今日 15:00 前重点关注
- 建议检查模型配置、网络连接和 API 额度。

## 六、加仓观察
- 暂无分析结果。

## 七、减仓观察
- 暂无分析结果。

## 八、持有观察
- 暂无分析结果。

## 九、个性化风险提醒
- 当前结果不完整，请勿据此做出投资决策。

## 十、可关注的新入场方向
- 暂无分析结果。

## 十一、结论
- 建议重新运行脚本，并结合日志排查异常。
"""


def _build_failure_report(last_error: Exception, attempted_models: list[str]) -> str:
    models_text = " -> ".join(attempted_models)
    return f"""# 支付宝基金日报分析

## 一、执行摘要
- 本次 AI 分析未成功完成，系统已自动尝试备用模型。

## 二、今日市场判断
- 暂无分析结果。

## 三、近一周市场回顾
- 暂无分析结果。

## 四、我的持仓结构画像
- 暂无分析结果。

## 五、今日 15:00 前重点关注
- 本次已尝试模型：{models_text}

## 六、加仓观察
- 暂无分析结果。

## 七、减仓观察
- 暂无分析结果。

## 八、持有观察
- 暂无分析结果。

## 九、个性化风险提醒
- 本次 AI 调用失败类型：`{type(last_error).__name__}`
- 建议查看 `logs/fund_analysis.log` 获取详细错误信息。

## 十、可关注的新入场方向
- 暂无分析结果。

## 十一、结论
- 当前建议以观察为主，等待模型服务恢复后再重新生成日报。
"""


def _load_model_candidates(provider: str, primary_model: str) -> list[str]:
    raw_fallbacks = os.getenv("OPENAI_FALLBACK_MODELS", "").strip()
    if raw_fallbacks:
        fallbacks = [item.strip() for item in raw_fallbacks.split(",") if item.strip()]
    else:
        fallbacks = DEFAULT_FALLBACK_MODELS.get(provider, [])

    candidates: list[str] = []
    for model_name in [primary_model, *fallbacks]:
        if model_name and model_name not in candidates:
            candidates.append(model_name)
    return candidates


def analyze_news(news_text: str, portfolio_text: str | None = None) -> str:
    """Call a compatible LLM to generate a fund-focused market analysis report."""
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower() or DEFAULT_PROVIDER
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    primary_model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()

    if not api_key:
        logger.warning("AI analysis skipped because API key is missing.")
        return _build_missing_key_report()

    client_kwargs = {"api_key": api_key}
    if provider == "zhipu":
        client_kwargs["base_url"] = base_url or DEFAULT_BASE_URL
    elif base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)
    if portfolio_text is None:
        portfolio = load_portfolio()
        portfolio_text = build_portfolio_summary(portfolio)

    prompt = FUND_ANALYSIS_PROMPT.format(
        news_text=news_text,
        portfolio_text=portfolio_text,
    )

    model_candidates = _load_model_candidates(provider, primary_model)
    attempted_models: list[str] = []
    last_error: Exception | None = None

    for model_name in model_candidates:
        attempted_models.append(model_name)
        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            try:
                logger.info(
                    "Starting AI analysis attempt %s/%s with provider=%s model=%s",
                    attempt,
                    MAX_RETRIES_PER_MODEL,
                    provider,
                    model_name,
                )
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                )
                report = (response.choices[0].message.content or "").strip()
                if report:
                    logger.info(
                        "AI analysis succeeded with provider=%s model=%s on attempt %s.",
                        provider,
                        model_name,
                        attempt,
                    )
                    return report
            except Exception as exc:
                last_error = exc
                logger.exception(
                    "AI analysis failed with provider=%s model=%s on attempt %s.",
                    provider,
                    model_name,
                    attempt,
                )
                if attempt < MAX_RETRIES_PER_MODEL:
                    time.sleep(RETRY_SLEEP_SECONDS)

        logger.warning("Switching to next fallback model after failures: %s", model_name)

    if last_error is not None:
        return _build_failure_report(last_error, attempted_models)

    return _build_empty_response_report()


if __name__ == "__main__":
    demo = analyze_news("这里是一段测试新闻：A股震荡，债市情绪偏稳，成长板块分化。")
    print(demo)
