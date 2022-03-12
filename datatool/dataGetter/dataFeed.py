import rqdatac as rq
from wtpy.WtCoreDefs import WTSBarStruct, WTSTickStruct
from wtpy.wrapper import WtDataHelper
import pandas as pd
from tqdm import tqdm
import os
class Ifeed(object):
    def __init__(self):
        self.dthelper = WtDataHelper()
        self.period_map = {"m1":"min1","m5":"min5","d":"day","tick":"ticks"}
        self.frequency_map = {
            "m1":"1m",
            "m5":"5m",
            "d":"1d",
        }
    
    def get_tick(self,symbol,start_date=None,end_date=None):
        return
    
    def get_bar(self,symbol,frequency,start_date=None,end_date=None):
        return
    
    def parse_code(self,code):
        items = code.split(".")
        return items[0],items[1],items[2]

    def code_std(self,stdCode:str):
        stdCode = stdCode.upper()
        items = stdCode.split(".")
        exchg = self.exchgStdToRQ(items[0])
        if len(items) == 2:
            # 简单股票代码，格式如SSE.600000
            return items[1] + "." + exchg
        elif items[1] in ["IDX","ETF","STK","OPT"]:
            # 标准股票代码，格式如SSE.IDX.000001
            return items[2] + "." + exchg
        elif len(items) == 3:
            # 标准期货代码，格式如CFFEX.IF.2103
            if items[2] != 'HOT':
                return ''.join(items[1:])
            else:
                return items[1] + "88"
            
    def cover_d_bar(self,df):
        count = len(df)
        BUFFER = WTSBarStruct * count
        buffer = BUFFER()
        for index, row in tqdm(df.iterrows()):
            curBar = buffer[index]
            curBar.date = int(row["date"])
            curBar.open = float(row["open"])
            curBar.high = float(row["high"])
            curBar.low = float(row["low"])
            curBar.close = float(row["close"])
            curBar.vol = float(row["vol"])
            curBar.money = float(row["money"])
            curBar.hold = float(row["hold"])
        return buffer
    
    def cover_m_bar(self,df):
        count = len(df)
        BUFFER = WTSBarStruct * count
        buffer = BUFFER()
        for index, row in tqdm(df.iterrows()):
            curBar = buffer[index]
            curBar.time = (int(row["date"])-19900000)*10000 + int(row["time"])
            curBar.open = float(row["open"])
            curBar.high = float(row["high"])
            curBar.low = float(row["low"])
            curBar.close = float(row["close"])
            curBar.vol = float(row["vol"])
            curBar.money = float(row["money"])
            curBar.hold = float(row["hold"])
        return buffer
        
    def cover_tick(self,df):
        count = len(df)
        BUFFER = WTSTickStruct * count
        buffer = BUFFER()
        for index, row in tqdm(df.iterrows()):
            curTick = buffer[index]
            curTick.exchg = bytes(row["exchg"],'utf-8')
            curTick.code = bytes(row["code"],'utf-8')
            curTick.price = float(row["price"])
            curTick.open = float(row["open"])
            curTick.high = float(row["high"])
            curTick.low = float(row["low"])
            curTick.settle_price = float(row["settle_price"])
            curTick.total_volume = float(row["total_volume"])
            curTick.volume = float(row["volume"])
            curTick.total_turnover = float(row["total_turnover"])
            curTick.turn_over = float(row["turn_over"])
            curTick.open_interest = float(row["open_interest"])
            curTick.diff_interest = float(row["diff_interest"])
            curTick.trading_date = int(row["trading_date"])
            curTick.action_date = int(row["action_date"])
            curTick.action_time = int(int(row["action_time"]) / 1000)
            curTick.pre_close = float(row["pre_close"])
            curTick.pre_settle = float(row["pre_settle"])
            curTick.pre_interest = float(0.0)
            for x in range(0,5):
                curTick.bid_prices[x] = float(row["bid_" + str(x+1)])
                curTick.bid_qty[x] = float(row["bid_qty_" + str(x+1)])
                curTick.ask_prices[x] = float(row["ask_" + str(x+1)])
                curTick.ask_qty[x] = float(row["ask_qty_" + str(x+1)])
        return buffer
        
    def bar_df_to_dsb(self,df,dsb_file,period):
        if "d" in period:
            buffer = self.cover_d_bar(df)
        elif "m" in period:
            buffer = self.cover_m_bar(df)      
        self.dthelper.store_bars(barFile=dsb_file,firstBar=buffer,count=len(buffer),period=period)

    def tick_df_to_dsb(self,df,dsb_file):
        buffer = self.cover_tick(df)
        self.dthelper.store_ticks(tickFile=dsb_file, firstTick=buffer, count=len(buffer))
        
    # 新下的数据会覆盖旧的数据
    def store_bin_bar(self,storage_path,code,start_date=None,end_date=None,frequency="1m",col_map=None):
        df = self.get_bar(code,start_date,end_date,frequency)
        period = self.period_map[frequency]
        save_path = os.path.join(storage_path,"bin",period)
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        dsb_path = os.path.join(save_path,f"{code}_{frequency}.dsb")
        self.bar_df_to_dsb(df,dsb_path,frequency)
        
    def store_bin_tick(self,storage_path,code,start_date=None,end_date=None,col_map=None):
        df = self.get_tick(code,start_date,end_date)
        save_path = os.path.join(storage_path,"bin","ticks")
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        g = df.groupby("trading_date")
        for trading_date,g_df in g:
            g_df = g_df.reset_index()
            dsb_path = os.path.join(save_path,f"{code}_tick_{trading_date}.dsb")
            self.tick_df_to_dsb(g_df,dsb_path)
    
    # 除了转换为dsb格式，还会按照his的格式进行存储
    def store_his_bar(self,storage_path,code,start_date=None,end_date=None,frequency="1m",skip_saved=False):
        exchange,pid,month = self.parse_code(code)
        if frequency not in self.frequency_map.keys():
            print("周期只能为m1、m5或d,回测或实盘中会自动拼接")
        period = self.period_map[frequency]
        save_path = os.path.join(storage_path,"his",period,exchange)
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        dsb_name = f"{pid}{month}.dsb"
        dsb_path = os.path.join(save_path,dsb_name)
        if skip_saved:
            saved_list = os.listdir(save_path)
            if dsb_name in saved_list:
                print(f"重复数据，跳过{dsb_name}")
                return
        df = self.get_bar(code,start_date,end_date,frequency)
        self.bar_df_to_dsb(df,dsb_path,frequency)
        
    def store_his_tick(self,storage_path,code,start_date=None,end_date=None,skip_saved=False):
        exchange,pid,month = self.parse_code(code)
        # 分天下载，避免内存超出
        for date in pd.date_range(start_date,end_date):
            save_path = os.path.join(storage_path,"his","ticks",exchange,date.strftime('%Y%m%d'))
            if not os.path.exists(save_path):
                os.makedirs(save_path)
            dsb_name = f"{pid}{month}.dsb"
            if skip_saved:
                saved_list = os.listdir(save_path)
                if dsb_name in saved_list:
                    print(f"重复数据，跳过{dsb_name}")
                    continue
            t_day = date.strftime('%Y.%m.%d')
            df = self.get_tick(code,t_day,t_day)
            if (df is None) or (df.empty):
                print(f"{date}:{code}没有数据")
                continue
            dsb_path = os.path.join(save_path,f"{pid}{month}.dsb")
            self.tick_df_to_dsb(df,dsb_path)
            
    def bar_dsb_to_csv(self,binFolder,csvFolder):
        self.dthelper.dump_bars(binFolder, csvFolder)
    
    def tick_dsb_to_csv(self,binFolder,csvFolder):
        self.dthelper.dump_ticks(binFolder, csvFolder)
        
