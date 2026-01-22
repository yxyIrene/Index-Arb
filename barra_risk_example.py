"""
Barra风险模型使用示例
展示如何使用新的barra_risk模块进行风险暴露计算和组合优化
"""

import pandas as pd
from Framework.barra_risk import BarraRiskModel
from Framework.pythonTool import *


def example_basic_exposure():
    """示例1: 基本风险暴露计算"""
    print("=" * 60)
    print("示例1: 基本风险暴露计算")
    print("=" * 60)
    
    date = '2024-11-12'
    model = BarraRiskModel(date=date)
    
    # 加载基准指数权重
    benchmark_weights = ddb(db='percy').load_table_by_sql(
        'dfs://jq_price', 'index_components',
        f'select * from index_components where date=2024.11.12, index_code="000300.XSHG"'
    )
    benchmark_weights = benchmark_weights.set_index('code')['weight']
    benchmark_weights = benchmark_weights / benchmark_weights.sum()
    
    # 计算基准暴露
    benchmark_exposure = model.set_benchmark(benchmark_weights)
    print("\n基准暴露:")
    for factor_name, exposure in benchmark_exposure.items():
        print(f"  {factor_name}: {exposure}")
    
    # 计算组合暴露（只持有前50只股票）
    portfolio_weights = benchmark_weights.head(50)
    portfolio_weights = portfolio_weights / portfolio_weights.sum()
    
    exposure_results = model.calculate_exposure(portfolio_weights)
    
    print("\n组合暴露:")
    for factor_name, result in exposure_results.items():
        print(f"\n  {factor_name}:")
        print(f"    多头暴露: {result.long_exposure}")
        print(f"    净暴露: {result.net_exposure}")


def example_long_short_exposure():
    """示例2: 多空头寸风险暴露计算"""
    print("\n" + "=" * 60)
    print("示例2: 多空头寸风险暴露计算")
    print("=" * 60)
    
    date = '2024-11-12'
    model = BarraRiskModel(date=date)
    
    # 加载基准权重
    benchmark_weights = ddb(db='percy').load_table_by_sql(
        'dfs://jq_price', 'index_components',
        f'select * from index_components where date=2024.11.12, index_code="000300.XSHG"'
    )
    benchmark_weights = benchmark_weights.set_index('code')['weight']
    benchmark_weights = benchmark_weights / benchmark_weights.sum()
    
    # 构建多空组合
    # 多头：前30只股票
    long_weights = benchmark_weights.head(30)
    long_weights = long_weights / long_weights.sum() * 1.5  # 1.5倍杠杆
    
    # 空头：后30只股票
    short_weights = benchmark_weights.tail(30)
    short_weights = short_weights / short_weights.sum() * 0.5  # 0.5倍杠杆
    
    # 计算多空暴露
    exposure_results = model.calculate_exposure(long_weights, short_weights)
    
    print("\n多空组合暴露:")
    for factor_name, result in exposure_results.items():
        print(f"\n  {factor_name}:")
        print(f"    多头暴露: {result.long_exposure}")
        print(f"    空头暴露: {result.short_exposure}")
        print(f"    净暴露: {result.net_exposure}")
        print(f"    总暴露: {result.gross_exposure}")


