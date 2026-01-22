from contextlib import contextmanager
import time
import os
import pandas as pd
from shutil import copy
import datetime
# import xlwings as xw


@contextmanager
def timer(name: str):
    s = time.time()
    yield
    elapsed = time.time() - s
    print(f'[{name}] {elapsed: .3f} sec')
    
def generate_fileName(fileName, dir, fileType='parquet'):
    # 生成fileName在dir文件夹下，带版本编号的文件名
    num_new = 1
    allfile = os.listdir(dir)
    for file in allfile:
        if file.startswith(fileName + "_v"):
            try:
                num = int(file.split('.')[0].split('v')[1])
                if num >= num_new:
                    num_new = num + 1
            except:
                pass
    return f'{fileName}_v{str(num_new)}.{fileType}'

def generate_file(file, fileName, dir, index=False):
    # 生成带版本编号的文件
    fileName_v = generate_fileName(fileName, dir)
    file.to_excel('{}{}'.format(dir, fileName_v), index=index)

def get_latest_file(fileName, dir, fileType='parquet'):
    allfile = os.listdir(dir)
    latest_num = -1
    for file in allfile:
        if file.startswith(fileName + '_v') and file.endswith(fileType):
            num = int(file.split('.')[0].split('v')[1])
            if num > latest_num:
                latest_num = num
    if latest_num == -1:
        raise Exception('未在{}找到{}'.format(dir, fileName))
    else:
        return f'{fileName}_v{str(latest_num)}.{fileType}'

def locate_tradeDate(current_date, trading_calendar_path='./config/trading_calendar.xlsx'):

    try:
        current_date_dt = pd.to_datetime(current_date)
    except:
        return False, False, False
    
    trading_calendar = pd.read_excel(trading_calendar_path)
    try:
        current_date_location = trading_calendar['A股交易日历'].tolist().index(current_date_dt)
        pre_tradeDate_location = current_date_location
        pre_tradeDate = current_date_location = trading_calendar['A股交易日历'].tolist()[pre_tradeDate_location-1].strftime('%Y%m%d')
        current_date = current_date_dt.strftime('%Y%m%d')
        return True, current_date, pre_tradeDate
    except:
        return False, False, False

def show_options(options, multiple_choice=False):
    # 展示选项
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    if multiple_choice:
        print('all: Execute all options listed')
    for i in range(len(options)):
        print(str(i) + " " + options[i])
    print('exit: Return to previous menu')
    print('')

def read_user_option(options, desc, multiple_choice=False):

    def _single_user_option(options, option_num):
        try:
            option = options[int(option_num)]
            return option
        except:
            print('Option not existed:{}. Please try again...'.format(option_num))
            return True
            
    option = True
    # 读入用户指令
    while option is True:
        option_num = input(desc)
        if option_num == 'exit':
            return True
        if multiple_choice:
            if option_num == 'all':
                option = options
            else:
                option_num_list = option_num.split(',')
                option = []
                for i in option_num_list:  
                    single_option = _single_user_option(options, i)
                    if single_option == True:
                        option = True
                    else:
                        option.append(single_option)
           
        else:
            option = _single_user_option(options, option_num)
            
    print('')

    return option

def make_user_option_interface(options, desc='请输入选项:', multiple_choice=False):
    # 展示选项并读入用户指令
    show_options(options, multiple_choice=multiple_choice)
    return read_user_option(options, desc, multiple_choice=multiple_choice)

def make_path(path):
    # 生成目标文件夹
    if not os.path.exists(path):
        os.mkdir(path)

def read_latest_file(fileName, path, fileType='parquet'):
    # 读取最新文件
    latest_fileName = get_latest_file(fileName, path, fileType=fileType)
    if fileType == 'parquet':
        latest_df = pd.read_parquet(path + latest_fileName)
    else:
        latest_df = pd.read_excel(path + fileName, dtype={'其他编号':str, '交易确认书编号':str, '补充确认书编号':str})
    return latest_df