class RqFeed(Ifeed):
    def __init__(self,user=None,passwd=None):
        super().__init__()
        self.rq = rq
        self.rq.init(user,passwd)
        self.bar_col_map = {
            "date":"date",
            "time":"time",
            "open":"open",
            "high":"high",
            "low":"low",
            "close":"close",
            "total_turnover":"money",
            "volume":"vol",
            "open_interest":"hold",
        }
        self.tick_col_map = {
            "code":"code",
            "exchg":"exchg",
            "last":"price",
            "open":"open",
            "high":"high",
            "low":"low",
            "volume":"total_volume",
            "vol":"volume",
            "total_turnover":"total_turnover",
            "turn_over":"turn_over",
            "open_interest":"open_interest",
            "diff_interest":"diff_interest",
            "trading_date":"trading_date",
            "date":"action_date",
            "time":"action_time",
            "prev_close":"pre_close",
            "settle_price":"settle_price",
            "prev_settlement":"pre_settle",
        }
        for i in [1,2,3,4,5]:
            self.tick_col_map[f"a{i}"] = f"ask_{i}"
            self.tick_col_map[f"b{i}"] = f"bid_{i}"
            self.tick_col_map[f"a{i}_v"] = f"ask_qty_{i}"
            self.tick_col_map[f"b{i}_v"] = f"bid_qty_{i}"
        
    def exchgStdToRQ(self,exchg:str) -> str:
        if exchg == 'SSE':
            return "XSHG"
        elif exchg == 'SZSE':
            return "XSHE"
        else:
            return exchg
    
    def code_std(self,stdCode:str):
        stdCode = stdCode.upper()
        items = stdCode.split(".")
        exchg = self.exchgStdToRQ(items[0])
        if len(items) == 2:
            # 简单股票代码，格式如SSE.600000
            return items[1] + "." + exchg
        elif items[1] in ["IDX","ETF","STK","OPT"]:
            # 标准股票代码，格式如SSE.IDX.000001
            return items[2] + "." + exchg
        elif len(items) == 3:
            # 标准期货代码，格式如CFFEX.IF.2103
            if items[2] != 'HOT':
                return ''.join(items[1:])
            else:
                return items[1] + "88"
        
    def get_tick(self,code,start_date=None,end_date=None):
        symbol = self.code_std(code)
        exchange,pid,month = self.parse_code(code)
        df = self.rq.get_price(symbol,start_date=start_date,end_date=end_date,frequency="tick")
        if df is None:
            return None
        df = df.reset_index()
        df["exchg"] = code.split(".")[0]
        df["code"] = code.split(".")[1] + code.split(".")[2]
        #改一下时间的格式
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df["date"] =  df["datetime"].dt.strftime("%Y%m%d")
            df["time"] =  df["datetime"].dt.strftime("%H%M%S%f")
            df["trading_date"] =  df["trading_date"].dt.strftime("%Y%m%d")
        else:
            df["date"] =  df["date"].astype("str")
            df["time"] = "00:00:00"
            
        multiplier = self.rq.futures.get_contract_multiplier(pid.upper(),start_date,end_date)["contract_multiplier"].max()
        df["settle_price"] = ((df["total_turnover"] / df["volume"]) * multiplier).fillna(0.0)
        df["turn_over"] = (df["total_turnover"] - df["total_turnover"].shift(1)).fillna(0.0)
        df["vol"] = (df["volume"] - df["volume"].shift(1)).fillna(0.0)
        df["diff_interest"] = (df["open_interest"] - df["open_interest"].shift(1)).fillna(0.0)
        df = df[[col for col in self.tick_col_map.keys()]]
        df = df.rename(columns=self.tick_col_map)
        return df
    
    def get_bar(self, code, start_date=None,end_date=None,frequency="1m"):
        if frequency not in self.frequency_map.keys():
            print("周期只能为m1、m5或d,回测或实盘中会自动拼接")
        rq_frequency = self.frequency_map[frequency]
        symbol = self.code_std(code)
        df = self.rq.get_price(symbol,start_date=start_date,end_date=end_date,frequency=rq_frequency)
        if df is None:
            return None
        df = df.reset_index()
        #改一下时间的格式
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df["date"] =  df["datetime"].dt.strftime("%Y%m%d")
            df["time"] =  df["datetime"].dt.strftime("%H%M%S")
        else:
            df["date"] =  df["date"].astype("str")
            df["time"] = "00:00:00"
        df = df[[col for col in self.bar_col_map.keys()]]
        df = df.rename(columns=self.bar_col_map)
        return df

