"""Eval 评估框架 — 三层评测。

1. 结构化回归 / 2. LLM-as-Judge / 3. 双实验设计（自进化+消融）。
通过 run_experiments() 运行完整双实验，返回 JSON 结果供报告使用。
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from core.config import config
from core.redis import get_redis
from core.llm import get_llm, call_llm, reset_token_usage, get_token_usage
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


# --- 测试用例定义 ---

class EvalCase:
    """单个评测用例"""
    def __init__(self, caseId, userMessage, userId=0, x=None, y=None,
                 expectedCategory=None, expectedPriceRange=None,
                 expectedMinScore=None, expectedMaxDistance=None,
                 minExpectedResults=1, maxExpectedHitl=1, maxExpectedIterations=3,
                 tags=None):
        self.caseId = caseId
        self.userMessage = userMessage
        self.userId = userId
        self.x = x
        self.y = y
        self.expectedCategory = expectedCategory
        self.expectedPriceRange = expectedPriceRange
        self.expectedMinScore = expectedMinScore
        self.expectedMaxDistance = expectedMaxDistance
        self.minExpectedResults = minExpectedResults
        self.maxExpectedHitl = maxExpectedHitl
        self.maxExpectedIterations = maxExpectedIterations
        self.tags = tags or []

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


class ScenarioStep:
    """多轮对话中的一个步骤"""
    def __init__(self, role, content, expect_type=None, check=None):
        self.role = role           # "user" | "assistant" | "check"
        self.content = content     # 发送内容（用户消息 / 检查指令）
        self.expect_type = expect_type  # "recommendation" | "interrupt" | None
        self.check = check         # 验证函数 / 验证条件 dict


class ScenarioCase:
    """多轮对话场景用例"""
    def __init__(self, caseId, steps, tags=None):
        self.caseId = caseId
        self.steps = steps         # list[ScenarioStep]
        self.tags = tags or []


# --- 1. 默认单轮用例集（60 条）---
# 维度：品类(6) × 约束复合度(单/双/三)
# 品类：美食正餐(12) / 小吃快餐(10) / 饮品(10) / 娱乐(10) / 生活服务(10) / 容错模糊(8)
# 约束：单约束~25 / 双约束~25 / 三约束~10

DEFAULT_CASES: list[EvalCase] = [
    # ═════════════════ 美食正餐（12 条）userId 1010-1021 ═════════════════
    # -- 单约束 --
    EvalCase("eat_hotpot",      "附近有什么好吃的火锅",              1010, 120.17, 30.31, "火锅",   minExpectedResults=2, tags=["美食正餐","火锅","单约束"]),
    EvalCase("eat_cantonese",   "附近有粤菜馆吗",                    1011, 120.17, 30.31, "粤菜",   minExpectedResults=1, tags=["美食正餐","粤菜","单约束"]),
    EvalCase("eat_dongbei",     "附近有东北菜吗",                    1012, 120.17, 30.31, "东北菜", minExpectedResults=1, tags=["美食正餐","东北菜","单约束"]),
    EvalCase("eat_gathering",   "帮我和朋友找个聚餐的地方",            1013, 120.17, 30.31, "美食",   minExpectedResults=3, tags=["美食正餐","聚餐","单约束"]),
    # -- 双约束 --
    EvalCase("eat_sichuan",     "想吃川菜，人均80以内",               1014, 120.17, 30.31, "川菜",   expectedPriceRange=(40,100),  minExpectedResults=1, tags=["美食正餐","川菜","双约束"]),
    EvalCase("eat_japanese",    "我想吃日料，预算200左右",            1015, 120.17, 30.31, "日料",   expectedPriceRange=(100,300), minExpectedResults=1, tags=["美食正餐","日料","双约束"]),
    EvalCase("eat_hunan",       "想吃湘菜，预算人均60-120",           1016, 120.17, 30.31, "湘菜",   expectedPriceRange=(60,120),  minExpectedResults=1, tags=["美食正餐","湘菜","双约束"]),
    EvalCase("eat_bbq",         "找个评分高的烧烤店",                 1017, 120.17, 30.31, "烧烤",   expectedMinScore=4.0,         minExpectedResults=1, tags=["美食正餐","烧烤","双约束"]),
    EvalCase("eat_seafood",     "海鲜餐厅，人均200-500",              1018, 120.17, 30.31, "海鲜",   expectedPriceRange=(200,500), minExpectedResults=1, tags=["美食正餐","海鲜","双约束"]),
    # -- 三约束 --
    EvalCase("eat_western",     "推荐西餐厅，人均150-300，评分4分以上", 1019, 120.17, 30.31, "西餐",  expectedPriceRange=(150,300), expectedMinScore=4.0, minExpectedResults=1, tags=["美食正餐","西餐","三约束"]),
    EvalCase("eat_hotpot_full", "附近火锅店，人均100以内，距离3公里内", 1020, 120.17, 30.31, "火锅",  expectedPriceRange=(0,100),   expectedMaxDistance=3.0, minExpectedResults=1, tags=["美食正餐","火锅","三约束"]),
    EvalCase("eat_buffet",      "自助餐，人均200以内，评分4分以上",     1021, 120.17, 30.31, "自助",  expectedPriceRange=(0,200),   expectedMinScore=4.0, minExpectedResults=1, tags=["美食正餐","自助","三约束"]),

    # ═════════════════ 小吃/快餐（10 条）userId 1022-1031 ═════════════════
    # -- 单约束 --
    EvalCase("snack_shaxian",   "附近有沙县小吃吗",                  1022, 120.17, 30.31, "沙县",   minExpectedResults=1, tags=["小吃快餐","沙县","单约束"]),
    EvalCase("snack_lanzhou",   "找个兰州拉面",                      1023, 120.17, 30.31, "拉面",   minExpectedResults=1, tags=["小吃快餐","拉面","单约束"]),
    EvalCase("snack_jianbing",  "附近有卖煎饼果子的吗",               1024, 120.17, 30.31, "煎饼",   minExpectedResults=1, tags=["小吃快餐","煎饼","单约束"]),
    EvalCase("snack_huangji",   "找个黄焖鸡米饭",                    1025, 120.17, 30.31, "黄焖鸡", minExpectedResults=1, tags=["小吃快餐","黄焖鸡","单约束"]),
    # -- 双约束 --
    EvalCase("snack_malatang",  "便宜的麻辣烫，人均30以内",           1026, 120.17, 30.31, "麻辣烫", expectedPriceRange=(0,30),   minExpectedResults=1, tags=["小吃快餐","麻辣烫","双约束"]),
    EvalCase("snack_fastfood",  "附近快餐店，人均20-40",              1027, 120.17, 30.31, "快餐",   expectedPriceRange=(20,40),  minExpectedResults=1, tags=["小吃快餐","快餐","双约束"]),
    EvalCase("snack_chuanchuan","串串香，人均50以内",                 1028, 120.17, 30.31, "串串",   expectedPriceRange=(0,50),   minExpectedResults=1, tags=["小吃快餐","串串","双约束"]),
    EvalCase("snack_maocai",    "冒菜，人均30-50",                    1029, 120.17, 30.31, "冒菜",   expectedPriceRange=(30,50),  minExpectedResults=1, tags=["小吃快餐","冒菜","双约束"]),
    EvalCase("snack_ramen",     "评分高的拉面馆",                     1030, 120.17, 30.31, "拉面",   expectedMinScore=4.0,        minExpectedResults=1, tags=["小吃快餐","拉面","双约束"]),
    # -- 三约束 --
    EvalCase("snack_ramen_full","拉面馆，人均30以内，评分4分以上",     1031, 120.17, 30.31, "拉面",   expectedPriceRange=(0,30), expectedMinScore=4.0, minExpectedResults=1, tags=["小吃快餐","拉面","三约束"]),

    # ═════════════════ 饮品（10 条）userId 1032-1041 ═════════════════
    # -- 单约束 --
    EvalCase("drink_coffee",    "找个安静的地方喝咖啡",               1032, 120.17, 30.31, "咖啡",   minExpectedResults=1, tags=["饮品","咖啡","单约束"]),
    EvalCase("drink_milktea",   "附近有什么好喝的奶茶店",             1033, 120.17, 30.31, "奶茶",   minExpectedResults=1, tags=["饮品","奶茶","单约束"]),
    EvalCase("drink_starbucks", "附近有星巴克吗",                    1034, 120.17, 30.31, "星巴克", minExpectedResults=1, tags=["饮品","咖啡","单约束"]),
    EvalCase("drink_fruittea",  "附近有果茶店吗",                    1035, 120.17, 30.31, "果茶",   minExpectedResults=1, tags=["饮品","果茶","单约束"]),
    EvalCase("drink_heytea",    "附近有喜茶吗",                      1036, 120.17, 30.31, "喜茶",   minExpectedResults=1, tags=["饮品","奶茶","单约束"]),
    # -- 双约束 --
    EvalCase("drink_coffee_p",  "咖啡店，人均30以内",                 1037, 120.17, 30.31, "咖啡",   expectedPriceRange=(0,30),   minExpectedResults=1, tags=["饮品","咖啡","双约束"]),
    EvalCase("drink_bar",       "找个安静的清吧",                     1038, 120.17, 30.31, "清吧",   minExpectedResults=1, tags=["饮品","酒吧","双约束"]),
    EvalCase("drink_coffee_s",  "评分高的咖啡馆",                     1039, 120.17, 30.31, "咖啡",   expectedMinScore=4.0,        minExpectedResults=1, tags=["饮品","咖啡","双约束"]),
    # -- 三约束 --
    EvalCase("drink_milktea_f", "奶茶店，人均15-25，评分4分以上",      1040, 120.17, 30.31, "奶茶",   expectedPriceRange=(15,25), expectedMinScore=4.0, minExpectedResults=1, tags=["饮品","奶茶","三约束"]),
    EvalCase("drink_coffee_f",  "咖啡店，人均30以内，距离2公里内，评分4分以上", 1041, 120.17, 30.31, "咖啡", expectedPriceRange=(0,30), expectedMaxDistance=2.0, expectedMinScore=4.0, minExpectedResults=1, tags=["饮品","咖啡","三约束"]),

    # ═════════════════ 娱乐（10 条）userId 1042-1051 ═════════════════
    # -- 单约束 --
    EvalCase("play_ktv",        "附近有什么KTV可以唱歌",              1042, 120.17, 30.31, "KTV",    minExpectedResults=2, tags=["娱乐","KTV","单约束"]),
    EvalCase("play_escape",     "想玩密室逃脱",                      1043, 120.17, 30.31, "密室",   minExpectedResults=1, tags=["娱乐","密室","单约束"]),
    EvalCase("play_cinema",     "最近有什么电影可以看",               1044, 120.17, 30.31, "电影",   minExpectedResults=1, tags=["娱乐","电影","单约束"]),
    EvalCase("play_netcafe",    "附近有网咖吗",                      1045, 120.17, 30.31, "网咖",   minExpectedResults=1, tags=["娱乐","网咖","单约束"]),
    EvalCase("play_billiards",  "附近有台球厅吗",                    1046, 120.17, 30.31, "台球",   minExpectedResults=1, tags=["娱乐","台球","单约束"]),
    # -- 双约束 --
    EvalCase("play_boardgame",  "桌游吧，人均50以内",                 1047, 120.17, 30.31, "桌游",   expectedPriceRange=(0,50),   minExpectedResults=1, tags=["娱乐","桌游","双约束"]),
    EvalCase("play_ktv_p",      "KTV，人均100以内",                  1048, 120.17, 30.31, "KTV",    expectedPriceRange=(0,100),  minExpectedResults=1, tags=["娱乐","KTV","双约束"]),
    EvalCase("play_party",      "轰趴馆，人均200以内",                1049, 120.17, 30.31, "轰趴",   expectedPriceRange=(0,200),  minExpectedResults=1, tags=["娱乐","轰趴","双约束"]),
    EvalCase("play_escape_s",   "评分高的密室逃脱",                   1050, 120.17, 30.31, "密室",   expectedMinScore=4.0,        minExpectedResults=1, tags=["娱乐","密室","双约束"]),
    # -- 三约束 --
    EvalCase("play_ktv_f",      "KTV，人均50-100，评分4分以上",       1051, 120.17, 30.31, "KTV",    expectedPriceRange=(50,100), expectedMinScore=4.0, minExpectedResults=1, tags=["娱乐","KTV","三约束"]),

    # ═════════════════ 生活服务（10 条）userId 1052-1061 ═════════════════
    # -- 单约束 --
    EvalCase("svc_nail",        "附近有美甲店吗",                    1052, 120.17, 30.31, "美甲",   minExpectedResults=1, tags=["生活服务","美甲","单约束"]),
    EvalCase("svc_foot",        "想做个足疗放松一下",                 1053, 120.17, 30.31, "足疗",   minExpectedResults=1, tags=["生活服务","足疗","单约束"]),
    EvalCase("svc_gym",         "附近有健身房吗",                    1054, 120.17, 30.31, "健身",   minExpectedResults=1, tags=["生活服务","健身","单约束"]),
    EvalCase("svc_yoga",        "附近有瑜伽馆吗",                    1055, 120.17, 30.31, "瑜伽",   minExpectedResults=1, tags=["生活服务","瑜伽","单约束"]),
    # -- 双约束 --
    EvalCase("svc_spa_p",       "美容SPA，人均300以内",               1056, 120.17, 30.31, "SPA",    expectedPriceRange=(0,300),  minExpectedResults=1, tags=["生活服务","SPA","双约束"]),
    EvalCase("svc_foot_s",      "评分高的足疗店",                     1057, 120.17, 30.31, "足疗",   expectedMinScore=4.0,        minExpectedResults=1, tags=["生活服务","足疗","双约束"]),
    EvalCase("svc_nail_p",      "美甲店，人均100以内",                1058, 120.17, 30.31, "美甲",   expectedPriceRange=(0,100),  minExpectedResults=1, tags=["生活服务","美甲","双约束"]),
    EvalCase("svc_hair_p",      "理发店，人均50-100",                 1059, 120.17, 30.31, "理发",   expectedPriceRange=(50,100), minExpectedResults=1, tags=["生活服务","理发","双约束"]),
    # -- 三约束 --
    EvalCase("svc_gym_f",       "健身房，年卡3000以内，评分4分以上",   1060, 120.17, 30.31, "健身",   expectedPriceRange=(0,3000), expectedMinScore=4.0, minExpectedResults=1, tags=["生活服务","健身","三约束"]),
    EvalCase("svc_spa_f",       "SPA，人均500以内，距离5公里内",       1061, 120.17, 30.31, "SPA",    expectedPriceRange=(0,500),  expectedMaxDistance=5.0, minExpectedResults=1, tags=["生活服务","SPA","三约束"]),

    # ═════════════════ 容错/模糊（8 条）userId 1062-1069 ═════════════════
    # -- 单约束 --
    EvalCase("edge_kvt",        "附近有什么kvt",                     1062, 120.17, 30.31, "KTV",    minExpectedResults=1, tags=["容错","拼写","单约束"]),
    EvalCase("edge_hguo",       "附近有好吃的hguo",                  1063, 120.17, 30.31, "火锅",   minExpectedResults=1, tags=["容错","拼写","单约束"]),
    EvalCase("edge_hungry",     "饿乐么",                            1064, 120.17, 30.31, "美食",   minExpectedResults=1, maxExpectedHitl=2, tags=["容错","模糊","单约束"]),
    # -- 双约束 --
    EvalCase("edge_vague_eat",  "随便吃点便宜的",                     1065, 120.17, 30.31, "美食",   expectedPriceRange=(0,50),   minExpectedResults=1, maxExpectedHitl=2, tags=["容错","模糊","双约束"]),
    EvalCase("edge_vague_fun",  "附近有什么好玩的，人均100以内",        1066, 120.17, 30.31, "娱乐",   expectedPriceRange=(0,100),  minExpectedResults=2, maxExpectedHitl=2, tags=["容错","模糊","双约束"]),
    EvalCase("edge_vague_cheap","便宜吃饭的地方，人均30以内",          1067, 120.17, 30.31, "美食",   expectedPriceRange=(0,30),   minExpectedResults=1, tags=["容错","价格","双约束"]),
    EvalCase("edge_vague_relax","想放松一下，预算200以内",             1068, 120.17, 30.31, "按摩",   expectedPriceRange=(0,200),  minExpectedResults=1, maxExpectedHitl=2, tags=["容错","模糊","双约束"]),
    EvalCase("edge_naicah",     "附近有卖naicah的店吗，人均20以内",    1069, 120.17, 30.31, "奶茶",   expectedPriceRange=(0,20),   minExpectedResults=1, tags=["容错","拼写","双约束"]),
]


# --- 2. 多轮对话场景用例（20 个）---
# 分类：指代消解(5) / 偏好修正(5) / 逐步细化(4) / HITL恢复(3) / 拼写容错跨轮(3)
# 每个场景 3-5 轮；场景末尾 step 做累计约束 ACSR 检查

MULTI_TURN_CASES: list[ScenarioCase] = [
    # ═════════════════ 指代消解（5）═════════════════
    # 01 价格指代：更便宜
    ScenarioCase("multi_ref_01", tags=["多轮","指代","价格","美食"], steps=[
        ScenarioStep("user", "附近有什么好吃的火锅"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={"min_results": 1}),
        ScenarioStep("user", "换一家更便宜的"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "cheaper_than_previous": True, "no_repeated_shops": True,
        }),
    ]),
    # 02 价格指代：更高档
    ScenarioCase("multi_ref_02", tags=["多轮","指代","价格","娱乐"], steps=[
        ScenarioStep("user", "附近有什么KTV可以唱歌"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={"min_results": 1}),
        ScenarioStep("user", "环境好一点的，预算更高的"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "more_expensive_than_previous": True, "no_repeated_shops": True,
        }),
    ]),
    # 03 距离指代：更近的
    ScenarioCase("multi_ref_03", tags=["多轮","指代","距离","饮品"], steps=[
        ScenarioStep("user", "找个地方喝咖啡"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={"min_results": 1}),
        ScenarioStep("user", "我现在不想走太远，换个更近的"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "nearer_than_previous": True, "no_repeated_shops": True,
        }),
    ]),
    # 04 评分指代：评分更高的
    ScenarioCase("multi_ref_04", tags=["多轮","指代","评分","美食"], steps=[
        ScenarioStep("user", "附近的粤菜馆"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={"min_results": 1}),
        ScenarioStep("user", "有没有评分更高的店"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "higher_score_than_previous": True, "no_repeated_shops": True,
        }),
    ]),
    # 05 排除指代：不要上一家
    ScenarioCase("multi_ref_05", tags=["多轮","指代","排除","娱乐"], steps=[
        ScenarioStep("user", "想玩密室逃脱"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={"min_results": 1}),
        ScenarioStep("user", "不要刚才推荐的那家，换一家"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "no_repeated_shops": True,
        }),
    ]),

    # ═════════════════ 偏好修正（5）═════════════════
    # 06 品类修正：火锅→粤菜
    ScenarioCase("multi_chg_01", tags=["多轮","偏好修正","品类","美食"], steps=[
        ScenarioStep("user", "附近有什么好吃的火锅"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["火锅"],
        }),
        ScenarioStep("user", "算了还是吃粤菜吧"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["粤菜"],
            "different_category_from_previous": "火锅",
        }),
    ]),
    # 07 品类修正：正餐→小吃
    ScenarioCase("multi_chg_02", tags=["多轮","偏好修正","品类","小吃"], steps=[
        ScenarioStep("user", "帮我找个吃川菜的地方"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["川菜"],
        }),
        ScenarioStep("user", "现在不太饿，还是随便吃点小吃吧"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1,
            "different_category_from_previous": "川菜",
        }),
    ]),
    # 08 价格方向反转：便宜→高档
    ScenarioCase("multi_chg_03", tags=["多轮","偏好修正","价格","饮品"], steps=[
        ScenarioStep("user", "附近有便宜的奶茶店吗"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "max_price": 30, "category_keywords": ["奶茶"],
        }),
        ScenarioStep("user", "今天发工资了，找个环境好点的咖啡店"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["咖啡"],
            "more_expensive_than_previous": True,
        }),
    ]),
    # 09 类别从吃→玩
    ScenarioCase("multi_chg_04", tags=["多轮","偏好修正","跨品类"], steps=[
        ScenarioStep("user", "附近有什么好吃的日料"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["日料"],
        }),
        ScenarioStep("user", "吃饱了，附近有什么地方可以唱歌吗"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["KTV","唱歌"],
            "different_category_from_previous": "日料",
        }),
    ]),
    # 10 拒绝后切换：不要火锅→换烧烤
    ScenarioCase("multi_chg_05", tags=["多轮","偏好修正","拒绝","美食"], steps=[
        ScenarioStep("user", "附近火锅店"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["火锅"],
        }),
        ScenarioStep("user", "火锅味道太重了，换成烧烤吧"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["烧烤"],
            "different_category_from_previous": "火锅",
        }),
    ]),

    # ═════════════════ 逐步细化（4）═════════════════
    # 11 四轮细化：吃饭→火锅→人均100内→评分4.5+
    ScenarioCase("multi_refine_01", tags=["多轮","逐步细化","ACSR","美食"], steps=[
        ScenarioStep("user", "附近有吃饭的地方吗"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={"min_results": 1}),
        ScenarioStep("user", "火锅怎么样"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["火锅"],
        }),
        ScenarioStep("user", "预算人均100以内"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["火锅"], "max_price": 100,
        }),
        ScenarioStep("user", "最好评分4分以上"),
        # ACSR：同时满足品类、价格、评分（全部累积约束）
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["火锅"],
            "max_price": 100, "min_score": 4.0,
        }),
    ]),
    # 12 三轮细化：附近放松→足疗→300内→评分4+
    ScenarioCase("multi_refine_02", tags=["多轮","逐步细化","ACSR","生活服务"], steps=[
        ScenarioStep("user", "我想放松一下"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={"min_results": 1}),
        ScenarioStep("user", "做个足疗吧，预算300以内"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["足疗"], "max_price": 300,
        }),
        ScenarioStep("user", "只看评分4分以上的"),
        # ACSR：足疗 + 300内 + 4分+
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["足疗"],
            "max_price": 300, "min_score": 4.0,
        }),
    ]),
    # 13 两轮细化：娱乐→KTV→人均80-150，不重复上一轮
    ScenarioCase("multi_refine_03", tags=["多轮","逐步细化","ACSR","娱乐"], steps=[
        ScenarioStep("user", "附近有什么娱乐场所"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={"min_results": 1}),
        ScenarioStep("user", "就KTV吧，人均80到150之间"),
        # ACSR：KTV + 80-150 + 不重复第一轮泛娱乐推荐
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["KTV","唱歌"],
            "price_range": (80, 150), "no_repeated_shops": True,
        }),
    ]),
    # 14 四轮细化：咖啡→3km内→安静→人均30内+评分4+
    ScenarioCase("multi_refine_04", tags=["多轮","逐步细化","ACSR","饮品"], steps=[
        ScenarioStep("user", "附近有咖啡店吗"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["咖啡"],
        }),
        ScenarioStep("user", "要3公里以内的"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["咖啡"], "max_distance": 3.0,
        }),
        ScenarioStep("user", "环境安静一点的"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["咖啡"], "max_distance": 3.0,
        }),
        ScenarioStep("user", "人均30以内，评分4分以上"),
        # ACSR：咖啡 + 3km + 30内 + 4分+
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["咖啡"],
            "max_distance": 3.0, "max_price": 30, "min_score": 4.0,
        }),
    ]),

    # ═════════════════ HITL 恢复（3）═════════════════
    # 15 模糊意图触发HITL后补充："吃什么" → "火锅 100以下"
    ScenarioCase("multi_hitl_01", tags=["多轮","HITL","模糊意图","美食"], steps=[
        ScenarioStep("user", "附近有什么吃的"),
        # HITL 触发：意图模糊，需要询问
        ScenarioStep("assistant", "", expect_type="interrupt"),
        ScenarioStep("user", "火锅，人均100以下"),
        # ACSR：恢复后需满足火锅 + 100以下
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 2, "category_keywords": ["火锅"], "max_price": 100,
        }),
    ]),
    # 16 候选过多触发HITL后补充预算："附近KTV" → "人均150以内"
    ScenarioCase("multi_hitl_02", tags=["多轮","HITL","候选过多","娱乐"], steps=[
        ScenarioStep("user", "附近有什么KTV可以唱歌"),
        # 若候选过多可能触发HITL；expect_type允许任意类型，最终step做硬约束
        ScenarioStep("assistant", "", expect_type="interrupt"),
        ScenarioStep("user", "人均150以内的"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["KTV","唱歌"], "max_price": 150,
        }),
    ]),
    # 17 模糊娱乐触发HITL，补充细化："去哪玩"→"密室逃脱 300以内"
    ScenarioCase("multi_hitl_03", tags=["多轮","HITL","模糊意图","娱乐"], steps=[
        ScenarioStep("user", "周末去哪玩"),
        ScenarioStep("assistant", "", expect_type="interrupt"),
        ScenarioStep("user", "密室逃脱，人均300以内"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["密室"], "max_price": 300,
        }),
    ]),

    # ═════════════════ 拼写容错跨轮（3）═════════════════
    # 18 拼写错误(kvt) 继续 + 约束收紧：kvt → 人均100内评分4+
    ScenarioCase("multi_typo_01", tags=["多轮","拼写","ACSR","娱乐"], steps=[
        ScenarioStep("user", "附近有什么kvt"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["KTV","唱歌"],
        }),
        ScenarioStep("user", "人均100以内，评分4分以上"),
        # ACSR：KTV + 100内 + 4分+
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["KTV","唱歌"],
            "max_price": 100, "min_score": 4.0,
        }),
    ]),
    # 19 拼写错误(hguo) 继续 + 不要上一家
    ScenarioCase("multi_typo_02", tags=["多轮","拼写","排除","美食"], steps=[
        ScenarioStep("user", "附近有好吃的hguo"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["火锅"],
        }),
        ScenarioStep("user", "换一家更便宜的，不要刚才那家"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["火锅"],
            "cheaper_than_previous": True, "no_repeated_shops": True,
        }),
    ]),
    # 20 拼写错误(naicah) 继续 + 价格范围+距离
    ScenarioCase("multi_typo_03", tags=["多轮","拼写","ACSR","饮品"], steps=[
        ScenarioStep("user", "附近有卖naicah的店吗"),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["奶茶"],
        }),
        ScenarioStep("user", "人均15-25，3公里以内的"),
        # ACSR：奶茶 + 15-25 + 3km内
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1, "category_keywords": ["奶茶"],
            "price_range": (15, 25), "max_distance": 3.0,
        }),
    ]),
]


class EvalMetrics:
    """单次评测的聚合指标"""
    def __init__(self, totalCases=0, passedCases=0, passRate=0.0,
                 avgIterations=0.0, avgHitlRate=0.0, avgResponseTimeMs=0.0,
                 avgReflectionScore=0.0, avgCandidateCount=0.0,
                 avgRelevanceScore=0.0, categoryBreakdown=None,
                 necessaryHitl=0, excessiveHitl=0,
                 avgInputTokens=0.0, avgOutputTokens=0.0, avgTotalTokens=0.0,
                 avgLlmCallCount=0.0, p50ResponseTimeMs=0.0, p95ResponseTimeMs=0.0):
        self.totalCases = totalCases
        self.passedCases = passedCases
        self.passRate = passRate
        self.avgIterations = avgIterations
        self.avgHitlRate = avgHitlRate
        self.avgResponseTimeMs = avgResponseTimeMs
        self.avgReflectionScore = avgReflectionScore
        self.avgCandidateCount = avgCandidateCount
        self.avgRelevanceScore = avgRelevanceScore or 0.0
        self.categoryBreakdown = categoryBreakdown or {}
        self.necessaryHitl = necessaryHitl
        self.excessiveHitl = excessiveHitl
        # 效率指标（Exp-3）
        self.avgInputTokens = avgInputTokens
        self.avgOutputTokens = avgOutputTokens
        self.avgTotalTokens = avgTotalTokens
        self.avgLlmCallCount = avgLlmCallCount
        self.p50ResponseTimeMs = p50ResponseTimeMs
        self.p95ResponseTimeMs = p95ResponseTimeMs

    def to_dict(self):
        return self.__dict__


class EvalResult:
    def __init__(self, runId="", runAt="", label="", metrics=None, caseResults=None):
        self.runId = runId
        self.runAt = runAt
        self.label = label
        self.metrics = metrics or EvalMetrics()
        self.caseResults = caseResults or []

    def to_dict(self):
        return {"runId": self.runId, "runAt": self.runAt, "label": self.label,
                "metrics": self.metrics.to_dict(), "caseResults": self.caseResults}


# --- 3. 规则检查 ---

def _check_category(shops, expected_category):
    """检查推荐的品类是否包含期望关键词"""
    if not expected_category:
        return 1.0
    if not shops:
        return 0.0
    keyword = expected_category.lower()
    match_count = 0
    for s in shops[:3]:
        name = (s.get("name") or "").lower()
        reason = (s.get("matchReason") or "").lower()
        if keyword in name or keyword in reason:
            match_count += 1
    return min(1.0, match_count / max(1, min(len(shops), 3)))


def _check_price(shops, expected_range):
    """检查推荐价格是否在期望范围内"""
    if not expected_range or not shops:
        return 1.0
    prices = [s.get("avgPrice", 0) for s in shops if s.get("avgPrice")]
    if not prices:
        return 1.0
    p_min, p_max = expected_range
    in_range = sum(1 for p in prices[:3] if p_min <= p <= p_max)
    return in_range / min(len(prices), 3)


def _check_score(shops, expected_min_score):
    """检查推荐商铺的评分是否达到期望最低分"""
    if not expected_min_score or not shops:
        return 1.0
    scores = [s.get("score", 0) for s in shops if s.get("score") is not None]
    if not scores:
        return 1.0
    qualified = sum(1 for s in scores[:3] if s >= expected_min_score)
    return qualified / min(len(scores), 3)


def _check_distance(shops, expected_max_distance):
    """检查推荐商铺的距离是否在期望范围内"""
    if not expected_max_distance or not shops:
        return 1.0
    distances = [s.get("distance") for s in shops if s.get("distance") is not None]
    if not distances:
        return 1.0
    in_range = sum(1 for d in distances[:3] if d <= expected_max_distance)
    return in_range / min(len(distances), 3)


def _calc_hitl_score(hitl_triggered, max_expected):
    """HITL 评分：触发次数越少越好，但不应始终为 0"""
    if not hitl_triggered:
        return 1.0
    if max_expected == 0:
        return 0.0
    return max(0.0, 1.0 - (1.0 / max_expected))


# --- 4. LLM-as-Judge（定义见下方实验框架区域） ---


# --- EvalRunner — 统一评测运行器 ---

class EvalRunner:
    """Eval 评测运行器 — 支持单轮 + 多轮场景 + LLM-as-Judge"""

    def __init__(self):
        self.prefix = getattr(config, 'EVAL_KEY_PREFIX', 'agent2:eval:')
        self.cases = list(DEFAULT_CASES)

    def get_cases(self) -> list[dict]:
        return [c.to_dict() for c in self.cases]

    # ---- 离线模式：直接 import graph，不调 HTTP ----

    async def run_single_case_offline(self, case: EvalCase, judge: bool = True) -> dict:
        """离线运行单个用例（直接 import compiled_graph）"""
        from graph.builder import run_graph
        from graph.state import AgentState

        start_time = time.time()
        out = {
            "caseId": case.caseId, "userMessage": case.userMessage,
            "passed": False, "hitlTriggered": False, "iterations": 0,
            "candidateCount": 0, "shops": [], "reflectionScore": 0.0,
            "responseTimeMs": 0.0, "error": None, "tags": case.tags,
            "categoryScore": 1.0, "priceScore": 1.0, "hitlScore": 1.0,
            "llmJudge": None,
            "tokenUsage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0, "llmCallCount": 0},
            "trajectoryData": None, "trajectoryJudge": None, "replanAnalysis": None,
        }

        # 重置 token 累加器，隔离每个用例的 token 统计
        reset_token_usage()

        try:
            state = AgentState(
                user_message=case.userMessage, user_id=case.userId,
                user_x=case.x, user_y=case.y,
                thread_id=f"eval-{uuid.uuid4().hex[:8]}",
            )
            result_state = await run_graph(state.model_dump())
            st = AgentState(**result_state)
            elapsed = (time.time() - start_time) * 1000
            out["responseTimeMs"] = round(elapsed, 1)
            out["iterations"] = st.iteration_count
            # 采集 agent 运行阶段的 token（不含 Judge）
            out["tokenUsage"] = get_token_usage()

            # 采集轨迹数据（Exp-2 轨迹评估 + replan 分析）
            node_logs = st.node_logs or []
            decisions = st.decisions or []
            out["trajectoryData"] = {
                "nodeLogs": node_logs,
                "decisions": decisions,
                "trajectoryId": st.trajectory_id,
            }
            # Replan 分析（纯解析，无 LLM 调用）
            out["replanAnalysis"] = _analyze_replan(node_logs, decisions, st.iteration_count)

            if st.hitl_needed:
                out["hitlTriggered"] = True
                out["error"] = f"HITL: {st.hitl_question}"
                out["passed"] = True
                # HITL 分类: 候选 < minExpectedResults → 必要; 候选 ≥ minExpectedResults → 过度
                candidate_count = len(st.candidate_shops or [])
                if candidate_count < case.minExpectedResults:
                    out["hitlType"] = "necessary"
                else:
                    out["hitlType"] = "excessive"
            else:
                shops = st.ranked_shops or []
                out["candidateCount"] = len(shops)
                out["shops"] = shops[:5]
                out["reflectionScore"] = st.reflection_score

                # 规则评分
                out["categoryScore"] = _check_category(shops, case.expectedCategory)
                out["priceScore"] = _check_price(shops, case.expectedPriceRange)
                out["scoreScore"] = _check_score(shops, case.expectedMinScore)
                out["distanceScore"] = _check_distance(shops, case.expectedMaxDistance)
                out["hitlScore"] = _calc_hitl_score(st.hitl_needed, case.maxExpectedHitl)

                # LLM-as-Judge 语义评分（Judge 的 token 也会被累加）
                if judge and shops:
                    out["llmJudge"] = await _llm_judge(case.userMessage, shops)

                # 采集含 Judge 的总 token
                out["tokenUsageWithJudge"] = get_token_usage()

                # 综合判定：品类匹配 + 结果数达标
                passed = (
                    len(shops) >= case.minExpectedResults
                    and out["categoryScore"] >= 0.5
                )
                out["passed"] = passed
                if not passed:
                    reasons = []
                    if len(shops) < case.minExpectedResults:
                        reasons.append(f"results={len(shops)} < {case.minExpectedResults}")
                    if out["categoryScore"] < 0.5:
                        reasons.append(f"categoryScore={out['categoryScore']:.1f}")
                    out["error"] = "; ".join(reasons) if reasons else None

            # Trajectory Judge: LLM 评估轨迹合理性（Exp-2）
            if judge and node_logs:
                tokens_before = get_token_usage().get("totalTokens", 0)
                out["trajectoryJudge"] = await _judge_trajectory(
                    case.userMessage, node_logs, decisions, st.iteration_count,
                )
                tokens_after = get_token_usage().get("totalTokens", 0)
                out["trajectoryJudgeTokens"] = tokens_after - tokens_before

        except Exception as e:
            out["error"] = str(e)
            out["responseTimeMs"] = round((time.time() - start_time) * 1000, 1)
            out["tokenUsage"] = get_token_usage()

        return out

    # ---- HTTP 模式（向后兼容）----

    async def run_single_case(self, case: EvalCase) -> dict:
        """HTTP 模式运行单个用例（需要 Agent2 服务在运行）"""
        import httpx

        start_time = time.time()
        out = {
            "caseId": case.caseId, "userMessage": case.userMessage,
            "passed": False, "hitlTriggered": False, "iterations": 0,
            "candidateCount": 0, "reflectionScore": 0.0,
            "responseTimeMs": 0.0, "error": None, "tags": case.tags,
            "categoryScore": 1.0, "priceScore": 1.0, "hitlScore": 1.0,
            "llmJudge": None,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"http://localhost:{config.AGENT2_PORT}/agent2/chat",
                    json={"userId": case.userId, "message": case.userMessage, "x": case.x, "y": case.y},
                    timeout=120.0,
                )
                data = resp.json()
            elapsed = (time.time() - start_time) * 1000
            out["responseTimeMs"] = round(elapsed, 1)

            if data.get("type") == "recommendation":
                shops = data.get("shops", [])
                out["candidateCount"] = len(shops)
                out["reflectionScore"] = data.get("reflectionScore", 0.0)
                out["passed"] = len(shops) >= case.minExpectedResults
                if not out["passed"]:
                    out["error"] = f"results={len(shops)} < {case.minExpectedResults}"
            elif data.get("type") == "interrupt":
                out["hitlTriggered"] = True
                out["passed"] = True
        except Exception as e:
            out["error"] = str(e)
            out["responseTimeMs"] = round((time.time() - start_time) * 1000, 1)
        return out

    # ---- 聚合 ----

    async def run_eval(self, label: str = "", judge: bool = True, mode: str = "offline") -> EvalResult:
        """运行完整评测"""
        run_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()
        case_results = []

        runner = self.run_single_case_offline if mode == "offline" else self.run_single_case
        total_n = len(self.cases)
        for idx, case in enumerate(self.cases):
            t0 = time.time()
            r = await runner(case, judge=judge) if mode == "offline" else await runner(case)
            case_results.append(r)
            status = "PASS" if r.get("passed") else "FAIL"
            print(f"  [{idx+1}/{total_n}] {case.caseId} {status} ({time.time()-t0:.1f}s, iter={r.get('iterations')}, hitl={r.get('hitlTriggered')})", flush=True)

        total = len(case_results)
        passed = sum(1 for r in case_results if r["passed"])
        hitl_count = sum(1 for r in case_results if r["hitlTriggered"])
        total_iter = sum(r["iterations"] for r in case_results)
        total_time = sum(r["responseTimeMs"] for r in case_results)
        total_candidates = sum(r.get("candidateCount", 0) for r in case_results)
        score_sum = sum(r.get("reflectionScore", 0) for r in case_results if r.get("reflectionScore", 0) > 0)
        rel_sum = sum(r.get("llmJudge", {}).get("relevance", 0) for r in case_results if r.get("llmJudge"))

        # Token 聚合（使用 agent 运行阶段的 tokenUsage，不含 Judge）
        token_usages = [r.get("tokenUsage", {}) for r in case_results if r.get("tokenUsage")]
        total_input = sum(t.get("inputTokens", 0) for t in token_usages)
        total_output = sum(t.get("outputTokens", 0) for t in token_usages)
        total_tokens = sum(t.get("totalTokens", 0) for t in token_usages)
        total_calls = sum(t.get("llmCallCount", 0) for t in token_usages)

        # 延迟分位数
        times_sorted = sorted(r["responseTimeMs"] for r in case_results)
        p50 = times_sorted[len(times_sorted) // 2] if times_sorted else 0
        p95_idx = int(len(times_sorted) * 0.95)
        p95 = times_sorted[min(p95_idx, len(times_sorted) - 1)] if times_sorted else 0

        metrics = EvalMetrics(
            totalCases=total, passedCases=passed,
            passRate=round(passed / total, 4) if total > 0 else 0,
            avgIterations=round(total_iter / total, 2) if total > 0 else 0,
            avgHitlRate=round(hitl_count / total, 4) if total > 0 else 0,
            avgResponseTimeMs=round(total_time / total, 1) if total > 0 else 0,
            avgReflectionScore=round(score_sum / total, 2) if total > 0 else 0,
            avgCandidateCount=round(total_candidates / total, 2) if total > 0 else 0,
            avgRelevanceScore=round(rel_sum / total, 2) if total > 0 else 0,
            categoryBreakdown=self._category_breakdown(case_results),
            avgInputTokens=round(total_input / total, 1) if total > 0 else 0,
            avgOutputTokens=round(total_output / total, 1) if total > 0 else 0,
            avgTotalTokens=round(total_tokens / total, 1) if total > 0 else 0,
            avgLlmCallCount=round(total_calls / total, 2) if total > 0 else 0,
            p50ResponseTimeMs=round(p50, 1),
            p95ResponseTimeMs=round(p95, 1),
        )

        # HITL 分类统计
        necessary_hitl = sum(1 for r in case_results if r.get("hitlType") == "necessary")
        excessive_hitl = sum(1 for r in case_results if r.get("hitlType") == "excessive")
        metrics.necessaryHitl = necessary_hitl
        metrics.excessiveHitl = excessive_hitl

        result = EvalResult(runId=run_id, runAt=now, label=label, metrics=metrics, caseResults=case_results)
        self._save_result(result)
        return result

    # ---- 消融实验（Exp-4）----

    async def run_ablation(self, variants=None, cases=None, judge=True) -> dict:
        """运行消融实验：对每个变体在相同用例集上运行，计算与 baseline 的差异。

        Args:
            variants: 消融变体列表，默认 ["baseline", "no_playbook", "no_memory", "no_replan"]
            cases: 用例列表，默认使用 self.cases（60 条单轮用例）
            judge: 是否启用 LLM-Judge

        Returns:
            {
                "variants": {variant_name: {metrics + caseResults}},
                "deltas": {variant_name: {metric: delta_vs_baseline}},
                "replanComparison": {...},  # baseline vs no_replan 在 replan 案例上的对比
            }
        """
        if variants is None:
            variants = ["baseline", "no_playbook", "no_memory", "no_replan"]
        if cases is None:
            cases = self.cases

        import core.shop_api_http as jc
        from core.shop_api_mysql import shop_api_mysql
        from core.redis import get_redis

        # Mock get_review_summary（Agent1 未启动）
        import graph.nodes as gn
        _orig_exec = gn.execute_tool
        async def _patched_exec(tool_name, params):
            if tool_name == "get_review_summary":
                return {"recommendation": "分析中", "topPros": [], "topCons": []}
            return await _orig_exec(tool_name, params)
        gn.execute_tool = _patched_exec
        jc.shop_api = shop_api_mysql

        all_results = {}

        for variant in variants:
            # 应用 patch
            restores = _apply_patches(variant)
            print(f"\n--- 变体: {variant} ---", flush=True)

            # 清理 Redis 缓存（隔离变体间状态）
            r = get_redis()
            for k in r.keys("agent2:*"):
                r.delete(k)

            # 运行所有用例
            case_results = []
            total_n = len(cases)
            for idx, case in enumerate(cases):
                t0 = time.time()
                result = await self.run_single_case_offline(case, judge=judge)
                case_results.append(result)
                status = "PASS" if result.get("passed") else "FAIL"
                print(f"  [{variant} {idx+1}/{total_n}] {case.caseId} {status} ({time.time()-t0:.1f}s)", flush=True)

            # 聚合指标
            metrics = self._aggregate_metrics(case_results)
            all_results[variant] = {
                "metrics": metrics,
                "caseResults": case_results,
            }

            # 恢复 patch
            _restore_patches(restores)

        # 恢复 mock
        gn.execute_tool = _orig_exec
        jc.shop_api = None

        # 计算 deltas vs baseline
        deltas = {}
        baseline_m = all_results.get("baseline", {}).get("metrics", {})
        for variant in variants:
            if variant == "baseline":
                continue
            v_metrics = all_results.get(variant, {}).get("metrics", {})
            deltas[variant] = _compute_deltas(baseline_m, v_metrics)

        # Replan 对比（Exp-2b: baseline vs no_replan）
        replan_comparison = _compare_replan(
            all_results.get("baseline", {}).get("caseResults", []),
            all_results.get("no_replan", {}).get("caseResults", []),
        )

        return {
            "variants": {v: all_results[v]["metrics"] for v in variants},
            "deltas": deltas,
            "replanComparison": replan_comparison,
        }

    def _aggregate_metrics(self, case_results: list) -> dict:
        """聚合用例结果为指标摘要"""
        total = len(case_results)
        if total == 0:
            return {}
        passed = sum(1 for r in case_results if r["passed"])
        hitl_count = sum(1 for r in case_results if r["hitlTriggered"])
        replan_count = sum(1 for r in case_results if r.get("replanAnalysis", {}).get("triggered", False))

        # CSR: 品类+价格+评分+距离 同时满足的比例
        csr_scores = []
        for r in case_results:
            if r.get("candidateCount", 0) > 0:
                scores = [r.get("categoryScore", 1), r.get("priceScore", 1),
                          r.get("scoreScore", 1), r.get("distanceScore", 1)]
                # 只计入有约束的维度
                csr_scores.append(min(scores))

        token_usages = [r.get("tokenUsage", {}) for r in case_results if r.get("tokenUsage")]

        # 轨迹评估分数
        traj_scores = []
        for r in case_results:
            tj = r.get("trajectoryJudge")
            if tj:
                avg_tj = sum(tj.values()) / len(tj) if tj else 0
                traj_scores.append(avg_tj)

        times_sorted = sorted(r["responseTimeMs"] for r in case_results)

        return {
            "totalCases": total,
            "passedCases": passed,
            "passRate": round(passed / total, 4),
            "avgIterations": round(sum(r["iterations"] for r in case_results) / total, 2),
            "hitlRate": round(hitl_count / total, 4),
            "replanTriggerRate": round(replan_count / total, 4),
            "avgCSR": round(sum(csr_scores) / len(csr_scores), 4) if csr_scores else 0,
            "avgReflectionScore": round(
                sum(r.get("reflectionScore", 0) for r in case_results if r.get("reflectionScore", 0) > 0) / total, 2
            ),
            "avgRelevanceScore": round(
                sum(r.get("llmJudge", {}).get("relevance", 0) for r in case_results if r.get("llmJudge")) / total, 2
            ),
            "avgTrajectoryScore": round(sum(traj_scores) / len(traj_scores), 2) if traj_scores else 0,
            "avgResponseTimeMs": round(sum(r["responseTimeMs"] for r in case_results) / total, 1),
            "p50ResponseTimeMs": round(times_sorted[len(times_sorted) // 2], 1) if times_sorted else 0,
            "p95ResponseTimeMs": round(times_sorted[min(int(len(times_sorted) * 0.95), len(times_sorted) - 1)], 1) if times_sorted else 0,
            "avgInputTokens": round(sum(t.get("inputTokens", 0) for t in token_usages) / total, 1),
            "avgOutputTokens": round(sum(t.get("outputTokens", 0) for t in token_usages) / total, 1),
            "avgTotalTokens": round(sum(t.get("totalTokens", 0) for t in token_usages) / total, 1),
            "avgLlmCallCount": round(sum(t.get("llmCallCount", 0) for t in token_usages) / total, 2),
        }

    # ---- 多轮场景评测 ----

    async def run_multi_turn_scenario(self, scenario: ScenarioCase) -> dict:
        """运行多轮对话场景评测：验证指代解析、HITL 恢复、拼写容错"""
        from graph.builder import run_graph
        from graph.state import AgentState
        from memory.conversation import append_turn, save_last_shops, clear_conversation

        thread_id = f"multi-{uuid.uuid4().hex[:8]}"
        clear_conversation(thread_id)

        out = {
            "caseId": scenario.caseId, "tags": scenario.tags,
            "steps": [], "passed": True, "error": None,
        }

        user_id = 9900
        prev_shops = []

        for i, step in enumerate(scenario.steps):
            step_result = {"index": i, "role": step.role, "expect": step.expect_type}

            if step.role == "user":
                append_turn(thread_id, user_id, "user", step.content)

                state = AgentState(
                    user_message=step.content, user_id=user_id,
                    user_x=120.17, user_y=30.31, thread_id=thread_id,
                )
                result_state = await run_graph(state.model_dump())
                st = AgentState(**result_state)

                if st.hitl_needed:
                    step_result["type"] = "interrupt"
                    step_result["question"] = st.hitl_question
                    if step.expect_type and step.expect_type != "interrupt":
                        step_result["status"] = "FAIL: expected recommendation got interrupt"
                        out["passed"] = False
                    else:
                        step_result["status"] = "OK"
                else:
                    shops = st.ranked_shops or []
                    step_result["type"] = "recommendation"
                    step_result["shopCount"] = len(shops)
                    step_result["shops"] = [s.get("name", "?")[:15] for s in shops[:3]]

                    # 保存结构化商铺数据供下一轮指代解析
                    save_last_shops(thread_id, shops)

                    assistant_msg = st.final_recommendation or json.dumps(shops[:3], ensure_ascii=False)
                    append_turn(thread_id, user_id, "assistant", assistant_msg[:300])

                    if step.expect_type and step.expect_type != "recommendation":
                        step_result["status"] = "FAIL: expected interrupt got recommendation"
                        out["passed"] = False
                    elif step.check:
                        check_result = self._check_scenario(step.check, shops, prev_shops)
                        step_result["check"] = check_result
                        if not check_result.get("passed", True):
                            out["passed"] = False
                    else:
                        step_result["status"] = "OK"

                    prev_shops = shops

            out["steps"].append(step_result)

        return out

    def _check_scenario(self, check: dict, shops: list, prev_shops: list) -> dict:
        """验证多轮场景的 check 条件（累计约束、指代解析、偏好修正等）"""
        result = {"passed": True, "checks": []}

        if "min_results" in check:
            ok = len(shops) >= check["min_results"]
            result["checks"].append(f"min_results={len(shops)}/{check['min_results']} {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        # ── 单轮硬约束检查 ──
        if "max_price" in check and shops:
            prices = [s.get("avgPrice", 0) for s in shops if s.get("avgPrice")]
            ok = all(p <= check["max_price"] for p in prices)
            result["checks"].append(f"max_price≤{check['max_price']} {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        if "price_range" in check and shops:
            p_min, p_max = check["price_range"]
            prices = [s.get("avgPrice", 0) for s in shops if s.get("avgPrice")]
            ok = all(p_min <= p <= p_max for p in prices)
            result["checks"].append(f"price_range=[{p_min},{p_max}] {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        if "min_score" in check and shops:
            scores = [s.get("score", 0) for s in shops if s.get("score") is not None]
            ok = all(s >= check["min_score"] for s in scores)
            result["checks"].append(f"min_score≥{check['min_score']} {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        if "max_distance" in check and shops:
            dists = [s.get("distance") for s in shops if s.get("distance") is not None]
            ok = all(d <= check["max_distance"] for d in dists)
            result["checks"].append(f"max_distance≤{check['max_distance']}km {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        # 品类关键词匹配（ACSR 核心：累积约束中，要求满足全部品类关键词）
        if "category_keywords" in check and shops:
            kws = check["category_keywords"] if isinstance(check["category_keywords"], list) else [check["category_keywords"]]
            n_checked = min(len(shops), 3)
            if n_checked:
                matched = 0
                for s in shops[:3]:
                    name = (s.get("name") or "").lower()
                    reason = (s.get("matchReason") or "").lower()
                    if any(k.lower() in name or k.lower() in reason for k in kws):
                        matched += 1
                ok = matched >= (check.get("category_need_match", n_checked) or n_checked)
                result["checks"].append(f"category[{','.join(kws)}]={matched}/{n_checked} {'✓' if ok else '✗'}")
                if not ok: result["passed"] = False

        # ── 多轮相对比较（指代解析 / 偏好修正 / 约束收紧）──
        if check.get("cheaper_than_previous") and shops and prev_shops:
            prev_min = min((s.get("avgPrice", 9999) for s in prev_shops if s.get("avgPrice")), default=9999)
            curr_min = min((s.get("avgPrice", 9999) for s in shops if s.get("avgPrice")), default=9999)
            ok = curr_min < prev_min
            result["checks"].append(f"cheaper: {curr_min}<{prev_min} {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        if check.get("more_expensive_than_previous") and shops and prev_shops:
            prev_max = max((s.get("avgPrice", 0) for s in prev_shops if s.get("avgPrice")), default=0)
            curr_max = max((s.get("avgPrice", 0) for s in shops if s.get("avgPrice")), default=0)
            ok = curr_max > prev_max
            result["checks"].append(f"more_expensive: {curr_max}>{prev_max} {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        if check.get("higher_score_than_previous") and shops and prev_shops:
            prev_avg = sum((s.get("score", 0) for s in prev_shops if s.get("score") is not None)) / max(1, len(prev_shops))
            curr_avg = sum((s.get("score", 0) for s in shops if s.get("score") is not None)) / max(1, len(shops))
            ok = curr_avg > prev_avg
            result["checks"].append(f"higher_score: {curr_avg:.2f}>{prev_avg:.2f} {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        if check.get("nearer_than_previous") and shops and prev_shops:
            prev_min = min((s.get("distance", 999) for s in prev_shops if s.get("distance") is not None), default=999)
            curr_min = min((s.get("distance", 999) for s in shops if s.get("distance") is not None), default=999)
            ok = curr_min < prev_min
            result["checks"].append(f"nearer: {curr_min:.2f}<{prev_min:.2f}km {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        # 不重复推荐上一轮出现过的商铺（按 id/name 判断）
        if check.get("no_repeated_shops") and shops and prev_shops:
            prev_ids = {s.get("id") for s in prev_shops if s.get("id")}
            prev_names = {s.get("name") for s in prev_shops if s.get("name")}
            repeats = [s for s in shops if s.get("id") in prev_ids or s.get("name") in prev_names]
            ok = len(repeats) == 0
            result["checks"].append(f"no_repeated: {len(repeats)} repeats {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        # 类别与上一轮不同（偏好修正）：要求推荐中不含上一轮品类关键词
        if "different_category_from_previous" in check and shops and prev_shops:
            kw = check["different_category_from_previous"]
            prev_reasons = " ".join(s.get("matchReason", "") for s in prev_shops[:3]).lower()
            curr_has_kw = any(kw.lower() in (s.get("name") or "").lower() or kw.lower() in (s.get("matchReason") or "").lower() for s in shops[:3])
            prev_had_kw = kw.lower() in prev_reasons
            ok = prev_had_kw and not curr_has_kw
            result["checks"].append(f"category_change[no {kw}]: {'✓' if ok else '✗'}")
            if not ok: result["passed"] = False

        return result

    def _category_breakdown(self, case_results):
        tag_stats = {}
        for r in case_results:
            for tag in r.get("tags", []):
                s = tag_stats.setdefault(tag, {"total": 0, "passed": 0})
                s["total"] += 1
                if r["passed"]: s["passed"] += 1
        return {tag: {"passRate": round(s["passed"] / s["total"], 4) if s["total"] > 0 else 0, **s} for tag, s in tag_stats.items()}

    # ---- 持久化 ----

    def _save_result(self, result: EvalResult):
        r = get_redis()
        r.set(f"{self.prefix}{result.runId}", json.dumps(result.to_dict(), ensure_ascii=False), ex=90 * 24 * 3600)
        ts = datetime.fromisoformat(result.runAt).timestamp()
        r.zadd(f"{self.prefix}index", {result.runId: ts})

    def get_result(self, run_id: str) -> Optional[dict]:
        r = get_redis()
        raw = r.get(f"{self.prefix}{run_id}")
        return json.loads(raw) if raw else None

    def list_results(self, limit: int = 20) -> list[dict]:
        r = get_redis()
        ids = r.zrevrange(f"{self.prefix}index", 0, limit - 1)
        results = []
        for rid in ids:
            result = self.get_result(rid)
            if result:
                results.append({"runId": result["runId"], "label": result["label"],
                                "runAt": result["runAt"], "passRate": result["metrics"]["passRate"]})
        return results

    def compare(self, before_id: str, after_id: str) -> dict:
        before = self.get_result(before_id)
        after = self.get_result(after_id)
        if not before or not after:
            return {"error": "Run not found"}

        bm, am = before["metrics"], after["metrics"]
        deltas = {k: round(am.get(k, 0) - bm.get(k, 0), 4) for k in bm if isinstance(bm[k], (int, float))}

        case_comparison = []
        before_cases = {c["caseId"]: c for c in before["caseResults"]}
        after_cases = {c["caseId"]: c for c in after["caseResults"]}
        for case_id in before_cases:
            bc, ac = before_cases.get(case_id, {}), after_cases.get(case_id, {})
            bp = bc.get("passed", False)
            ap = ac.get("passed", False)
            status = "regressed" if bp and not ap else "improved" if not bp and ap else "both_passed" if bp and ap else "both_failed"
            case_comparison.append({"caseId": case_id, "beforePassed": bp, "afterPassed": ap, "status": status})

        regressions = [c for c in case_comparison if c["status"] == "regressed"]
        improvements = [c for c in case_comparison if c["status"] == "improved"]

        return {
            "before": {"runId": before_id, "label": before["label"], "metrics": bm},
            "after": {"runId": after_id, "label": after["label"], "metrics": am},
            "deltas": deltas,
            "caseComparison": case_comparison,
            "summary": {
                "improvements": len(improvements),
                "regressions": len(regressions),
                "overallVerdict": "improved" if deltas.get("passRate", 0) > 0 else
                                  "regressed" if deltas.get("passRate", 0) < 0 else "neutral",
            },
        }


# --- 实验框架 — 双实验设计：自进化效果 + 消融实验 ---

ABLATION_NAMES = {
    "baseline":    "完整系统（基准）",
    "no_playbook": "移除 Playbook（全局经验）",
    "no_memory":   "移除 User Memory（用户偏好）",
    "no_replan":   "移除 Replan（最大迭代=1，禁用 evaluate-replan 和 reflect-replan）",
}

JUDGE_PROMPT = """你是推荐质量评估器。对以下推荐打分（1-5）。

