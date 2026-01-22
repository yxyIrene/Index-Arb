
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from Framework.pythonTool import ddb
from Framework.dataTool import BarraDataLoader


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

class LogSizeFactor(RiskFactor):
    """对数市值因子"""
    
    def __init__(self, factor_data: Optional[pd.Series] = None):
        """
        Args:
            factor_data: 对数市值数据Series，index为股票代码，values为对数市值
                        如果为None，需要通过set_factor_data设置或使用data_loader
        """
        super().__init__('log_size', factor_data)
    
    @classmethod
    def from_data_loader(cls, data_loader: BarraDataLoader) -> 'LogSizeFactor':
        """
        从DataLoader创建因子实例
        
        Args:
            data_loader: BarraDataLoader实例
            
        Returns:
            LogMarketCapFactor实例
        """
        log_size_data = data_loader.load_log_size_data()
        return cls(factor_data=log_size_data)
    
    def calculate_exposure(self, weights: pd.Series) -> Dict:
        """计算对数市值暴露"""
        log_market_caps = self.get_factor_data(weights.index.tolist())
        log_market_caps = (log_market_caps - log_market_caps.mean()) / log_market_caps.std() # 标准化
        
        # 只计算有数据的股票
        valid_codes = log_market_caps.index.intersection(weights.index)
        if len(valid_codes) < len(weights.index):
            weights = weights.loc[valid_codes]
        
        # 加权平均
        exposure = (log_market_caps.loc[valid_codes] * weights).sum()
        return {'log_size': exposure}
    
    def build_exposure_matrix(self, pool: List[str]) -> Tuple[np.ndarray, Optional[List[str]]]:
        """构建对数市值暴露向量"""
        return super().build_exposure_matrix(pool)
    
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