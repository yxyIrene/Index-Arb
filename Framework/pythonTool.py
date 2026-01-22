import pandas as pd
import numpy as np
import dolphindb
import time
import datetime
import warnings
warnings.filterwarnings("ignore")

################################ 交易日处理工具 #################################

def get_weekly_tradedays(start_date,end_date,k,transform=False):
    """
    k = 1表示每周的第1个交易日,-1是最后一个交易日,可取1-5或者-1,最后一周的最后一个交易日即为end_date
    """
    date_df = pd.DataFrame(get_tradedays(start_date,end_date,transform=True),columns=['date'])
    date_df['year'] = date_df.apply(lambda x: datetime.date.fromtimestamp(time.mktime(time.strptime(x['date'],'%Y-%m-%d'))).isocalendar()[0],axis=1)
    date_df['week'] = date_df.apply(lambda x: datetime.date.fromtimestamp(time.mktime(time.strptime(x['date'],'%Y-%m-%d'))).isocalendar()[1],axis=1)
    if k > 0:
        date_list = date_df.groupby(['year','week']).nth(k-1)['date'].tolist()
    else:
        date_list = date_df.groupby(['year','week']).nth(k)['date'].tolist()
    if transform:
        return date_list
    else:
        return pd.to_datetime(date_list)

def get_monthly_tradedays(start_date,end_date,k,transform=False):
    """
    k = 1表示每月的第1个交易日,-1是最后一个交易日,可取1-5或-1,当取-1时,最后一个月的最后一个交易日即为end_date
    """
    date_df = pd.DataFrame(get_tradedays(start_date,end_date,transform=True),columns=['date'])
    date_df['year'] = date_df.apply(lambda x: datetime.date.fromtimestamp(time.mktime(time.strptime(x['date'],'%Y-%m-%d'))).isocalendar()[0],axis=1)
    date_df['month'] = date_df.apply(lambda x: int(x['date'][5:7]),axis=1)
    if k > 0:
        date_list = date_df.groupby(['year','month']).nth(k-1)['date'].tolist()
    else:
        date_list = date_df.groupby(['year','month']).nth(k)['date'].tolist()
    if transform:
        return date_list
    else:
        return pd.to_datetime(date_list)

def get_tradedays(start_date,end_date,transform=False):
    '''获取两个日期间的所有交易日'''
    dol = ddb(db='bctmate')
    start_date = pd.to_datetime(start_date).strftime('%Y.%m.%d')
    end_date = pd.to_datetime(end_date).strftime('%Y.%m.%d')
    trade_cal = dol.load_table_by_sql('dfs://jq_price','trade_cal',"select * from trade_cal where date(date) >= {} and date(date) <= {}".format(start_date,end_date))
    if len(trade_cal) > 0:
        trade_cal = trade_cal.sort_values(by='date',ascending=True)
        if transform:
            trade_cal['date'] = [x.strftime('%Y-%m-%d') for x in trade_cal['date']]
        return trade_cal['date'].tolist()
    else:
        return []

def get_previous_tradedate(date = time.strftime('%Y.%m.%d',time.localtime()),n = 1, transform=False):
    '''获取上一个交易日'''
    dol = ddb(db='bctmate')
    date = pd.to_datetime(date).strftime('%Y.%m.%d')
    sql = "select * from trade_cal where date(date) < {}".format(date)
    trade_cal = dol.load_table_by_sql('dfs://jq_price','trade_cal',sql)
    trade_cal = trade_cal.sort_index(ascending=True)
    trade_cal.index = range(len(trade_cal))
    previous_tradedate = trade_cal.iloc[-n]['date']
    if transform:
        return previous_tradedate.strftime('%Y-%m-%d')
    else:
        return previous_tradedate

