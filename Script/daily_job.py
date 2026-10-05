import pandas as pd
import numpy as np
from Strategy.replication import *
from Strategy.get_basket import *
import os 
from Framework.tool import *
current_path = os.path.dirname(os.path.abspath(__file__))
project_name = '001_Index_Arbitrage'
project_path = current_path.split(project_name)[0] + project_name + '/'
import tqdm



def get_all_strategy(current_date):

    eod_path = get_target_path('台账EOD', current_date=current_date)
    asset_df = read_latest_file('标的明细', eod_path)

    condition = {'交易对手方': 'CAD'}
    all_basket = get_basket(asset_df=asset_df, groupby='交易确认书编号', condition=condition)

    make_path(project_path + f'Portfolio/{current_date}/')

    for basket_name in all_basket.keys():
        all_basket[basket_name] = all_basket[basket_name].rename(columns={'交易确认书编号': '组合名称'})
        all_basket[basket_name].to_excel(project_path + f'Portfolio/{current_date}/{basket_name}.xlsx')
    return


def adjust_all_strategy(current_date):
    """
    根据组合管理配置, 对当前所有头寸进行调整
    """
    jq_ticker_mapping = {'SH000905 Index': '000905.XSHG',
                      'SHSZ300 Index': '000300.XSHG',
                      'CSI1000 Index': '000852.XSHG'}

    strategy_config = pd.read_excel(project_path + 'Script/组合管理.xlsx', sheet_name='组合管理')

    total_deviation = []
    industry_deviation = []
    log_market_cap_deviation = []
    strategy_stock_num = []
    make_path(project_path + f'Output/{current_date}/')
    make_path(project_path + f'Output/{current_date}/策略目标仓位/')
    make_path(project_path + f'Output/{current_date}/投资组合当日流水/')
    make_path(project_path + f'Output/{current_date}/投资组合交易指令/')

    strategy_weight = {}

    # 优化计算策略目标仓位
    with timer('组合策略目标持仓优化完成'):
        for i in tqdm.trange(len(strategy_config)):
            strategy_info = strategy_config.iloc[i]
            strategy_name = strategy_info['策略编号']
            print(f'开始优化组合: {strategy_name}')
            index_jq_ticker = jq_ticker_mapping.get(strategy_info['挂钩指数'], strategy_info['挂钩指数'])

            print(index_jq_ticker)

            weight_df, strategy_exposures = replicate_index(index=index_jq_ticker, date=current_date, 
                                                        exclude_restricted=strategy_info['禁投池限制'], 
                                                        exclude_st=strategy_info['ST限制'], 
                                                        exclude_paused=strategy_info['停牌限制'],
                                                        industry_deviation=strategy_info['行业偏离度'], 
                                                        log_market_cap_deviation=strategy_info['对数市值偏离度'],
                                                        min_avg_amount=(strategy_info['滚动天数'], strategy_info['最低成交额限制']), 
                                                        min_price=None,
                                                        notional=strategy_info['组合规模'])
            
            # 输出目标仓位
            weight_df.to_excel(project_path + f'Output/{current_date}/策略目标仓位/{strategy_name}目标仓位.xlsx')
            # 生成交易文件
            weight_df['code2'] = weight_df.index
            weight_df['市场'] = weight_df['code2'].apply(lambda x: x[-1])
            weight_df['市场'] = weight_df['市场'].apply(lambda x: 1 if x=='E' else 0)
            weight_df['代码'] = weight_df['code2'].apply(lambda x: x[:6])
            weight_df['委托数量'] = weight_df['组合实际数量']
            weight_df['买卖方向'] = 'B'
            weight_df['产品'] = 2
            weight_df['资产单元'] = 139
            weight_df['投资组合'] = 144
            weight_df['名称'] = None
            weight_df['开平标志'] = None
            weight_df['投保标志'] = None
            weight_df['委托价格'] = None
            weight_df['扩展业务类型'] = None
            weight_df['扩展业务方向'] = None
            trade_df = weight_df.loc[weight_df['委托数量'] > 0]
            trade_df = trade_df[['产品','资产单元',	'投资组合',	'市场',	'代码',	'名称',	'买卖方向',	'开平标志',	'投保标志',	'委托价格',	'委托数量']]
            trade_df.to_excel(project_path + f'Output/{current_date}/策略目标仓位/{strategy_name} IMS交易指令模板.xlsx', index=False)

            strategy_weight[strategy_name] = weight_df

            total_deviation.append(strategy_exposures['total deviation'])
            industry_deviation.append(strategy_exposures['industry deviation'])
            log_market_cap_deviation.append(strategy_exposures['log_market_cap deviation'])
            strategy_stock_num.append(len(weight_df.loc[weight_df['组合实际数量'] > 0]))


    # with timer('当日流水汇总完毕'):
    #     # 获取当日流水
    #     all_file = os.listdir(project_path + f'Output/{current_date}/投资组合当日流水/')
    #     all_trade = pd.DataFrame(columns=['投资组合', '合约代码', '成交数量', '交易类型'])
    #     for file in all_file:
    #         if '成交' in file:
    #             trade = pd.read_excel(project_path + f'Output/{current_date}/投资组合当日流水/' + file)
    #             all_trade = pd.concat([all_trade, trade])
    #     all_trade = all_trade.rename(columns={'合约代码':'code'})
    #     all_trade['成交数量'] = all_trade['成交数量'].apply(lambda x: int(str(x).replace(',', '')))
    #     # buy_type_mapping = {'普通买入':1, '普通卖出':-1}
   
    #     # all_trade['数量变动'] = all_trade.apply(lambda x: buy_type_mapping.get(x['交易类型']) * x['成交数量'], axis=1)
    #     all_trade['trade_code'] = all_trade['code'].apply(lambda x: any_to_code(x))


    # with timer('投资组合头寸汇总完毕'):
    # # 获取投资组合当前仓位
    #     all_portfolio = set(strategy_config['投资组合'])
    #     for portfolio in all_portfolio:

    #         # 获取隔日头寸
    #         all_portfolio_strategy = strategy_config.set_index('投资组合').loc[[portfolio]]
    #         portfolio_position = pd.DataFrame(columns=['标的代码', '分红调整剩余数量', '期初成本', '每股成本'])
    #         for i in range(len(all_portfolio_strategy)):
    #             strategy_name = all_portfolio_strategy.iloc[i]['策略编号']
    #             try:
    #                 strategy_position = pd.read_excel(project_path + f'Portfolio/{current_date}/{strategy_name}.xlsx')
    #             except:
    #                 print(f'{strategy_name}: 昨日暂无持仓')
    #                 strategy_position = pd.DataFrame(columns=['标的代码', '分红调整剩余数量', '期初成本', '每股成本'])
                
    #             portfolio_position = pd.concat([portfolio_position, strategy_position])

    #         portfolio_position['trade_code'] = portfolio_position['标的代码'].apply(lambda x: any_to_code(x))
            
    #         # 汇总组合头寸
    #         portfolio_position = portfolio_position.groupby('标的代码').sum()[['分红调整剩余数量']].reset_index()
    #         portfolio_position['trade_code'] = portfolio_position['标的代码'].apply(lambda x: any_to_code(x))
            
    #         # 获取组合当日流水
    #         portfolio_trade = all_trade.loc[all_trade['投资组合'] == portfolio]
    #         portfolio_trade = portfolio_trade[['trade_code', '交易类型', '成交数量']]
    #         portfolio_trade = portfolio_trade.groupby(['trade_code', '交易类型']).sum()
    #         portfolio_trade = portfolio_trade.reset_index()
    #         portfolio_trade = portfolio_trade.pivot(index='trade_code', columns='交易类型', values='成交数量').fillna(0)

    #         # 合并昨日头寸和当日流水
    #         portfolio_current_position = portfolio_position.merge(portfolio_trade, left_on='trade_code', right_index=True, how='outer')
    #         portfolio_current_position = portfolio_current_position.rename(columns={'分红调整剩余数量':'昨日收盘数量', '普通买入':'当日买入数量', '普通卖出':'当日卖出数量'})
    #         if '当日买入数量' in portfolio_current_position.columns:
    #             pass
    #         else:
    #             portfolio_current_position['当日买入数量'] = 0
            
    #         if '当日卖出数量' in portfolio_current_position.columns:
    #             pass
    #         else:
    #             portfolio_current_position['当日卖出数量'] = 0


    #         portfolio_current_position = portfolio_current_position[['trade_code', '昨日收盘数量', '当日买入数量', '当日卖出数量']].set_index('trade_code')
    #         portfolio_current_position = portfolio_current_position.fillna(0)
    #         portfolio_current_position = portfolio_current_position.applymap(lambda x: int(x))
    #         portfolio_current_position['当前持仓'] = portfolio_current_position['昨日收盘数量'] + portfolio_current_position['当日买入数量'] - portfolio_current_position['当日卖出数量']

    #         # 合并策略目标仓位
    #         portfolio_target = pd.DataFrame()
    #         for i in range(len(all_portfolio_strategy)):
    #             strategy_name = all_portfolio_strategy.iloc[i]['策略编号']

    #             portfolio_target = pd.concat([portfolio_target, strategy_weight[strategy_name]])

            
    #         portfolio_target = portfolio_target.reset_index()
    #         portfolio_target['trade_code'] = portfolio_target['code'].apply(lambda x: any_to_code(x))
    #         portfolio_target = portfolio_target[['trade_code', '组合理论数量']].groupby('trade_code').sum()

    #         portfolio_instruction = portfolio_target.merge(portfolio_current_position, left_on='trade_code', right_on='trade_code', how='outer') 
    #         portfolio_instruction = portfolio_instruction.fillna(0)
    #         portfolio_instruction['需调仓数量'] = portfolio_instruction['组合理论数量'] - portfolio_instruction['当前持仓']
            
    #         portfolio_instruction.to_excel(project_path + f'Output/{current_date}/投资组合交易指令/{portfolio}当前头寸及交易指令.xlsx')
  
    
    
    strategy_config['个股整体偏离度'] = total_deviation
    strategy_config['行业偏离度'] = industry_deviation
    strategy_config['对数市值偏离度'] = log_market_cap_deviation
    strategy_config['组合股票数量'] = strategy_stock_num
    strategy_config = strategy_config[['投资组合', '策略编号', '挂钩指数', '挂钩指数份额', '指数行情', '组合规模', '组合股票数量', 
                                         '行业偏离度', '对数市值偏离度', '最低成交额限制', '滚动天数', '禁投池限制', 'ST限制', '停牌限制']]
    
    strategy_config.to_excel(project_path + f'Output/{current_date}/组合优化结果.xlsx', index=False)




