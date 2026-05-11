"""
 模块化报告 Schema — Greenblatt 排名法 v3.0

核心设计:
  - 模块清单固定，按 section 组织
  - 模块内容动态：搜索 agent 填，审核 agent 验
  - 特殊资产（BTC）通过 ModuleOverride 显式豁免

用法:
  from report_engine.schema import StockReport, ModuleStatus, ModuleOverride
"""
from __future__ import annotations
from typing import Optional, Literal, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


# ═══════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════

class AssetCategory(str, Enum):
    STOCK = "stock"
    HK_STOCK = "hk_stock"
    CRYPTO = "crypto"

class SignalType(str, Enum):
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"

class ConfidenceType(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class HorizonType(str, Enum):
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG_TERM = "LONG-TERM"

class ActionType(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"

class ConvictionType(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"

class ChartType(str, Enum):
    LINE = "line"
    BAR = "bar"
    RADAR = "radar"

class DotType(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    NEUT = "neut"

class ModuleStatus(str, Enum):
    FILLED = "filled"         # 已成功填充
    MISSING = "missing"       # 未找到，等待审核
    EXEMPTED = "exempted"     # 审核通过，豁免
    REJECTED = "rejected"     # 审核驳回，需重搜


# ═══════════════════════════════════════════════════════════
# 模块清单 — 全部模块定义
# ═══════════════════════════════════════════════════════════

class ModuleDef(BaseModel):
    """单个模块的元定义"""
    module_id: str
    section: str                  # S1-S8, Cover, Verdict
    label: str                    # 中文名
    asset_categories: list[AssetCategory]  # 适用哪些资产
    required: bool = True         # 是否强制
    description: str = ""


# 全部模块清单（并集）
ALL_MODULES: list[ModuleDef] = [
    # Cover
    ModuleDef(module_id="cover_kpi", section="Cover", label="封面 KPI 指标条",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True, description="6 个关键 KPI 数字"),
    # S1
    ModuleDef(module_id="s1_price_changes", section="S1", label="涨跌比例总览",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True, description="至少 4 行涨跌数据"),
    ModuleDef(module_id="s1_core_judgment", section="S1", label="核心判断段落",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True),
    # S2
    ModuleDef(module_id="s2_overview", section="S2", label="公司/资产概览",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True, description="商业模式、核心指标表"),
    # S3
    ModuleDef(module_id="s3_price_chart", section="S3", label="过去一年走势图",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True, description="priceChart, type=line"),
    ModuleDef(module_id="s3_analysis", section="S3", label="走势分析文字",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True),
    # S4
    ModuleDef(module_id="s4_competition", section="S4", label="竞争格局/市场结构",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True),
    # S5
    ModuleDef(module_id="s5_greenblatt", section="S5", label="Greenblatt 三层排名",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK],
              required=True, description="L1 EBIT/EV + L2 ROIC + L3 F-Score"),
    ModuleDef(module_id="s5_crypto_ranking", section="S5", label="加密货币适配排名",
              asset_categories=[AssetCategory.CRYPTO],
              required=True, description="L1 MVRV + L2 网络强度 + L3 改编F-Score"),
    ModuleDef(module_id="s5_f_score", section="S5", label="Piotroski F-Score (9项)",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK],
              required=True),
    ModuleDef(module_id="s5_crypto_f_score", section="S5", label="加密改编 F-Score",
              asset_categories=[AssetCategory.CRYPTO],
              required=True),
    ModuleDef(module_id="s5_valuation_radar", section="S5", label="估值雷达图",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK],
              required=True, description="valuationRadar, type=radar"),
    ModuleDef(module_id="s5_peer_comparison", section="S5", label="同行估值对比图",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK],
              required=True, description="peerCompareChart, type=bar"),
    ModuleDef(module_id="s5_crypto_metrics_chart", section="S5", label="加密关键指标图",
              asset_categories=[AssetCategory.CRYPTO],
              required=True, description="vmScoreChart + mvrvChart"),
    ModuleDef(module_id="s5_dcf_chart", section="S5", label="DCF/目标价对比图",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True, description="dcfChart, type=bar"),
    ModuleDef(module_id="s5_revenue_timeline", section="S5", label="季度营收趋势图",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK],
              required=False, description="timelineChart, type=bar, 可选"),
    ModuleDef(module_id="s5_dashboard", section="S5", label="关键指标仪表盘",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True, description="10+ 个指标"),
    ModuleDef(module_id="s5_valuation_text", section="S5", label="估值分析文字",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True),
    # S6
    ModuleDef(module_id="s6_scenario_chart", section="S6", label="情景分析图",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True, description="scenarioChart, type=bar/line"),
    ModuleDef(module_id="s6_scenarios", section="S6", label="情景分析文字",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True, description="至少 3 个情景"),
    # S7
    ModuleDef(module_id="s7_risks", section="S7", label="风险矩阵",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True, description="至少 5 项风险"),
    # S8
    ModuleDef(module_id="s8_signal", section="S8", label="投资信号块",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True),
    # Verdict
    ModuleDef(module_id="verdict", section="Verdict", label="最终裁决",
              asset_categories=[AssetCategory.STOCK, AssetCategory.HK_STOCK, AssetCategory.CRYPTO],
              required=True, description="看多/看空 + 综合排名"),
]