class GqdbFeed(Ifeed):
    def __init__(self,host="localhost",port=8900,user="admin",pwd="123456"):
        super().__init__()
        from gqdb_sdk.client import session
        self.s = session(host,port,user,pwd)
        self.bar_col_map = {
            "date":"date",
            "time":"time",
            "open":"open",
            "high":"high",
            "low":"low",
            "close":"close",
            "total_turnover":"money",
            "volume":"vol",
            "open_interest":"hold",
        }
        self.tick_col_map = {
            "code":"code",
            "exchg":"exchg",
            "last":"price",
            "open":"open",
            "high":"high",
            "low":"low",
            "volume":"total_volume",
            "vol":"volume",
            "total_turnover":"total_turnover",
            "turn_over":"turn_over",
            "open_interest":"open_interest",
            "diff_interest":"diff_interest",
            "trading_date":"trading_date",
            "date":"action_date",
            "time":"action_time",
            "prev_close":"pre_close",
            "settle_price":"settle_price",
            "prev_settlement":"pre_settle",
        }
        for i in [1,2,3,4,5]:
            self.tick_col_map[f"a{i}"] = f"ask_{i}"
            self.tick_col_map[f"b{i}"] = f"bid_{i}"
            self.tick_col_map[f"a{i}_v"] = f"ask_qty_{i}"
            self.tick_col_map[f"b{i}_v"] = f"bid_qty_{i}"
        
        self.frequency_map = {
            "m1":"1m",
            "m5":"5m",
            "d":"1d",
        }
        
        self.multiple_map = {'A': 10.0, 'AG': 15.0, 'AL': 5.0, 'AP': 10.0, 'AU': 1000.0, 'B': 10.0, 'BB': 500.0, 'BC': 5.0,
            'BU': 10.0, 'C': 10.0, 'CF': 5.0, 'CJ': 5.0, 'CS': 10.0, 'CU': 5.0, 'CY': 5.0, 'EB': 5.0,
            'EG': 10.0, 'FB': 10.0, 'FG': 20.0, 'FU': 10.0, 'HC': 10.0, 'I': 100.0, 'IC': 200.0, 'IF': 300.0,
            'IH': 300.0, 'J': 100.0, 'JD': 10.0, 'JM': 60.0, 'JR': 20.0, 'L': 5.0, 'LH': 16.0, 'LR': 20.0,
            'LU': 10.0, 'M': 10.0, 'MA': 10.0, 'NI': 1.0, 'NR': 10.0, 'OI': 10.0, 'P': 10.0, 'PB': 5.0,
            'PF': 5.0, 'PG': 20.0, 'PK': 5.0, 'PM': 50.0, 'PP': 5.0, 'RB': 10.0, 'RI': 20.0, 'RM': 10.0,
            'RR': 10.0, 'RS': 10.0, 'RU': 10.0, 'SA': 20.0, 'SC': 1000.0, 'SF': 5.0, 'SM': 5.0, 'SN': 1.0,
            'SP': 10.0, 'SR': 10.0, 'SS': 5.0, 'T': 10000.0, 'TA': 5.0, 'TF': 10000.0, 'TS': 20000.0, 'UR': 20.0,
            'V': 5.0, 'WH': 20.0, 'WR': 10.0, 'Y': 10.0, 'ZC': 100.0, 'ZN': 5.0}
        
    def exchgStdToRQ(self,exchg:str) -> str:
        if exchg == 'SSE':
            return "XSHG"
        elif exchg == 'SZSE':
            return "XSHE"
        else:
            return exchg
    
    def get_tick(self,code,start_date=None,end_date=None):
        symbol = self.code_std(code)
        exchange,pid,month = self.parse_code(code)
        df = self.s.get_price(symbol,start_date=start_date,end_date=end_date,frequency="Tick")
        if df is None:
            return None
        df = df.reset_index()
        df["exchg"] = code.split(".")[0]
        df["code"] = code.split(".")[1] + code.split(".")[2]
        #改一下时间的格式
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df["date"] =  df["datetime"].dt.strftime("%Y%m%d")
            df["time"] =  df["datetime"].dt.strftime("%H%M%S%f")
            df["trading_date"] =  df["trading_date"].dt.strftime("%Y%m%d")
        else:
            df["date"] =  df["date"].astype("str")
            df["time"] = "00:00:00"
        
        multiplier = self.multiple_map.get(pid.upper(),0) 
        df["settle_price"] = ((df["total_turnover"] / df["volume"]) * multiplier).fillna(0.0)
        df["turn_over"] = (df["total_turnover"] - df["total_turnover"].shift(1)).fillna(0.0)
        df["vol"] = (df["volume"] - df["volume"].shift(1)).fillna(0.0)
        df["diff_interest"] = (df["open_interest"] - df["open_interest"].shift(1)).fillna(0.0)
        df = df[[col for col in self.tick_col_map.keys()]]
        df = df.rename(columns=self.tick_col_map)
        return df
    
    def get_bar(self, code, start_date=None,end_date=None,frequency="1m"):
        frequency = self.frequency_map[frequency]
        symbol = self.code_std(code)
        df = self.s.get_price(symbol,start_date=start_date,end_date=end_date,interval=frequency[0],frequency=frequency[1])
        if df is None:
            return None
        df = df.reset_index()
        #改一下时间的格式
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df["date"] =  df["datetime"].dt.strftime("%Y%m%d")
            df["time"] =  df["datetime"].dt.strftime("%H%M%S")
        else:
            df["date"] =  df["date"].astype("str")
            df["time"] = "00:00:00"
        df = df[[col for col in self.bar_col_map.keys()]]
        df = df.rename(columns=self.bar_col_map)
        return df

if __name__ == '__main__':
    # 从米筐下载数据
    feed = RqFeed()
    # 从GQDB下载
    # feed = GqdbFeed(host="192.168.0.132")
    # 数据存储的目录
    storage_path = "./storage"
    # 输入的代码记得区分大小写
    feed.store_his_bar(storage_path,"SHFE.ni.2201",start_date="20211225",end_date="20220101",frequency="m1",skip_saved=False)
    feed.store_his_tick(storage_path,"SHFE.ni.2201",start_date="20211225",end_date="20220101",skip_saved=False)
    # 读取dsb数据
    dtHelper = WtDataHelper()
    dtHelper.dump_bars(binFolder="./storage/his/min1/SHFE/", csvFolder="min1_csv")
    dtHelper.dump_ticks(binFolder="./storage/his/ticks/SHFE/20211227/", csvFolder="ticks_csv")