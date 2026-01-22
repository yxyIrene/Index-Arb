
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from Framework.pythonTool import ddb
from Framework.tool import bbg_to_jq


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
        self._size_data = None
        self._log_size_data = None
    
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
    
    def load_log_size_data(self) -> pd.Series:
        """
        加载对数市值数据
        Returns:
            size_data: Series，index为股票代码，values为市值（或对数市值）
        """
        if self._log_size_data is None:
            size = self.load_size_data()
            self._log_size_data = np.log(size)
        return self._log_size_data
    
    def load_size_data(self) -> pd.Series:
        if self._size_data is None:
            size = self.db.load_table_by_sql(
                'dfs://jq_fundamental', 'valuation',
                f'select code, market_cap from valuation where date={self.date_str}'
            )
            size = size.set_index('code')['market_cap']
            self._size_data = size
        
        return self._size_data
      
    def load_all(self):
        """批量加载所有数据"""
        self.load_industry_data()
        self.load_size_data()
        self.load_log_size_data()
    

    def clear_cache(self):
        """清除数据缓存"""
        self._industry_data = None
        self._size_data = None
        self._log_size_data = None


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


class PriceDataLoader:
    """
    个股及指数行情加载器
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
        self._price_mapping = {}
        

    def _load_stock_price(self)  -> pd.Series:  
        """
        加载股票收盘价数据
        """
        data = self.db.load_table_by_sql(
            'dfs://jq_price', 'daily',
            f'select code, close from daily where date={self.date_str}'
        )
        self._price_mapping.update(data.set_index('code')['close'])
        return
    
    def _load_index_price(self)  -> pd.Series:
        """
        加载指数收盘价数据
        """

        data = self.db.load_table_by_sql(
            'dfs://jq_price', 'index_daily',
            f'select code, close from index_daily where date={self.date_str}'
        )
        self._price_mapping.update(data.set_index('code')['close'])
        return

    def load_price(self) -> pd.Series:
        """加载股票及指数价格数据"""

        if self._price_mapping == {}:
            self._load_index_price()
            self._load_stock_price()

        return self._price_mapping
    

class PortfolioLoader:
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
        self._portfolio_position = {}

        underlying_info = self.db.load_table_by_sql('dfs://bctmate_info', 'underlying_info', 'select BBGcode, 挂钩标的, 交易所, 市场, 标的类型 from underlying_info')
        self._underlying_info_mapping = underlying_info.set_index('BBGcode').to_dict('dict')
        daily_close = self.db.load_table_by_sql('dfs://bctmate_info', 'market_price', f'select 标的代码, close, 交易所代码 from market_price where 估值日期={self.date_str}')
        self._underlying_close_mapping = daily_close.set_index('标的代码')['close'].to_dict()
        self._exchange_mapping = daily_close.set_index('标的代码')['交易所代码'].to_dict()

    def load_portfolio_from_bctmate(self, main_contracts: List[str], portfolio_name: str, replace_future=True) -> pd.DataFrame:  
        """
        加载BCTMate组合持仓数据
        """
        
        if portfolio_name not in self._portfolio_position.keys():
            position = ddb('bctmate').load_table_by_sql('dfs://bctmate_report', 'trade_detail', f'select 标的代码, 分红调整剩余数量, 客户头寸方向, 标的乘数, 标的类型 from trade_detail where 估值日期=2025.12.31, 主合约编号 in {main_contracts}')
            position = position.loc[position['客户头寸方向'].isin(['多头', '空头'])]
            position['side'] = position['客户头寸方向'].map({'多头': 1, '空头': -1})
            position['quantity'] = position['分红调整剩余数量'] * position['side'] * position['标的乘数']

            position['挂钩标的'] = position['标的代码'].map(self._underlying_info_mapping['挂钩标的'])  
            position['exchange_code'] = position['标的代码'].map(self._exchange_mapping)
            if replace_future:
                position['bbg_code'] = position['标的代码'].mask(position['标的类型'] == '股指期货', position['挂钩标的'])
                position['asset_type'] = position['标的类型'].mask(position['标的类型'] == '股指期货', '指数')
            else:
                position['bbg_code'] = position['标的代码']
                position['asset_type'] = position['标的类型']

            position['asset_type'] = position['asset_type'].map({'股票':'stock', '指数':'index', '股指期货':'future'})
            position['close'] = position['挂钩标的'].map(self._underlying_close_mapping)
            
            position = position.groupby(['bbg_code', 'asset_type'], as_index=False).agg({'quantity':'sum', 'close':'first', 'exchange_code':'first'})
            position['market_value'] = position['quantity'] * position['close']
            

            if len(position.loc[position['market_value'].isna()]) >0:
                print(f'警告: 组合 {portfolio_name} 中存在标的收盘价缺失，可能影响持仓市值计算')
                print(position.loc[position['market_value'].isna()])     

            position['code'] = position.apply(lambda row: bbg_to_jq(row['bbg_code'], row['asset_type'], row['exchange_code']), axis=1)
            self._portfolio_position[portfolio_name] = position[['code', 'quantity', 'close', 'market_value', 'asset_type', 'exchange_code']]


        return self._portfolio_position[portfolio_name]
