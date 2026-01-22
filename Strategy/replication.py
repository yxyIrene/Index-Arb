import pandas as pd
import datetime
from Framework.indexTool import select_index_component_by_condition
from Framework.pythonTool import *
from Framework.riskModule import BARRA
from Framework.tool import *

import os 
current_path = os.path.dirname(os.path.abspath(__file__))
project_name = 'Index_Arbitrage'
project_path = current_path.split(project_name)[0] + project_name + '/'


def replicate_index(index, date=None, exclude_restricted=True, exclude_st=True, exclude_paused=True,
                    industry_deviation=0.01, log_market_cap_deviation=0.01,
                    min_avg_amount=(20, 20000000), min_price=None,
                    notional=10000000):
    """
    在成分股内复制指定指数
    Args:
        index: 指数代码 string
        date: 复制日期 string
        exclude_restricted: 是否排除限制名单 bool
        exclude_st: 是否排除st股票 bool
        exclude_paused:  是否排除停牌股票 bool
        industry_deviation: 行业偏离度限制 float
        log_market_cap_deviation: 对数市值偏离度限制 float
        min_avg_amount: 最低过去n日日均成交额 (n int, amount float)
        min_price: 最低股价 float

    Returns:
        weight: 组合权重 pd.Series
        portfolio_exposures: 组合偏离度 dict
    """
    if date is None:
        date = datetime.datetime.today().strftime('%Y-%m-%d')
        date_str = datetime.datetime.today().strftime('%Y.%m.%d')
    else:
        date_str = pd.to_datetime(date).strftime('%Y.%m.%d')

    if exclude_restricted:
        stock_config = pd.read_excel('./config/stock_config.xlsx')
        restricted_list = list(stock_config[['code', 'restricted']].set_index('restricted')['code'].loc[True])
    else:
        restricted_list = []

    if exclude_st:
        st_info = ddb(db='bctmate').load_table_by_sql('dfs://jq_price', 'st', f'select code, is_st from st where date={date_str}')
        st_list = list(st_info.set_index('is_st')['code'].loc[1])
    else:
        st_list = []

    if exclude_paused:
        paused_info = ddb(db='bctmate').load_table_by_sql('dfs://jq_price', 'daily', f'select code, paused from daily where date={date_str}')
        paused_list = list(paused_info.set_index('paused')['code'].loc[1])
    else:
        paused_list = []

    print(index, date, min_price, min_avg_amount)

    qualified_weight = select_index_component_by_condition(index=index, date=date,
                                                            min_price=min_price, min_avg_amount=min_avg_amount,
                                                            restricted_list=restricted_list,
                                                            st_list= st_list,
                                                            paused_list=paused_list)
    
    qualified_weight = qualified_weight/100
    

    # 根据名义本金, 剔除半手都买不到的标的
    date_dol = pd.to_datetime(date).strftime('%Y.%m.%d')
    close_price = ddb(db='bctmate').load_table_by_sql('dfs://jq_price', 'daily', f'select code, close from daily where date={date_dol}')
    close_price_mapping = close_price.set_index('code')['close']
    slot_mapping = stock_config[['code', 'slot_quantity']].set_index('code')['slot_quantity'].to_dict()

    qualified_weight = pd.DataFrame(qualified_weight)
    qualified_weight['名义本金'] = qualified_weight['weight'] * notional
    qualified_weight = qualified_weight.reset_index()
    qualified_weight['slot'] = qualified_weight['code'].apply(lambda x: slot_mapping.get(x))
    qualified_weight['收盘价'] = qualified_weight['code'].apply(lambda x: close_price_mapping.get(x))
    qualified_weight['理论数量'] = qualified_weight['名义本金']/qualified_weight['收盘价']
    qualified_weight['理论手数'] = qualified_weight['理论数量']/qualified_weight['slot']
    # qualified_weight = qualified_weight.loc[qualified_weight['理论手数']>0.5]
    qualified_pool = qualified_weight['code'].tolist()


    barra = BARRA(date=date, index_benchmark=index)
    barra.get_benchmark_exposure()
    weight, portfolio_exposures = barra.portfolio_optimize(pool=qualified_pool,
                                                           risk_factor_deviation={'industry': industry_deviation,
                                                                                  'log_market_cap': log_market_cap_deviation})

    weight_df = weight.to_frame()
    weight_df.columns = ['组合权重']
    index_component = ddb(db='bctmate').load_table_by_sql('dfs://jq_price', 'index_components',
                                              f'select * from index_components where date={date_str}, index_code="{index}"')
    index_component = index_component[['code', 'weight']].set_index('code')
    index_component['weight'] = index_component['weight']/100 
    index_component.columns = ['指数权重']
    weight_df = pd.merge(weight_df, index_component, how='outer', left_index=True, right_index=True)
    weight_df = weight_df.reset_index()
    weight_df = weight_df.rename(columns={'index':'code'})
    weight_df['组合权重'] = weight_df['组合权重'].fillna(0)

    # 计算数量
    weight_df['名义本金'] = notional * weight_df['组合权重']
    weight_df['slot'] = weight_df['code'].apply(lambda x: slot_mapping.get(x))
    weight_df['收盘价'] = weight_df['code'].apply(lambda x: close_price_mapping.get(x))
    weight_df['组合理论数量'] = weight_df['名义本金']/weight_df['收盘价']
    weight_df['组合实际数量'] = (weight_df['组合理论数量']/weight_df['slot']).round(0) * weight_df['slot']
    weight_df = weight_df.set_index('code')

    date_str2 = pd.to_datetime(date).strftime('%Y%m%d')
    make_path(project_path + f'./Output/{date_str2}')

    return weight_df, portfolio_exposures

def monitor_basket(index, basket_weight, date=None):
    """
    监控策略组合偏离情况
    basket为pd.Series, index为标的代码(jq), value为标的数量
    """    
    if date is None:
        date = datetime.datetime.today().strftime('%Y-%m-%d')
        date_str = datetime.datetime.today().strftime('%Y.%m.%d')
    else:
        date_str = pd.to_datetime(date).strftime('%Y.%m.%d')

    barra = BARRA(date=date, index_benchmark=index)
    barra.get_benchmark_exposure()

    




def adjust_basket(index, basket, date=None, exclude_restricted=True, exclude_st=True, exclude_paused=True,
                    industry_deviation=0.01, log_market_cap_deviation=0.01,
                    min_avg_amount=(20, 20000000), min_price=None,
                    notional=10000000):
    
    """
    根据目标指数调整当前篮子
    """
    pass

