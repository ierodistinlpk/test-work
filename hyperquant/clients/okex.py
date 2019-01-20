import hashlib
import hmac
from operator import itemgetter

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
        print (params)
        result = self._send("GET", endpoint, params, version, **kwargs)
        return result

    
# WebSocket

class OkexWSConverterV1(WSConverter):
    # Main params:
    base_url = "wss://real.okex.com:10440"

    #IS_SUBSCRIPTION_COMMAND_SUPPORTED = False

    supported_endpoints = [Endpoint.TRADE, Endpoint.CANDLE]
    # symbol_endpoints = [Endpoint.TRADE, Endpoint.CANDLE]
    # supported_symbols = None

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
        "trade": Endpoint.TRADE,
        "kline": Endpoint.CANDLE,
    }
	
	#https://github.com/okcoin-okex/API-docs-OKEx.com/blob/master/API-For-Spot-EN/Error%20Code%20For%20Spot.md
    error_code_by_platform_error_code = {
         10000: ErrorCode.WRONG_PARAM,
    }
    error_code_by_http_status = {}

    # For converting time
    is_source_in_milliseconds = True
    def _get_platform_endpoint(self, endpoint, params):
        # Convert our code's endpoint to custom platform's endpoint

        # Endpoint.TRADE -> "trades/{symbol}" or "trades" or lambda params: "trades"
        platform_endpoint = self.endpoint_lookup.get(endpoint, endpoint) if self.endpoint_lookup else endpoint
        if callable(platform_endpoint):
            platform_endpoint = platform_endpoint(params)
        self.logger.debug("EP: %s, Params: %s",platform_endpoint,params)    
        if platform_endpoint:
            platform_endpoint = platform_endpoint.format(**params)

        return platform_endpoint




class OkexWSClient(WSClient):
    platform_id = Platform.OKEX
    version = "1"  # Default version

    _converter_class_by_version = {
        "1": OkexWSConverterV1,
    }

    # @property
    # def url(self):
    #     # Generate subscriptions
    #     if not self.current_subscriptions:
    #         self.logger.warning("Making URL while current_subscriptions are empty. "
    #                             "There is no sense to connect without subscriptions.")
    #         subscriptions = ""
    #         # # There is no sense to connect without subscriptions
    #         # return None
    #     elif len(self.current_subscriptions) > 1:
    #         subscriptions = "stream?streams=" + "/".join(self.current_subscriptions)
    #     else:
    #         subscriptions = "ws/" + "".join(self.current_subscriptions)

    #     self.is_subscribed_with_url = True
    #     return super().url + subscriptions


    def _send_subscribe(self, subscriptions):
        for subscription in subscriptions:
            print ('subscr:'+subscription)
            self.ws.send("{'event':'addChannel','channel':{subscription}}");

    def _send_unsubscribe(self, subscriptions):
        for subscription in subscriptions:
            print ('subscr:'+subscription)
            self.ws.send("{'event':'delChannel','channel':{subscription}}");

    def subscribe(self, endpoints=None, symbols=None, **params):
        self._check_params(endpoints, symbols, **params)

        super().subscribe(endpoints, symbols, **params)

    def unsubscribe(self, endpoints=None, symbols=None, **params):
        self._check_params(endpoints, symbols, **params)

        super().unsubscribe(endpoints, symbols, **params)

    def _check_params(self, endpoints=None, symbols=None, **params):
        LEVELS_AVAILABLE = [5, 10, 20]
        if endpoints and Endpoint.ORDER_BOOK in endpoints and ParamName.LEVEL in params and \
                params.get(ParamName.LEVEL) not in LEVELS_AVAILABLE:
            self.logger.error("For %s endpoint %s param must be of values: %s, but set: %s",
                              Endpoint.ORDER_BOOK, ParamName.LEVEL, LEVELS_AVAILABLE,
                              params.get(ParamName.LEVEL))