用户请求: {query}
推荐结果: {shops}

评分维度:
- relevance: 推荐是否匹配用户的品类/偏好/意图（1=完全不匹配, 5=完全匹配）
- diversity: Top-3 是否覆盖不同类型的选项（1=同质化, 5=多样化）
- reasoning: matchReason 是否有说服力和个性化（1=敷衍模板, 5=有理有据）

只输出 JSON: {{"relevance": 4, "diversity": 3, "reasoning": 4}}"""

PLAYBOOK_JUDGE_PROMPT = """你是经验质量评估器。请评估以下 Agent 自主提炼的经验规则是否有价值。

经验规则:
{entries}

评分维度（1-5）:
- actionability: 规则是否可执行（1=模糊空泛, 5=有明确操作指令）
- correctness: 规则逻辑是否正确（1=有逻辑错误, 5=完全正确）
- novelty: 规则是否有洞察价值（1=常识废话, 5=非显而易见的洞察）

只输出 JSON: {{"actionability": 4, "correctness": 5, "novelty": 3}}"""


# --- Trajectory Judge: 评估推理轨迹合理性 ---

TRAJECTORY_JUDGE_PROMPT = """你是 Agent 推理轨迹评估器。请评估以下推荐 Agent 的执行轨迹是否合理。

## 用户请求
{user_message}