def get_next_tradedate(date,n = 1,transform=False):
    dol = ddb(db='bctmate')
    date = pd.to_datetime(date).strftime('%Y.%m.%d')
    sql = "select * from trade_cal where date(date) > {}".format(date)
    trade_cal = dol.load_table_by_sql('dfs://jq_price','trade_cal',sql)
    trade_cal = trade_cal.sort_index(ascending=True)
    trade_cal.index = range(len(trade_cal))
    next_tradedate = trade_cal.iloc[n-1]['date']
    if transform:
        return next_tradedate.strftime('%Y-%m-%d')
    else:
        return next_tradedate

def is_tradingday(date):
    dol = ddb(db='bctmate')
    date = pd.to_datetime(date).strftime('%Y.%m.%d')
    trade_cal = dol.load_table_by_sql('dfs://jq_price','trade_cal',"select * from trade_cal where date(date) = {}".format(date))
    if len(trade_cal) > 0:
        return True
    else:
        return False

def get_info_available_date(date, transform=False, bynow=False):
    next_tradedate = get_next_tradedate(date)
    date = pd.to_datetime(date)
    info_available_date = date + (next_tradedate - date) - datetime.timedelta(1)
    if bynow:
        info_available_date = min(datetime.datetime.today(), info_available_date)
    if transform:
        return info_available_date.strftime('%Y-%m-%d')
    else:
        return info_available_date
    


################################ 报告期处理工具 #################################

def get_last_season(date, transform=False):
    date = pd.to_datetime(date)
    quarter = int((date.month - 1) / 3 + 1)
    if quarter == 1:
        date = datetime.datetime(date.year - 1, 12, 31)
    elif quarter == 2:
        date = datetime.datetime(date.year, 3, 31)
    elif quarter == 3:
        date = datetime.datetime(date.year, 6, 30)
    else:
        date = datetime.datetime(date.year, 9, 30)
    if transform:
        return date.strftime('%Y-%m-%d')
    else:
        return date

def get_lastyear_date(date, transform=False):
    date = pd.to_datetime(date)
    date = datetime.datetime(date.year - 1, date.month, date.day)
    if transform:
        return date.strftime('%Y-%m-%d')
    else:
        return date

def get_lastyear_season(date, transform=False):
    date = pd.to_datetime(date)
    date = datetime.datetime(date.year - 1, 12, 31)
    if transform:
        return date.strftime('%Y-%m-%d')
    else:
        return date

def get_wind_data(sql):
    engine = sqlalchemy.create_engine("mysql+pymysql://quant_db:quant_db*-+@172.16.68.235:3306/wind?utf8")
    df = pd.read_sql(sql,engine)
    engine.dispose()
    return df

def wind_to_jq(codelist):
    return [x[:6]+'.XSHE' if x[-1] == 'Z' else x[:6]+'.XSHG' for x in codelist]

def jq_to_wind(codelist):
    def trans_jq_wind(code):
        if code[0] == '6':
            return code[:6] + '.SH'
        elif code[0] == '0' or code[0] == '3':
            return code[:6] + '.SZ'
        else:
            return code[:6] + '.BJ'
    return [trans_jq_wind(x) for x in codelist]

def next_period(statDate):
    '''获取下个报告期:2012q1 > 2012q2'''
    if statDate[-1] == '4':
        return str(int(statDate[:4])+1)+'q1'
    else:
        return statDate[:5]+str(int(statDate[-1])+1)

def get_stat_list(start_stat,end_stat):
    '''获取两个报告期之间的所有报告期'''
    stat_list = []
    stat = start_stat
    while stat <= end_stat:
        stat_list.append(stat)
        stat = next_period(stat)
    return stat_list

def stat_to_date(stat):
    '''格式转化: 2012q1 > 2012-03-31'''
    if stat[-1] == '1':
        return stat[:4]+'-03-31'
    elif stat[-1] == '2':
        return stat[:4]+'-06-30'
    elif stat[-1] == '3':
        return stat[:4]+'-09-30'
    else:
        return stat[:4]+'-12-31'

def date_to_stat(date):
    '''格式转化: 2012-03-31 > 2012q1'''
    if date[-5:] == '03-31':
        return date[:4]+'q1'
    elif date[-5:] == '06-30':
        return date[:4]+'q2'
    elif date[-5:] == '09-30':
        return date[:4]+'q3'
    else:
        return date[:4]+'q4'

