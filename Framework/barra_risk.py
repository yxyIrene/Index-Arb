"""
Barra风险模型模块
支持多空头寸的风险暴露计算和投资组合优化
"""
import sys
sys.path.append('E:\Index_Arbitrage')

import pandas as pd
import numpy as np
import cvxpy as cp
import datetime
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from Framework.pythonTool import *


class BarraDataLoader:
    """Barra风险模型数据加载器
    
    负责从数据库加载风险因子所需的数据，支持数据缓存和批量加载
    """
    
    def __init__(self, date: str, db_instance=None):
        """
        Args:
            date: 数据日期，格式 'YYYY-MM-DD'
            db_instance: 数据库实例，如果为None则创建默认的ddb实例
        """
        self.date = date
        self.date_str = pd.to_datetime(date).strftime('%Y.%m.%d')
        self.db = db_instance if db_instance is not None else ddb(db='bctmate')
        
        # 数据缓存
        self._industry_data = None
        self._market_cap_data = None
    
    def load_industry_data(self) -> pd.Series:
        """
        加载行业数据（申万一级）
        
        Returns:
            industry_mapping: Series，index为股票代码，values为行业名称
        """
        if self._industry_data is None:
            data = self.db.load_table_by_sql(
                'dfs://jq_price', 'industry',
                f'select code, sw_l1 from industry where date={self.date_str}'
            )
            self._industry_data = data.set_index('code')['sw_l1']
        return self._industry_data
    
    def load_market_cap_data(self, use_log: bool = True) -> pd.Series:
        """
        加载市值数据
        
        Args:
            use_log: 是否返回对数市值，如果False则返回原始市值
        
        Returns:
            market_cap_data: Series，index为股票代码，values为市值（或对数市值）
        """
        if self._market_cap_data is None:
            market_caps = self.db.load_table_by_sql(
                'dfs://jq_fundamental', 'valuation',
                f'select code, market_cap from valuation where date={self.date_str}'
            )
            market_caps = market_caps.set_index('code')['market_cap']
            if use_log:
                self._market_cap_data = np.log(market_caps)
            else:
                self._market_cap_data = market_caps
        return self._market_cap_data
    
    def load_all(self):
        """批量加载所有数据"""
        self.load_industry_data()
        self.load_market_cap_data()
    
    def clear_cache(self):
        """清除数据缓存"""
        self._industry_data = None
        self._market_cap_data = None


class IndexDataLoader:
    """Barra风险模型数据加载器
    
    负责从数据库加载风险因子所需的数据，支持数据缓存和批量加载
    """
    
    def __init__(self, date: str, db_instance=None):
        """
        Args:
            date: 数据日期，格式 'YYYY-MM-DD'
            db_instance: 数据库实例，如果为None则创建默认的ddb实例
        """
        self.date = date
        self.date_str = pd.to_datetime(date).strftime('%Y.%m.%d')
        self.db = db_instance if db_instance is not None else ddb(db='bctmate')
        
        # 数据缓存
        self._index_weight = {}

    def load_index_weight(self, index_code: str) -> pd.Series:  
        """
        加载指数成分权重数据
        """
        if index_code not in self._index_weight:
            data = self.db.load_table_by_sql(
                'dfs://jq_price', 'index_components',
                f'select code, weight from index_components where index_code="{index_code}" and date={self.date_str}'
            )
            self._index_weight[index_code] = data.set_index('code')['weight']/100
        return self._index_weight[index_code]
    
    def clear_cache(self):
        """清除数据缓存"""
        self._index_weight = {}


@dataclass
class ExposureResult:
    """风险暴露结果"""
    long_exposure: Dict  # 多头暴露
    short_exposure: Dict  # 空头暴露
    net_exposure: Dict  # 净暴露
    gross_exposure: Dict  # 总暴露（绝对值之和）


