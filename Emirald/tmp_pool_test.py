import sys
sys.path.insert(0, 'src')
from emirald.nous_client import NousClientPool, LLMUnavailable, _is_rate_limit
from openai import OpenAI

keys = [
    'sk-nous-Nn7BU7Ae9KqikUs1LBSAXucsHef16emC',
    'sk-nous-A6tPQTwIceJA6hMgj7nk3zQXSgZ50DAu',
    'sk-nous-G5fUj1TcUqaFEXtBt6XozCQQL6LWHoRE',
    'sk-nous-6Y8mRztIi7QBUlcWk7xchfhHLNTFaCyi',
]
pool = NousClientPool(
    keys=keys,
    model='stepfun/step-3.7-flash:free',
    base_url='https://inference-api.nousresearch.com/v1',
    timeout_seconds=15,
    reasoning_effort='low',
    max_output_tokens=200,
)

class DummyExc(Exception):
    def __init__(self, msg):
        super().__init__(msg)
        self.status_code = None
        self.response = None

print('RATE_LIMIT_DETECTION', _is_rate_limit(DummyExc("Error code: 429 - Hold up")))
print('RATE_LIMIT_DETECTION_MSG', _is_rate_limit(DummyExc("You are rate limited")))

try:
    pool.decide('ping', 'reply pong')
except LLMUnavailable as e:
    print('POOL_UNAVAILABLE', repr(e))