def get_after_report_tradedate(date):
    dol = ddb(db='bctmate')
    date = pd.to_datetime(date)
    previous_date = get_previous_tradedate(date,130)
    next_date = get_next_tradedate(date,15)
    sql = "select code,pub_date,report_date from balance_sheet where pub_date <= {} and pub_date >= {} and report_type = 0".format(date.strftime('%Y.%m.%d'),previous_date.strftime('%Y.%m.%d'))
    pub_date = dol.load_table_by_sql('dfs://jq_fundamental_report','balance_sheet',sql)
    oneday = pub_date.groupby('code',as_index=False).max()
    oneday['date'] = date
    calendar_dates = pd.DataFrame(pd.date_range(previous_date,next_date),columns=['calendar_date'])
    trade_dates = pd.DataFrame(get_tradedays(previous_date,next_date),columns=['first_tradeday'])
    merge_dates = pd.merge(calendar_dates,trade_dates,left_on='calendar_date',right_on='first_tradeday',how='left')
    merge_dates = merge_dates.fillna(method = 'backfill')
    after_report_tradedate = pd.merge(oneday,merge_dates,left_on='pub_date',right_on='calendar_date',how='left').dropna()[['code','date','report_date','first_tradeday']]
    return after_report_tradedate

def get_after_forecast_tradedate(date):
    dol = ddb(db='bctmate')
    date = pd.to_datetime(date)
    previous_date = get_previous_tradedate(date,130)
    next_date = get_next_tradedate(date,15)
    sql = "select code,pub_date,end_date,report_type,type from fin_forcast where pub_date <= {} and pub_date >= {}".format(date.strftime('%Y.%m.%d'),previous_date.strftime('%Y.%m.%d'))
    pub_date = dol.load_table_by_sql('dfs://jq_fundamental_report','fin_forcast',sql)
    oneday = pub_date.groupby('code',as_index=False).max()
    oneday['date'] = date
    calendar_dates = pd.DataFrame(pd.date_range(previous_date,next_date),columns=['calendar_date'])
    trade_dates = pd.DataFrame(get_tradedays(previous_date,next_date),columns=['first_tradeday'])
    merge_dates = pd.merge(calendar_dates,trade_dates,left_on='calendar_date',right_on='first_tradeday',how='left')
    merge_dates = merge_dates.fillna(method = 'backfill')
    after_forecast_tradedate = pd.merge(oneday,merge_dates,left_on='pub_date',right_on='calendar_date',how='left').dropna()[['code','date','end_date','first_tradeday','type','report_type']]
    return after_forecast_tradedate 


################################ DDB 数据库脚本 #################################