## 执行轨迹（节点日志）
{node_logs}

## 决策序列
{decisions}

## 迭代次数
{iteration_count}

评估维度（1-5 分）:
- intent_understanding: plan 节点是否正确理解用户意图（1=完全误解, 5=精准理解）
- tool_selection: 选择的工具是否恰当（1=全错, 5=全部最优选择）
- tool_order: 工具调用顺序是否合理，有无冗余调用（1=混乱冗余, 5=简洁高效）
- reflection_utilization: 非首轮 plan 是否有效利用了上一轮的 replan_hints（1=未利用, 5=充分利用。首轮则为 5）
- termination_timing: 是否在数据充分时及时停止，无过度迭代（1=过早停止或过度迭代, 5=时机恰当）

只输出 JSON: {{"intent_understanding": 4, "tool_selection": 4, "tool_order": 5, "reflection_utilization": 3, "termination_timing": 4}}"""


async def _judge_trajectory(user_message, node_logs, decisions, iteration_count):
    """LLM-as-Judge 评估推理轨迹合理性（Exp-2 轨迹评估）"""
    if not node_logs:
        return {}
    try:
        logs_text = "\n".join([
            f"[{log.get('timestamp', '')}] {log.get('nodeName', '?')}: "
            f"{log.get('inputSummary', '')} → {log.get('outputSummary', '')} "
            f"({log.get('durationMs', 0)}ms)"
            for log in node_logs
        ])
        decisions_text = "\n".join([
            f"- [{d.get('node', '?')}] {d.get('decision', '?')}: {d.get('reasoning', '')[:100]}"
            for d in (decisions or [])
        ])

        resp = await call_llm([HumanMessage(content=TRAJECTORY_JUDGE_PROMPT.format(
            user_message=user_message,
            node_logs=logs_text[:2000],
            decisions=decisions_text[:1000],
            iteration_count=iteration_count,
        ))])
        import re
        m = re.search(r'\{.*\}', resp.content, re.DOTALL)
        return json.loads(m.group()) if m else {}
    except Exception:
        return {}


def _analyze_replan(node_logs, decisions, iteration_count):
    """解析轨迹中的 replan 事件：类型、次数、触发点（Exp-2 replan 有效性评估）

    返回:
        triggered: 是否触发了 replan
        count: replan 次数
        types: replan 类型列表 ("evaluate_replan" | "reflect_replan")
        evaluate_replan_count: evaluate 触发的 replan 次数
        reflect_replan_count: reflect 触发的 replan 次数
    """
    if iteration_count <= 1 or not node_logs:
        return {
            "triggered": False, "count": 0, "types": [],
            "evaluateReplanCount": 0, "reflectReplanCount": 0,
        }

    node_sequence = [log.get("nodeName", "") for log in node_logs]
    replan_events = []

    for i in range(1, len(node_sequence)):
        if node_sequence[i] == "plan":
            prev = node_sequence[i - 1]
            if prev == "evaluate":
                replan_events.append("evaluate_replan")
            elif prev == "reflect":
                replan_events.append("reflect_replan")

    eval_count = sum(1 for t in replan_events if t == "evaluate_replan")
    reflect_count = sum(1 for t in replan_events if t == "reflect_replan")

    return {
        "triggered": len(replan_events) > 0,
        "count": len(replan_events),
        "types": replan_events,
        "evaluateReplanCount": eval_count,
        "reflectReplanCount": reflect_count,
    }


async def _llm_judge(query, shops):
    """LLM-as-Judge 对单条推荐结果打分"""
    if not shops:
        return {}
    try:
        shops_text = json.dumps([{
            "name": s.get("name", "?"), "avgPrice": s.get("avgPrice", "?"),
            "score": s.get("score", "?"), "reason": s.get("matchReason", "")[:60],
        } for s in shops[:5]], ensure_ascii=False)
        resp = await call_llm([HumanMessage(content=JUDGE_PROMPT.format(query=query, shops=shops_text))])
        import re
        m = re.search(r'\{.*\}', resp.content, re.DOTALL)
        return json.loads(m.group()) if m else {}
    except Exception:
        return {}


async def _judge_playbook(entries):
    """LLM-as-Judge 对 Playbook 经验条目质量打分"""
    if not entries:
        return {}
    try:
        entries_text = "\n".join([f"- [{e.category}] {e.description[:80]}" for e in entries[:10]])
        resp = await call_llm([HumanMessage(content=PLAYBOOK_JUDGE_PROMPT.format(entries=entries_text))])
        import re
        m = re.search(r'\{.*\}', resp.content, re.DOTALL)
        return json.loads(m.group()) if m else {}
    except Exception:
        return {}


async def _run_single(msg, uid, x=120.17, y=30.31):
    """运行单次推荐并收集结果（含 LLM-Judge）"""
    from graph.builder import run_graph
    from graph.state import AgentState
    import time
    state = AgentState(user_message=msg, user_id=uid, user_x=x, user_y=y,
                       thread_id=f"exp-{uid}-{int(time.time()*1000)}")
    r = await run_graph(state.model_dump())
    st = AgentState(**r)
    shops = st.ranked_shops or []
    judge = await _llm_judge(msg, shops) if shops and not st.hitl_needed else {}
    return {
        "results": len(shops), "hitl": st.hitl_needed, "reflect": st.reflection_score,
        "shops": shops, "judge": judge,
    }


def _avg_judge(rows, key):
    scores = [r["judge"].get(key, 0) for r in rows if r.get("judge") and not r["hitl"]]
    return round(sum(scores) / len(scores), 2) if scores else 0.0


async def _clear_playbook():
    """清空 Playbook 数据（MySQL + Redis + ChromaDB）"""
    import memory.playbook as pb
    from core.redis import get_redis
    from core.mysql_store import get_pool
    import aiomysql, chromadb, os

    r = get_redis()
    for k in r.keys("agent2:playbook:*"):
        r.delete(k)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM tb_agent_playbook")

    try:
        from core.config import config
        cd = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)
        cd.delete_collection("playbook_entries")
    except Exception:
        pass
    pb.playbook._collection = None


def _get_patches(variant: str):
    """返回消融变体需要替换的函数列表

    返回格式: [(target, attr_name, replacement), ...]
    特殊: config 类型的 patch 用 ("__config__", key_name, original_value)
    """
    import memory.playbook as pb
    import memory.preferences as mu

    if variant == "no_playbook":
        async def empty_context(*a, **kw):
            return "(暂无历史经验)"
        # patch 类方法而非实例，避免残留实例属性
        return [(type(pb.playbook), "get_context", empty_context)]

    elif variant == "no_memory":
        async def empty_memory(user_id):
            return {"userId": user_id, "preferences": {}}
        return [(mu, "load_memory", empty_memory)]

    elif variant == "no_replan":
        # 设置最大迭代次数为 1，禁用 evaluate-replan 和 reflect-replan
        # should_hitl 中: iteration_count >= MAX_ITERATIONS → 直接 generate
        # reflect_node 中: iteration_count < MAX_ITERATIONS 为 False → 不触发 replan
        return [("__config__", "AGENT2_MAX_ITERATIONS", 1)]

    return []


def _apply_patches(variant: str) -> list:
    """应用消融 patch，返回恢复信息列表"""
    patches = _get_patches(variant)
    restores = []
    for target, attr, new_val in patches:
        if target == "__config__":
            old_val = getattr(config, attr)
            setattr(config, attr, new_val)
            restores.append(("__config__", attr, old_val))
        else:
            old_val = getattr(target, attr)
            setattr(target, attr, new_val)
            restores.append((target, attr, old_val))
    return restores


def _restore_patches(restores: list):
    """恢复消融 patch"""
    for target, attr, old_val in restores:
        if target == "__config__":
            setattr(config, attr, old_val)
        else:
            setattr(target, attr, old_val)


def _compute_deltas(baseline: dict, variant: dict) -> dict:
    """计算变体相对 baseline 的指标差异"""
    deltas = {}
    for key in baseline:
        if key in variant and isinstance(baseline[key], (int, float)):
            b = baseline[key]
            v = variant[key]
            deltas[key] = {
                "baseline": b,
                "variant": v,
                "delta": round(v - b, 4),
                "deltaPct": round((v - b) / b * 100, 2) if b != 0 else 0,
            }
    return deltas


def _compare_replan(baseline_results: list, noreplan_results: list) -> dict:
    """Replan 有效性对比：在 baseline 触发了 replan 的案例上，比较 baseline vs no_replan

    Exp-2b: 评估 replan 之后的推荐结果是否有改进
    """
    # 匹配 caseId
    noreplan_map = {r["caseId"]: r for r in noreplan_results}

    replan_cases = []
    for br in baseline_results:
        ra = br.get("replanAnalysis", {})
        if not ra.get("triggered", False):
            continue
        nr = noreplan_map.get(br["caseId"])
        if not nr:
            continue

        # 计算各指标差异
        b_csr = min(br.get("categoryScore", 1), br.get("priceScore", 1),
                    br.get("scoreScore", 1), br.get("distanceScore", 1))
        n_csr = min(nr.get("categoryScore", 1), nr.get("priceScore", 1),
                    nr.get("scoreScore", 1), nr.get("distanceScore", 1))

        b_tokens = br.get("tokenUsage", {}).get("totalTokens", 0)
        n_tokens = nr.get("tokenUsage", {}).get("totalTokens", 0)

        replan_cases.append({
            "caseId": br["caseId"],
            "replanTypes": ra.get("types", []),
            "replanCount": ra.get("count", 0),
            "baseline": {
                "iterations": br["iterations"],
                "candidateCount": br.get("candidateCount", 0),
                "reflectionScore": br.get("reflectionScore", 0),
                "csr": round(b_csr, 4),
                "totalTokens": b_tokens,
                "responseTimeMs": br["responseTimeMs"],
            },
            "noReplan": {
                "iterations": nr["iterations"],
                "candidateCount": nr.get("candidateCount", 0),
                "reflectionScore": nr.get("reflectionScore", 0),
                "csr": round(n_csr, 4),
                "totalTokens": n_tokens,
                "responseTimeMs": nr["responseTimeMs"],
            },
            "deltas": {
                "csr": round(b_csr - n_csr, 4),
                "reflectionScore": round(br.get("reflectionScore", 0) - nr.get("reflectionScore", 0), 2),
                "candidateCount": br.get("candidateCount", 0) - nr.get("candidateCount", 0),
                "totalTokens": b_tokens - n_tokens,
                "responseTimeMs": round(br["responseTimeMs"] - nr["responseTimeMs"], 1),
            },
            # replan 有效：baseline 的 CSR 或 reflectionScore 优于 no_replan
            "replanEffective": (b_csr > n_csr) or (br.get("reflectionScore", 0) > nr.get("reflectionScore", 0)),
        })

    total_replan = len(replan_cases)
    effective_count = sum(1 for c in replan_cases if c["replanEffective"])

    # 聚合差异
    if replan_cases:
        avg_delta_csr = sum(c["deltas"]["csr"] for c in replan_cases) / total_replan
        avg_delta_score = sum(c["deltas"]["reflectionScore"] for c in replan_cases) / total_replan
        avg_delta_candidates = sum(c["deltas"]["candidateCount"] for c in replan_cases) / total_replan
        avg_delta_tokens = sum(c["deltas"]["totalTokens"] for c in replan_cases) / total_replan
    else:
        avg_delta_csr = avg_delta_score = avg_delta_candidates = avg_delta_tokens = 0

    return {
        "totalReplanCases": total_replan,
        "effectiveCount": effective_count,
        "replanSuccessRate": round(effective_count / total_replan, 4) if total_replan > 0 else 0,
        "avgDeltaCSR": round(avg_delta_csr, 4),
        "avgDeltaReflectionScore": round(avg_delta_score, 2),
        "avgDeltaCandidateCount": round(avg_delta_candidates, 2),
        "avgDeltaTotalTokens": round(avg_delta_tokens, 1),
        "caseDetails": replan_cases,
    }


async def run_experiments(cases=None):
    """运行双实验：自进化效果（Fresh vs Accumulated）+ 消融实验。返回 JSON 供报告使用"""
    import core.shop_api_http as jc
    from core.shop_api_mysql import shop_api_mysql
    from core.redis import get_redis
    import memory.playbook as pb

    # 默认用例集
    if cases is None:
        cases = [
            ("火锅", "附近有什么好吃的火锅"),
            ("咖啡", "找个安静的地方喝咖啡"),
            ("KTV",  "附近有什么KTV可以唱歌"),
            ("足疗", "想做个足疗放松一下"),
            ("日料", "我想吃日料，预算200左右"),
        ]

    # Mock get_review_summary (Agent1 未启动)
    import graph.nodes as gn
    _orig_exec = gn.execute_tool
    async def _patched(tool_name, params):
        if tool_name == "get_review_summary":
            return {"recommendation": "分析中", "topPros": [], "topCons": []}
        return await _orig_exec(tool_name, params)
    gn.execute_tool = _patched

    jc.shop_api = shop_api_mysql
    r = get_redis()

    # --- 实验一: Playbook 自进化效果 ---
    await _clear_playbook()

    # Phase A: Fresh Start
    for k in r.keys("agent2:*"):
        r.delete(k)
    rows_fresh = []
    print("  [Phase A] Fresh Start...", flush=True)
    for uid, (name, msg) in enumerate(cases):
        t0 = time.time()
        row = await _run_single(msg, uid + 100)
        row["case"] = name
        rows_fresh.append(row)
        print(f"    fresh {name}: judge_rel={row.get('judge',{}).get('relevance')} hitl={row['hitl']} ({time.time()-t0:.1f}s)", flush=True)

    # Phase B: 累积 4 轮
    print("  [Phase B] 累积 4 轮经验...", flush=True)
    for round_n in range(4):
        for k in r.keys("agent2:*"):
            r.delete(k)
        for uid, (name, msg) in enumerate(cases):
            await _run_single(msg, 200 + round_n * 100 + uid)
        print(f"    round {round_n+1}/4 done", flush=True)
    n_entries = len(await pb.playbook.get_entries())
    print(f"  Playbook 累积条目数: {n_entries}", flush=True)

    # Phase C: Accumulated
    for k in r.keys("agent2:*"):
        r.delete(k)
    rows_accum = []
    print("  [Phase C] Accumulated...", flush=True)
    for uid, (name, msg) in enumerate(cases):
        t0 = time.time()
        row = await _run_single(msg, uid + 700)
        row["case"] = name
        rows_accum.append(row)
        print(f"    accum {name}: judge_rel={row.get('judge',{}).get('relevance')} hitl={row['hitl']} ({time.time()-t0:.1f}s)", flush=True)

    exp1 = {
        "fresh": {
            "relevance": _avg_judge(rows_fresh, "relevance"),
            "diversity": _avg_judge(rows_fresh, "diversity"),
            "reasoning": _avg_judge(rows_fresh, "reasoning"),
            "hitl": sum(1 for r in rows_fresh if r["hitl"]),
        },
        "accumulated": {
            "relevance": _avg_judge(rows_accum, "relevance"),
            "diversity": _avg_judge(rows_accum, "diversity"),
            "reasoning": _avg_judge(rows_accum, "reasoning"),
            "hitl": sum(1 for r in rows_accum if r["hitl"]),
        },
        "playbook_entries": n_entries,
    }

    # Playbook 经验质量评估
    pb_entries = await pb.playbook.get_entries()
    pb_judge = await _judge_playbook(pb_entries)
    exp1["playbook_quality"] = pb_judge

    # 恢复 exp1 的 mock
    gn.execute_tool = _orig_exec
    jc.shop_api = None

    # --- 实验二: 消融实验（A0 baseline / A1 no_playbook / A2 no_memory / A4 no_replan）---
    # 使用 EvalRunner.run_ablation 进行完整指标采集（CSR / Token / 轨迹评估 / replan 对比）
    ablation_cases = [
        EvalCase(caseId=f"ablation_{i}", userMessage=msg, userId=800 + i,
                 x=120.17, y=30.31, expectedCategory=None,
                 minExpectedResults=1, tags=["ablation", name])
        for i, (name, msg) in enumerate(cases)
    ]
    exp2 = await eval_runner.run_ablation(
        variants=["baseline", "no_playbook", "no_memory", "no_replan"],
        cases=ablation_cases,
        judge=True,
    )

    return {"exp1_self_improvement": exp1, "exp2_ablation": exp2}


eval_runner = EvalRunner()
