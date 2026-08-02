"""
Agent1: 评价摘要 Agent

线性 Pipeline 模式，无 HITL。
流程：shopId → 数据采集 → LLM 感情分析 → 统计汇总 → LLM 综合建议 → 结构化输出

使用 LangChain with_structured_output 替代手动 JSON 解析，
使用 abatch 并发处理多批评价。
"""

import json
import logging
from collections import Counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import config
from models import SummaryRequest, BatchReviewAnalysis, RecommendationResult
from java_api_client import java_api
from redis_client import get_redis
from llm import get_llm

logger = logging.getLogger(__name__)

app = FastAPI(title="Agent1 - Review Summary", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Step 1: 数据采集 ----

async def collect_data(shop_id: int) -> dict:
    """采集商铺详情 + 全量评价"""
    shop = await java_api.get_shop_detail(shop_id)

    # 分页获取所有评价
    reviews = []
    page = 1
    while True:
        batch = await java_api.get_shop_reviews(shop_id, current=page)
        if not batch:
            break
        reviews.extend(batch)
        # 如果返回少于 MAX_PAGE_SIZE(10)，说明没有更多了
        if len(batch) < 10:
            break
        page += 1
        # 安全上限：最多获取 250 条
        if len(reviews) >= 250:
            break

    return {"shop": shop, "reviews": reviews}


# ---- Step 2: LLM 逐条情感分析 ----

SENTIMENT_PROMPT = """请对以下 {count} 条评价逐一进行结构化分析。

{reviews_text}

对每条评价提取：
- sentiment: 整体情感倾向（positive / neutral / negative）
- pros: 具体优点列表
- cons: 具体缺点列表
- keyPhrases: 关键名词短语（菜品名、体验关键词等）

注意：如果内容过短或无明确倾向，sentiment 填 neutral。"""


async def analyze_reviews(reviews: list[dict], llm) -> list[dict]:
    """批量分析评价，使用 with_structured_output + abatch 并发处理"""
    batch_size = 5

    # 评价太多时按 liked 排序取代表性样本
    if len(reviews) > 200:
        sorted_reviews = sorted(reviews, key=lambda r: r.get("liked", 0), reverse=True)
        reviews_to_analyze = sorted_reviews[:150] + sorted_reviews[-30:]
    else:
        reviews_to_analyze = reviews

    # 构建所有批次的 prompt
    prompts = []
    for i in range(0, len(reviews_to_analyze), batch_size):
        batch = reviews_to_analyze[i : i + batch_size]
        parts = []
        for idx, review in enumerate(batch, 1):
            title = review.get("title", "")
            content = review.get("content", "")
            if not content:
                content = title
            parts.append(f"评价{idx}：\n标题：{title}\n内容：{content}")
        prompts.append(
            SENTIMENT_PROMPT.format(reviews_text="\n\n".join(parts), count=len(batch))
        )

    if not prompts:
        return []

    # 并发调用 LLM，with_structured_output 保证返回结构化对象
    structured_llm = llm.with_structured_output(BatchReviewAnalysis)
    try:
        results = await structured_llm.abatch(prompts)
    except Exception as e:
        logger.warning(f"LLM batch sentiment analysis failed: {e}")
        return []

    all_analyses = []
    for result in results:
        if result and result.reviews:
            all_analyses.extend(r.model_dump() for r in result.reviews)
    return all_analyses


# ---- Step 3: 统计汇总 ----

def compute_statistics(
    shop: dict, reviews: list[dict], analyses: list[dict]
) -> dict:
    """纯代码计算统计指标"""
    total_reviews = len(reviews)
    if total_reviews == 0:
        return {
            "totalReviews": 0,
            "positiveRate": 0,
            "avgLikedPerReview": 0,
            "topPros": [],
            "topCons": [],
            "keyPhrases": [],
        }

    # 好评率
    sentiments = [a.get("sentiment", "neutral") for a in analyses]
    positive_count = sum(1 for s in sentiments if s == "positive")
    positive_rate = positive_count / len(sentiments) if sentiments else 0

    # 平均点赞
    total_liked = sum(r.get("liked", 0) for r in reviews)
    avg_liked = total_liked / total_reviews if total_reviews > 0 else 0

    # Top 优点/缺点/关键词频次排序
    all_pros = []
    all_cons = []
    all_phrases = []
    for a in analyses:
        all_pros.extend(a.get("pros", []))
        all_cons.extend(a.get("cons", []))
        all_phrases.extend(a.get("keyPhrases", []))

    top_pros = [item for item, _ in Counter(all_pros).most_common(3)]
    top_cons = [item for item, _ in Counter(all_cons).most_common(3)]
    key_phrases = [item for item, _ in Counter(all_phrases).most_common(5)]

    return {
        "totalReviews": total_reviews,
        "positiveRate": round(positive_rate, 2),
        "avgLikedPerReview": round(avg_liked, 1),
        "topPros": top_pros,
        "topCons": top_cons,
        "keyPhrases": key_phrases,
    }


# ---- Step 4: LLM 综合建议 ----

RECOMMENDATION_PROMPT = """你是一个客观的评价分析师。请根据以下数据为用户生成一份商铺评价综合摘要。

商铺：{name}
评分：{score}/5 | 均价：{avgPrice}元 | 销量：{sold} | 评论数：{comments}

评价统计：
- 好评率：{positiveRate}
- 最常提到的优点：{topPros}
- 最常提到的缺点：{topCons}
- 高频关键词：{keyPhrases}

请生成：
- recommendation: 100字左右的综合建议，客观评价优缺点，给出适用人群建议
- scoreBreakdown.overall: 评分 {score}
- scoreBreakdown.interpretation: 评分解读，结合销量和评论数说明"""


async def generate_recommendation(stats: dict, shop: dict, llm) -> dict:
    """LLM 生成综合建议，使用 with_structured_output 保证结构化输出"""
    # score 转换：数据库存的是 1-50，实际是 1-5 分
    raw_score = shop.get("score", 0)
    real_score = raw_score / 10.0 if raw_score > 5 else raw_score

    prompt = RECOMMENDATION_PROMPT.format(
        name=shop.get("name", "未知商铺"),
        score=real_score,
        avgPrice=shop.get("avgPrice", "未知"),
        sold=shop.get("sold", 0),
        comments=shop.get("comments", 0),
        positiveRate=stats["positiveRate"],
        topPros=stats["topPros"],
        topCons=stats["topCons"],
        keyPhrases=stats["keyPhrases"],
    )

    structured_llm = llm.with_structured_output(RecommendationResult)
    try:
        result = await structured_llm.ainvoke(prompt)
        return result.model_dump()
    except Exception as e:
        logger.warning(f"LLM recommendation generation failed: {e}")
        return {
            "recommendation": "暂无法生成综合建议。",
            "scoreBreakdown": {
                "overall": real_score,
                "interpretation": f"评分 {real_score}/5",
            },
        }


# ---- Step 5: 组装输出 ----

def build_response(shop: dict, stats: dict, recommendation: dict) -> dict:
    """合并统计 + LLM 输出 → 最终 JSON"""
    raw_score = shop.get("score", 0)
    real_score = raw_score / 10.0 if raw_score > 5 else raw_score

    return {
        "shopId": shop.get("id"),
        "shopName": shop.get("name"),
        "totalReviews": stats["totalReviews"],
        "positiveRate": stats["positiveRate"],
        "avgLikedPerReview": stats["avgLikedPerReview"],
        "topPros": stats["topPros"],
        "topCons": stats["topCons"],
        "keyPhrases": stats["keyPhrases"],
        "recommendation": recommendation.get("recommendation", ""),
        "scoreBreakdown": recommendation.get("scoreBreakdown", {
            "overall": real_score,
            "interpretation": f"评分 {real_score}/5",
        }),
    }


# ---- 缓存 ----

def get_cached_summary(shop_id: int) -> dict | None:
    """从 Redis 获取缓存的评价摘要"""
    r = get_redis()
    key = f"agent1:summary:{shop_id}"
    raw = r.get(key)
    if raw:
        return json.loads(raw)
    return None


def cache_summary(shop_id: int, summary: dict) -> None:
    """缓存评价摘要到 Redis，TTL 30min"""
    r = get_redis()
    key = f"agent1:summary:{shop_id}"
    r.set(key, json.dumps(summary, ensure_ascii=False), ex=config.AGENT1_CACHE_TTL)


# ---- Pipeline 入口 ----

async def run_pipeline(shop_id: int) -> dict:
    """完整 Pipeline 执行"""
    # 先查缓存
    cached = get_cached_summary(shop_id)
    if cached:
        logger.info(f"Returning cached summary for shop {shop_id}")
        return cached

    llm = get_llm()

    # Step 1
    data = await collect_data(shop_id)
    shop = data["shop"]
    reviews = data["reviews"]

    if not reviews:
        # 无评价时直接返回基础信息
        raw_score = shop.get("score", 0)
        real_score = raw_score / 10.0 if raw_score > 5 else raw_score
        result = {
            "shopId": shop.get("id"),
            "shopName": shop.get("name"),
            "totalReviews": 0,
            "positiveRate": 0,
            "avgLikedPerReview": 0,
            "topPros": [],
            "topCons": [],
            "keyPhrases": [],
            "recommendation": "暂无评价数据，无法生成综合建议。",
            "scoreBreakdown": {
                "overall": real_score,
                "interpretation": f"评分 {real_score}/5，暂无评价数据",
            },
        }
        cache_summary(shop_id, result)
        return result

    # Step 2
    analyses = await analyze_reviews(reviews, llm)

    # Step 3
    stats = compute_statistics(shop, reviews, analyses)

    # Step 4
    recommendation = await generate_recommendation(stats, shop, llm)

    # Step 5
    result = build_response(shop, stats, recommendation)

    # 缓存
    cache_summary(shop_id, result)

    return result


# ---- FastAPI 路由 ----

@app.post("/agent1/summary")
async def summary_endpoint(req: SummaryRequest):
    """评价摘要接口"""
    try:
        result = await run_pipeline(req.shopId)
        return result
    except Exception as e:
        logger.error(f"Agent1 pipeline failed: {e}", exc_info=True)
        return {"error": str(e), "shopId": req.shopId}


@app.get("/agent1/health")
async def health():
    return {"status": "ok", "service": "agent1-review-summary"}


@app.on_event("shutdown")
async def shutdown():
    await java_api.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.AGENT1_PORT)