class RiskFactor(ABC):
    """风险因子抽象基类"""
    
    def __init__(self, name: str, factor_data: Optional[pd.Series] = None):
        """
        Args:
            name: 因子名称
            factor_data: 因子数据Series（可选），如果提供则直接使用，否则需要通过data_loader加载
        """
        self.name = name
        self._factor_data = factor_data
    
    @abstractmethod
    def calculate_exposure(self, weights: pd.Series) -> Dict:
        """
        计算组合的因子暴露
        Args:
            weights: 权重Series，index为股票代码（可以为正负，表示多空）
        Returns:
            暴露字典
        """
        pass
    
    def get_factor_data(self, codes: Optional[List[str]] = None) -> pd.Series:
        """
        获取因子数据
        
        Args:
            codes: 股票代码列表，如果为None则返回所有数据
            
        Returns:
            因子数据Series
        """
        if self._factor_data is None:
            raise ValueError(f"因子 {self.name} 的数据未初始化，请先设置factor_data或使用data_loader")
        
        if codes is None:
            return self._factor_data
        
        # 返回请求的代码对应的数据（只包含存在的代码）
        available_codes = [c for c in codes if c in self._factor_data.index]
        if len(available_codes) < len(codes):
            missing_codes = [c for c in codes if c not in self._factor_data.index]
            if len(missing_codes) <= 10:
                print(f'警告: 以下代码缺少 {self.name} 数据: {missing_codes}')
            else:
                print(f'警告: {len(missing_codes)} 个代码缺少 {self.name} 数据，前10个: {missing_codes[:10]}')
        return self._factor_data.loc[available_codes] if available_codes else pd.Series(dtype=float)
    
    def set_factor_data(self, factor_data: pd.Series):
        """设置因子数据"""
        self._factor_data = factor_data
    
    def build_exposure_matrix(self, pool: List[str]) -> Tuple[np.ndarray, Optional[List[str]]]:
        """
        构建暴露矩阵，用于优化器约束
        
        Args:
            pool: 股票代码列表
            
        Returns:
            (暴露矩阵, 暴露项列表)
            对于标量因子，返回 (向量, None)
            对于分类因子（如行业），返回 (矩阵, 类别列表)
        """
        # 默认实现：子类可以重写
        factor_data = self.get_factor_data(pool)
        n = len(pool)
        exposure_vector = np.zeros(n)
        for i, code in enumerate(pool):
            if code in factor_data.index:
                exposure_vector[i] = factor_data.loc[code]
        return exposure_vector, None


class IndustryFactor(RiskFactor):
    """行业因子（申万一级）"""
    
    def __init__(self, factor_data: Optional[pd.Series] = None):
        """
        Args:
            factor_data: 行业数据Series，index为股票代码，values为行业名称
                        如果为None，需要通过set_factor_data设置或使用data_loader
        """
        super().__init__('industry', factor_data)
    
    @classmethod
    def from_data_loader(cls, data_loader: BarraDataLoader) -> 'IndustryFactor':
        """
        从DataLoader创建因子实例
        
        Args:
            data_loader: BarraDataLoader实例
            
        Returns:
            IndustryFactor实例
        """
        industry_data = data_loader.load_industry_data()
        return cls(factor_data=industry_data)
    
    def calculate_exposure(self, weights: pd.Series) -> Dict:
        """计算行业暴露"""
        industry_mapping = self.get_factor_data(weights.index.tolist())
        
        # 合并权重和行业
        exposure_df = pd.merge(
            weights.to_frame('weight'),
            industry_mapping.to_frame('industry'),
            left_index=True,
            right_index=True,
            how='inner'
        )
        
        # 按行业汇总权重
        exposure = exposure_df.groupby('industry')['weight'].sum().to_dict()
        return exposure
    
    def build_exposure_matrix(self, pool: List[str]) -> Tuple[np.ndarray, Optional[List[str]]]:
        """构建行业暴露矩阵"""
        factor_data = self.get_factor_data(pool)
        industry_set = set(factor_data.values)
        industry_list = sorted(list(industry_set))
        
        n = len(pool)
        ind_matrix = np.zeros((len(industry_list), n))
        for i, code in enumerate(pool):
            if code in factor_data.index:
                industry = factor_data.loc[code]
                if industry in industry_list:
                    j = industry_list.index(industry)
                    ind_matrix[j, i] = 1
        
        return ind_matrix, industry_list