# ═══════════════════════════════════════════════════════════
# 协商数据结构 (搜索 ↔ 审核)
# ═══════════════════════════════════════════════════════════

class ModuleOverride(BaseModel):
    """搜索 agent 声明某模块无法填充时的豁免请求"""
    module_id: str
    reason: str                   # "比特币无 PE 概念，无法生成同行 PE 对比图"
    alternative_modules: list[str] = []  # 替代模块 ID 列表
    search_attempts: list[str] = []     # 已尝试的搜索策略
    round: int = 1                      # 第几轮协商

class ReviewResult(BaseModel):
    """审核 agent 对单个 override 的裁决"""
    module_id: str
    approved: bool                # 是否批准豁免
    severity: Literal["blocking", "warning", "ok"] = "ok"
    message: str                  # 裁决理由
    fix_suggestion: str = ""      # 如驳回，给搜索建议


class NegotiationResult(BaseModel):
    """整体协商结果"""
    approved: bool                # 全部通过？
    module_results: list[ReviewResult]
    verdict: Literal["APPROVED", "REJECTED", "PARTIAL"]
    fix_instructions: str = ""    # 如 rejected，给整体修复指令
    round: int = 1


# ═══════════════════════════════════════════════════════════
# 图表
# ═══════════════════════════════════════════════════════════

class ChartDataset(BaseModel):
    model_config = {"extra": "ignore"}
    label: str = ""
    data: list[float] = []
    color: str = "#2563eb"
    fill: bool = True
    tension: float = 0.3
    point_radius: int = 3
    border_width: float = 2.0
    border_dash: Optional[list[int]] = None
    point_background_color: Optional[str] = None
    point_background_colors: Optional[list[str]] = None

class ChartDef(BaseModel):
    chart_id: str
    chart_type: ChartType
    section_id: str
    title: str = ""
    labels: list[str] = []
    datasets: list[ChartDataset] = []
    y_axis_label: str = "$"
    y_axis_format: str = "$"
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    horizontal: bool = False
    tooltip_prefix: str = "$"
    tooltip_suffix: str = ""


# ═══════════════════════════════════════════════════════════
# 各 Section 数据模型
# ═══════════════════════════════════════════════════════════

class KPIItem(BaseModel):
    label: str                    # "52周变动"
    value: str                    # "+803.9%"
    sub: Optional[str] = None     # "超买"
    css_class: Optional[str] = None  # "up" / "dn"

class PriceChangeRow(BaseModel):
    dimension: str
    change_pct: str
    corresponding_price: str
    probability_weight: str
    industry_compare: str

class KeyMetricRow(BaseModel):
    """仪表盘指标行"""
    label: str                    # "营收增长率"
    value: str                    # "+65.5%"
    note: Optional[str] = None    # "YoY"

class CompanyOverview(BaseModel):
    title: str                    # "🏢 公司概览" or "🪙 资产概览"
    subtitle: str
    body_html: str
    key_metrics: list[KeyMetricRow]

class CompetitonSection(BaseModel):
    title: str                    # "⚔️ 竞争格局" or "🌐 市场结构"
    subtitle: str
    body_html: str

class RankingRow(BaseModel):
    layer: str = ""               # "L1" | "L2" | "L3" | "L4"
    dimension: str = ""           # "💰 便不便宜"
    metric: str = ""              # "EBIT/EV"
    value: str = ""               # "2.52%"
    rank: str = ""                # "#3/8"
    weight: str = ""              # "40%"
    verdict: str = ""             # 判断说明

class FScoreItem(BaseModel):
    group: str = ""               # "盈利" / "杠杆" / "效率"
    criterion: str = ""
    score: int = 0
    reason: str = ""

class ValuationMethod(BaseModel):
    name: str                     # "DCF 保守"
    value: str                    # "$247"
    probability: str              # "50%"

class ScenarioRow(BaseModel):
    scenario: str                 # "悲观"
    probability: str              # "25%"
    price_target: str             # "$140"
    return_pct: str               # "-35%"
    description: str

class RiskItem(BaseModel):
    risk: str
    probability: str
    impact: str
    mitigation: str