class ddb:
    def __init__(self, db='bctmate'):
        self.choose_db(db)
        return
    
    def choose_db(self, db):

        if db == 'bctmate':
            self.host = '172.30.128.13'
            self.port = 80
            self.user = "admin"
            self.password = "123456"
            # print('Database switched to BCTMATE')

        elif db == 'bctmate':
            self.host = "10.178.120.43"
            self.port = 8848
            self.user = "admin"
            self.password = "123456"
            # print('Database switched to bctmate Personal DataBase')
        else:
            print(f'{db}:NO database found!')
        return

    def create_value_table_to_ddb(self, data, dbPath, dbName, tableName, partition_startdate="2010-01-01", partition_enddate="2036-12-31", partition_period="M", partitionColumns="date", initialization=False):
        # partion_period need to be one of ['D','M','Y']

        s = dolphindb.session()
        x = s.connect(self.host, self.port, self.user, self.password)

        if partition_period == 'D':
            datetype = "datetime64[D]"
        elif partition_period == 'M':
            datetype = "datetime64[M]"
        elif partition_period == 'Y':
            datetype = "datetime64[Y]"
 
        if not s.existsDatabase(dbPath):    
   
            partitions = np.array(pd.date_range(start=partition_startdate, end=partition_enddate,freq=partition_period), dtype=datetype)
            db = s.database(dbName=dbName, partitionType=dolphindb.settings.VALUE, partitions=partitions, dbPath=dbPath)
        else:
            db = s.database(dbName=dbName, dbPath=dbPath)
        data = data.fillna(np.nan)
        data = s.table(data=data)
        if initialization: 
            self.drop_table_from_ddb(dbPath=dbPath, tableName=tableName)    
        db.createPartitionedTable(table=data, tableName=tableName, partitionColumns=partitionColumns).append(data)
        s.close()

    def create_range_table_to_ddb(self, data, dbPath, dbName, tableName, partitions, partitionColumns, initialization=False):
        s = dolphindb.session()
        s.connect(self.host, self.port, self.user, self.password)

        if initialization and s.existsDatabase(dbPath):
            s.dropDatabase(dbPath)

        if not s.existsDatabase(dbPath):    
            db = s.database(dbName=dbName, partitionType=dolphindb.settings.RANGE, partitions=partitions, dbPath=dbPath)
        else:
            db = s.database(dbName=dbName, dbPath=dbPath)
        data = data.fillna(np.nan)
        data = s.table(data=data)
        db.createPartitionedTable(table=data, tableName=tableName, partitionColumns=partitionColumns).append(data)
        s.close()
        
    def append_to_ddb(self, data, dbPath, tableName):
        s = dolphindb.session()

        s.connect(self.host, self.port, self.user, self.password)
        appender = dolphindb.tableAppender(dbPath=dbPath, tableName=tableName, ddbSession = s)
        data = data.fillna(np.nan)
        appender.append(data)
        s.close()

    def release_cache(self):
        s = dolphindb.session()
        s.connect(self.host, self.port, self.user, self.password)
        sessions = s.run(script = "pnodeRun(getSessionMemoryStat)")['sessionId'].tolist()
        sessions.reverse()
        try:
            for session in sessions:
                s.run(script = "closeSessions({})".format(session))
        except:
            print("current session has been killed first")
    
    def drop_database_from_ddb(self,dbPath):
        s = dolphindb.session()
        s.connect(self.host, self.port, self.user, self.password)
        if s.existsDatabase(dbPath):
            s.dropDatabase(dbPath)
        s.close()

    def drop_partitions_from_ddb(self,dbPath,partitionPaths,tableName):
        s = dolphindb.session()
        s.connect(self.host, self.port, self.user, self.password)
        s.dropPartition(dbPath, partitionPaths=partitionPaths, tableName=tableName)
        s.close()

    def drop_table_from_ddb(self, dbPath, tableName):
        s = dolphindb.session()
        s.connect(self.host, self.port, self.user, self.password)
        try:
            s.dropTable(dbPath=dbPath, tableName=tableName)
        except:
            pass
        s.close()

    def delete_from_table(self, dbPath, tableName, condition):
        # condition must be like "date(time) = 2017.02.01"
        s = dolphindb.session()
        s.connect(self.host, self.port, self.user, self.password)
        table=s.loadTable(tableName=tableName,dbPath=dbPath)
        table.delete().where(condition).execute()
        s.close()

    def load_table_by_sql(self,dbPath,tableName,sql):
        s = dolphindb.session()
        s.connect(self.host, self.port, self.user, self.password)
        try:
            df = s.loadTableBySQL(tableName=tableName, dbPath=dbPath, sql=sql).toDF()
        except:
            df = pd.DataFrame()
        s.close()
        return df

    def run_ddb_func(self,func):
        s = dolphindb.session()
        s.connect(self.host, self.port, self.user, self.password)
        try:
            df = s.run(func)
            s.close()
            return df
        except:
            s.close()
            print("func format error")

    def get_latest_record_time(self, columnName, dbPath, tableName):
        s = dolphindb.session()
        s.connect(self.host, self.port, self.user, self.password)
        record = s.run("select max({}) from loadTable('{}', '{}')".format(columnName,dbPath,tableName)).values[0][0]
        s.close()
        return pd.to_datetime(str(record))

    def get_latest_record_date(self,columnName,dbPath,tableName):
        record = self.get_latest_record_time(columnName, dbPath, tableName)
        return record.strftime("%Y-%m-%d")

    def show_tables_in_ddb(self,dbPath):
        return self.run_ddb_func("database('{}').getTables()".format(dbPath))

    def show_all_dfs_database(self):
        return self.run_ddb_func("getDFSDatabases()")