class LogMarketCapFactor(RiskFactor):
    """对数市值因子"""
    
    def __init__(self, factor_data: Optional[pd.Series] = None):
        """
        Args:
            factor_data: 对数市值数据Series，index为股票代码，values为对数市值
                        如果为None，需要通过set_factor_data设置或使用data_loader
        """
        super().__init__('log_market_cap', factor_data)
    
    @classmethod
    def from_data_loader(cls, data_loader: BarraDataLoader) -> 'LogMarketCapFactor':
        """
        从DataLoader创建因子实例
        
        Args:
            data_loader: BarraDataLoader实例
            
        Returns:
            LogMarketCapFactor实例
        """
        log_market_cap_data = data_loader.load_market_cap_data(use_log=True)
        return cls(factor_data=log_market_cap_data)
    
    def calculate_exposure(self, weights: pd.Series) -> Dict:
        """计算对数市值暴露"""
        log_market_caps = self.get_factor_data(weights.index.tolist())
        
        # 只计算有数据的股票
        valid_codes = log_market_caps.index.intersection(weights.index)
        if len(valid_codes) < len(weights.index):
            weights = weights.loc[valid_codes]
        
        # 加权平均
        exposure = (log_market_caps.loc[valid_codes] * weights).sum()
        return {'log_market_cap': exposure}
    
    def build_exposure_matrix(self, pool: List[str]) -> Tuple[np.ndarray, Optional[List[str]]]:
        """构建对数市值暴露向量"""
        return super().build_exposure_matrix(pool)


class PortfolioExposureCalculator:
    """组合风险暴露计算器"""
    
    def __init__(self, factors: Optional[List[RiskFactor]] = None, data_loader: Optional[BarraDataLoader] = None):
        """
        Args:
            factors: 风险因子列表，如果为None则使用默认因子（需要提供data_loader）
            data_loader: BarraDataLoader实例，用于创建默认因子
        """
        if factors is None:
            if data_loader is None:
                raise ValueError("factors和data_loader不能同时为None")
            factors = [
                IndustryFactor.from_data_loader(data_loader),
                LogMarketCapFactor.from_data_loader(data_loader)
            ]
        
        self.factors = {f.name: f for f in factors}
    
    def add_factor(self, factor: RiskFactor):
        """添加风险因子"""
        self.factors[factor.name] = factor
    
    def calculate_long_short_exposure(
        self,
        long_weights: pd.Series,
        short_weights: Optional[pd.Series] = None
    ) -> Dict[str, ExposureResult]:
        """
        计算多空头寸的风险暴露
        
        Args:
            long_weights: 多头权重Series，index为股票代码
            short_weights: 空头权重Series，index为股票代码（可选）
            
        Returns:
            每个因子的暴露结果字典
        """
        if short_weights is None:
            short_weights = pd.Series(dtype=float)
        
        # 获取所有涉及的股票代码
        all_codes = set(long_weights.index) | set(short_weights.index)
        
        results = {}
        
        for factor_name, factor in self.factors.items():
            # 计算多头和空头暴露
            long_exposure = factor.calculate_exposure(long_weights) if len(long_weights) > 0 else {}
            short_exposure = factor.calculate_exposure(short_weights) if len(short_weights) > 0 else {}
            
            # 计算净暴露和总暴露
            all_keys = set(long_exposure.keys()) | set(short_exposure.keys())
            net_exposure = {}
            gross_exposure = {}
            
            for key in all_keys:
                long_val = long_exposure.get(key, 0)
                short_val = short_exposure.get(key, 0)
                net_exposure[key] = long_val - short_val  # 净暴露 = 多头 - 空头
                gross_exposure[key] = abs(long_val) + abs(short_val)  # 总暴露 = |多头| + |空头|
            
            results[factor_name] = ExposureResult(
                long_exposure=long_exposure,
                short_exposure=short_exposure,
                net_exposure=net_exposure,
                gross_exposure=gross_exposure
            )
        
        return results
    
    def calculate_net_exposure(self, weights: pd.Series) -> Dict[str, Dict]:
        """
        计算净暴露（允许权重为正负）
        
        Args:
            weights: 权重Series，可以为正（多头）或负（空头）
            
        Returns:
            每个因子的净暴露字典
        """
        long_weights = weights[weights > 0].copy()
        short_weights = -weights[weights < 0].copy()
        
        exposure_results = self.calculate_long_short_exposure(long_weights, short_weights)
        
        return {name: result.net_exposure for name, result in exposure_results.items()}
    
    def calculate_aggregate_exposure(
        self,
        portfolios: Dict[str, pd.Series]
    ) -> Dict[str, ExposureResult]:
        """
        计算多个组合的汇总暴露
        
        Args:
            portfolios: 组合字典，{组合名: 权重Series}
            
        Returns:
            每个因子的汇总暴露结果
        """
        # 合并所有组合的权重
        all_codes = set().union(*(w.index for w in portfolios.values()))
        combined_weights = pd.Series(0.0, index=list(all_codes))
        for weights in portfolios.values():
            combined_weights = combined_weights.add(weights, fill_value=0)
        
        # 按多空拆分并计算暴露
        long_weights = combined_weights[combined_weights > 0]
        short_weights = -combined_weights[combined_weights < 0]
        
        return self.calculate_long_short_exposure(long_weights, short_weights)


