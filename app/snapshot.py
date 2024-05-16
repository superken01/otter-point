import time
from collections import Counter
from datetime import datetime

import psycopg
import requests
from psycopg.rows import dict_row
from web3 import Web3
from web3.middleware import geth_poa_middleware

vault_abi = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "from",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "to",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "value",
                "type": "uint256",
            },
        ],
        "name": "Transfer",
        "type": "event",
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalAssets",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


oracle_abi = [
    {
        "inputs": [],
        "name": "latestAnswer",
        "outputs": [{"internalType": "int256", "name": "", "type": "int256"}],
        "stateMutability": "view",
        "type": "function",
    }
]

vault_snapshot_block_cte = """
WITH "VaultSnapshotBlock" AS (
    SELECT
        vsb.*,
        sb."blockNumber"
    FROM public."VaultSnapshotBlock" vsb
    JOIN public."SnapshotBlock" sb ON vsb."snapshotBlockId" = sb.id
)
"""


def main():
    w3 = Web3(Web3.HTTPProvider("https://rpc.scroll.io"))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    # create snapshot blocks
    print("Creating snapshot blocks...")
    with psycopg.connect(autocommit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT EXTRACT(EPOCH FROM timestamp)::int FROM "SnapshotBlock" ORDER BY "timestamp" DESC LIMIT 1'
        )
        row = cur.fetchone()
        if row:
            from_timestamp = row[0] + 86400
        else:
            from_timestamp = 1708992000

        to_timestamp = int(time.time())
        to_timestamp = to_timestamp - (to_timestamp % 86400)

        if from_timestamp <= to_timestamp:
            api_key = "V5BY34919KHPK7Q56GDV2R9NHB86519VNB"
            session = requests.Session()

            for timestamp in range(from_timestamp, to_timestamp + 86400, 86400):
                response = session.get(
                    "https://api.scrollscan.com/api",
                    params={
                        "module": "block",
                        "action": "getblocknobytime",
                        "timestamp": timestamp,
                        "closest": "after",
                        "apikey": api_key,
                    },
                )
                data = response.json()
                block_number = int(data["result"])
                block = w3.eth.get_block(block_number)
                timestamp = block.timestamp
                print(timestamp, block_number)
                with conn.transaction():
                    cur.execute(
                        'INSERT INTO "SnapshotBlock" ("blockNumber", "timestamp") VALUES (%s, %s)',
                        (block_number, datetime.fromtimestamp(timestamp)),
                    )
                time.sleep(0.2)

    # take snapshot
    print("Taking snapshot...")
    with psycopg.connect(autocommit=True) as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute('SELECT * FROM public."Vault"')
        for vault in cur.fetchall():
            print(vault["name"])

            cur.execute(
                f'{vault_snapshot_block_cte} SELECT * FROM "VaultSnapshotBlock" WHERE "vaultId" = %s ORDER BY "blockNumber" DESC LIMIT 1',
                (vault["id"],),
            )
            last_vault_snapshot_block = cur.fetchone()

            vault_contract = w3.eth.contract(address=vault["address"], abi=vault_abi)
            oracle_contract = w3.eth.contract(
                address=vault["oracleAddress"], abi=oracle_abi
            )

            counter = Counter()

            if last_vault_snapshot_block is None:
                from_block_number = vault["blockNumber"]
            else:
                from_block_number = last_vault_snapshot_block["blockNumber"] + 1
                print(last_vault_snapshot_block)
                cur.execute(
                    'SELECT * FROM public."WalletVaultSnapshot" WHERE "vaultSnapshotBlockId" = %s',
                    (last_vault_snapshot_block["id"],),
                )
                wallet_vault_snapshots = cur.fetchall()
                for wallet_vault_snapshot in wallet_vault_snapshots:
                    counter[wallet_vault_snapshot["address"]] = wallet_vault_snapshot[
                        "amount"
                    ]

            # for address, amount in counter.items():
            #     print(address, amount)

            cur.execute(
                'SELECT * FROM public."SnapshotBlock" WHERE "blockNumber" >= %s ORDER BY "blockNumber" ASC',
                (from_block_number,),
            )
            snapshot_blocks = cur.fetchall()

            for snapshot_block in snapshot_blocks:
                to_block_number = snapshot_block["blockNumber"]
                print(
                    snapshot_block["timestamp"],
                    "==============================",
                    from_block_number,
                    to_block_number,
                )
                logs = vault_contract.events.Transfer().get_logs(
                    fromBlock=from_block_number, toBlock=to_block_number
                )
                for log in logs:
                    from_address = log.args["from"]
                    to_address = log.args["to"]
                    value = log.args["value"]
                    counter[from_address] -= value
                    counter[to_address] += value

                from_block_number = to_block_number + 1

                total_assets = vault_contract.functions.totalAssets().call(
                    block_identifier=to_block_number
                )
                total_supply = vault_contract.functions.totalSupply().call(
                    block_identifier=to_block_number
                )
                rate = 0 if total_supply == 0 else total_assets / total_supply
                print("rate:", rate, total_assets, total_supply)
                price = oracle_contract.functions.latestAnswer().call(
                    block_identifier=to_block_number
                )
                print("price:", price / 100000000)

                # select Referrral and join with refereeUserId and referrerUserId

                with conn.transaction():
                    cur.execute(
                        'INSERT INTO public."VaultSnapshotBlock" ("vaultId", rate, price, "snapshotBlockId") VALUES (%s, %s, %s, %s) RETURNING id',
                        (vault["id"], rate, price, snapshot_block["id"]),
                    )
                    vault_snapshot_block_id = cur.fetchone()["id"]

                    for address, amount in counter.items():
                        if address == "0x0000000000000000000000000000000000000000":
                            continue
                        cur.execute(
                            'INSERT INTO public."WalletVaultSnapshot" ("vaultSnapshotBlockId", address, amount) VALUES (%s, %s, %s)',
                            (vault_snapshot_block_id, address, amount),
                        )


if __name__ == "__main__":
    main()