################################ 其他工具 #################################

from contextlib import contextmanager
@contextmanager
def timer(name: str):
    s = time.time()
    yield
    elapsed = time.time() - s
    print(f'[{name}] {elapsed: .3f} sec')

def PrintProgress(percent, start_time):
    if percent > 0:
        res = int(50 * percent) * '#'
        end_time = time.time()
        passed_time = (end_time - start_time)
        remaining_time = passed_time*(1 - percent)/percent
        print('\r[%-50s] %s%% Passed Time: %d s,  Remaining Time: %d s' % (res, str('%.2f'%round(percent*100,2)), passed_time, remaining_time), end='')

'''**********下面是结构化风险调整所需函数**********'''
def half_life(tau = 63, window = 252):
    ''' 半衰指数加权，赋予最近的数据更高的权重
        tau: 半衰期
        window: 时间窗
    '''
    t = np.arange(window)[::-1]   # 越早的数据在越前面
    w = (1/2) **(t/tau) / sum((1/2) ** (t/tau))
    return w
    
def weighted_factor_cov(df, tau=90, window=252):
    '''采用权重指数衰减方法计算协方差矩阵'''
    w = half_life(tau, window)
    demean_df = df - df.mul(w,axis=0).sum(axis=0)   # 去均值
    df_cov = demean_df.mul(w,axis=0).T.dot(demean_df)
    return df_cov

def Newey_West_factor(df, D,tau=90, window=252):
    '''Newey-West调整'''
    f_raw = weighted_factor_cov(df,tau, window)
    
    for d in range(1,D+1):
        ac = ac_factor_cov(df,tau, window, d)
        barlett_w = 1 - d/(1+D)
        f_raw += barlett_w * (ac + ac.T)
    
    return f_raw

def ac_factor_cov(df, tau=90, window=252, d=1):
    '''计算Newey-West调整中的自协方差矩阵, 也同样采用权重指数衰减方法'''
    w = half_life(tau, window)
    demean_df = df - df.mul(w,axis=0).sum(axis=0)   # 去均值
    wd = half_life(tau, window-d)
    ac = np.array(demean_df.iloc[:-d,:].mul(wd,axis=0)).T.dot(np.array(demean_df.iloc[d:,:]))
    
    df_ac = pd.DataFrame(ac, index=df.columns, columns=df.columns) 
    
    return df_ac

def cal_factor_nw_cov(df_return,date,n=252,D=2):
    '''传入四个参数
    第一个是因子收益率矩阵，index是日期，columns是因子
    第二个是计算协方差矩阵的日期
    第三个是估计协方差矩阵的时间窗口长度，默认n=252
    第四个是nw调整的最大滞后期数，默认D=2'''
    start_date = get_previous_tradedate(date,n-1)
    df = df_return[(df_return.index >= start_date)&(df_return.index <= date)]
    df.dropna(axis=1,inplace=True)
    return Newey_West_factor(df, D,tau=90, window=n)