def save_file_v(fileName, df, path, fileType='parquet'):
    # 储存带版本号的文件
    fileName_v = generate_fileName(fileName, path, fileType=fileType)
    df.to_parquet(path + fileName_v)
    return

def copy_or_replace(from_path_name, to_path, to_name):
    # 将from_path_name对应文件拷贝到to_path, 并重命名为to_name. 若存在则替换.
    if os.path.exists(to_path + to_name):
        os.remove(to_path + to_name)
    copy(from_path_name, to_path + to_name)

    return 
   
def logger(command_num, current_date):
    operation_dict = {"0": "Pre_booking",
                    "1": "Booking",
                    "2": "Initialize",
                    "3": "Execute Event",
                    "4": "Contract Clearing",
                    "5": "Valuation",
                    "6": "Adjust Data",
                    "7": "Summarize Exchange Position",
                    "8": "Generate Position Monitor",
                    "9": "Generate MTM Monitor",
                    "10": "Generate Daily Statistic",
                    "11": "Generate Daily Report",
                    "12": "Generate Client Valuation Report",
                    "13": "Generate Settlement Notice",
                    "14": "Mail Sender",
                    "all": "DO all(1~10)",
                    "exit": "Exit the Program",
                    "switch date": "Switch to New Trade Date"}

    try:
        log_file = pd.read_excel(f'./log/{current_date}/user_command_log.xlsx')
    except:
        log_file = pd.DataFrame(columns=['time', 'user', 'command_num', 'command', 'detail'])
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    log = pd.Series({'time':current_time, 'user':'jupyter user(probably Ziyun)', 'command_num':str(command_num), 'command':operation_dict[str(command_num)], 'detail':''})
    log_file.loc[len(log_file)] = log
    log_file.to_excel(f'./log/{current_date}/user_command_log.xlsx', index=False)

def find_all_file(path, keyword=None):
    '''
    找到path路径下带有keyword关键字的全部文件, 并返回包含完整路径的文件list. keyword可以为None, 字符串或者元素为字符串的list
    '''
    allfile = os.listdir(path)
    allfile_keyword = []
    if type(keyword) == str:
        keyword = [keyword]
    for file in allfile:
        if keyword is None:
            allfile_keyword.append(path+file)
        else:
            f = True
            for key in keyword:
                if not(key in file):
                    f = False
            if f:
                allfile_keyword.append(path+file)
    return allfile_keyword

def combine_all_file(allfile):
    combined_df = pd.DataFrame()
    for file in allfile:
        try:
            this_df = pd.read_excel(file)
            combined_df = pd.concat([combined_df, this_df])
        except:
            pass
    combined_df.index = [i for i in range(len(combined_df))]
    return combined_df

def read_target_file(fileName, dtype={}, header=0, sep=',', **kwargs):
    '''根据./management/文件路径配置, 读取指定文件, 支持xlsx及csv'''
    path_list = pd.read_excel('./management/文件路径配置.xlsx', index_col='FileName')
    file_path = path_list.loc[fileName, 'Path']
    sheet_name = None
    if len(kwargs) > 0:
        if 'current_date' in kwargs.keys():
            file_path = file_path.format(current_date=kwargs['current_date'])
            
        if 'sheet_name' in kwargs.keys():
            sheet_name = kwargs['sheet_name']

    file_type = file_path.split('.')[-1]

    if (file_type == 'xlsx') or (file_type == 'xls'):
        try:
            if sheet_name is None:
                df = pd.read_excel(file_path, dtype=dtype, header=header)
            else:
                df = pd.read_excel(file_path, dtype=dtype, sheet_name=sheet_name, header=header)
        except:
            print(f'{fileName}: File not found!')
            return True
    elif file_type == 'csv':
        try:
            if sheet_name is None:
                df = pd.read_csv(file_path, dtype=dtype, header=header, sep=sep)
            else:
                df = pd.read_csv(file_path, dtype=dtype, sheet_name=sheet_name, header=header, sep=sep)
        except:
            print(f'{fileName}: File not found!')
            return True
    else:
        print('File type not supported, or not a file')
        return True
    return df

