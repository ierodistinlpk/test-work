import zlib
import re
import datetime

from hyperquant.api import Platform, Sorting, Interval, Direction, OrderType
from hyperquant.clients import WSClient, Endpoint, Trade, Error, ErrorCode, \
    ParamName, WSConverter, RESTConverter, PrivatePlatformRESTClient, MyTrade, Candle, Ticker, OrderBookItem, Order, \
    OrderBook, Account, Balance


# REST

# TODO check getting trades history from_id=1
class OkexRESTConverterV1(RESTConverter):
    ''' Okex REST Converter 
	Currently supports trades and klines only
	'''
	# Main params:
    base_url = "https://www.okex.com/api/v{version}/"

    # Settings:

    # Converting info:
    # For converting to platform
    endpoint_lookup = {
        Endpoint.TRADE: "trades.do",
        Endpoint.TRADE_HISTORY: "trades.do",
        Endpoint.CANDLE: "kline.do",
    }
    param_name_lookup = {
        ParamName.SYMBOL: "symbol",
        ParamName.LIMIT: "size",
#        ParamName.IS_USE_MAX_LIMIT: None,
        ParamName.INTERVAL: "type",
        ParamName.FROM_ITEM: "since",
#        ParamName.TO_ITEM: None,
        ParamName.FROM_TIME: "since",
#        ParamName.TO_TIME: None,
        ParamName.PRICE: "price",
        ParamName.AMOUNT: "amount",
    }
    param_value_lookup = {
        # Sorting.ASCENDING: None,
        # Sorting.DESCENDING: None,
        Sorting.DEFAULT_SORTING: Sorting.ASCENDING,

        Interval.MIN_1: "1min",
        Interval.MIN_3: "3min",
        Interval.MIN_5: "5min",
        Interval.MIN_15: "15min",
        Interval.MIN_30: "30min",
        Interval.HRS_1: "1hour",
        Interval.HRS_2: "2hour",
        Interval.HRS_4: "4hour",
        Interval.HRS_6: "6hour",
        Interval.HRS_8: "8hour",
        Interval.HRS_12: "12hour",
        Interval.DAY_1: "1day",
        Interval.DAY_3: None, #"3d",
        Interval.WEEK_1: "1week",
        Interval.MONTH_1: None, #"1M",

        # By properties:
        ParamName.DIRECTION: {
            Direction.SELL: "sell",
            Direction.BUY: "buy",
        },
    }
    max_limit_by_endpoint = {
        Endpoint.TRADE: 1000,
        Endpoint.TRADE_HISTORY: 1000,
        Endpoint.ORDER_BOOK: 1000,
        Endpoint.CANDLE: 1000,
    }

    # For parsing
    item_class_by_endpoint = {
        endpoint_lookup[Endpoint.TRADE]: Trade,
        endpoint_lookup[Endpoint.TRADE_HISTORY]: Trade,
        endpoint_lookup[Endpoint.CANDLE]: Candle,
    }

    param_lookup_by_class = {
        # Error
        Error: {
            "code": "error_code",
            "msg": "result",
        },
        # Data
	Trade: {
            #"date": ParamName.TIMESTAMP,
            "tid": ParamName.ITEM_ID,
            "price": ParamName.PRICE,
            "amount": ParamName.AMOUNT,
            "date_ms": ParamName.TIMESTAMP,
            "type": ParamName.DIRECTION,
        },
	Candle: [
            ParamName.TIMESTAMP,
            ParamName.PRICE_OPEN,
            ParamName.PRICE_HIGH,
            ParamName.PRICE_LOW,
            ParamName.PRICE_CLOSE,
       	    ParamName.AMOUNT,  # only volume present
        ],
    }
	#https://github.com/okcoin-okex/API-docs-OKEx.com/blob/master/API-For-Spot-EN/Error%20Code%20For%20Spot.md
    error_code_by_platform_error_code = {
        -2014: ErrorCode.UNAUTHORIZED,
        -1121: ErrorCode.WRONG_SYMBOL,
        10000: ErrorCode.WRONG_PARAM,
    }
    error_code_by_http_status = {
        429: ErrorCode.RATE_LIMIT,
        418: ErrorCode.IP_BAN,
    }

    # For converting time
    is_source_in_milliseconds = True

    # timestamp_platform_names = [ParamName.TIMESTAMP]

    def _process_param_value(self, name, value):
        if name == ParamName.FROM_ITEM: #or name == ParamName.TO_ITEM:
            if isinstance(value, Trade):  # ItemObject):
                return value.item_id
        return super()._process_param_value(name, value)