# 因子收益的特征值调整
def eigenfactor(mat_nw,T=100,M=3000,a=0.6):
    '''传入四个参数
    第一个是经过nw调整后的协方差矩阵估计
    第二个是模拟特征值组合的收益期数，默认T=100
    第三个是蒙特卡洛模拟的期数，默认M=3000
    第四个是调整系数，系数越大，特征值调整幅度越大，根据历史数据网格搜索默认选取参数a=0.6'''
    m = 0
    d ,V = np.linalg.eig(mat_nw)    #计算特征值和特征向量
    D = np.diag(d)
    dm_adj_list = []
    dm_list = []
    while m <= M:
        m += 1
        np.random.seed(m)
        bm = np.array([np.random.normal(0,np.sqrt(d[0]),T)])
        for i in range(1,len(d)):
            bm = np.insert(bm,i,values=np.random.normal(0,np.sqrt(d[i]),T),axis=0)
        fm = V.dot(bm)
        Fm = np.cov(fm)
        dm, Vm = np.linalg.eig(Fm)
        Dm_adj = Vm.T.dot(mat_nw).dot(Vm)
        dm_adj = np.diagonal(Dm_adj)
        dm_adj_list.append(dm_adj)
        dm_list.append(dm)
    dm_adj_df = pd.DataFrame(dm_adj_list)
    dm_df = pd.DataFrame(dm_list)
    lamd_df = dm_adj_df/dm_df
    lamd = a * (np.array(np.sqrt(lamd_df.sum()/M)) - 1) + 1
    lamd_mat = np.diag(lamd)
    D_real = lamd_mat.dot(lamd_mat).dot(D)
    eigen_adj = pd.DataFrame(V.dot(D_real).dot(V.T),index=mat_nw.columns,columns=mat_nw.columns)
    return eigen_adj


# 波动率偏误调整
def cal_factor_bs_adj(eigenfactor_mat,df_return,date,T=252,hl=42):
    '''传入五个参数
    第一个eigenfactor_mat是经过特征值调整后的协方差矩阵估计
    第二个是因子收益矩阵，df，index是日期，columns是因子
    第三个是eigenfactor_mat计算对应的日期，必须与eigenfactor_mat保持一致，理论上与传入neweywest的参数也保持一致
    第四个T是波动率调整加权平均的窗口期，默认T=252
    第五个hl是权重半衰期，默认hl=42'''
    start_date = get_previous_tradedate(date,n=T-1)
    adj_dates = get_tradedays(start_date,date)
    Bt = []
    for oneday in adj_dates:
        oneday_return = df_return.loc[oneday]
        oneday_std = df_return.loc[get_previous_tradedate(oneday,251):oneday].std()   # 用因子过去一年的收益率标准差来当作波动率的预测
        oneday_bk = oneday_return/oneday_std
        Bt.append(np.sqrt((oneday_bk**2).sum()/len(oneday_bk)))
    halflife = half_life(tau=hl,window=T)
    bs_adj_coe = np.sqrt(([x**2 for x in Bt] * halflife).sum())
    bs_adj_mat = bs_adj_coe**2 * eigenfactor_mat
    return bs_adj_mat

# 估计个股特异性收益的协方差矩阵并对其做newey-west调整
def specific_cov(df,tau=90, window=252):
    '''采用权重指数衰减方法计算特异性收益协方差矩阵，传入的收益序列长度必须等于window，且不存在缺失值
    第一个参数df传入特异性收益df，index为日期，columns为code'''
    w = half_life(tau, window)
    demean_df = df - df.mul(w,axis=0).sum(axis=0)   # 去均值
    cov_mat = demean_df.mul(w,axis=0).T.dot(demean_df)
    cov_mat = np.diag(np.diagonal(cov_mat))
    cov_df = pd.DataFrame(cov_mat,index=df.columns,columns=df.columns)
    return cov_df

def Newey_west_specific_cov(df ,D ,tau=90, window=252):
    '''针对特异性收益的Newey-West调整'''
    f_raw = specific_cov(df ,tau ,window)
    
    for d in range(1,D+1):
        ac = ac_specific_cov(df,tau, window, d)
        barlett_w = 1 - d/(1+D)
        f_raw += barlett_w * (ac + ac.T)
    
    return f_raw

def ac_specific_cov(df, tau=90, window=252, d=1):
    '''计算Newey-West调整中的自协方差矩阵, 也同样采用权重指数衰减方法,最后返回滞后t期的自相关协方差的对角阵'''
    w = half_life(tau, window)
    demean_df = df - df.mul(w,axis=0).sum(axis=0)   # 去均值
    wd = half_life(tau, window-d)
    ac = np.array(demean_df.iloc[:-d,:].mul(wd,axis=0)).T.dot(np.array(demean_df.iloc[d:,:]))

    ac = np.diag(np.diagonal(ac))
    
    df_ac = pd.DataFrame(ac, index=df.columns, columns=df.columns)

    
    return df_ac