def get_target_path(name, **kwargs):
    '''根据./management/文件路径配置, 返回指定路径位置'''
    path_list = pd.read_excel('E:\Index_Arbitrage\config\文件路径配置.xlsx', index_col='FileName')
    try:
        path = path_list.loc[name, 'Path']
        if len(kwargs) > 0:
            if 'current_date' in kwargs.keys():
                path = path.format(current_date=kwargs['current_date'])
        return path
    except:
        return False
      
def select_target_dataframe(df, conditions={}, reverse_conditions={}):
    '''根据给定条件筛选dataframe'''    

    for field in conditions:
        df = df.loc[df[field].apply(lambda x: x in conditions[field])]
        
    for field in reverse_conditions:
        df = df.loc[df[field].apply(lambda x: not(x in reverse_conditions[field]))]
    return df

def get_BBGticker_mapping():
    '''获取BBG ticker映射表及标的货币映射表'''
    hk_BBGticker_mapping = read_target_file('港股BBG代码映射', dtype={'标的代码':str})[['标的代码', 'BBG Ticker']]
    hk_BBGticker_mapping['货币'] = 'HKD' 
    us_BBGticker_mapping = read_target_file('美股BBG代码映射', dtype={'标的代码':str})[['标的代码', 'BBG Ticker']]
    us_BBGticker_mapping['货币'] = 'USD'
    cn_BBGticker_mapping = read_target_file('A股BBG代码映射', dtype={'标的代码':str})[['标的代码', 'BBG Ticker']]
    cn_BBGticker_mapping['货币'] = 'CNH'
    BBGticker = pd.concat([hk_BBGticker_mapping, us_BBGticker_mapping, cn_BBGticker_mapping])
    # 数据查重去重
    ticker_count = BBGticker['标的代码'].value_counts()  
    ticker_count_duplicate = ticker_count.loc[ticker_count > 1]
    if len(ticker_count_duplicate) > 0:
        print('WARNING!!! The following codes apear more than once! Please check to avoid mistake in valuation!')
        
    BBGticker_mapping = BBGticker.drop_duplicates(subset='标的代码').set_index('标的代码')['BBG Ticker'].to_dict()
    currency_mapping = BBGticker.drop_duplicates(subset='标的代码').set_index('标的代码')['货币'].to_dict()
          
    return BBGticker_mapping, currency_mapping


def any_to_code(code):
    return code[:6]

def code_to_wind(code):
    if code.startswith('0'):
        return code + '.SZ'
    elif code.startswith('3'):
        return code + '.SZ'
    elif code.startswith('6'):
        return code + '.SH'
    else:
        return code
    
def code_to_jq(code):
    if code.startswith('0'):
        return code + '.XSHE'
    elif code.startswith('3'):
        return code + '.XSHE'
    elif code.startswith('6'):
        return code + '.XSHG'
    else:
        return code

    

def bbg_to_jq(bbg_code, asset_type, exchange_code=None):
    index_mapping = {'CSI1000 Index':'000852.XSHG',
                     'SH000905 Index':'000905.XSHG',
                     'SHSZ300 Index': '000300.XSHG'}

    if asset_type == 'stock':
        code = bbg_code.split(' ')[0]
        return f"{code}.XSHG" if exchange_code == "XSHG" else f"{code}.XSHE"
    
    elif asset_type == 'index':
        if bbg_code in index_mapping:
            return index_mapping[bbg_code]
        else:
            print(f'[WARNING] {bbg_code} 指数未找到jq代码映射')
            return
    else:
        print(f'[WARNING] 不支持的资产类型: {asset_type}')
        return
        



    
    
    