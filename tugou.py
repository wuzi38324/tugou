from web3 import Web3
from eth_utils import to_checksum_address
from eth_account import Account
from web3.middleware import geth_poa_middleware


class Sniper():
    def __init__(self):
        self.mainnet_url = ''
        self.web3 = Web3(Web3.HTTPProvider('https://bsc-dataseed1.binance.org:443'))
        self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)

        self.factory_address = '0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73'
        self.flat = '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c'  # 该链的法币(全小写） 例如 wbnb weth
        self.USD = [
            '0x55d398326f99059ff775485246999027b3197955',
            '0xe9e7cea3dedca5984780bafc599bd69add087d56'
        ]  # USDT和BUSD地址
        self.account = Account.from_key('YOUR_PRIVATE_KEY')
        self.slippage = 0.3 / 100

    # 获取Web3实例
    def get_web3_instance(self, provider_url):
        web3 = Web3(Web3.HTTPProvider(provider_url))
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return web3

    # 获取代币价格
    def get_token_price(self, token_address):
        pair_address = self.get_pair_address(token_address, self.flat)
        if not pair_address:
            return None

        token0, token1, reserves0, reserves1 = self.get_pool_attributes(pair_address)

        if token0 == token_address:
            price = reserves1 / reserves0
        else:
            price = reserves0 / reserves1

        return price

    # 获取代币对的池子地址
    def get_pair_address(self, token1, token2):
        token1, token2 = to_checksum_address(token1), to_checksum_address(token2)
        factory = self.web3.eth.contract(address=self.factory_address, abi=self.factory_abi)
        pair_address = factory.functions.getPair(token1, token2).call()
        return pair_address

    # 获取池子信息
    def get_pool_attributes(self, pool_address):
        pool_contract = self.web3.eth.contract(address=pool_address, abi=self.pool_abi)
        token0 = pool_contract.functions.token0().call()
        token1 = pool_contract.functions.token1().call()
        reserves = pool_contract.functions.getReserves().call()
        reserves0 = reserves[0]
        reserves1 = reserves[1]
        return token0, token1, reserves0, reserves1

    # 授权代币
    def approve_token(self, token_address, spender):
        token_contract = self.web3.eth.contract(address=token_address, abi=self.erc20_abi)
        approval_tx = token_contract.functions.approve(spender, 2 ** 256 - 1).buildTransaction({
            'from': self.account.address,
            'gas': 200000,
            'gasPrice': self.web3.eth.gas_price,
            'nonce': self.web3.eth.get_transaction_count(self.account.address)
        })
        signed_tx = self.web3.eth.account.sign_transaction(approval_tx, self.account.key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        self.web3.eth.wait_for_transaction_receipt(tx_hash)

    # 限价交易
    def limit_order(self, token_address, value, price, is_buy=True):
        router_address = '0x10ED43C718714eb63d5aA57B78B54704E256024E'
        router_contract = self.web3.eth.contract(address=router_address, abi=self.router_abi)

        token_path = [to_checksum_address(self.flat), to_checksum_address(token_address)] if is_buy else [to_checksum_address(token_address), to_checksum_address(self.flat)]
        amount_in = value if is_buy else self.web3.toWei(value, 'ether')
        amount_out_min = self.web3.toWei(price * value, 'ether') if is_buy else self.web3.toWei(price * value * (1 - self.slippage), 'ether')

        deadline = self.web3.eth.get_block('latest')['timestamp'] + 10 * 60

        if not is_buy:
            self.approve_token(token_address, router_address)

        txn = router_contract.functions.swapExactETHForTokens(
            amount_out_min,
            token_path,
            self.account.address,
            deadline
        ).buildTransaction({
            'from': self.account.address,
            'value': amount_in,
            'gas': 2000000,
            'gasPrice': self.web3.eth.gas_price,
            'nonce': self.web3.eth.get_transaction_count(self.account.address)
        })

        signed_txn = self.web3.eth.account.sign_transaction(txn, self.account.key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        self.web3.eth.wait_for_transaction_receipt(tx_hash)

    # 限价买入
    def buy_market(self, token_address, value, price):
        self.limit_order(token_address, value, price, is_buy=True)

    # 限价卖出
    def sell_market(self, token_address, value, price):
        self.limit_order(token_address, value, price, is_buy=False)


if __name__ == '__main__':
    token = '0x7102f5bb8cb9c6e7d085626e7a1347aafdf001f6'
    sniper = Sniper()
    price = sniper.get_token_price(token)
    if price is not None:
        sniper.buy_market(token, 0.01, price)