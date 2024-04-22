from tronpy import Tron
from tronpy.providers import HTTPProvider

trongrid_api_key = "38e35982-a15d-4efd-b949-36a1d98f6e4d"
client = Tron(HTTPProvider(api_key=[trongrid_api_key]))


def batch_balance(addresses):
    balances = client.get_account(addresses)
    return balances


addresses = "TQRJM2i7vZa6VyFF9YW7eEprGMMDUsNS8n"
print(batch_balance(addresses))
