
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from Framework.riskFactor import RiskFactor
from Framework.dataTool import PriceDataLoader, IndexDataLoader

@dataclass
class ExposureResult:
    """风险暴露结果"""
    long_exposure: Dict  # 多头暴露
    short_exposure: Dict  # 空头暴露
    net_exposure: Dict  # 净暴露
    gross_exposure: Dict  # 总暴露（绝对值之和）
    deviation_ratio: Dict  # 偏离比例
    total_abs_deviation: float



class PortfolioExposureCalculator:
    """组合风险暴露计算器"""
    
    def __init__(self, factors: Optional[List[RiskFactor]] = [], price_data_loader: PriceDataLoader = None, index_data_loader: IndexDataLoader=None, date=None):
        """
        Args:
            factors: 风险因子列表
        """
        if factors is None:
            pass
        else: 
            self.factors = {f.name: f for f in factors}

        if price_data_loader is None:
            if date is None:
                print(f'[WARNING] 未提供价格数据加载器，且日期为空')
                raise Exception('必须提供价格数据加载器或日期')
            
            else:
                self.price_data_loader = PriceDataLoader(date)

        if index_data_loader is None:
            if date is None:
                print(f'[WARNING] 未提供指数数据加载器，且日期为空')
                raise Exception('必须提供指数数据加载器或日期')
            
            else:
                self.index_data_loader = IndexDataLoader(date)

        self.portfolio_exposure = {}
    
    def add_factor(self, factor: RiskFactor):
        """添加风险因子"""
        self.factors[factor.name] = factor

    def calculate_market_exposure(self):
        # 计算市场暴露
        if self.long_portfolio is not None and self.short_portfolio is not None:
            long_market_exposure = round(self.long_portfolio['market_value'].sum(),2)
            short_market_exposure = round(self.short_portfolio['market_value'].sum(),2)
            net_market_exposure = round(long_market_exposure + short_market_exposure,2)
            deviation_ratio = abs(net_market_exposure/short_market_exposure) if short_market_exposure != 0 else np.nan

            self.portfolio_exposure['market'] = ExposureResult(
                long_exposure={'market': long_market_exposure},
                short_exposure={'market': short_market_exposure},
                net_exposure={'market': net_market_exposure},
                gross_exposure={'market': abs(long_market_exposure) + abs(short_market_exposure)},
                deviation_ratio={'market': deviation_ratio},
                total_abs_deviation = None
            )

            return self.portfolio_exposure['market']

    def _breakdown_portfolio(self, portfolio: pd.DataFrame) -> pd.DataFrame:
        """
        分解投资组合，计算市值和权重
        
        Args:
            portfolio: 投资组合DataFrame，包含'code', 'quantity', 'asset_type'列
            
        Returns:
            包含市值和权重的投资组合DataFrame
        """
        def break_down_underlying(code, market_value, asset_type):
            if asset_type == 'stock':
                return {code: market_value}
            elif asset_type == 'index':
                index_weights = self.index_data_loader.load_index_weight(code)
                breakdown = index_weights * market_value
                return breakdown.to_dict()

        # 将指数分解为个股权重
        breakdown_detail  = portfolio.apply(lambda row: break_down_underlying(row['code'], row['market_value'], row['asset_type']), axis=1).tolist()
        breakdown_portfolio = {}
        for detail in breakdown_detail:
            for code, market_value in detail.items():
                breakdown_portfolio[code] = breakdown_portfolio.get(code, 0) + market_value

        breakdown_portfolio = pd.Series(breakdown_portfolio, name='market_value').to_frame().reset_index().rename(columns={'index': 'code'})
        breakdown_portfolio['weight'] = breakdown_portfolio['market_value'] / breakdown_portfolio['market_value'].abs().sum()

        return breakdown_portfolio.set_index('code')['weight']

    def process_portfolio(self, portfolio: pd.DataFrame):

        # 储存投资组合信息
        portfolio = portfolio[['code', 'quantity', 'asset_type']].copy()
        portfolio['close'] = portfolio['code'].map(self.price_data_loader.load_price())

        if len(portfolio.loc[portfolio['close'].isna()]) > 0:
            print("以下股票缺少价格数据，无法计算市值及权重：")
            print(portfolio.loc[portfolio['close'].isna(), 'code'].tolist())
            portfolio = portfolio.loc[portfolio['close'].notna()]

        portfolio['market_value'] = portfolio['quantity'] * portfolio['close']
        self.long_portfolio = portfolio.loc[portfolio['market_value'] > 0].copy()
        self.short_portfolio = portfolio.loc[portfolio['market_value'] < 0].copy()
        self.calculate_market_exposure()

        self.long_weight_breakdown = self._breakdown_portfolio(self.long_portfolio)
        self.short_weight_breakdown = self._breakdown_portfolio(self.short_portfolio)

    def calculate_factor_exposure(self) -> Dict[str, ExposureResult]:
        """
        计算多空头寸的风险暴露
            
        Returns:
            每个因子的暴露结果字典
        """

        results = {}
        long_mv = abs(self.portfolio_exposure['market'].long_exposure['market'])
        short_mv = abs(self.portfolio_exposure['market'].short_exposure['market'])
        
        for factor_name, factor in self.factors.items():
            # 计算多头和空头暴露
            long_exposure = factor.calculate_exposure(self.long_weight_breakdown) if len(self.long_weight_breakdown) > 0 else {}
            short_exposure = factor.calculate_exposure(self.short_weight_breakdown) if len(self.short_weight_breakdown) > 0 else {}
            
            # 计算净暴露和总暴露
            all_keys = set(long_exposure.keys()) | set(short_exposure.keys())
            net_exposure = {}
            gross_exposure = {}
            deviation_ratio = {}
            
            for key in all_keys:
                long_val = long_exposure.get(key, 0)
                short_val = short_exposure.get(key, 0)
                net_exposure[key] = (long_val * long_mv + short_val * short_mv) / (long_mv + short_mv)  # 净暴露 = 多头 - 空头
                gross_exposure[key] = (abs(long_val * long_mv) + abs(short_val * short_mv)) / (long_mv + short_mv)  # 总暴露 = |多头| + |空头|\
                deviation_ratio[key] = (abs(long_val * long_mv) - abs(short_val * short_mv))/ abs(short_val * short_mv)
              
            total_abs_deviation = sum([abs(net_exposure[k]) for k in net_exposure.keys()])

            results[factor_name] = ExposureResult(
                long_exposure=long_exposure,
                short_exposure=short_exposure,
                net_exposure=net_exposure,
                gross_exposure=gross_exposure,
                deviation_ratio = deviation_ratio,
                total_abs_deviation = total_abs_deviation
            )
        self.portfolio_exposure.update(results)
        
        return results

    def calculate_stock_exposure(self) -> Dict[str, float]:
        """
        计算股票暴露
        """
        stock_exposure = {}
        for factor_name, factor in self.factors.items():
            stock_exposure[factor_name] = factor.calculate_exposure(self.long_weight_breakdown)
        return stock_exposure