def cal_specific_nw_cov(df_return,date,hl=90,n=252,D=2):
    '''传入四个参数
    第一个是个股特异性收益率矩阵，index是日期，columns是因子
    第二个是计算协方差矩阵的日期
    第三个参数是半衰期，默认90天
    第四个是估计协方差矩阵的时间窗口长度，默认n=252
    第五个是nw调整的最大滞后期数，默认D=5'''
    start_date = get_previous_tradedate(date,n-1)
    df = df_return[(df_return.index >= start_date)&(df_return.index <= date)]                                                
    df = df.loc[:,df.apply(no_null_count) >200]
    df.fillna(df.mean(),inplace=True)
    return Newey_west_specific_cov(df ,D ,tau=hl, window=n)

def specific_bayes_adj(after_nw_mat,w_cap,date,q=1):
    '''贝叶斯压缩
    传入四个参数
    第一个after_nw_mat为经过neweywest调整后的特异性收益协方差矩阵
    第二个w_cap是个股历史的市值序列，index为['code','date']
    第三个date是计算贝叶斯调整的日期，必须和newey_west调整的日期对齐
    第四个是压缩系数，默认经验取值q=1
    '''
    after_nw_mat_reshape = pd.DataFrame(np.diagonal(after_nw_mat),index=after_nw_mat.index,columns=['predict_vol'])
    w_cap_reshape = w_cap[w_cap.index.get_level_values(1)==date].reset_index()[['code','w_cap']].set_index('code')
    bayes_df = pd.merge(after_nw_mat_reshape,w_cap_reshape,left_index=True,right_index=True,how='left')
    bayes_df['bin'] = pd.qcut(bayes_df.w_cap,list(np.arange(0,1.1,0.1)),labels=list(np.arange(1,11,1)))
    bins_mean = bayes_df[['bin','predict_vol']].groupby('bin').mean().rename(columns={'predict_vol':'group_mean_vol'})
    bayes_df = pd.merge(bayes_df,bins_mean,left_on='bin',right_index=True,how='left')
    bayes_adj_df = pd.DataFrame()
    for bin_number in range(1,11):
        bayes_each = bayes_df[bayes_df['bin'] == bin_number]
        bayes_each['vn'] = q*abs(bayes_each['predict_vol'] - bayes_each['group_mean_vol'])/(q*abs(bayes_each['predict_vol'] - bayes_each['group_mean_vol'])+bayes_each['predict_vol'].std())
        bayes_adj_df = pd.concat([bayes_adj_df,bayes_each])
    bayes_adj_df['bayes_adj_vol'] = bayes_adj_df['vn']*bayes_adj_df['group_mean_vol']+(1-bayes_adj_df['vn'])*bayes_adj_df['predict_vol']
    bayes_adj_mat = pd.DataFrame(np.diag(bayes_adj_df['bayes_adj_vol']),index=bayes_adj_df.index,columns=bayes_adj_df.index)
    return bayes_adj_mat

def specific_bs_adj(bayes_adj_mat,df_return,date,T=252,hl=42):
    '''传入五个参数
    第一个bayes_adj_mat是经过贝叶斯压缩后的特异性收益协方差矩阵估计
    第二个是个股特异性收益矩阵specific_return，index是日期，columns是code
    第三个是bayes_adj_mat计算对应的日期，必须与bayes_adj_mat保持一致，理论上与传入neweywest的参数也保持一致
    第四个T是波动率调整加权平均的窗口期，默认T=252
    第五个hl是权重半衰期，默认hl=42'''
    start_date = get_previous_tradedate(date,n=T-1)
    adj_dates = get_tradedays(start_date,date)
    Bt = []
    for oneday in adj_dates:
        oneday_return = df_return.loc[oneday]
        oneday_std = df_return.loc[get_previous_tradedate(oneday,251):oneday].std()   # 用因子过去一年的收益率标准差来当作波动率的预测
        oneday_bk = oneday_return/oneday_std
        Bt.append(np.sqrt((oneday_bk**2).sum()/len(oneday_bk)))
    halflife = half_life(tau=hl,window=T)
    bs_adj_coe = np.sqrt(([x**2 for x in Bt] * halflife).sum())
    bs_adj_mat = bs_adj_coe**2 * bayes_adj_mat
    return bs_adj_mat


