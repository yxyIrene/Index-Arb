import pandas as pd
import datetime
from Framework.pythonTool import *
from Framework.indexTool import *
import numpy as np
import cvxpy as cp


class BARRA:
    def __init__(self, date=None, index_benchmark=None):
        """
        构建Barra风险模型对象
        Args:
            date: 构建日期 string
            index_benchmark: 基准 string
        """
        self.index_benchmark = None
        self.benchmark_weights = None
        self.benchmark_exposures = {}
        self.underlying_exposures = {}

        if date is None:
            self.date = (datetime.datetime.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            self.date = date

        self.date_str = pd.to_datetime(self.date).strftime('%Y.%m.%d')
        self.set_index_benchmark(index_benchmark)

        return

    def set_index_benchmark(self, index_benchmark):
        self.index_benchmark = index_benchmark
        if index_benchmark is None:
            pass
        else:
            benchmark_weights = ddb(db='bctmate').load_table_by_sql('dfs://jq_price', 'index_components',
                                                        f'select * from index_components where date={self.date_str}, index_code="{index_benchmark}"')

            self.benchmark_weights = benchmark_weights.set_index('code')['weight']
            self.benchmark_weights = self.benchmark_weights/self.benchmark_weights.sum()  # 权重标准化
            
        return

    def get_benchmark_exposure(self, risk_factors=None):
        """
        计算index_benchmark指定的风险敞口
        Args:
            risk_factors: 风险因子列表 list of string

        Returns: None
        """
        if risk_factors is None:
            risk_factors = ['industry', 'log_market_cap']

        # 计算指数暴露
        for factor in risk_factors:
            if factor == 'industry':
                with timer('Industry exposure(sw_l1) calculated'):
                    self.benchmark_exposures['industry'] = self.get_exposure_industry(self.benchmark_weights)
            elif factor == 'log_market_cap':
                with timer('Log market cap exposure calculated'):
                    self.benchmark_exposures['log_market_cap'] = self.get_exposure_log_market_cap(self.benchmark_weights)
            else:
                print(f'{factor}: No method defined')

    def get_exposure_industry(self, weights):
        """
        返回组合申万一级行业暴露（行业权重)
        Args:
            weights: 成分股权重 pd.Series

        Returns:
            组合行业暴露（行业权重） pd.Series
        """
        data = ddb(db='bctmate').load_table_by_sql('dfs://jq_price', 'industry',
                                             f'select code, sw_l1 from industry where date={self.date_str}')
        industries = data.set_index('code')['sw_l1']
        exposure_df = pd.merge(left=weights, right=industries, left_index=True, right_index=True, how='inner')
        exposure_industry = exposure_df.groupby('sw_l1').sum()['weight'].to_dict()

        # 储存标的行业哑变量暴露字典
        self.underlying_exposures['industry'] = {}
        industry_df = data[['code', 'sw_l1']].set_index('code')
        industry_set = set(industry_df['sw_l1'])
        for industry in industry_set:
            industry_df[industry] = industry_df['sw_l1'].apply(lambda x: x == industry)
            self.underlying_exposures['industry'][industry] = industry_df[industry].to_dict()
            
        return exposure_industry

    def get_exposure_log_market_cap(self, weights):
        """
        返回组合对数市值暴露（市值取亿人民币）
        Args:
            weights: 成分股权重 pd.Series

        Returns:
            组合对数市值暴露（亿人民币)

        """
        market_caps = ddb(db='bctmate').load_table_by_sql('dfs://jq_fundamental', 'valuation',
                                              f'select code, market_cap from valuation where date={self.date_str}')

        market_caps = market_caps.set_index('code')['market_cap']
        log_market_caps = np.log(market_caps)
        codes_nodata = [code for code in weights.index if not(code in log_market_caps.index)]

        # 判断是否存在数据缺失, 后续计算会剔除缺失数据标的(大概率是退市标的)
        if len(codes_nodata) > 0:
            print('No data for following codes. Codes will be dropped')
            print(codes_nodata)

        exposure_log_market_cap = log_market_caps * weights
        exposure_log_market_cap = exposure_log_market_cap.loc[weights.index].sum()
        self.underlying_exposures['log_market_cap'] = log_market_caps.to_dict()  # 储存标的对数市值暴露字典

        return exposure_log_market_cap

    def portfolio_optimize(self, pool, risk_factor_deviation=None):
        """

        Args:
            pool: 选股池 list
            risk_factor_deviation: 偏离度限制 dict

        Returns:
            weight: 优化权重结果 pd.Series
            portfolio_exposures: 组合风险偏离度 dict
        """

        if risk_factor_deviation is None:
            risk_factor_deviation = {'industry':0.005,
                            'log_market_cap':0.01}

        # 以给定选股池构建因变量
      
        X = cp.Variable(len(pool))
        constraints = []

        for factor in risk_factor_deviation.keys():
            if factor == 'industry':

                # 生成行业哑变量矩阵, index为行业, columns为标的代码
                ind_matrix = pd.DataFrame(self.underlying_exposures['industry'])
                ind_matrix = ind_matrix.loc[pool].T

                # 可能指数成分不包含部分行业, 将这部分drop掉
                ind_matrix= ind_matrix.loc[ind_matrix.sum(axis=1).apply(lambda x: True if x >0 else False)]

                # 生成benchmark行业暴露
                benchmark_industry_exposures = pd.Series(self.benchmark_exposures['industry']).loc[ind_matrix.index]

                # 生成组合行业偏离度限制
                ind_condition = cp.sum(cp.abs(np.array(ind_matrix) @ X - np.array(benchmark_industry_exposures))) <= risk_factor_deviation[factor]
                constraints.append(ind_condition)

            elif factor == 'log_market_cap':

                # 生成选股池个股暴露series
                log_market_cap_series = pd.Series(self.underlying_exposures['log_market_cap']).loc[pool]

                # 生成对数市值偏离度限制
                log_market_cap_deviation = cp.abs(np.array(log_market_cap_series) @ X - self.benchmark_exposures['log_market_cap'])
                log_market_cap_condition = log_market_cap_deviation <= (self.benchmark_exposures['log_market_cap'] * risk_factor_deviation[factor])
                constraints.append(log_market_cap_condition)

            else:
                print(f'{factor}: Factor constraint method not defined')

        constraints.append((cp.sum(X)==1))  # 总权重限制
        constraints.append(X>=0)  # 非负条件限制

        # 构造目标函数: 最小化个股偏离度之和
        total_deviation = cp.sum(cp.abs(X - np.array(self.benchmark_weights.loc[pool])))
        objective = cp.Minimize(total_deviation)
        # 求解凸优化问题
        prob = cp.Problem(objective, constraints)
        prob.solve(solver=cp.ECOS)
        # 生成结果
        weight = pd.Series(X.value, index=pool)

        portfolio_exposures = {}
        portfolio_exposures['total deviation'] = sum(abs(X.value - np.array(self.benchmark_weights.loc[pool])))
        for factor in risk_factor_deviation.keys():
            if factor == 'industry':
                portfolio_exposures[f'{factor} deviation'] = sum(abs(np.array(ind_matrix).dot(X.value) - np.array(benchmark_industry_exposures)))
            elif factor == 'log_market_cap':
                portfolio_exposures[f'{factor} deviation'] = (np.array(log_market_cap_series).dot(X.value) - self.benchmark_exposures['log_market_cap'])/self.benchmark_exposures['log_market_cap']
            else:
                pass


        return weight, portfolio_exposures


if __name__ == '__main__':
    b = BARRA(date='2024-11-12', index_benchmark='000300.XSHG')
    b.get_benchmark_exposure()
    pool = select_index_component_by_condition('000300.XSHG', '2024-11-12', min_avg_amount=(20,10000000)).index


    weight, portfolio_exposures = b.portfolio_optimize(pool, risk_factor_deviation={'log_market_cap':0.01, 'industry':0.01})
    print('优化后组合风险暴露为:')
    print(portfolio_exposures)