class SignalBlock(BaseModel):
    signal: str = "NEUTRAL"      # BULLISH / NEUTRAL / BEARISH
    confidence: str = "MEDIUM"   # HIGH / MEDIUM / LOW
    horizon: str = "MEDIUM"      # SHORT / MEDIUM / LONG-TERM
    action: str = "HOLD"         # BUY / HOLD / SELL
    conviction: str = "MODERATE" # STRONG / MODERATE / WEAK
    rank_summary: Optional[str] = None
    composite_rank: Optional[str] = None

class VerdictSection(BaseModel):
    title: str = "最终裁决"
    bull_points: list[str]
    bear_points: list[str]
    composite_rank: str           # "L1#3 + L2#1 = 4 → #2/6"
    f_score_total: str            # "8/9"
    recommendation: str           # "强力推荐"
    rec_class: Literal["bull", "neut", "bear"]


# ═══════════════════════════════════════════════════════════
# 根 Schema — StockReport
# ═══════════════════════════════════════════════════════════

class ModuleState(BaseModel):
    """单个模块的状态"""
    module_id: str
    status: ModuleStatus = ModuleStatus.MISSING
    override: Optional[ModuleOverride] = None
    data: Any = None              # 模块的实际数据（已填时）
    review_result: Optional[ReviewResult] = None


class StockReport(BaseModel):
    model_config = {"extra": "ignore"}

    report_version: str = "3.0"
    ticker: str = ""
    company_name: str = ""
    company_name_en: str = ""
    exchange: str = ""
    sector: str = ""
    asset_category: AssetCategory = AssetCategory.STOCK
    report_date: str = ""
    data_date: str = ""
    company_dir: str = ""

    module_states: dict[str, ModuleState] = {}

    cover_kpi: list[KPIItem] = []
    cover_title: str = ""
    cover_price: str = ""
    cover_market_cap: str = ""

    s1_price_changes: list[PriceChangeRow] = []
    s1_core_judgment: str = ""

    s2: Optional[CompanyOverview] = None

    s3_body_html: str = ""

    s4: Optional[CompetitonSection] = None

    greenblatt_ranking: list[RankingRow] = []
    ranking_summary: str = ""
    f_score_items: list[FScoreItem] = []
    f_score_total: int = 0
    composite_score: float = 0.0          # 加权综合分 (越小越好)
    composite_rank_8: str = ""            # "#3/8" 统一8家排名
    layer_weights: dict[str, str] = {"L1":"40%","L2":"25%","L3":"25%","L4":"10%"}

    s5_body_html: str = ""
    s5_valuation_methods: list[ValuationMethod] = []

    dashboard_metrics: list[KeyMetricRow] = []

    s6_body_html: str = ""
    s6_scenarios: list[ScenarioRow] = []

    s7_risks: list[RiskItem] = []

    s8_signal: Optional[SignalBlock] = None

    charts: list[ChartDef] = []

    verdict: Optional[VerdictSection] = None

    sidebar_dots: dict[str, str] = {}

    overrides: list[ModuleOverride] = []
    negotiation_result: Optional[NegotiationResult] = None

    footer_text: str = "InvestSkill v3.0 · 教育性分析，不构成投资建议"


    def get_module_statuses(self) -> dict[str, ModuleStatus]:
        """获取所有模块的状态摘要"""
        result = {}
        for m in ALL_MODULES:
            if m.module_id in self.module_states:
                result[m.module_id] = self.module_states[m.module_id].status
            else:
                result[m.module_id] = ModuleStatus.MISSING
        return result

    def get_missing_required(self) -> list[str]:
        """获取缺少的强制模块"""
        statuses = self.get_module_statuses()
        missing = []
        for m in ALL_MODULES:
            if not m.required:
                continue
            if self.asset_category not in m.asset_categories:
                continue
            if statuses.get(m.module_id) in (ModuleStatus.MISSING, ModuleStatus.REJECTED):
                missing.append(m.module_id)
        return missing

    def get_exempted_modules(self) -> list[ModuleOverride]:
        """获取已豁免的模块"""
        return [o for o in self.overrides
                if self.module_states.get(o.module_id, ModuleState(module_id=o.module_id)).status == ModuleStatus.EXEMPTED]

    def is_complete(self) -> bool:
        """是否所有强制模块都已填充或豁免"""
        return len(self.get_missing_required()) == 0


# ═══════════════════════════════════════════════════════════
# 审核 Agent 输入/输出
# ═══════════════════════════════════════════════════════════

class ReviewInput(BaseModel):
    """给审核 agent 的输入"""
    ticker: str
    company_name: str
    asset_category: AssetCategory
    module_statuses: dict[str, ModuleStatus]
    overrides: list[ModuleOverride]    # 搜索 agent 申请的豁免
    missing_modules: list[str]          # 当前缺失的模块 ID
    negotiation_round: int = 1
    previous_rejections: list[ReviewResult] = []  # 上一轮的驳回