def example_portfolio_optimization():
    """示例3: 组合优化"""
    print("\n" + "=" * 60)
    print("示例3: 组合优化")
    print("=" * 60)
    
    date = '2024-11-12'
    model = BarraRiskModel(date=date)
    
    # 设置基准
    benchmark_weights = ddb(db='percy').load_table_by_sql(
        'dfs://jq_price', 'index_components',
        f'select * from index_components where date=2024.11.12, index_code="000300.XSHG"'
    )
    benchmark_weights = benchmark_weights.set_index('code')['weight']
    benchmark_weights = benchmark_weights / benchmark_weights.sum()
    
    benchmark_exposure = model.set_benchmark(benchmark_weights)
    
    # 选股池（前100只股票）
    pool = benchmark_weights.index.tolist()[:100]
    
    # 优化组合：最小化跟踪误差，同时控制风险暴露
    optimized_weights, results = model.optimize_portfolio(
        pool=pool,
        target_weights=benchmark_weights.loc[pool],
        exposure_constraints={
            'industry': 0.01,  # 行业偏离度不超过1%
            'log_market_cap': 0.01  # 对数市值偏离度不超过1%
        },
        benchmark_exposure=benchmark_exposure,
        long_only=True
    )
    
    print("\n优化结果:")
    print(f"  优化状态: {results['status']}")
    print(f"  目标函数值: {results['value']:.6f}")
    print(f"  跟踪误差: {results['tracking_error']:.6f}")
    print(f"\n  优化后暴露:")
    for factor_name, exposure in results['exposures'].items():
        print(f"    {factor_name}: {exposure}")
    
    print(f"\n  优化后持仓数量: {len(optimized_weights)}")
    print(f"  最大权重: {optimized_weights.max():.4f}")
    print(f"  最小权重: {optimized_weights.min():.4f}")


def example_aggregate_exposure():
    """示例4: 多个组合的汇总暴露"""
    print("\n" + "=" * 60)
    print("示例4: 多个组合的汇总暴露")
    print("=" * 60)
    
    date = '2024-11-12'
    model = BarraRiskModel(date=date)
    
    # 加载基准权重
    benchmark_weights = ddb(db='percy').load_table_by_sql(
        'dfs://jq_price', 'index_components',
        f'select * from index_components where date=2024.11.12, index_code="000300.XSHG"'
    )
    benchmark_weights = benchmark_weights.set_index('code')['weight']
    benchmark_weights = benchmark_weights / benchmark_weights.sum()
    
    # 构建多个组合
    portfolios = {
        '组合1': benchmark_weights.head(30) / benchmark_weights.head(30).sum(),
        '组合2': benchmark_weights.iloc[30:60] / benchmark_weights.iloc[30:60].sum(),
        '组合3': benchmark_weights.iloc[60:90] / benchmark_weights.iloc[60:90].sum(),
    }
    
    # 计算汇总暴露
    aggregate_exposure = model.exposure_calculator.calculate_aggregate_exposure(portfolios)
    
    print("\n汇总暴露:")
    for factor_name, result in aggregate_exposure.items():
        print(f"\n  {factor_name}:")
        print(f"    多头暴露: {result.long_exposure}")
        print(f"    空头暴露: {result.short_exposure}")
        print(f"    净暴露: {result.net_exposure}")
        print(f"    总暴露: {result.gross_exposure}")


def example_net_exposure():
    """示例5: 净暴露计算（权重可为正负）"""
    print("\n" + "=" * 60)
    print("示例5: 净暴露计算（权重可为正负）")
    print("=" * 60)
    
    date = '2024-11-12'
    model = BarraRiskModel(date=date)
    
    # 加载基准权重
    benchmark_weights = ddb(db='percy').load_table_by_sql(
        'dfs://jq_price', 'index_components',
        f'select * from index_components where date=2024.11.12, index_code="000300.XSHG"'
    )
    benchmark_weights = benchmark_weights.set_index('code')['weight']
    benchmark_weights = benchmark_weights / benchmark_weights.sum()
    
    # 构建多空组合（权重可为正负）
    weights = benchmark_weights.head(50).copy()
    # 前25只为多头，后25只为空头
    weights.iloc[25:] = -weights.iloc[25:] * 0.5
    weights = weights / weights.abs().sum()  # 标准化
    
    # 计算净暴露
    net_exposure = model.calculate_net_exposure(weights)
    
    print("\n净暴露:")
    for factor_name, exposure in net_exposure.items():
        print(f"  {factor_name}: {exposure}")


if __name__ == '__main__':
    try:
        example_basic_exposure()
        example_long_short_exposure()
        example_portfolio_optimization()
        example_aggregate_exposure()
        example_net_exposure()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