class PortfolioOptimizer:
    """投资组合优化器"""
    
    def __init__(self, exposure_calculator: PortfolioExposureCalculator):
        """
        Args:
            exposure_calculator: 风险暴露计算器
        """
        self.exposure_calculator = exposure_calculator
        self.factors = exposure_calculator.factors
    
    def optimize_with_exposure_constraints(
        self,
        pool: List[str],
        target_weights: Optional[pd.Series] = None,
        exposure_constraints: Optional[Dict[str, Union[float, Tuple[float, float]]]] = None,
        benchmark_exposure: Optional[Dict[str, Dict]] = None,
        objective: str = 'minimize_tracking_error',
        min_weight: float = 0.0,
        max_weight: float = 1.0,
        long_only: bool = True,
        leverage_constraint: Optional[float] = None
    ) -> Tuple[pd.Series, Dict]:
        """
        在暴露约束下优化投资组合
        
        Args:
            pool: 选股池
            target_weights: 目标权重（用于跟踪误差最小化）
            exposure_constraints: 暴露约束，{因子名: (下界, 上界)} 或 {因子名: 绝对值上限}
            benchmark_exposure: 基准暴露，{因子名: {暴露项: 值}}
            objective: 优化目标
                - 'minimize_tracking_error': 最小化跟踪误差（需要target_weights）
                - 'minimize_variance': 最小化组合方差（需要协方差矩阵，暂未实现）
                - 'maximize_expected_return': 最大化预期收益（需要预期收益，暂未实现）
            min_weight: 最小权重
            max_weight: 最大权重
            long_only: 是否只允许做多
            leverage_constraint: 杠杆约束（总权重绝对值之和的上限）
            
        Returns:
            优化后的权重Series和优化结果字典
        """
        n = len(pool)
        X = cp.Variable(n)
        
        # 构建约束
        constraints = self._build_basic_constraints(
            X, long_only, min_weight, max_weight, leverage_constraint
        )
        constraints.extend(
            self._build_exposure_constraints(
                X, pool, exposure_constraints, benchmark_exposure
            )
        )
        
        # 构建目标函数
        objective_func = self._build_objective(X, pool, target_weights, objective)
        
        # 求解优化问题
        prob = self._solve_optimization(objective_func, constraints)
        
        # 构建结果
        optimized_weights, results = self._build_results(
            X, prob, pool, target_weights
        )
        
        return optimized_weights, results
    
    def _build_basic_constraints(
        self,
        X: cp.Variable,
        long_only: bool,
        min_weight: float,
        max_weight: float,
        leverage_constraint: Optional[float]
    ) -> List:
        """
        构建基本约束（权重范围、权重和等）
        
        Args:
            X: 优化变量
            long_only: 是否只允许做多
            min_weight: 最小权重
            max_weight: 最大权重
            leverage_constraint: 杠杆约束
            
        Returns:
            约束列表
        """
        constraints = []
        
        if long_only:
            constraints.append(X >= min_weight)
            constraints.append(X <= max_weight)
            constraints.append(cp.sum(X) == 1.0)
        else:
            constraints.append(X >= -max_weight)  # 允许做空
            constraints.append(X <= max_weight)
            if leverage_constraint is not None:
                constraints.append(cp.sum(cp.abs(X)) <= leverage_constraint)
            else:
                constraints.append(cp.sum(X) == 1.0)  # 默认净敞口为1
        
        return constraints
    
    def _build_exposure_constraints(
        self,
        X: cp.Variable,
        pool: List[str],
        exposure_constraints: Optional[Dict[str, Union[float, Tuple[float, float]]]],
        benchmark_exposure: Optional[Dict[str, Dict]]
    ) -> List:
        """
        构建暴露约束
        
        Args:
            X: 优化变量
            pool: 选股池
            exposure_constraints: 暴露约束字典
            benchmark_exposure: 基准暴露字典
            
        Returns:
            约束列表
        """
        if not exposure_constraints:
            return []
        
        constraints = []
        
        for factor_name, factor in self.factors.items():
            if factor_name not in exposure_constraints:
                continue
            
            constraint_value = exposure_constraints[factor_name]
            exposure_matrix, exposure_items = factor.build_exposure_matrix(pool)
            
            # 计算组合暴露
            if exposure_matrix.ndim == 1:
                # 标量因子（如对数市值）
                portfolio_exposure = exposure_matrix @ X
                constraints.extend(
                    self._apply_exposure_constraint(
                        portfolio_exposure, constraint_value, factor_name,
                        benchmark_exposure, None, is_vector=False
                    )
                )
            else:
                # 向量因子（如行业）
                portfolio_exposure = exposure_matrix @ X
                constraints.extend(
                    self._apply_exposure_constraint(
                        portfolio_exposure, constraint_value, factor_name,
                        benchmark_exposure, exposure_items, is_vector=True
                    )
                )
        
        return constraints
    
    def _apply_exposure_constraint(
        self,
        portfolio_exposure: cp.Expression,
        constraint_value: Union[float, Tuple[float, float]],
        factor_name: str,
        benchmark_exposure: Optional[Dict[str, Dict]],
        exposure_items: Optional[List[str]] = None,
        is_vector: bool = False
    ) -> List:
        """
        应用暴露约束（通用方法）
        
        Args:
            portfolio_exposure: 组合暴露表达式
            constraint_value: 约束值
            factor_name: 因子名称
            benchmark_exposure: 基准暴露
            exposure_items: 暴露项列表（用于向量因子，如行业列表）
            is_vector: 是否为向量因子
            
        Returns:
            约束列表
        """
        constraints = []
        
        # 获取基准暴露
        bench_exposure = None
        if benchmark_exposure and factor_name in benchmark_exposure:
            if is_vector and exposure_items:
                # 向量因子：基准暴露是字典
                bench_exposure = np.array([
                    benchmark_exposure[factor_name].get(item, 0) 
                    for item in exposure_items
                ])
            else:
                # 标量因子：基准暴露是单个值
                bench_exposure = benchmark_exposure[factor_name].get(factor_name, 0)
        
        if isinstance(constraint_value, tuple):
            # 上下界约束
            lower, upper = constraint_value
            if bench_exposure is not None:
                constraints.append(portfolio_exposure >= bench_exposure + lower)
                constraints.append(portfolio_exposure <= bench_exposure + upper)
            else:
                constraints.append(portfolio_exposure >= lower)
                constraints.append(portfolio_exposure <= upper)
        else:
            # 绝对值约束
            if bench_exposure is not None:
                deviation = cp.abs(portfolio_exposure - bench_exposure)
                if is_vector:
                    constraints.append(cp.sum(deviation) <= constraint_value)
                else:
                    # 对于标量，支持相对偏离度
                    if abs(bench_exposure) > 1e-6:
                        constraints.append(deviation <= abs(bench_exposure) * constraint_value)
                    else:
                        constraints.append(deviation <= constraint_value)
            else:
                if is_vector:
                    constraints.append(cp.sum(cp.abs(portfolio_exposure)) <= constraint_value)
                else:
                    constraints.append(cp.abs(portfolio_exposure) <= constraint_value)
        
        return constraints
    
    def _build_objective(
        self,
        X: cp.Variable,
        pool: List[str],
        target_weights: Optional[pd.Series],
        objective: str
    ) -> cp.Minimize:
        """
        构建目标函数
        
        Args:
            X: 优化变量
            pool: 选股池
            target_weights: 目标权重
            objective: 目标函数类型
            
        Returns:
            目标函数表达式
        """
        if objective == 'minimize_tracking_error':
            if target_weights is None:
                raise ValueError("target_weights required for minimize_tracking_error objective")
            
            # 构建目标权重数组
            target_array = np.array([target_weights.get(code, 0.0) for code in pool])
            
            return cp.Minimize(cp.sum(cp.abs(X - target_array)))
        else:
            raise ValueError(f"Unknown objective: {objective}")
    
    def _solve_optimization(
        self,
        objective_func: cp.Minimize,
        constraints: List
    ) -> cp.Problem:
        """
        求解优化问题
        
        Args:
            objective_func: 目标函数
            constraints: 约束列表
            
        Returns:
            优化问题对象（已求解）
        """
        prob = cp.Problem(objective_func, constraints)
        prob.solve(solver=cp.ECOS)
        
        if prob.status != 'optimal':
            raise RuntimeError(f"Optimization failed with status: {prob.status}")
        
        return prob
    
    def _build_results(
        self,
        X: cp.Variable,
        prob: cp.Problem,
        pool: List[str],
        target_weights: Optional[pd.Series]
    ) -> Tuple[pd.Series, Dict]:
        """
        构建优化结果
        
        Args:
            X: 优化变量
            prob: 优化问题对象（已求解）
            pool: 选股池
            target_weights: 目标权重
            
        Returns:
            (优化后的权重Series, 结果字典)
        """
        # 构建权重Series
        optimized_weights = pd.Series(X.value, index=pool)
        optimized_weights = optimized_weights[abs(optimized_weights) > 1e-6]  # 去掉接近0的权重
        
        # 计算实际暴露
        actual_exposures = self.exposure_calculator.calculate_net_exposure(optimized_weights)
        
        # 计算跟踪误差
        tracking_error = None
        if target_weights is not None:
            common_codes = set(optimized_weights.index) & set(target_weights.index)
            if common_codes:
                tracking_error = sum(abs(optimized_weights.loc[list(common_codes)] - 
                                       target_weights.loc[list(common_codes)]))
        
        results = {
            'status': prob.status,
            'value': prob.value,
            'tracking_error': tracking_error,
            'exposures': actual_exposures
        }
        
        return optimized_weights, results