class OkexRESTClient(PrivatePlatformRESTClient):
    # Settings:
    platform_id = Platform.OKEX
    version = "1"  # Default version
    _converter_class_by_version = {
        "1": OkexRESTConverterV1,
    }

    # State:
    ratelimit_error_in_row_count = 0

    @property
    def headers(self):
        result = super().headers
        #result["X-MBX-APIKEY"] = self._api_key
        result["Content-Type"] = "application/x-www-form-urlencoded"
        return result

    def _on_response(self, response, result):
        self.delay_before_next_request_sec = 0
        if isinstance(result, Error):
            if result.code == ErrorCode.RATE_LIMIT:
                self.ratelimit_error_in_row_count += 1
                self.delay_before_next_request_sec = 60 * 2 * self.ratelimit_error_in_row_count  # some number - change
            elif result.code == ErrorCode.IP_BAN:
                self.ratelimit_error_in_row_count += 1
                self.delay_before_next_request_sec = 60 * 5 * self.ratelimit_error_in_row_count  # some number - change
            else:
                self.ratelimit_error_in_row_count = 0
        else:
            self.ratelimit_error_in_row_count = 0

    
    def fetch_trades_history(self, symbol, limit=None, from_item=None, to_item=None,
                             sorting=None, is_use_max_limit=False, from_time=None, to_time=None,
                             version=None, **kwargs):
        return self.fetch_history(self.converter.endpoint_lookup[Endpoint.TRADE], symbol, limit, from_item, to_item,
                                  sorting, is_use_max_limit, from_time, to_time,
                                  version, **kwargs)

    def fetch_candles(self, symbol, interval, limit=None, from_time=None, to_time=None,
                      is_use_max_limit=False, version=None, **kwargs):
        endpoint = self.converter.endpoint_lookup[Endpoint.CANDLE]
        param_name_lookup=self.converter.param_name_lookup
        params = {
            param_name_lookup[ParamName.SYMBOL]: symbol,
            param_name_lookup[ParamName.INTERVAL]: interval,
            param_name_lookup[ParamName.LIMIT]: limit,
            param_name_lookup[ParamName.FROM_TIME]: from_time,
        }
        result = self._send("GET", endpoint, params, version, **kwargs)
        return result

    
# WebSocket