############################### 滚动计算beta ################################
def calc_beta(s: np.ndarray, m: np.ndarray):
    x = np.concatenate([np.ones_like(m), m], axis=1)
    b = np.linalg.pinv(x.T.dot(x)).dot(x.T).dot(s)
    return b[1]

def rolling_calc_beta(s_df: pd.DataFrame, m_df: pd.DataFrame, period: int, halflife_tau=63, start_date='2014-01-01', end_date=None):
    s_df = s_df.loc[start_date:end_date]
    m_df = m_df.loc[start_date:end_date]
    w = half_life(tau = halflife_tau, window = period)
    result = np.ndarray(shape=s_df.shape, dtype=float)
    l = s_df.shape[0]
    result[0:period - 1, :] = np.nan
    s_arr = s_df.values
    m_arr = m_df.values
    for row in range(period, l):
        c = s_arr[row - period:row, :]
        aa = np.concatenate([np.multiply(x,w).reshape(period,1) for x in c.T],axis=1)
        bb = np.multiply(m_arr[row - period:row].reshape(period),w).reshape(period,1)
        result[row, :] = calc_beta(aa, bb)
    return pd.DataFrame(data=result, index=s_df.index, columns=s_df.columns)

def calc_hsigma(s: np.ndarray, m: np.ndarray):
    x = np.concatenate([np.ones_like(m), m], axis=1)
    b = np.linalg.pinv(x.T.dot(x)).dot(x.T).dot(s)
    return np.std(s - np.dot(x,b), axis=0)

def rolling_calc_hsigma(s_df: pd.DataFrame, m_df: pd.DataFrame, period: int, halflife_tau=63, start_date='2014-01-01', end_date=None):
    s_df = s_df.loc[start_date:end_date]
    m_df = m_df.loc[start_date:end_date]
    w = half_life(tau = halflife_tau, window = period)
    result = np.ndarray(shape=s_df.shape, dtype=float)
    l = s_df.shape[0]
    result[0:period - 1, :] = np.nan
    s_arr = s_df.values
    m_arr = m_df.values
    for row in range(period, l):
        c = s_arr[row - period:row, :]
        aa = np.concatenate([np.multiply(x,w).reshape(period,1) for x in c.T],axis=1)
        bb = np.multiply(m_arr[row - period:row].reshape(period),w).reshape(period,1)
        result[row, :] = calc_hsigma(aa, bb)
    return pd.DataFrame(data=result, index=s_df.index, columns=s_df.columns)
    
def winsorize(a, limit = 3):
    mean = np.mean(a.replace(np.inf,np.nan).replace(-np.inf,np.nan))
    std = np.std(a.replace(np.inf,np.nan).replace(-np.inf,np.nan))
    a_new = a.copy()
    a_new[a < mean - std * limit] = mean - std*limit
    a_new[a > mean + std * limit] = mean + std*limit
    return a_new

# Z-score标准化处理
def normalize(a):
    mean = np.mean(a)
    std = np.std(a)
    a_new = (a - mean)/std
    return a_new

def standard_factor_byindex(data):
    data_new = data.copy()
    for i in data_new.index:
        data_new.loc[i] = normalize(winsorize(data_new.loc[i]))
    return data_new

def standard_factor_bycolumns(data):
    data_new = data.copy()
    for i in data_new.columns:
        data_new[i] = normalize(winsorize(data_new[i]))
    return data_new