import pandas as pd

def get_basket(asset_df, groupby, condition=None):
    """
    根据条件筛选持仓组合
    """

    if condition is None:
        pass
    else:
        for key in condition.keys():
            fields = condition.get(key)
            if type(fields) == str:
                fields = [fields]
        
            asset_df = asset_df.loc[asset_df[key].apply(lambda x: x in  fields)]
    
    asset_df[['交易确认书编号', '标的代码', '分红调整剩余数量', '分红调整期初价格']]
    asset_df['期初成本'] = asset_df['分红调整期初价格'] * asset_df['分红调整剩余数量']

    all_group_name = set(asset_df[groupby])
    all_group = {}
    for group_name in all_group_name:
        portfolio_df = asset_df.loc[asset_df[groupby] == group_name]

        portfolio_df = portfolio_df[['标的代码', '分红调整剩余数量', '期初成本']].groupby('标的代码').sum()
        portfolio_df['每股成本'] = portfolio_df['期初成本']/portfolio_df['分红调整剩余数量']
        all_group[group_name] = portfolio_df
    
    return all_group





    