class OkexWSConverterV1(WSConverter):
    # Main params:
    base_url = "wss://real.okex.com:10440"

    #IS_SUBSCRIPTION_COMMAND_SUPPORTED = False

    supported_endpoints = [Endpoint.TRADE, Endpoint.CANDLE]
    symbol_endpoints = [Endpoint.TRADE, Endpoint.CANDLE]
    #supported_symbols = ['ltc_btc', 'eth_btc', 'etc_btc', 'bch_btc', 'btc_usdt', 'eth_usdt', 'ltc_usdt', 'etc_usdt', 'bch_usdt', 'etc_eth', 'bt1_btc', 'bt2_btc', 'btg_btc', 'qtum_btc', 'hsr_btc', 'neo_btc', 'gas_btc', 'qtum_usdt', 'hsr_usdt', 'neo_usdt', 'gas_usdt']
    supported_symbols = ['ltc_btc', 'eth_btc']
    interval_endpoints= {Endpoint.CANDLE}
    supported_intervals=[Interval.MIN_1, Interval.MIN_3, Interval.MIN_5, Interval.MIN_15, Interval.MIN_30, Interval.HRS_1, Interval.HRS_2, Interval.HRS_4, Interval.HRS_6, Interval.HRS_8, Interval.HRS_12, Interval.DAY_1, Interval.WEEK_1]
    subscribed_interval=None
    param_value_lookup = {
        Interval.MIN_1: "1min",
        Interval.MIN_3: "3min",
        Interval.MIN_5: "5min",
        Interval.MIN_15: "15min",
        Interval.MIN_30: "30min",
        Interval.HRS_1: "1hour",
        Interval.HRS_2: "2hour",
        Interval.HRS_4: "4hour",
        Interval.HRS_6: "6hour",
        Interval.HRS_8: "8hour",
        Interval.HRS_12: "12hour",
        Interval.DAY_1: "1day",
        Interval.WEEK_1: "1week",
    }

    
    # Settings:

    # Converting info:
    # For converting to platform

    endpoint_lookup = {
        Endpoint.TRADE: "ok_sub_spot_{symbol}_deals",
        Endpoint.CANDLE: "ok_sub_spot_{symbol}_kline_{interval}",
    }
    # For parsing
    param_lookup_by_class = {
        # Error
        Error: {
            # "code": "code",
            # "msg": "message",
        },
        # Data
        Trade: [ParamName.ITEM_ID, ParamName.PRICE, ParamName.AMOUNT, ParamName.TIMESTAMP, ParamName.DIRECTION],
        Candle:[ParamName.TIMESTAMP, ParamName.PRICE_OPEN, ParamName.PRICE_HIGH, ParamName.PRICE_LOW, ParamName.PRICE_CLOSE, ParamName.AMOUNT]       
    }
    event_type_param = "e"
    endpoint_by_event_type = {
        "deals": Endpoint.TRADE,
        "kline": Endpoint.CANDLE,
    }
	
	#https://github.com/okcoin-okex/API-docs-OKEx.com/blob/master/API-For-Spot-EN/Error%20Code%20For%20Spot.md
    error_code_by_platform_error_code = {
         10000: ErrorCode.WRONG_PARAM,
    }
    error_code_by_http_status = {}

    # For converting time
    is_source_in_milliseconds = True

    def generate_subscriptions(self, endpoints, symbols, **params):
        #handle interval parameter
        if self.interval_endpoints.intersection(endpoints):
            if 'interval' in params:
                #save for the future and run with unchanged params
                self.subscribed_interval=self.param_value_lookup.get(params['interval'],params['interval'])
            else:
                #mutate params with previous interval
                params['interval']=self.subscribed_interval
        #self.logger.debug("gen_subscr_end: %s", params)
        return super().generate_subscriptions(endpoints,symbols, **params)

    def _parse_item(self, endpoint, item_data):
        endpoint = self.get_endpoint_type(item_data['channel'])
        super()._parse_item(endpoint, item_data['data'][0])

    # returns endpoint type without symbols and params
    def get_endpoint_type(self, endpoint):
        ep_regex=re.compile('ok_sub_spot_(?P<symbol>[a-z]{3}_[a-z]{3})_(?P<endpoint>[a-z]+)')
        ep_type= ep_regex.match(endpoint).groupdict()['endpoint']
        return self.endpoint_by_event_type[ep_type]

    #full of dirty hacks dou to different time formats in different data sources. 'Deals' request returns Time instead of Timestamp =(
    def _convert_timestamp_from_platform(self, timestamp):
        if not timestamp:
            return timestamp
        if type(timestamp)==str and timestamp[2]==':' :
            [hour,minute,sec]=map(lambda x: int(x), timestamp.split(':'))
            #assuming that it's today transaction. no more info in data
            timestamp=int(datetime.datetime.today().replace(hour=hour,minute=minute,second=sec).timestamp())
        elif self.is_source_in_milliseconds:
            timestamp = int(timestamp)/1000
            # if int(timestamp) == timestamp:
            #     timestamp = int(timestamp)
        elif self.is_source_in_timestring:
            timestamp = parser.parse(timestamp).timestamp()

        if self.use_milliseconds:
            timestamp = int(timestamp * 1000)
        return timestamp

        

class OkexWSClient(WSClient):
    platform_id = Platform.OKEX
    version = "1"  # Default version

    _converter_class_by_version = {
        "1": OkexWSConverterV1,
    }
        
    def _on_message(self, message):
        super()._on_message(inflate(message).decode('utf-8'))
        
    def _send_subscribe(self, subscriptions):
        self.logger.debug("_send_subscr: %s",subscriptions)
        for subscription in subscriptions:
            self.ws.send("{'event':'addChannel','channel':'"+subscription+"'}")

    def _send_unsubscribe(self, subscriptions):
        for subscription in subscriptions:
            self.ws.send("{'event':'delChannel','channel':'"+subscription+"'}")


def inflate(data):
    decompress = zlib.decompressobj(
            -zlib.MAX_WBITS  # see above
    )
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated
