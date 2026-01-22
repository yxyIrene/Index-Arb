import pandas as pd
import numpy as np
from Framework.pythonTool import *

def notional_breakdown(notional, weights, prices, slot=100):
    """
    将名义本金额按照weights进行break down, 并根据标的prices计算成分数量
    Args:
        notional: 名义本金额 float
        weights: 指数权重 pd.Series
        prices: 股票价格 pd.Series
        slot: 标的每手最低交易数量 int

    Returns:
        component_quantity_slot: slot调整后成分数量 pd.Series
        component_notional_slot: slot调整后成分名本 pd.Series
        notional_error: 整体notional偏差
        total_abs_error: 成分绝对误差汇总
    """
    component_notional = notional * weights
    prices = prices.loc[component_notional.index]
    component_quantity = component_notional / prices
    component_quantity_slot = round(component_quantity / slot) * slot
    component_notional_slot = component_quantity_slot * prices
    notional_error = abs(component_notional_slot.sum() - notional)/notional
    total_abs_error = abs(component_notional_slot - component_notional).sum()/notional

    return component_quantity_slot, component_notional_slot, notional_error, total_abs_error

def select_index_component_by_condition(index, date, min_price=None, min_avg_amount=None, restricted_list=[], st_list=[], paused_list=[]):
    """
    根据要求, 从指数成分股中进行选股
    Args:
        index: 指数代码 string
        date: 日期 string
        min_price: 最低股价要求 float
        min_avg_amount: 最低日均成交额(滚动天数, 最低成交额) tuple(int, float)
        restricted_list: 限制清单 list of string
        st_list: st清单 list of string
        paused_list: 停牌清单 list of string

    Returns:
        index_component: 筛选后成分股权重(未标准化) pd.Series
    """
    date_str = pd.to_datetime(date).strftime("%Y.%m.%d")
    index_component = ddb(db='bctmate').load_table_by_sql('dfs://jq_price', 'index_components',
                                              f'select * from index_components where date={date_str}, index_code="{index}"')
    index_component = index_component.set_index('code')
    prices = ddb(db='bctmate').load_table_by_sql('dfs://jq_price', 'daily', f'select * from daily where date={date_str}')
    prices = prices[['code', 'close']].set_index('code')['close']
    # 合并代码, 剔除没有行情的标的(退市）
    codes = [code for code in index_component.index if code in prices.index]
    index_component = index_component.loc[codes]

    if min_price is None:
        pass
    else:
        prices = prices.loc[codes]
        index_component = index_component.loc[prices > min_price]

    if min_avg_amount is None:
        pass
    else:
        try:
            rolling_days = min_avg_amount[0]
            min_amount = min_avg_amount[1]
        except:
            print('min_avg_amount should be a tuple like (rolling_days, min_amount)')
            return index_component

        start_date = get_previous_tradedate(date, rolling_days)
        start_date_str = start_date.strftime("%Y.%m.%d")
        prices_period = ddb(db='bctmate').load_table_by_sql('dfs://jq_price', 'daily',
                                                f'select * from daily where date<={date_str}, date>={start_date_str}')
        rolling_avg_amount = prices_period[['code', 'money']].groupby('code').mean()['money']
        rolling_avg_amount = rolling_avg_amount.loc[codes]
        index_component = index_component.loc[rolling_avg_amount > min_amount]

    codes = [code for code in index_component.index if not(code in restricted_list)]
    codes = [code for code in codes if not(code in st_list)]
    codes = [code for code in codes if not(code in paused_list)]

    index_component = index_component.loc[codes]
    index_component = index_component['weight']
    return index_component

def calculate_weight(basket, date):
    """
    basket为pd.Series
    """
    date_str = pd.to_datetime(date).strftime("%Y.%m.%d")
    close_price = ddb(db='bctmate').load_table_by_sql('dfs://jq_price', 'daily', f'select code, close from daily where date={date_str}')
    close_price_mapping = close_price.set_index('code')['close']
    basket_df = basket.to_frame()


    pass
if __name__ == '__main__':
    stocks = select_index_component_by_condition('000852.XSHG', '2024-08-15', 1, (10,10000000), ['600836.XSHE'])
    print(stocks)