class BarraRiskModel:
    """Barra风险模型主类"""
    
    def __init__(
        self,
        date: Optional[str] = None,
        data_loader: Optional[BarraDataLoader] = None,
        factors: Optional[List[RiskFactor]] = None,
        industry_data: Optional[pd.Series] = None,
        market_cap_data: Optional[pd.Series] = None
    ):
        """
        Args:
            date: 计算日期，如果为None则使用上一个交易日（当data_loader和factors都为None时使用）
            data_loader: BarraDataLoader实例，用于加载数据
            factors: 风险因子列表，如果为None则使用默认因子
            industry_data: 行业数据Series（可选），直接传入数据而不使用data_loader
            market_cap_data: 市值数据Series（可选），直接传入数据而不使用data_loader
        """
        # 确定日期
        if date is None:
            date = data_loader.date if data_loader else (datetime.datetime.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        self.date = date
        
        # 创建data_loader（如果需要）
        if data_loader is None and factors is None:
            data_loader = BarraDataLoader(date)
        self.data_loader = data_loader
        
        # 创建因子
        if factors is None:
            factors = self._create_default_factors(industry_data, market_cap_data)
        
        self.exposure_calculator = PortfolioExposureCalculator(factors=factors, data_loader=data_loader)
        self.optimizer = PortfolioOptimizer(self.exposure_calculator)
    
    def _create_default_factors(self, industry_data: Optional[pd.Series], market_cap_data: Optional[pd.Series]) -> List[RiskFactor]:
        """创建默认因子"""
        factors = []
        if industry_data is not None:
            factors.append(IndustryFactor(factor_data=industry_data))
        elif self.data_loader is not None:
            factors.append(IndustryFactor.from_data_loader(self.data_loader))
        
        if market_cap_data is not None:
            factors.append(LogMarketCapFactor(factor_data=market_cap_data))
        elif self.data_loader is not None:
            factors.append(LogMarketCapFactor.from_data_loader(self.data_loader))
        
        if not factors:
            raise ValueError("必须提供data_loader、factors或直接数据")
        
        return factors
    
    def calculate_exposure(
        self,
        long_weights: pd.Series,
        short_weights: Optional[pd.Series] = None
    ) -> Dict[str, ExposureResult]:
        """
        计算组合风险暴露
        
        Args:
            long_weights: 多头权重
            short_weights: 空头权重（可选）
            
        Returns:
            风险暴露结果
        """
        return self.exposure_calculator.calculate_long_short_exposure(long_weights, short_weights)
    
    def calculate_net_exposure(self, weights: pd.Series) -> Dict[str, Dict]:
        """
        计算净暴露
        
        Args:
            weights: 权重Series（可为正负）
            
        Returns:
            净暴露字典
        """
        return self.exposure_calculator.calculate_net_exposure(weights)
    
    def optimize_portfolio(
        self,
        pool: List[str],
        target_weights: Optional[pd.Series] = None,
        exposure_constraints: Optional[Dict[str, Union[float, Tuple[float, float]]]] = None,
        benchmark_exposure: Optional[Dict[str, Dict]] = None,
        **optimizer_kwargs
    ) -> Tuple[pd.Series, Dict]:
        """
        优化投资组合
        
        Args:
            pool: 选股池
            target_weights: 目标权重
            exposure_constraints: 暴露约束
            benchmark_exposure: 基准暴露
            **optimizer_kwargs: 其他优化器参数
            
        Returns:
            优化后的权重和结果
        """
        return self.optimizer.optimize_with_exposure_constraints(
            pool=pool,
            target_weights=target_weights,
            exposure_constraints=exposure_constraints,
            benchmark_exposure=benchmark_exposure,
            **optimizer_kwargs
        )
    
    def add_factor(self, factor: RiskFactor):
        """添加自定义风险因子"""
        self.exposure_calculator.add_factor(factor)
        self.optimizer.factors = self.exposure_calculator.factors
    
    def set_benchmark(self, benchmark_weights: pd.Series) -> Dict[str, Dict]:
        """
        设置基准并计算基准暴露
        
        Args:
            benchmark_weights: 基准权重
            
        Returns:
            基准暴露字典
        """
        self.benchmark_weights = benchmark_weights
        self.benchmark_exposure = self.exposure_calculator.calculate_net_exposure(benchmark_weights)
        return self.benchmark_exposure


if __name__ == '__main__':
    # 示例用法
    date = '2025-01-02'
    
    # 方式1: 使用DataLoader（推荐）
    data_loader = BarraDataLoader(date=date)
    data_loader.load_all()  # 批量加载数据

    print(data_loader.load_market_cap_data())
    
    # model = BarraRiskModel(date=date, data_loader=data_loader)
    
    # # 方式2: 直接传入数据
    # # industry_data = data_loader.load_industry_data()
    # # market_cap_data = data_loader.load_market_cap_data()
    # # model = BarraRiskModel(date=date, industry_data=industry_data, market_cap_data=market_cap_data)
    
    # # 设置基准
    # benchmark_weights = ddb(db='percy').load_table_by_sql(
    #     'dfs://jq_price', 'index_components',
    #     f'select * from index_components where date=2024.11.12, index_code="000300.XSHG"'
    # )
    # benchmark_weights = benchmark_weights.set_index('code')['weight']
    # benchmark_weights = benchmark_weights / benchmark_weights.sum()
    
    # benchmark_exposure = model.set_benchmark(benchmark_weights)
    # print("基准暴露:")
    # print(benchmark_exposure)
    
    # # 计算组合暴露
    # long_weights = benchmark_weights.head(50)  # 假设只持有前50只
    # long_weights = long_weights / long_weights.sum()
    
    # exposure = model.calculate_exposure(long_weights)
    # print("\n组合暴露:")
    # for factor_name, result in exposure.items():
    #     print(f"\n{factor_name}:")
    #     print(f"  多头暴露: {result.long_exposure}")
    #     print(f"  净暴露: {result.net_exposure}")
    
    # # 优化组合
    # pool = benchmark_weights.index.tolist()[:100]  # 选股池
    
    # optimized_weights, results = model.optimize_portfolio(
    #     pool=pool,
    #     target_weights=benchmark_weights.loc[pool],
    #     exposure_constraints={
    #         'industry': 0.01,  # 行业偏离度不超过1%
    #         'log_market_cap': 0.01  # 对数市值偏离度不超过1%
    #     },
    #     benchmark_exposure=benchmark_exposure
    # )
    
    # print("\n优化结果:")
    # print(f"跟踪误差: {results['tracking_error']}")
    # print(f"优化后暴露: {results['exposures']}")

