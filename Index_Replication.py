import os 
current_path = os.path.dirname(os.path.abspath(__file__))
project_name = 'Index_Arbitrage'
project_path = current_path.split(project_name)[0] + project_name + '/'
from Script.daily_job import *
from Strategy.replication import *
from Framework.tool import *



if __name__ == '__main__':
    current_date = '20260105'

    ##################################### 从台账eod中获取交易组合 #########################################
    # get_all_strategy(current_date)

    ##################################### 调整组合目标仓位 #########################################
    adjust_all_strategy(current_date)



    
