import time
import json
import requests
from Crypto.Hash import keccak
from urllib.parse import urlparse
from fastapi import FastAPI
from fastapi.responses import JSONResponse

class Blockchain:
    def __init__(self , address : str):
        self.address = address
        self.chain = []
        self.nodes = set()
        self.mempool = []
        self.reward = int(50)
        self.proof = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF // 2
        self.block = None
        self.start_block_chain()
    def start_block_chain(self):
        m1 = {"message" : "this is first block of blockchain(Genesis block)"}
        m2 = {"message" : "this is second block of blockchain"}
        b1 = {
                "index" : 0,
                "0_index_block_hash" : self.hash(m1),
                "message":m1}
        b1_1 = {
                "index" : 0,
                "0_index_block_hash" : b1["0_index_block_hash"],
                "message":b1["message"],
                "block_footer":self.hash(b1)}
        self.chain.append(b1_1)
        b2 = {
                "index" : 1,
                "1_index_block_hash" : self.hash(m2),
                "message":m2,
                "previous_hash":self.previous_block(1)["block_footer"]}
        b2_2 = {
                "index" : 1,
                "1_index_block_hash" : self.hash(m2),
                "message":m2,
                "previous_hash":self.previous_block(1)["block_footer"],
                "block_footer" : self.hash(b2)}
        self.chain.append(b2_2)
    def hash(self , block : dict):
        block_copy = block.copy()
        block_copy.pop("block_footer" , None)
        hasher = keccak.new(digest_bits=256)
        hasher.update(json.dumps(block_copy , sort_keys=True).encode())
        return hasher.hexdigest()
    def create_block(self):
        current_index = len(self.chain)
        reward_trx = {
                    "sender" : "0",
                    "recipient" : self.address,
                    "amount" : self.block_reward(current_index),
                    "timestamp" : time.time()
        }
        block = {
                "index" : len(self.chain),
                "2_block_previous_hash" : self.previous_block(2)["block_footer"],
                "1_block_previous_hash" : self.previous_block(1)["block_footer"],
                "timestamp" : time.time(),
                "proof" : self.get_proof_for_index(current_index),
                "trxs" : [reward_trx] + self.mempool[:5],
                "nonce" : 0,
                "seed" : 0,
                "block_footer" : None
                }
        return block
    def previous_block(self,index):
        return self.chain[-(index)]
    def mine_block(self):       
        self.block = self.create_block()
        target_proof = self.block["proof"]
        while True:
            if int(self.hash(self.block) , 16) > target_proof:
                if self.block["nonce"] < 777000000:
                    self.block["nonce"] += 1
                else:
                    self.block["nonce"] = 0
                    self.block["seed"] += 1   
            else:
                self.block["block_footer"] = self.hash(self.block)
                self.chain.append(self.block)
                mine_user_trxs = self.block["trxs"][1:]
                self.mempool = [t for t in self.mempool if t not in mine_user_trxs]
                break
    def valid_chain(self , chain = None):
        if chain == None:
            chain = self.chain
        for index in range(1 , len(chain)):
            if not self.valid_block(index , chain):
                return False
        return True
    def valid_block(self , index , chain = None):
        if chain == None:
            chain = self.chain
        if index >= len(chain):
            return False
        current_block : dict = chain[index]
        if index == 1 :
            genesis_block : dict = chain[0]
            return current_block.get("previous_hash") == genesis_block.get("block_footer") and current_block.get("block_footer") == self.hash(current_block)
        if not self.valid_proof(current_block["proof"] , index):
            return False
        if int(self.hash(current_block) , 16) > current_block["proof"]:
            return False
        if "trxs" not in current_block or not self.valid_trxs(current_block["trxs"] , index , chain):
            return False
        if current_block["block_footer"] != self.hash(current_block):
            return False
        prev_1_block_hash = current_block.get("1_block_previous_hash")
        if prev_1_block_hash != chain[index - 1]["block_footer"]:
            return False
        prev_2_block_hash = current_block.get("2_block_previous_hash")
        if prev_2_block_hash != chain[index - 2]["block_footer"]:
            return False
        return True
    def new_trx(self , sender , recipient , amount):
        if sender == "0":
            return False
        pending_amount = sum(t["amount"] for t in self.mempool if t["sender"] == sender)
        current_balance = self.get_balance(sender)

        if amount <= 0 or sender == recipient:
            return False
        if (amount + pending_amount) > current_balance:
            return False
        trx = {
            "sender" : sender,
            "recipient" : recipient,
            "amount" : amount,
            "timestamp" : time.time()
        }
        self.mempool.append(trx)
        return True
    def valid_trx(self , trx : dict , block_index : int = None , chain = None):
        if trx["amount"] <= 0:
            return False
        if trx["sender"] == trx["recipient"]:
            return False
        if trx["sender"] == "0" :
            expected = self.block_reward(block_index if block_index is not None else len(self.chain))
            return abs(trx["amount"] - expected) < 1e-6
        if trx["amount"] > self.get_balance(trx["sender"] , chain , block_index):
            return False
        return True
    def block_reward(self , index : int):
        halvings = index // 256
        return int(50.0 * (0.8 **halvings))
    def valid_trxs(self , trxs : list , block_index : int = None , chain = None):
        if not isinstance(trxs , list) or len(trxs) == 0:
            return False
        if trxs[0].get("sender") != "0":
            return False
        temp_balance = {}
        for idx, trx in enumerate(trxs):
            sender = trx["sender"]
            amount = trx["amount"]
            if idx > 0 and sender == "0" :
                return False
            if sender != "0":
                if sender not in temp_balance:
                    temp_balance[sender] = self.get_balance(sender , chain , block_index if block_index is not None else len(self.chain))
                if amount > temp_balance[sender]:
                    return False
                temp_balance[sender] -=amount
            if not self.valid_trx(trx , block_index , chain):
                return False
        return True 
    def get_balance(self , address : str , chain = None , max_index = None):
        if chain is None:
            chain = self.chain
        if max_index is None:
            max_index = len(chain)
        balance = 0
        for index in range(2 ,max_index):
            for trx in chain[index].get("trxs" , []):
                if trx["recipient"] == address:
                    balance += trx["amount"]
                if trx["sender"] == address:
                    balance -= trx["amount"]
        return balance
    def add_node(self , address : str):
        parsed_url = urlparse(address)
        node_address = parsed_url.netloc or parsed_url.path
        if node_address:
            self.nodes.add(node_address)
            return True
        return False
    def consensus(self):
        new_chain = None
        neighbours = self.nodes
        max_length = len(self.chain)
        for node in neighbours:
            try:
                response = requests.get(f"http://{node}/get_chain" , timeout = 5)
                if response.status_code == 200:
                    data : dict = response.json()
                    length = data.get("length")
                    chain = data.get("chain") 
                    if length and chain and length > max_length and self.valid_chain(chain):
                        max_length = length
                        new_chain = chain
            except requests.exceptions.RequestException:
                continue
        if new_chain:
            self.chain = new_chain
            new_len = len(self.chain)
            self.proof = self.get_proof_for_index(new_len)
            self.reward = self.block_reward(new_len)
            chain_trxs = []
            for block in self.chain[2:]:
                chain_trxs.extend(block.get("trxs" , []))
            self.mempool = [t for t in self.mempool if t not in chain_trxs]
            return True
        return False 
    def valid_proof(self , proof , index : int = 0):
        initial_proof = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF // 2
        if not isinstance(proof , int) or proof <= 0:
            return False
        halvings = index // 256
        expected_proof = initial_proof // (2 ** halvings)
        if proof != expected_proof:
            return False
        return True
    def get_proof_for_index(self , index : int ):
        initial_proof = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF // 2
        halvings = index //256 
        return initial_proof // (2 ** halvings)


wallet_address = "some_wallet_address"
blockchain = Blockchain(wallet_address)
print(blockchain.chain)
app = FastAPI()

# we need 8 endpoint